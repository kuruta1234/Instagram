"""投稿ドラフトの永続化(作成・保存・読込・一覧)。

各投稿は data/posts/<post_id>/ 配下に以下の構成で保存される。

    meta.yaml               投稿メタデータ(Post を YAML にしたもの)
    images/original/        アップロードした元画像
    images/edited/           編集後の画像
"""

from __future__ import annotations

import shutil
from pathlib import Path

import yaml

from . import config
from .models import ImageAsset, Post, PostStatus
from .utils import generate_post_id


class PostNotFoundError(Exception):
    pass


def post_dir(post_id: str) -> Path:
    return config.POSTS_DIR / post_id


def _meta_path(post_id: str) -> Path:
    return post_dir(post_id) / "meta.yaml"


def original_dir(post_id: str) -> Path:
    return post_dir(post_id) / "images" / "original"


def edited_dir(post_id: str) -> Path:
    return post_dir(post_id) / "images" / "edited"


def save(post: Post) -> None:
    post.touch()
    pdir = post_dir(post.id)
    pdir.mkdir(parents=True, exist_ok=True)
    with open(_meta_path(post.id), "w", encoding="utf-8") as f:
        yaml.safe_dump(post.to_dict(), f, allow_unicode=True, sort_keys=False)


def load(post_id: str) -> Post:
    meta_path = _meta_path(post_id)
    if not meta_path.exists():
        raise PostNotFoundError(f"投稿が見つかりません: {post_id}")
    with open(meta_path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return Post.from_dict(data)


def exists(post_id: str) -> bool:
    return _meta_path(post_id).exists()


def list_ids() -> list[str]:
    config.ensure_dirs()
    if not config.POSTS_DIR.exists():
        return []
    return sorted(
        p.name for p in config.POSTS_DIR.iterdir() if p.is_dir() and (p / "meta.yaml").exists()
    )


def list_posts(status: PostStatus | None = None) -> list[Post]:
    posts = [load(pid) for pid in list_ids()]
    if status is not None:
        posts = [p for p in posts if p.status == status]
    posts.sort(key=lambda p: p.created_at, reverse=True)
    return posts


def create(topic: str, image_paths: list[Path]) -> Post:
    config.ensure_dirs()
    post_id = generate_post_id(topic)
    while exists(post_id):  # 衝突した場合は作り直す(ほぼ発生しない)
        post_id = generate_post_id(topic)

    post = Post(id=post_id, topic=topic)

    orig_dir = original_dir(post_id)
    orig_dir.mkdir(parents=True, exist_ok=True)
    for src in image_paths:
        src = Path(src)
        if not src.exists():
            raise FileNotFoundError(f"画像が見つかりません: {src}")
        dest = orig_dir / src.name
        shutil.copy2(src, dest)
        rel = dest.relative_to(post_dir(post_id))
        post.images.append(ImageAsset(original=str(rel)))

    save(post)
    return post


def resolve_image_path(post_id: str, relative_path: str) -> Path:
    return post_dir(post_id) / relative_path


def delete(post_id: str) -> None:
    pdir = post_dir(post_id)
    if not pdir.exists():
        raise PostNotFoundError(f"投稿が見つかりません: {post_id}")
    shutil.rmtree(pdir)
