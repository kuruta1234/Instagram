"""igtool-gui のルーティング定義。"""

from __future__ import annotations

import tempfile
from pathlib import Path

from flask import (
    Blueprint,
    abort,
    flash,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)
from werkzeug.utils import secure_filename

from .. import edit_ops, export_ops, image_edit, storage
from ..caption import CaptionGenerationError, describe_image, generate_caption_via_cli, parse_hashtags
from ..models import Post, PostStatus

bp = Blueprint("igtool", __name__)

WATERMARK_POSITIONS = ["bottom-right", "bottom-left", "top-right", "top-left", "center"]
TEXT_POSITIONS = ["top", "center", "bottom"]


def _get_post_or_404(post_id: str) -> Post:
    try:
        return storage.load(post_id)
    except storage.PostNotFoundError:
        abort(404)


def _image_index_or_404(post: Post, index: int) -> None:
    if index < 0 or index >= len(post.images):
        abort(404)


@bp.app_template_filter("cache_bust")
def cache_bust_filter(post_and_index: tuple[Post, int]) -> int:
    """画像URLのキャッシュ回避用に、現在の画像ファイルの更新時刻を返す。"""
    post, index = post_and_index
    asset = post.images[index]
    rel = asset.edited or asset.original
    path = storage.resolve_image_path(post.id, rel)
    return int(path.stat().st_mtime) if path.exists() else 0


@bp.route("/")
def index():
    return redirect(url_for("igtool.posts_list"))


@bp.route("/posts")
def posts_list():
    status_filter = request.args.get("status") or None
    status_enum = PostStatus(status_filter) if status_filter else None
    posts = storage.list_posts(status=status_enum)
    return render_template(
        "posts_list.html",
        posts=posts,
        statuses=list(PostStatus),
        current_status=status_filter,
    )


@bp.route("/posts/new", methods=["GET", "POST"])
def post_new():
    if request.method == "GET":
        return render_template("post_new.html")

    topic = request.form.get("topic", "").strip()
    uploads = [f for f in request.files.getlist("images") if f and f.filename]

    if not topic:
        flash("トピックを入力してください", "error")
        return render_template("post_new.html"), 400
    if not uploads:
        flash("画像を1枚以上選択してください", "error")
        return render_template("post_new.html"), 400

    with tempfile.TemporaryDirectory() as tmp_dir:
        image_paths: list[Path] = []
        for upload in uploads:
            filename = secure_filename(upload.filename) or "image.jpg"
            dest = Path(tmp_dir) / filename
            upload.save(dest)
            image_paths.append(dest)

        post = storage.create(topic=topic, image_paths=image_paths)

    flash(f"投稿を作成しました: {post.id}", "success")
    return redirect(url_for("igtool.post_detail", post_id=post.id))


@bp.route("/posts/<post_id>")
def post_detail(post_id: str):
    post = _get_post_or_404(post_id)
    image_infos = []
    for i, asset in enumerate(post.images):
        rel = asset.edited or asset.original
        path = storage.resolve_image_path(post.id, rel)
        image_infos.append({"index": i, "asset": asset, "description": describe_image(path)})
    return render_template("post_detail.html", post=post, image_infos=image_infos)


@bp.route("/posts/<post_id>/caption", methods=["POST"])
def post_caption(post_id: str):
    post = _get_post_or_404(post_id)
    caption_text = request.form.get("caption_text", "")
    hashtags_raw = request.form.get("hashtags", "")
    post.caption = caption_text
    post.hashtags = parse_hashtags(hashtags_raw)
    storage.save(post)
    flash("キャプションを保存しました", "success")
    return redirect(url_for("igtool.post_detail", post_id=post_id))


@bp.route("/posts/<post_id>/caption/generate", methods=["POST"])
def post_caption_generate(post_id: str):
    post = _get_post_or_404(post_id)
    if not post.images:
        flash("画像が登録されていません", "error")
        return redirect(url_for("igtool.post_detail", post_id=post_id))

    primary = post.primary_image()
    image_path = storage.resolve_image_path(post.id, primary.edited or primary.original)
    notes = request.form.get("notes", "")

    try:
        result = generate_caption_via_cli(topic=post.topic, image_path=image_path, notes=notes)
    except CaptionGenerationError as exc:
        flash(f"{exc} 下のキャプション欄に直接入力することもできます。", "error")
        return redirect(url_for("igtool.post_detail", post_id=post_id))

    post.caption = str(result["caption"])
    post.hashtags = list(result["hashtags"])
    storage.save(post)
    flash("Claudeがキャプション案を作成しました。内容を確認し、必要なら編集して保存してください。", "success")
    return redirect(url_for("igtool.post_detail", post_id=post_id))


@bp.route("/posts/<post_id>/images/<int:index>/<variant>")
def serve_image(post_id: str, index: int, variant: str):
    post = _get_post_or_404(post_id)
    _image_index_or_404(post, index)
    asset = post.images[index]
    if variant == "raw":
        rel = asset.original
    elif variant == "current":
        rel = asset.edited or asset.original
    else:
        abort(404)
    path = storage.resolve_image_path(post.id, rel)
    if not path.exists():
        abort(404)
    return send_file(path)


@bp.route("/posts/<post_id>/edit/<int:index>")
def image_editor(post_id: str, index: int):
    post = _get_post_or_404(post_id)
    _image_index_or_404(post, index)
    return render_template(
        "image_editor.html",
        post=post,
        index=index,
        presets=image_edit.PRESETS,
        watermark_positions=WATERMARK_POSITIONS,
        text_positions=TEXT_POSITIONS,
        fonts=image_edit.FONTS,
        default_font=image_edit.DEFAULT_FONT,
    )


def _resolve_target_size(form) -> tuple[int, int] | None:
    preset = form.get("resize_preset", "")
    if preset in image_edit.PRESETS:
        return image_edit.PRESETS[preset]
    if preset == "custom":
        try:
            width = int(form.get("resize_width", "0"))
            height = int(form.get("resize_height", "0"))
        except ValueError:
            return None
        if width > 0 and height > 0:
            return (width, height)
    return None


@bp.route("/posts/<post_id>/edit/<int:index>/crop", methods=["POST"])
def apply_crop(post_id: str, index: int):
    post = _get_post_or_404(post_id)
    _image_index_or_404(post, index)

    try:
        x = float(request.form["crop_x"])
        y = float(request.form["crop_y"])
        width = float(request.form["crop_width"])
        height = float(request.form["crop_height"])
    except (KeyError, ValueError):
        flash(
            "トリミング範囲を取得できませんでした。画像上で範囲を選択してから適用してください。",
            "error",
        )
        return redirect(url_for("igtool.image_editor", post_id=post_id, index=index))

    if width <= 0 or height <= 0:
        flash("トリミング範囲が小さすぎます。もう一度選択してください。", "error")
        return redirect(url_for("igtool.image_editor", post_id=post_id, index=index))

    target_size = _resolve_target_size(request.form)

    asset, img = edit_ops.load_current_image(post, index)
    cropped = image_edit.crop_and_resize(img, x, y, width, height, target_size=target_size)
    edit_ops.save_edited(post, asset, cropped, ["crop"])
    storage.save(post)

    flash("トリミングを適用しました", "success")
    return redirect(url_for("igtool.image_editor", post_id=post_id, index=index))


@bp.route("/posts/<post_id>/edit/<int:index>/enhance", methods=["POST"])
def apply_enhance(post_id: str, index: int):
    post = _get_post_or_404(post_id)
    _image_index_or_404(post, index)

    asset, img = edit_ops.load_current_image(post, index)
    enhanced = image_edit.auto_enhance(img)
    edit_ops.save_edited(post, asset, enhanced, ["enhance"])
    storage.save(post)

    flash("自動補正を適用しました", "success")
    return redirect(url_for("igtool.image_editor", post_id=post_id, index=index))


@bp.route("/posts/<post_id>/edit/<int:index>/bg-remove", methods=["POST"])
def apply_bg_remove(post_id: str, index: int):
    post = _get_post_or_404(post_id)
    _image_index_or_404(post, index)

    asset, img = edit_ops.load_current_image(post, index)
    try:
        result = image_edit.remove_background(img)
    except RuntimeError as exc:
        flash(str(exc), "error")
        return redirect(url_for("igtool.image_editor", post_id=post_id, index=index))

    edit_ops.save_edited(post, asset, result, ["bg-remove"])
    storage.save(post)

    flash("背景を除去しました", "success")
    return redirect(url_for("igtool.image_editor", post_id=post_id, index=index))


@bp.route("/posts/<post_id>/edit/<int:index>/watermark", methods=["POST"])
def apply_watermark(post_id: str, index: int):
    post = _get_post_or_404(post_id)
    _image_index_or_404(post, index)

    upload = request.files.get("watermark_file")
    position = request.form.get("watermark_position", "bottom-right")
    if not upload or not upload.filename:
        flash("透かし画像を選択してください", "error")
        return redirect(url_for("igtool.image_editor", post_id=post_id, index=index))

    with tempfile.TemporaryDirectory() as tmp_dir:
        watermark_path = Path(tmp_dir) / (secure_filename(upload.filename) or "watermark.png")
        upload.save(watermark_path)

        asset, img = edit_ops.load_current_image(post, index)
        watermarked = image_edit.add_watermark(img, watermark_path, position=position)

    edit_ops.save_edited(post, asset, watermarked, ["watermark"])
    storage.save(post)

    flash("透かしを追加しました", "success")
    return redirect(url_for("igtool.image_editor", post_id=post_id, index=index))


@bp.route("/posts/<post_id>/edit/<int:index>/text", methods=["POST"])
def apply_text(post_id: str, index: int):
    post = _get_post_or_404(post_id)
    _image_index_or_404(post, index)

    text = request.form.get("overlay_text", "").strip()
    position = request.form.get("text_position", "bottom")
    font = request.form.get("text_font", image_edit.DEFAULT_FONT)
    if font not in image_edit.FONTS:
        font = image_edit.DEFAULT_FONT
    try:
        font_size = int(request.form.get("text_size", "56"))
    except ValueError:
        font_size = 56
    font_size = max(8, min(font_size, 300))
    color = image_edit.parse_hex_color(request.form.get("text_color", "#ffffff"))

    def _parse_ratio(value: str | None) -> float | None:
        if value is None or value == "":
            return None
        try:
            return max(0.0, min(1.0, float(value)))
        except ValueError:
            return None

    text_x = _parse_ratio(request.form.get("text_x"))
    text_y = _parse_ratio(request.form.get("text_y"))

    if not text:
        flash("画像に合成するテキストを入力してください", "error")
        return redirect(url_for("igtool.image_editor", post_id=post_id, index=index))

    asset, img = edit_ops.load_current_image(post, index)
    result = image_edit.add_text_overlay(
        img,
        text,
        x=text_x,
        y=text_y,
        position=position,
        font=font,
        font_size=font_size,
        color=color,
    )
    edit_ops.save_edited(post, asset, result, ["text"])
    storage.save(post)

    flash("テキストを追加しました", "success")
    return redirect(url_for("igtool.image_editor", post_id=post_id, index=index))


@bp.route("/posts/<post_id>/edit/<int:index>/illustrate", methods=["POST"])
def apply_illustrate(post_id: str, index: int):
    post = _get_post_or_404(post_id)
    _image_index_or_404(post, index)

    asset, img = edit_ops.load_current_image(post, index)
    result = image_edit.illustrate(img)
    edit_ops.save_edited(post, asset, result, ["illustrate"])
    storage.save(post)

    flash("イラスト風に変換しました", "success")
    return redirect(url_for("igtool.image_editor", post_id=post_id, index=index))


@bp.route("/posts/<post_id>/edit/<int:index>/reset", methods=["POST"])
def reset_image(post_id: str, index: int):
    post = _get_post_or_404(post_id)
    _image_index_or_404(post, index)

    asset = post.images[index]
    edit_ops.reset_image(post, asset)
    storage.save(post)

    flash("元画像に戻しました", "success")
    return redirect(url_for("igtool.image_editor", post_id=post_id, index=index))


@bp.route("/posts/<post_id>/export", methods=["POST"])
def post_export(post_id: str):
    post = _get_post_or_404(post_id)
    buffer, filename = export_ops.build_export_zip(post)
    return send_file(
        buffer,
        mimetype="application/zip",
        as_attachment=True,
        download_name=filename,
    )


@bp.route("/posts/<post_id>/mark-posted", methods=["POST"])
def post_mark_posted(post_id: str):
    post = _get_post_or_404(post_id)
    post.status = PostStatus.POSTED
    storage.save(post)
    flash("投稿済みにしました", "success")
    return redirect(url_for("igtool.post_detail", post_id=post_id))


@bp.route("/posts/<post_id>/delete", methods=["POST"])
def post_delete(post_id: str):
    try:
        storage.delete(post_id)
    except storage.PostNotFoundError:
        abort(404)
    flash(f"削除しました: {post_id}", "success")
    return redirect(url_for("igtool.posts_list"))
