from PIL import Image

from ig_toolkit import image_edit


def test_resize_and_crop_square():
    img = Image.new("RGB", (2000, 1000), color=(10, 20, 30))
    out = image_edit.resize_and_crop(img, "square")
    assert out.size == (1080, 1080)


def test_validate_instagram_size_warns_on_low_res():
    img = Image.new("RGB", (100, 100))
    warnings = image_edit.validate_instagram_size(img)
    assert warnings  # 低解像度なので警告が出る


def test_validate_instagram_size_ok():
    img = Image.new("RGB", (1080, 1080))
    warnings = image_edit.validate_instagram_size(img)
    assert warnings == []


def test_auto_enhance_preserves_size():
    img = Image.new("RGB", (500, 500), color=(120, 130, 140))
    out = image_edit.auto_enhance(img)
    assert out.size == img.size
