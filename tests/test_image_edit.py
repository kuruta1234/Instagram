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


def test_bundled_fonts_exist_and_are_valid_ttf():
    from PIL import ImageFont

    for path in image_edit.FONTS.values():
        assert path.exists(), f"フォントファイルが見つかりません: {path}"
        ImageFont.truetype(str(path), 32)  # 読み込めることを確認(壊れたTTFなら例外)


def test_add_text_overlay_renders_japanese_without_error():
    img = Image.new("RGB", (600, 600), color=(80, 120, 200))
    out = image_edit.add_text_overlay(
        img, "秋の新作紅茶が入荷しました", font="gothic", font_size=48, color=(255, 255, 255)
    )
    assert out.size == img.size


def test_add_text_overlay_unknown_font_path_raises():
    img = Image.new("RGB", (200, 200))
    try:
        image_edit.add_text_overlay(img, "test", font_path="/no/such/font.ttf")
        assert False, "例外が発生するはず"
    except ValueError:
        pass


def test_parse_hex_color():
    assert image_edit.parse_hex_color("#ff0080") == (255, 0, 128)
    assert image_edit.parse_hex_color("ff0080") == (255, 0, 128)
    assert image_edit.parse_hex_color("invalid", default=(1, 2, 3)) == (1, 2, 3)


def test_illustrate_preserves_size_and_changes_pixels():
    img = Image.new("RGB", (300, 300), color=(200, 100, 50))
    for x in range(150, 300):
        for y in range(150, 300):
            img.putpixel((x, y), (50, 100, 200))

    out = image_edit.illustrate(img)
    assert out.size == img.size
    assert out.mode == "RGB"
    # 何らかの変換が行われている(元画像と完全一致しない)
    assert out.tobytes() != img.tobytes()
