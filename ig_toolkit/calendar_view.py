"""投稿予定日ベースのカレンダー表示。"""

from __future__ import annotations

import calendar as _calendar
from collections import defaultdict
from datetime import date

from .models import Post


def posts_by_day(posts: list[Post], year: int, month: int) -> dict[int, list[Post]]:
    """指定した年月について、日付(1〜31) -> その日にscheduled_dateを持つ投稿一覧。"""
    grouped: dict[int, list[Post]] = defaultdict(list)
    prefix = f"{year:04d}-{month:02d}-"
    for post in posts:
        if post.scheduled_date and post.scheduled_date.startswith(prefix):
            try:
                day = int(post.scheduled_date[8:10])
            except ValueError:
                continue
            grouped[day].append(post)
    return grouped


def render_text_calendar(posts: list[Post], year: int, month: int) -> str:
    """月間カレンダーをテキストで描画する(投稿がある日にはトピックを添える)。"""
    grouped = posts_by_day(posts, year, month)
    cal = _calendar.Calendar(firstweekday=6)  # 日曜始まり

    lines = [f"{year}年{month}月 投稿カレンダー", ""]
    weekday_labels = ["日", "月", "火", "水", "木", "金", "土"]
    lines.append("  ".join(weekday_labels))

    for week in cal.monthdayscalendar(year, month):
        cells = []
        for day in week:
            if day == 0:
                cells.append("  ")
            else:
                marker = "*" if day in grouped else " "
                cells.append(f"{day:2d}{marker}")
        lines.append(" ".join(cells))

    if grouped:
        lines.append("")
        lines.append("予定:")
        for day in sorted(grouped):
            for post in grouped[day]:
                lines.append(
                    f"  {year:04d}-{month:02d}-{day:02d}  [{post.status.value}] "
                    f"{post.topic} ({post.id})"
                )
    else:
        lines.append("")
        lines.append("この月に予定はありません。")

    return "\n".join(lines)


def today_year_month() -> tuple[int, int]:
    today = date.today()
    return today.year, today.month
