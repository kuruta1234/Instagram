from unittest.mock import patch

from click.testing import CliRunner
from PIL import Image

from ig_toolkit.caption import CaptionGenerationError
from ig_toolkit.cli import main


def _make_image(path):
    Image.new("RGB", (200, 200), color=(10, 20, 30)).save(path)
    return path


def _create_post(runner, tmp_path, topic="テスト投稿") -> str:
    img_path = _make_image(tmp_path / "sample.jpg")
    result = runner.invoke(main, ["new", "--topic", topic, "--image", str(img_path)])
    assert result.exit_code == 0, result.output
    return result.output.split("作成しました: ")[1].splitlines()[0].strip()


def test_caption_falls_back_to_manual_when_cli_unavailable(isolated_data_dir, tmp_path):
    runner = CliRunner()
    post_id = _create_post(runner, tmp_path)

    with patch(
        "ig_toolkit.cli.generate_caption_via_cli",
        side_effect=CaptionGenerationError("claude コマンドが見つかりません"),
    ):
        result = runner.invoke(
            main,
            ["caption", post_id],
            input="1行目のキャプション\n\nタグ1, タグ2\n",
        )

    assert result.exit_code == 0, result.output
    assert "手入力モードに切り替えます" in result.output
    assert "キャプションを保存しました" in result.output
    # Anthropic APIへのフォールバックは行わない
    assert "ANTHROPIC_API_KEY" not in result.output

    from ig_toolkit import storage

    post = storage.load(post_id)
    assert post.caption == "1行目のキャプション"
    assert post.hashtags == ["#タグ1", "#タグ2"]


def test_caption_ai_success_skips_manual_prompt(isolated_data_dir, tmp_path):
    runner = CliRunner()
    post_id = _create_post(runner, tmp_path)

    with patch(
        "ig_toolkit.cli.generate_caption_via_cli",
        return_value={"caption": "AI生成キャプション", "hashtags": ["#a", "#b"]},
    ) as cli_mock:
        result = runner.invoke(main, ["caption", post_id])

    assert result.exit_code == 0, result.output
    cli_mock.assert_called_once()
    assert "手入力モードに切り替えます" not in result.output

    from ig_toolkit import storage

    post = storage.load(post_id)
    assert post.caption == "AI生成キャプション"
    assert post.hashtags == ["#a", "#b"]


def test_caption_manual_flag_skips_ai_entirely(isolated_data_dir, tmp_path):
    runner = CliRunner()
    post_id = _create_post(runner, tmp_path)

    with patch("ig_toolkit.cli.generate_caption_via_cli") as cli_mock:
        result = runner.invoke(
            main,
            ["caption", post_id, "--manual"],
            input="手入力のキャプション\n\nfree\n",
        )

    assert result.exit_code == 0, result.output
    cli_mock.assert_not_called()

    from ig_toolkit import storage

    post = storage.load(post_id)
    assert post.caption == "手入力のキャプション"
    assert post.hashtags == ["#free"]
