from ig_toolkit.calendar_view import posts_by_day, render_text_calendar
from ig_toolkit.models import Post, PostStatus


def _post(post_id, scheduled_date):
    return Post(id=post_id, topic="テスト", status=PostStatus.SCHEDULED, scheduled_date=scheduled_date)


def test_posts_by_day_groups_correctly():
    posts = [
        _post("p1", "2026-09-05"),
        _post("p2", "2026-09-05"),
        _post("p3", "2026-10-01"),
    ]
    grouped = posts_by_day(posts, 2026, 9)
    assert set(grouped.keys()) == {5}
    assert len(grouped[5]) == 2


def test_render_text_calendar_includes_topic():
    posts = [_post("p1", "2026-09-05")]
    text = render_text_calendar(posts, 2026, 9)
    assert "2026年9月" in text
    assert "p1" in text
