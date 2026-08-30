"""共通ユーティリティ関数。"""

import re
import secrets
import unicodedata
from datetime import date


def slugify(text: str, max_len: int = 24) -> str:
    """日本語を含む文字列からファイル名/ID用の英数スラッグを作る。

    日本語はローマ字変換までは行わず、ASCII英数字のみを残す簡易実装。
    英数字が残らない場合は "post" にフォールバックする。
    """
    normalized = unicodedata.normalize("NFKC", text)
    ascii_only = re.sub(r"[^a-zA-Z0-9]+", "-", normalized).strip("-").lower()
    ascii_only = re.sub(r"-{2,}", "-", ascii_only)
    if not ascii_only:
        return "post"
    return ascii_only[:max_len].strip("-") or "post"


def generate_post_id(topic: str, today: date | None = None) -> str:
    """`YYYYMMDD-topic-slug-xxxx` 形式の一意な投稿IDを生成する。"""
    today = today or date.today()
    date_part = today.strftime("%Y%m%d")
    slug = slugify(topic)
    suffix = secrets.token_hex(2)
    return f"{date_part}-{slug}-{suffix}"
