import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from ig_toolkit.caption import (
    CaptionGenerationError,
    _parse_ai_response,
    describe_image,
    format_context_for_input,
    generate_caption,
    generate_caption_via_api,
    generate_caption_via_cli,
    parse_hashtags,
)


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
    text = format_context_for_input(topic="秋の新作紅茶", image_paths=[img_path])
    assert "秋の新作紅茶" in text
    assert "a.jpg" in text


def test_format_context_for_input_no_images():
    text = format_context_for_input(topic="テスト", image_paths=[])
    assert "画像: (なし)" in text


def test_parse_ai_response_well_formed():
    text = (
        "【キャプション】\n"
        "秋限定の新作紅茶が入荷しました。ぜひお試しください。\n\n"
        "【ハッシュタグ】\n"
        "#紅茶 #秋限定 #新作"
    )
    result = _parse_ai_response(text)
    assert "秋限定の新作紅茶" in result["caption"]
    assert result["hashtags"] == ["#紅茶", "#秋限定", "#新作"]


def test_parse_ai_response_fallback_when_unformatted():
    text = "適当な本文です #tag1 #tag2"
    result = _parse_ai_response(text)
    assert result["caption"] == text
    assert result["hashtags"] == ["#tag1", "#tag2"]


def _fake_completed_process(stdout: str, returncode: int = 0, stderr: str = ""):
    class _Result:
        pass

    r = _Result()
    r.stdout = stdout
    r.stderr = stderr
    r.returncode = returncode
    return r


def test_generate_caption_via_cli_success(tmp_path):
    img_path = tmp_path / "sample.jpg"
    Image.new("RGB", (100, 100)).save(img_path)

    payload = json.dumps(
        {
            "is_error": False,
            "result": "【キャプション】\nテストキャプション\n\n【ハッシュタグ】\n#a #b",
        }
    )

    with patch("ig_toolkit.caption.shutil.which", return_value="/usr/bin/claude"), patch(
        "ig_toolkit.caption.subprocess.run", return_value=_fake_completed_process(payload)
    ):
        result = generate_caption_via_cli(topic="テスト", image_path=img_path)

    assert result["caption"] == "テストキャプション"
    assert result["hashtags"] == ["#a", "#b"]


def test_generate_caption_via_cli_missing_binary(tmp_path):
    img_path = tmp_path / "sample.jpg"
    Image.new("RGB", (100, 100)).save(img_path)

    with patch("ig_toolkit.caption.shutil.which", return_value=None):
        with pytest.raises(CaptionGenerationError, match="見つかりません"):
            generate_caption_via_cli(topic="テスト", image_path=img_path)


def test_generate_caption_via_cli_missing_image():
    with patch("ig_toolkit.caption.shutil.which", return_value="/usr/bin/claude"):
        with pytest.raises(CaptionGenerationError, match="画像が見つかりません"):
            generate_caption_via_cli(topic="テスト", image_path=Path("/no/such/file.jpg"))


def test_generate_caption_via_cli_nonzero_exit(tmp_path):
    img_path = tmp_path / "sample.jpg"
    Image.new("RGB", (100, 100)).save(img_path)

    with patch("ig_toolkit.caption.shutil.which", return_value="/usr/bin/claude"), patch(
        "ig_toolkit.caption.subprocess.run",
        return_value=_fake_completed_process("", returncode=1, stderr="boom"),
    ):
        with pytest.raises(CaptionGenerationError, match="失敗しました"):
            generate_caption_via_cli(topic="テスト", image_path=img_path)


def test_generate_caption_via_cli_is_error_response(tmp_path):
    img_path = tmp_path / "sample.jpg"
    Image.new("RGB", (100, 100)).save(img_path)

    payload = json.dumps({"is_error": True, "result": "permission denied"})

    with patch("ig_toolkit.caption.shutil.which", return_value="/usr/bin/claude"), patch(
        "ig_toolkit.caption.subprocess.run", return_value=_fake_completed_process(payload)
    ):
        with pytest.raises(CaptionGenerationError, match="エラーを返しました"):
            generate_caption_via_cli(topic="テスト", image_path=img_path)


# --- Anthropic APIフォールバック(generate_caption_via_api) ---


def test_generate_caption_via_api_success(tmp_path):
    img_path = tmp_path / "sample.jpg"
    Image.new("RGB", (100, 100)).save(img_path)

    text_block = MagicMock()
    text_block.type = "text"
    text_block.text = "【キャプション】\nAPIキャプション\n\n【ハッシュタグ】\n#x #y"
    mock_response = MagicMock()
    mock_response.content = [text_block]
    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_response

    with patch("anthropic.Anthropic", return_value=mock_client):
        result = generate_caption_via_api(topic="テスト", image_path=img_path, api_key="sk-test")

    assert result["caption"] == "APIキャプション"
    assert result["hashtags"] == ["#x", "#y"]
    mock_client.messages.create.assert_called_once()


def test_generate_caption_via_api_missing_key(tmp_path):
    img_path = tmp_path / "sample.jpg"
    Image.new("RGB", (100, 100)).save(img_path)

    with patch("ig_toolkit.config.ANTHROPIC_API_KEY", None):
        with pytest.raises(CaptionGenerationError, match="ANTHROPIC_API_KEY"):
            generate_caption_via_api(topic="テスト", image_path=img_path)


def test_generate_caption_via_api_missing_image():
    with pytest.raises(CaptionGenerationError, match="画像が見つかりません"):
        generate_caption_via_api(topic="テスト", image_path=Path("/no/such/file.jpg"), api_key="sk-test")


# --- generate_caption(): CLI優先+APIフォールバックの統合ロジック ---


def test_generate_caption_prefers_cli_and_skips_api(tmp_path):
    img_path = tmp_path / "sample.jpg"
    Image.new("RGB", (100, 100)).save(img_path)

    with patch(
        "ig_toolkit.caption.generate_caption_via_cli",
        return_value={"caption": "cli-caption", "hashtags": ["#a"]},
    ) as cli_mock, patch("ig_toolkit.caption.generate_caption_via_api") as api_mock:
        result = generate_caption(topic="t", image_path=img_path)

    assert result["caption"] == "cli-caption"
    cli_mock.assert_called_once()
    api_mock.assert_not_called()


def test_generate_caption_falls_back_to_api_when_cli_fails(tmp_path):
    img_path = tmp_path / "sample.jpg"
    Image.new("RGB", (100, 100)).save(img_path)

    with patch(
        "ig_toolkit.caption.generate_caption_via_cli",
        side_effect=CaptionGenerationError("cli not found"),
    ), patch("ig_toolkit.caption.config.ANTHROPIC_API_KEY", "sk-test"), patch(
        "ig_toolkit.caption.generate_caption_via_api",
        return_value={"caption": "api-caption", "hashtags": ["#b"]},
    ) as api_mock:
        result = generate_caption(topic="t", image_path=img_path)

    assert result["caption"] == "api-caption"
    api_mock.assert_called_once()


def test_generate_caption_raises_when_both_unavailable(tmp_path):
    img_path = tmp_path / "sample.jpg"
    Image.new("RGB", (100, 100)).save(img_path)

    with patch(
        "ig_toolkit.caption.generate_caption_via_cli",
        side_effect=CaptionGenerationError("cli not found"),
    ), patch("ig_toolkit.caption.config.ANTHROPIC_API_KEY", None):
        with pytest.raises(CaptionGenerationError, match="ANTHROPIC_API_KEY"):
            generate_caption(topic="t", image_path=img_path)


def test_generate_caption_raises_combined_error_when_both_fail(tmp_path):
    img_path = tmp_path / "sample.jpg"
    Image.new("RGB", (100, 100)).save(img_path)

    with patch(
        "ig_toolkit.caption.generate_caption_via_cli",
        side_effect=CaptionGenerationError("cli fail"),
    ), patch("ig_toolkit.caption.config.ANTHROPIC_API_KEY", "sk-test"), patch(
        "ig_toolkit.caption.generate_caption_via_api",
        side_effect=CaptionGenerationError("api fail"),
    ):
        with pytest.raises(CaptionGenerationError, match="失敗しました"):
            generate_caption(topic="t", image_path=img_path)
