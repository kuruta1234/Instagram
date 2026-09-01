"""投稿ドラフトのデータモデル。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class PostStatus(str, Enum):
    DRAFT = "draft"  # 作成後、まだ投稿していない
    POSTED = "posted"  # 手動で投稿済みとマーク済み


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
class Post:
    id: str
    topic: str
    created_at: str = field(default_factory=_now_iso)
    updated_at: str = field(default_factory=_now_iso)
    caption: str = ""
    hashtags: list[str] = field(default_factory=list)
    images: list[ImageAsset] = field(default_factory=list)
    status: PostStatus = PostStatus.DRAFT

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
            "caption": self.caption,
            "hashtags": list(self.hashtags),
            "images": [img.to_dict() for img in self.images],
            "status": self.status.value,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Post":
        return cls(
            id=data["id"],
            topic=data.get("topic", ""),
            created_at=data.get("created_at", _now_iso()),
            updated_at=data.get("updated_at", _now_iso()),
            caption=data.get("caption", ""),
            hashtags=list(data.get("hashtags", [])),
            images=[ImageAsset.from_dict(i) for i in data.get("images", [])],
            status=PostStatus(data.get("status", PostStatus.DRAFT.value)),
        )
