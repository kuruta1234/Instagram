"""承認済み投稿を手動投稿用にエクスポートする処理(CLIとWeb GUIで共通)。"""

from __future__ import annotations

from pathlib import Path

from . import config, storage
from .models import Post


def export_post(post: Post) -> Path:
    """画像とキャプションテキストを data/exports/<post_id>/ にまとめて書き出す。"""
    export_dir = config.EXPORTS_DIR / post.id
    export_dir.mkdir(parents=True, exist_ok=True)

    for i, asset in enumerate(post.images, start=1):
        rel = asset.edited or asset.original
        src = storage.resolve_image_path(post.id, rel)
        dest = export_dir / f"{i:02d}{src.suffix}"
        dest.write_bytes(src.read_bytes())

    caption_text = post.caption.strip()
    if post.hashtags:
        caption_text += "\n\n" + " ".join(post.hashtags)
    (export_dir / "caption.txt").write_text(caption_text, encoding="utf-8")

    return export_dir
