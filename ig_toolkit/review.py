"""投稿前チェック(承認フロー)のロジック。

対話的なUIはcli.py側に置き、ここでは判定ロジックのみを扱う。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from . import image_edit, ng_words, storage
from .models import Post, PostStatus


@dataclass
class AutoCheckResult:
    ng_word_hits: list[str] = field(default_factory=list)
    image_warnings: dict[str, list[str]] = field(default_factory=dict)  # 画像パス -> 警告一覧
    caption_empty: bool = True
    hashtags_empty: bool = True

    @property
    def has_blocking_issue(self) -> bool:
        return bool(self.ng_word_hits) or self.caption_empty


def run_auto_checks(post: Post) -> AutoCheckResult:
    result = AutoCheckResult()

    full_text = post.caption + " " + " ".join(post.hashtags)
    result.ng_word_hits = ng_words.check_text(full_text)
    result.caption_empty = not post.caption.strip()
    result.hashtags_empty = not post.hashtags

    for img in post.images:
        rel_path = img.edited or img.original
        abs_path = storage.resolve_image_path(post.id, rel_path)
        if not abs_path.exists():
            result.image_warnings[rel_path] = ["ファイルが見つかりません"]
            continue
        pil_img = image_edit.load_image(abs_path)
        warnings = image_edit.validate_instagram_size(pil_img)
        if warnings:
            result.image_warnings[rel_path] = warnings

    return result


def set_caption(post: Post, caption_text: str, hashtags: list[str]) -> Post:
    """キャプション・ハッシュタグを設定する(CLI/Web共通)。内容が変わるためチェック済みフラグはリセットする。"""
    post.caption = caption_text
    post.hashtags = hashtags
    post.checklist.caption_ok = False
    post.checklist.hashtag_ok = False
    post.checklist.ng_word_ok = False
    if post.status == PostStatus.DRAFT:
        post.status = PostStatus.IN_REVIEW
    return post


def approve(post: Post) -> Post:
    if not post.checklist.all_passed():
        raise ValueError("チェックリストが全て完了していません。approveできません。")
    post.status = PostStatus.APPROVED
    post.approved_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return post


def schedule(post: Post, scheduled_date: str) -> Post:
    if post.status not in (PostStatus.APPROVED, PostStatus.SCHEDULED):
        raise ValueError(
            f"承認済み(approved)の投稿のみスケジュール設定できます(現在: {post.status.value})"
        )
    post.scheduled_date = scheduled_date
    post.status = PostStatus.SCHEDULED
    return post


def mark_posted(post: Post) -> Post:
    post.status = PostStatus.POSTED
    return post
