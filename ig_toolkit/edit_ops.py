"""画像編集の適用ロジック(CLIとWeb GUIで共通)。

「現在の画像を読み込む」「編集結果を保存してPostのメタデータを更新する」という
一連の手続きをここに集約し、CLIコマンドとWebアプリのルートで重複させない。
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from . import image_edit, storage
from .models import ImageAsset, Post


def load_current_image(post: Post, image_index: int) -> tuple[ImageAsset, Image.Image]:
    """指定インデックスの画像の「現在の状態」(編集済みがあればそれ、なければ元画像)を読み込む。"""
    asset = post.images[image_index]
    rel = asset.edited or asset.original
    path = storage.resolve_image_path(post.id, rel)
    return asset, image_edit.load_image(path)


def save_edited(post: Post, asset: ImageAsset, img: Image.Image, edit_names: list[str]) -> None:
    """編集結果を images/edited/ に保存し、Postのメタデータを更新する(保存はしない)。"""
    dest_name = Path(asset.original).stem + "_edited" + Path(asset.original).suffix
    dest_path = storage.edited_dir(post.id) / dest_name
    image_edit.save_image(img, dest_path)

    asset.edited = str(dest_path.relative_to(storage.post_dir(post.id)))
    asset.edits.extend(edit_names)
    post.checklist.image_ok = False


def reset_image(post: Post, asset: ImageAsset) -> None:
    """編集を取り消し、元画像の状態に戻す。"""
    if asset.edited:
        path = storage.resolve_image_path(post.id, asset.edited)
        if path.exists():
            path.unlink()
    asset.edited = None
    asset.edits = []
    post.checklist.image_ok = False
