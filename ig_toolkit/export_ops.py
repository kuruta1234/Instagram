"""承認済み投稿を手動投稿用にエクスポートする処理(CLIとWeb GUIで共通)。"""

from __future__ import annotations

import io
import zipfile
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


def build_export_zip(post: Post) -> tuple[io.BytesIO, str]:
    """エクスポート済みディレクトリの内容をZIPにまとめ、ブラウザダウンロード用に返す。"""
    export_dir = export_post(post)

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(export_dir.iterdir()):
            if path.is_file():
                zf.write(path, arcname=path.name)
    buffer.seek(0)

    return buffer, f"{post.id}.zip"
