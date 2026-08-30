from ig_toolkit.ng_words import check_text


def test_check_text_detects_hit():
    hits = check_text("これを使えば必ず痩せる！今すぐ試してね", ng_words=["必ず痩せる", "副作用なし"])
    assert hits == ["必ず痩せる"]


def test_check_text_no_hit():
    hits = check_text("秋限定の新作紅茶が入荷しました", ng_words=["必ず痩せる", "副作用なし"])
    assert hits == []
