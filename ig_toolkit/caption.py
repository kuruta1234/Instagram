"""キャプション・ハッシュタグの手入力(APIキー不要)をサポートするヘルパー関数群。

対話的な入力受付そのものはcli.py側で行い、ここでは入力補助のための
表示整形・パース処理のみを扱う。
"""

from __future__ import annotations

import re
from pathlib import Path

from PIL import Image, UnidentifiedImageError


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


def format_context_for_input(
    topic: str,
    keywords: list[str],
    tone: str,
    image_paths: list[Path],
) -> str:
    """キャプション入力時に参考として表示する投稿情報を整形する。"""
    lines = [f"トピック: {topic}"]
    if keywords:
        lines.append(f"キーワード: {', '.join(keywords)}")
    lines.append(f"トーン: {tone}")
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
