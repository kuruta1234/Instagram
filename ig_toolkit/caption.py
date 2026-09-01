"""キャプション・ハッシュタグの作成支援。

- 手入力向けの表示整形・パース処理
- キャプション/ハッシュタグの下書きをAIで自動生成する処理。2つの方式を用意している。

  1. Claude Code CLI(`claude -p`)をサブプロセスとして呼び出す方式(既定・優先)。
     Anthropic APIキーは不要で、`claude` コマンドが既にログイン済み
     (Claude Pro/Max/Team等のサブスクリプション、または `claude` に設定したAPIキー)
     であればそのまま動作する。
  2. Anthropic APIを直接呼ぶ方式(フォールバック)。`claude` コマンドが未インストール・
     未ログインで使えない場合に、ANTHROPIC_API_KEYが設定されていれば自動的にこちらを使う。
     claude.aiのプラン(Free/Pro/Max等)に関係なく、APIキーさえあれば誰でも利用できる。

generate_caption() が上記2方式を自動的に使い分けるエントリーポイント。
"""

from __future__ import annotations

import base64
import json
import mimetypes
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


def _build_prompt_rules(topic: str, hashtag_count: int, notes: str) -> str:
    """CLI経由・API経由の両方で共通する指示文(画像の入手方法だけが異なる)。"""
    topic_line = topic.strip() if topic.strip() else "(指定なし。画像の内容から適切なテーマを判断してください)"
    notes_line = notes.strip() if notes.strip() else "(特になし)"

    return f"""その内容を踏まえて、Instagram投稿用のキャプションとハッシュタグを
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


def _build_cli_prompt(topic: str, image_path: Path, hashtag_count: int, notes: str) -> str:
    return (
        f"あなたはInstagram運用を支援する、プロのSNSマーケター・コピーライターです。\n"
        f"画像 {image_path} を読み込んでください。\n\n"
        + _build_prompt_rules(topic, hashtag_count, notes)
    )


def _build_api_prompt(topic: str, hashtag_count: int, notes: str) -> str:
    return (
        "あなたはInstagram運用を支援する、プロのSNSマーケター・コピーライターです。\n"
        "添付されている画像を確認してください。\n\n"
        + _build_prompt_rules(topic, hashtag_count, notes)
    )


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

    prompt = _build_cli_prompt(topic, image_path.resolve(), hashtag_count, notes)

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


def generate_caption_via_api(
    topic: str,
    image_path: Path,
    hashtag_count: int = 10,
    notes: str = "",
    api_key: str | None = None,
    model: str | None = None,
) -> dict[str, str | list[str]]:
    """Anthropic APIを直接呼び出してキャプション/ハッシュタグ案を生成する(フォールバック用)。

    `claude` コマンドの有無・ログイン状態に関係なく、ANTHROPIC_API_KEYさえあれば動作する。
    """
    try:
        import anthropic
    except ImportError as exc:
        raise CaptionGenerationError(
            "Anthropic API連携には追加パッケージが必要です: pip install anthropic"
        ) from exc

    api_key = api_key or config.ANTHROPIC_API_KEY
    if not api_key:
        raise CaptionGenerationError(
            "ANTHROPIC_API_KEYが設定されていません。.envに設定するか、"
            "Claude Code CLI(`claude login`)を使う方法もあります。"
        )

    image_path = Path(image_path)
    if not image_path.exists():
        raise CaptionGenerationError(f"画像が見つかりません: {image_path}")

    media_type = mimetypes.guess_type(str(image_path))[0] or "image/jpeg"
    image_data = base64.standard_b64encode(image_path.read_bytes()).decode("ascii")
    prompt = _build_api_prompt(topic, hashtag_count, notes)

    client = anthropic.Anthropic(api_key=api_key)
    try:
        response = client.messages.create(
            model=model or config.ANTHROPIC_MODEL,
            max_tokens=1024,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": image_data,
                            },
                        },
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
        )
    except anthropic.AuthenticationError as exc:
        raise CaptionGenerationError("ANTHROPIC_API_KEYが無効です。") from exc
    except anthropic.APIConnectionError as exc:
        raise CaptionGenerationError(
            "Anthropic APIに接続できませんでした。ネットワーク環境を確認してください。"
        ) from exc
    except anthropic.APIStatusError as exc:
        raise CaptionGenerationError(f"Anthropic APIでエラーが発生しました: {exc}") from exc

    result_text = "\n".join(
        block.text for block in response.content if getattr(block, "type", "") == "text"
    )
    if not result_text.strip():
        raise CaptionGenerationError("Anthropic APIから空の応答が返されました。")

    return _parse_ai_response(result_text)


def generate_caption(
    topic: str,
    image_path: Path,
    hashtag_count: int = 10,
    notes: str = "",
) -> dict[str, str | list[str]]:
    """Claude Code CLIを優先して使い、使えない場合はAnthropic APIキーにフォールバックする。

    どちらの方式で生成しても、返るキャプション/ハッシュタグの形式は同じ。
    claude.aiのプラン(Free/Pro/Max等)に依らず、`claude` コマンドがログイン済みか、
    ANTHROPIC_API_KEYが設定されていればいずれかの方式で生成できる。
    """
    try:
        return generate_caption_via_cli(
            topic, image_path, hashtag_count=hashtag_count, notes=notes
        )
    except CaptionGenerationError as cli_error:
        if not config.ANTHROPIC_API_KEY:
            raise CaptionGenerationError(
                f"{cli_error} また、ANTHROPIC_API_KEYも未設定のため、Anthropic API経由の"
                "生成もできません。`claude login`でログインするか、.envにANTHROPIC_API_KEYを"
                "設定してください(pip install anthropicが必要です)。"
            ) from cli_error

        try:
            return generate_caption_via_api(
                topic, image_path, hashtag_count=hashtag_count, notes=notes
            )
        except CaptionGenerationError as api_error:
            raise CaptionGenerationError(
                f"Claude Code CLIでの生成に失敗し({cli_error})、"
                f"Anthropic API経由の生成にも失敗しました({api_error})。"
            ) from api_error
