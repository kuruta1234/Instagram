from pathlib import Path

from PIL import Image


def _make_test_image(path: Path) -> Path:
    Image.new("RGB", (200, 200), color=(255, 0, 0)).save(path)
    return path


def test_create_and_load(isolated_data_dir, tmp_path):
    from ig_toolkit import storage

    img_path = _make_test_image(tmp_path / "sample.jpg")
    post = storage.create(topic="秋の新作紅茶", image_paths=[img_path])

    assert storage.exists(post.id)
    loaded = storage.load(post.id)
    assert loaded.topic == "秋の新作紅茶"
    assert len(loaded.images) == 1

    resolved = storage.resolve_image_path(post.id, loaded.images[0].original)
    assert resolved.exists()


def test_list_posts_and_delete(isolated_data_dir, tmp_path):
    from ig_toolkit import storage

    img_path = _make_test_image(tmp_path / "sample2.jpg")
    post = storage.create(topic="商品A", image_paths=[img_path])

    assert post.id in storage.list_ids()
    posts = storage.list_posts()
    assert any(p.id == post.id for p in posts)

    storage.delete(post.id)
    assert not storage.exists(post.id)
