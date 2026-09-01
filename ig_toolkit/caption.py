"""キャプション・ハッシュタグの作成支援。

- 手入力向けの表示整形・パース処理
- Claude Code CLI(`claude`)をサブプロセスとして呼び出し、画像を読ませて
  キャプション/ハッシュタグの下書きを自動生成する処理

Anthropic APIキーは使わない。ユーザーが `claude` コマンドで既にログイン済み
(Claude Pro/Max等のサブスクリプション、またはAPIキー)であれば、その認証情報を
そのまま利用する。
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from . import config

RESULT_MARKER_CAPTION = "【キャプション】"
RESULT_MARKER_HASHTAGS = "【ハッシュタグ】"


class CaptionGenerationError(Exception):
    pass


def describe_image(path: Path) -> str:
    """入力時に表示する画像の簡単な説明(ファイル名・サイズ)を返す。"""
    if not path.exists():
        return f"{path.name}  (ファイルが見つかりません)"
    try:
        with Image.open(path) as img:
            width, height = img.size
    except (UnidentifiedImageError, OSError):
        return path.name
    size_kb = path.stat().st_size / 1024
    return f"{path.name}  ({width}x{height}px, {size_kb:.0f}KB)"


def format_context_for_input(topic: str, image_paths: list[Path]) -> str:
    """キャプション入力時に参考として表示する投稿情報を整形する。"""
    lines = [f"トピック: {topic}"]
    if image_paths:
        lines.append("画像:")
        for path in image_paths:
            lines.append(f"  - {describe_image(path)}")
    else:
        lines.append("画像: (なし)")
    return "\n".join(lines)


def parse_hashtags(raw: str) -> list[str]:
    """カンマ・空白・改行区切りのハッシュタグ入力をリストに正規化する。

    各要素の先頭に "#" がなければ付与する。空要素は無視する。
    """
    if not raw or not raw.strip():
        return []
    parts = re.split(r"[,\s]+", raw.strip())
    tags = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        if not part.startswith("#"):
            part = f"#{part}"
        tags.append(part)
    return tags


def _build_ai_prompt(topic: str, image_path: Path, hashtag_count: int, notes: str) -> str:
    topic_line = topic.strip() if topic.strip() else "(指定なし。画像の内容から適切なテーマを判断してください)"
    notes_line = notes.strip() if notes.strip() else "(特になし)"

    return f"""あなたはInstagram運用を支援する、プロのSNSマーケター・コピーライターです。
画像 {image_path} を読み込み、その内容を踏まえて投稿用のキャプションとハッシュタグを
プロの品質で作成してください。

# 投稿テーマ
{topic_line}

# 補足・注意事項
{notes_line}

# 出力ルール
- 画像に写っているものを具体的に描写し、読み手が情景を想像できる文章にする
- キャプションは2〜5文程度、読みやすい改行を入れる
- 誇大表現・医療/効能を断定する表現・差別的表現は避ける
- ハッシュタグは{hashtag_count}個、日本語・英語を適度に混ぜてよい
- 他の作業(ファイル編集など)は一切行わないこと
- 前置き・確認・後書きの言葉は書かず、以下のフォーマットのみを出力すること(見出し文言も含めて厳守)

{RESULT_MARKER_CAPTION}
(ここにキャプション本文)

{RESULT_MARKER_HASHTAGS}
#tag1 #tag2 #tag3 ...
"""


def _parse_ai_response(text: str) -> dict[str, str | list[str]]:
    if RESULT_MARKER_CAPTION in text and RESULT_MARKER_HASHTAGS in text:
        caption_part, hashtag_part = text.split(RESULT_MARKER_CAPTION, 1)[1].split(
            RESULT_MARKER_HASHTAGS, 1
        )
        caption = caption_part.strip()
        hashtags = re.findall(r"#[^\s#]+", hashtag_part)
    else:
        # フォーマットに従わなかった場合のフォールバック: 本文全体をキャプションとする
        caption = text.strip()
        hashtags = re.findall(r"#[^\s#]+", text)
    return {"caption": caption, "hashtags": hashtags}


def generate_caption_via_cli(
    topic: str,
    image_path: Path,
    hashtag_count: int = 10,
    notes: str = "",
    command: str | None = None,
    timeout: float | None = None,
) -> dict[str, str | list[str]]:
    """Claude Code CLI(`claude -p`)を使い、画像を見た上でのキャプション/ハッシュタグ案を生成する。

    Anthropic APIキーは不要。`claude` コマンドが既にログイン済み
    (Claude Pro/Max等のサブスクリプション、またはAPIキー)であればそのまま動作する。
    """
    command = command or config.CLAUDE_CLI_COMMAND
    timeout = config.CLAUDE_CLI_TIMEOUT if timeout is None else timeout

    if shutil.which(command) is None:
        raise CaptionGenerationError(
            f"Claude Code CLI ('{command}') が見つかりません。"
            " https://claude.com/claude-code からインストールし、"
            "`claude` コマンドでログイン済みであることを確認してください。"
        )

    image_path = Path(image_path)
    if not image_path.exists():
        raise CaptionGenerationError(f"画像が見つかりません: {image_path}")

    prompt = _build_ai_prompt(topic, image_path.resolve(), hashtag_count, notes)

    try:
        proc = subprocess.run(
            [command, "-p", "--allowedTools", "Read", "--output-format", "json", prompt],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError as exc:
        raise CaptionGenerationError(
            f"Claude Code CLI ('{command}') の実行に失敗しました。インストール状況を確認してください。"
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise CaptionGenerationError(
            f"Claude Code CLIの応答がタイムアウトしました({timeout:.0f}秒)。"
        ) from exc

    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip()[:500]
        raise CaptionGenerationError(
            f"Claude Code CLIの実行に失敗しました(終了コード {proc.returncode}): {detail}"
        )

    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise CaptionGenerationError(
            f"Claude Code CLIの出力を解析できませんでした: {proc.stdout.strip()[:500]}"
        ) from exc

    if payload.get("is_error"):
        raise CaptionGenerationError(
            f"Claude Code CLIがエラーを返しました: {str(payload.get('result', ''))[:500]}"
        )

    result_text = payload.get("result") or ""
    if not result_text.strip():
        raise CaptionGenerationError("Claude Code CLIから空の応答が返されました。")

    return _parse_ai_response(result_text)
