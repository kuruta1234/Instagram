from ig_toolkit.models import ImageAsset, Post, PostStatus


def test_post_roundtrip_dict():
    post = Post(
        id="20260101-test-abcd",
        topic="テスト投稿",
        caption="キャプション本文",
        hashtags=["#a", "#b"],
        images=[ImageAsset(original="images/original/x.jpg")],
    )
    data = post.to_dict()
    restored = Post.from_dict(data)

    assert restored.id == post.id
    assert restored.topic == post.topic
    assert restored.caption == post.caption
    assert restored.hashtags == post.hashtags
    assert restored.images[0].original == "images/original/x.jpg"
    assert restored.status == PostStatus.DRAFT


def test_post_status_values():
    assert PostStatus.DRAFT.value == "draft"
    assert PostStatus.POSTED.value == "posted"
