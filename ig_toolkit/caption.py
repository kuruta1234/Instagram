"""Anthropic APIを使ったInstagram投稿キャプション・ハッシュタグの自動生成。"""

from __future__ import annotations

import base64
import mimetypes
import re
from pathlib import Path

from . import config

TONE_GUIDE: dict[str, str] = {
    "casual": "親しみやすく、絵文字を適度に使ったカジュアルな口調",
    "formal": "丁寧でビジネスライクな敬語",
    "energetic": "元気で勢いのあるテンションの高い口調",
    "elegant": "上品で落ち着いた洗練された口調",
}

RESULT_MARKER_CAPTION = "【キャプション】"
RESULT_MARKER_HASHTAGS = "【ハッシュタグ】"


class CaptionGenerationError(Exception):
    pass


def _build_prompt(
    topic: str,
    keywords: list[str],
    tone: str,
    notes: str,
    hashtag_count: int,
) -> str:
    tone_desc = TONE_GUIDE.get(tone, TONE_GUIDE["casual"])
    keyword_line = "、".join(keywords) if keywords else "(指定なし)"
    notes_line = notes.strip() if notes.strip() else "(特になし)"

    return f"""あなたはInstagram運用を支援するプロのSNSマーケターです。
以下の情報をもとに、Instagramフィード投稿用のキャプションとハッシュタグを作成してください。

# 投稿テーマ
{topic}

# 含めたいキーワード
{keyword_line}

# トーン
{tone_desc}

# 補足・注意事項
{notes_line}

# 出力ルール
- 添付画像がある場合は画像の内容を踏まえて具体的に書く
- キャプションは2〜5文程度、読みやすい改行を入れる
- 誇大表現・医療/効能を断定する表現・差別的表現は避ける
- ハッシュタグは{hashtag_count}個、日本語・英語を適度に混ぜてよい
- 出力は必ず以下のフォーマットに従うこと(見出し文言も含めて厳守)

{RESULT_MARKER_CAPTION}
(ここにキャプション本文)

{RESULT_MARKER_HASHTAGS}
#tag1 #tag2 #tag3 ...
"""


def _parse_response(text: str) -> dict[str, str | list[str]]:
    caption = ""
    hashtags: list[str] = []

    if RESULT_MARKER_CAPTION in text and RESULT_MARKER_HASHTAGS in text:
        caption_part = text.split(RESULT_MARKER_CAPTION, 1)[1]
        caption_part, hashtag_part = caption_part.split(RESULT_MARKER_HASHTAGS, 1)
        caption = caption_part.strip()
        hashtags = re.findall(r"#[^\s#]+", hashtag_part)
    else:
        # フォーマットに従わなかった場合のフォールバック: 本文全体をキャプションとする
        caption = text.strip()
        hashtags = re.findall(r"#[^\s#]+", text)

    return {"caption": caption, "hashtags": hashtags}


def generate_caption(
    topic: str,
    keywords: list[str] | None = None,
    tone: str = "casual",
    notes: str = "",
    hashtag_count: int = 12,
    image_path: Path | None = None,
    api_key: str | None = None,
    model: str | None = None,
) -> dict[str, str | list[str]]:
    """トピック・キーワード・(任意で)画像からキャプションとハッシュタグを生成する。"""
    try:
        import anthropic
    except ImportError as exc:
        raise CaptionGenerationError(
            "anthropicパッケージが未インストールです: pip install anthropic"
        ) from exc

    api_key = api_key or config.ANTHROPIC_API_KEY
    if not api_key:
        raise CaptionGenerationError(
            "ANTHROPIC_API_KEYが設定されていません。.envに設定してください。"
        )

    prompt = _build_prompt(topic, keywords or [], tone, notes, hashtag_count)
    content: list[dict] = []

    if image_path is not None:
        image_path = Path(image_path)
        if not image_path.exists():
            raise CaptionGenerationError(f"画像が見つかりません: {image_path}")
        media_type = mimetypes.guess_type(str(image_path))[0] or "image/jpeg"
        b64_data = base64.standard_b64encode(image_path.read_bytes()).decode("ascii")
        content.append(
            {
                "type": "image",
                "source": {"type": "base64", "media_type": media_type, "data": b64_data},
            }
        )

    content.append({"type": "text", "text": prompt})

    client = anthropic.Anthropic(api_key=api_key)
    try:
        response = client.messages.create(
            model=model or config.CLAUDE_MODEL,
            max_tokens=1024,
            messages=[{"role": "user", "content": content}],
        )
    except Exception as exc:  # anthropic側の例外を共通エラーに変換
        raise CaptionGenerationError(f"キャプション生成に失敗しました: {exc}") from exc

    text_blocks = [block.text for block in response.content if getattr(block, "type", "") == "text"]
    full_text = "\n".join(text_blocks)
    return _parse_response(full_text)
