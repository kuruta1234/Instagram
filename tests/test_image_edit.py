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


def _find_color_bbox(img, color, tol=30):
    px = img.convert("RGB").load()
    w, h = img.size
    min_x = min_y = max_x = max_y = None
    for y in range(h):
        for x in range(w):
            r, g, b = px[x, y]
            if abs(r - color[0]) <= tol and abs(g - color[1]) <= tol and abs(b - color[2]) <= tol:
                if min_x is None or x < min_x:
                    min_x = x
                if max_x is None or x > max_x:
                    max_x = x
                if min_y is None or y < min_y:
                    min_y = y
                if max_y is None or y > max_y:
                    max_y = y
    return min_x, min_y, max_x, max_y


def test_add_text_overlay_free_position_matches_requested_ratio():
    img = Image.new("RGB", (400, 400), color=(0, 0, 0))
    out = image_edit.add_text_overlay(
        img, "A", x=0.25, y=0.75, font_size=80, color=(255, 0, 0), stroke_width=0
    ).convert("RGB")

    bbox = _find_color_bbox(out, (255, 0, 0))
    assert bbox[0] is not None, "テキストのピクセルが見つかりません"
    center_x = (bbox[0] + bbox[2]) / 2
    center_y = (bbox[1] + bbox[3]) / 2
    assert abs(center_x - 400 * 0.25) < 40
    assert abs(center_y - 400 * 0.75) < 40


def test_add_text_overlay_default_position_is_bottom_center():
    img = Image.new("RGB", (400, 400), color=(0, 0, 0))
    out = image_edit.add_text_overlay(
        img, "A", position="bottom", font_size=80, color=(255, 0, 0), stroke_width=0
    ).convert("RGB")

    bbox = _find_color_bbox(out, (255, 0, 0))
    assert bbox[0] is not None
    center_x = (bbox[0] + bbox[2]) / 2
    assert abs(center_x - 200) < 40  # positionのみ指定時は画像全体で水平中央揃え
    assert bbox[3] > 300  # 下寄りに配置されている


def test_add_text_overlay_xy_clamped_to_valid_range():
    img = Image.new("RGB", (200, 200), color=(0, 0, 0))
    out = image_edit.add_text_overlay(
        img, "A", x=-5, y=10, font_size=40, color=(255, 0, 0), stroke_width=0
    )
    assert out.size == img.size  # 範囲外の値でも例外にならずクランプされる


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
