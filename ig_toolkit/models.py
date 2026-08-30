"""投稿ドラフトのデータモデル。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class PostStatus(str, Enum):
    DRAFT = "draft"  # 作成直後、キャプション/画像とも未確定
    IN_REVIEW = "in_review"  # チェック中
    APPROVED = "approved"  # 承認済み、投稿可能
    SCHEDULED = "scheduled"  # 投稿予定日が設定済み
    POSTED = "posted"  # 手動で投稿済みとマーク済み

    @classmethod
    def order(cls) -> list["PostStatus"]:
        return [cls.DRAFT, cls.IN_REVIEW, cls.APPROVED, cls.SCHEDULED, cls.POSTED]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class ImageAsset:
    original: str  # postディレクトリからの相対パス
    edited: str | None = None
    edits: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"original": self.original, "edited": self.edited, "edits": list(self.edits)}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ImageAsset":
        return cls(
            original=data["original"],
            edited=data.get("edited"),
            edits=list(data.get("edits", [])),
        )


@dataclass
class ReviewChecklist:
    image_ok: bool = False  # 画像サイズ・内容に問題なし
    caption_ok: bool = False  # キャプション内容を確認済み
    hashtag_ok: bool = False  # ハッシュタグを確認済み
    rights_ok: bool = False  # 画像の権利関係(自社/使用許諾あり)を確認済み
    ng_word_ok: bool = False  # NGワードチェック済み

    def all_passed(self) -> bool:
        return all(
            [self.image_ok, self.caption_ok, self.hashtag_ok, self.rights_ok, self.ng_word_ok]
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "image_ok": self.image_ok,
            "caption_ok": self.caption_ok,
            "hashtag_ok": self.hashtag_ok,
            "rights_ok": self.rights_ok,
            "ng_word_ok": self.ng_word_ok,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ReviewChecklist":
        return cls(
            image_ok=bool(data.get("image_ok", False)),
            caption_ok=bool(data.get("caption_ok", False)),
            hashtag_ok=bool(data.get("hashtag_ok", False)),
            rights_ok=bool(data.get("rights_ok", False)),
            ng_word_ok=bool(data.get("ng_word_ok", False)),
        )


@dataclass
class Post:
    id: str
    topic: str
    created_at: str = field(default_factory=_now_iso)
    updated_at: str = field(default_factory=_now_iso)
    keywords: list[str] = field(default_factory=list)
    tone: str = "casual"
    caption: str = ""
    hashtags: list[str] = field(default_factory=list)
    images: list[ImageAsset] = field(default_factory=list)
    status: PostStatus = PostStatus.DRAFT
    scheduled_date: str | None = None
    checklist: ReviewChecklist = field(default_factory=ReviewChecklist)
    approved_at: str | None = None
    notes: str = ""

    def touch(self) -> None:
        self.updated_at = _now_iso()

    def primary_image(self) -> ImageAsset | None:
        return self.images[0] if self.images else None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "topic": self.topic,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "keywords": list(self.keywords),
            "tone": self.tone,
            "caption": self.caption,
            "hashtags": list(self.hashtags),
            "images": [img.to_dict() for img in self.images],
            "status": self.status.value,
            "scheduled_date": self.scheduled_date,
            "checklist": self.checklist.to_dict(),
            "approved_at": self.approved_at,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Post":
        return cls(
            id=data["id"],
            topic=data.get("topic", ""),
            created_at=data.get("created_at", _now_iso()),
            updated_at=data.get("updated_at", _now_iso()),
            keywords=list(data.get("keywords", [])),
            tone=data.get("tone", "casual"),
            caption=data.get("caption", ""),
            hashtags=list(data.get("hashtags", [])),
            images=[ImageAsset.from_dict(i) for i in data.get("images", [])],
            status=PostStatus(data.get("status", PostStatus.DRAFT.value)),
            scheduled_date=data.get("scheduled_date"),
            checklist=ReviewChecklist.from_dict(data.get("checklist", {})),
            approved_at=data.get("approved_at"),
            notes=data.get("notes", ""),
        )
