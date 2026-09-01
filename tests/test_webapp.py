import io

from PIL import Image


def _make_image_bytes(size=(800, 600), color=(120, 130, 140)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color=color).save(buf, format="JPEG")
    buf.seek(0)
    return buf.read()


def _create_post(client, topic="秋の新作紅茶") -> str:
    data = {
        "topic": topic,
        "keywords": "紅茶, 秋限定",
        "tone": "casual",
        "images": (io.BytesIO(_make_image_bytes()), "sample.jpg"),
    }
    resp = client.post(
        "/posts/new", data=data, content_type="multipart/form-data", follow_redirects=False
    )
    assert resp.status_code == 302
    post_id = resp.headers["Location"].rstrip("/").rsplit("/", 1)[-1]
    return post_id


def _app_client(isolated_data_dir):
    from ig_toolkit.webapp import create_app

    app = create_app()
    app.testing = True
    return app.test_client()


def test_full_lifecycle_via_web(isolated_data_dir):
    client = _app_client(isolated_data_dir)

    # 一覧(空)
    resp = client.get("/posts")
    assert resp.status_code == 200

    # 新規作成
    post_id = _create_post(client)

    # 詳細ページ
    resp = client.get(f"/posts/{post_id}")
    assert resp.status_code == 200
    assert "秋の新作紅茶".encode() in resp.data

    # 画像を配信できる
    resp = client.get(f"/posts/{post_id}/images/0/raw")
    assert resp.status_code == 200
    resp = client.get(f"/posts/{post_id}/images/0/current")
    assert resp.status_code == 200

    # キャプション保存
    resp = client.post(
        f"/posts/{post_id}/caption",
        data={"caption_text": "秋限定の新作紅茶です", "hashtags": "紅茶, 秋限定"},
    )
    assert resp.status_code == 302

    from ig_toolkit import storage

    post = storage.load(post_id)
    assert post.caption == "秋限定の新作紅茶です"
    assert post.hashtags == ["#紅茶", "#秋限定"]

    # 画像編集ページが開ける
    resp = client.get(f"/posts/{post_id}/edit/0")
    assert resp.status_code == 200
    assert b"cropper.min.js" in resp.data

    # 自由トリミング(中央でない任意範囲)を適用
    resp = client.post(
        f"/posts/{post_id}/edit/0/crop",
        data={
            "crop_x": "50",
            "crop_y": "20",
            "crop_width": "300",
            "crop_height": "200",
            "resize_preset": "",
        },
    )
    assert resp.status_code == 302
    post = storage.load(post_id)
    assert post.images[0].edited is not None
    edited_path = storage.resolve_image_path(post_id, post.images[0].edited)
    with Image.open(edited_path) as img:
        assert img.size == (300, 200)

    # 自動補正
    resp = client.post(f"/posts/{post_id}/edit/0/enhance")
    assert resp.status_code == 302

    # 元に戻す
    resp = client.post(f"/posts/{post_id}/edit/0/reset")
    assert resp.status_code == 302
    post = storage.load(post_id)
    assert post.images[0].edited is None

    # レビューページ
    resp = client.get(f"/posts/{post_id}/review")
    assert resp.status_code == 200

    resp = client.post(
        f"/posts/{post_id}/review",
        data={
            "image_ok": "on",
            "caption_ok": "on",
            "hashtag_ok": "on",
            "rights_ok": "on",
            "ng_word_ok": "on",
        },
    )
    assert resp.status_code == 302
    post = storage.load(post_id)
    assert post.checklist.all_passed()

    # 承認
    resp = client.post(f"/posts/{post_id}/approve")
    assert resp.status_code == 302
    post = storage.load(post_id)
    assert post.status.value == "approved"

    # スケジュール
    resp = client.post(f"/posts/{post_id}/schedule", data={"date": "2026-09-05", "time": ""})
    assert resp.status_code == 302
    post = storage.load(post_id)
    assert post.scheduled_date == "2026-09-05"
    assert post.status.value == "scheduled"

    # カレンダー
    resp = client.get("/calendar?year=2026&month=9")
    assert resp.status_code == 200
    assert "秋の新作紅茶".encode() in resp.data

    # エクスポート
    resp = client.post(f"/posts/{post_id}/export")
    assert resp.status_code == 302

    from ig_toolkit import config

    export_dir = config.EXPORTS_DIR / post_id
    assert (export_dir / "caption.txt").exists()

    # 投稿済みにする
    resp = client.post(f"/posts/{post_id}/mark-posted")
    assert resp.status_code == 302
    post = storage.load(post_id)
    assert post.status.value == "posted"

    # 削除
    resp = client.post(f"/posts/{post_id}/delete")
    assert resp.status_code == 302
    assert not storage.exists(post_id)


def test_new_post_requires_topic_and_image(isolated_data_dir):
    client = _app_client(isolated_data_dir)

    resp = client.post(
        "/posts/new",
        data={"topic": "", "keywords": "", "tone": "casual"},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 400


def test_crop_missing_data_flashes_error(isolated_data_dir):
    client = _app_client(isolated_data_dir)
    post_id = _create_post(client)

    resp = client.post(f"/posts/{post_id}/edit/0/crop", data={}, follow_redirects=True)
    assert resp.status_code == 200
    assert "トリミング範囲を取得できませんでした".encode() in resp.data


def test_unknown_post_returns_404(isolated_data_dir):
    client = _app_client(isolated_data_dir)
    resp = client.get("/posts/does-not-exist")
    assert resp.status_code == 404
