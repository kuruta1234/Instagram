from pathlib import Path

from PIL import Image

from ig_toolkit.caption import describe_image, format_context_for_input, parse_hashtags


def test_parse_hashtags_comma_separated():
    assert parse_hashtags("紅茶,秋限定, 新作") == ["#紅茶", "#秋限定", "#新作"]


def test_parse_hashtags_keeps_existing_hash_and_dedupes_whitespace():
    assert parse_hashtags("#紅茶   秋限定\n新作") == ["#紅茶", "#秋限定", "#新作"]


def test_parse_hashtags_empty_input():
    assert parse_hashtags("") == []
    assert parse_hashtags("   ") == []


def test_describe_image_existing_file(tmp_path):
    path = tmp_path / "sample.jpg"
    Image.new("RGB", (400, 300), color=(1, 2, 3)).save(path)
    desc = describe_image(path)
    assert "sample.jpg" in desc
    assert "400x300" in desc


def test_describe_image_missing_file(tmp_path):
    path = tmp_path / "missing.jpg"
    desc = describe_image(path)
    assert "見つかりません" in desc


def test_format_context_for_input_includes_topic_and_images(tmp_path):
    img_path = tmp_path / "a.jpg"
    Image.new("RGB", (100, 100)).save(img_path)
    text = format_context_for_input(
        topic="秋の新作紅茶",
        keywords=["紅茶", "秋限定"],
        tone="casual",
        image_paths=[img_path],
    )
    assert "秋の新作紅茶" in text
    assert "紅茶, 秋限定" in text
    assert "a.jpg" in text


def test_format_context_for_input_no_images():
    text = format_context_for_input(topic="テスト", keywords=[], tone="casual", image_paths=[])
    assert "画像: (なし)" in text
