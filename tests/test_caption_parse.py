from ig_toolkit.caption import _parse_response


def test_parse_response_well_formed():
    text = (
        "【キャプション】\n"
        "秋限定の新作紅茶が入荷しました。ぜひお試しください。\n\n"
        "【ハッシュタグ】\n"
        "#紅茶 #秋限定 #新作"
    )
    result = _parse_response(text)
    assert "秋限定の新作紅茶" in result["caption"]
    assert result["hashtags"] == ["#紅茶", "#秋限定", "#新作"]


def test_parse_response_fallback_when_unformatted():
    text = "適当な本文です #tag1 #tag2"
    result = _parse_response(text)
    assert result["caption"] == text
    assert result["hashtags"] == ["#tag1", "#tag2"]
