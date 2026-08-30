from ig_toolkit.models import ImageAsset, Post, PostStatus, ReviewChecklist


def test_post_roundtrip_dict():
    post = Post(
        id="20260101-test-abcd",
        topic="テスト投稿",
        keywords=["a", "b"],
        images=[ImageAsset(original="images/original/x.jpg")],
    )
    data = post.to_dict()
    restored = Post.from_dict(data)

    assert restored.id == post.id
    assert restored.topic == post.topic
    assert restored.keywords == post.keywords
    assert restored.images[0].original == "images/original/x.jpg"
    assert restored.status == PostStatus.DRAFT


def test_checklist_all_passed():
    cl = ReviewChecklist()
    assert not cl.all_passed()
    cl.image_ok = cl.caption_ok = cl.hashtag_ok = cl.rights_ok = cl.ng_word_ok = True
    assert cl.all_passed()
