"""igtool: Instagram投稿業務を効率化するローカルCLI。

GUIで操作したい場合は `igtool-gui` を実行するとブラウザで使えるWebアプリが起動する。

主なコマンド:
    igtool new        投稿ドラフトを新規作成
    igtool list        投稿一覧を表示
    igtool show         投稿の詳細を表示
    igtool caption      キャプション/ハッシュタグを手入力で設定
    igtool edit          画像を編集(リサイズ/自動補正/背景除去/透かし/テキスト)
    igtool review        投稿前チェックリストを対話的に実施
    igtool approve       チェック済みの投稿を承認
    igtool schedule      投稿予定日を設定
    igtool calendar      月間の投稿予定カレンダーを表示
    igtool export        承認済み投稿を手動投稿用にエクスポート
    igtool mark-posted  手動投稿が完了した投稿にマークする
    igtool delete        投稿ドラフトを削除
"""

from __future__ import annotations

from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from . import calendar_view, config, edit_ops, export_ops, image_edit, review, storage
from .caption import format_context_for_input, parse_hashtags
from .models import Post, PostStatus

console = Console()


def _load_or_fail(post_id: str) -> Post:
    try:
        return storage.load(post_id)
    except storage.PostNotFoundError as exc:
        raise click.ClickException(str(exc)) from exc


@click.group()
@click.version_option()
def main() -> None:
    """Instagram投稿の下書き作成・キャプション入力・画像編集・承認フローを支援するCLI。"""
    config.ensure_dirs()


@main.command()
@click.option("--topic", required=True, help="投稿のテーマ・商品名など")
@click.option("--keyword", "keywords", multiple=True, help="含めたいキーワード(複数指定可)")
@click.option(
    "--tone",
    type=click.Choice(["casual", "formal", "energetic", "elegant"]),
    default="casual",
    show_default=True,
)
@click.option(
    "--image",
    "images",
    multiple=True,
    required=True,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="投稿に使う画像ファイル(複数指定可)",
)
def new(topic: str, keywords: tuple[str, ...], tone: str, images: tuple[Path, ...]) -> None:
    """投稿ドラフトを新規作成する。"""
    post = storage.create(topic=topic, keywords=list(keywords), tone=tone, image_paths=list(images))
    console.print(f"[green]作成しました:[/green] {post.id}")
    console.print(f"  画像 {len(post.images)} 枚を取り込みました")
    console.print(f"  次は [bold]igtool caption {post.id}[/bold] でキャプションを入力できます")


@main.command(name="list")
@click.option(
    "--status",
    type=click.Choice([s.value for s in PostStatus]),
    default=None,
    help="ステータスで絞り込み",
)
def list_cmd(status: str | None) -> None:
    """投稿ドラフトの一覧を表示する。"""
    status_enum = PostStatus(status) if status else None
    posts = storage.list_posts(status=status_enum)
    if not posts:
        console.print("投稿がありません。`igtool new` で作成してください。")
        return

    table = Table(title="投稿一覧")
    table.add_column("ID")
    table.add_column("ステータス")
    table.add_column("トピック")
    table.add_column("予定日")
    table.add_column("更新日時")
    for p in posts:
        table.add_row(p.id, p.status.value, p.topic, p.scheduled_date or "-", p.updated_at)
    console.print(table)


@main.command()
@click.argument("post_id")
def show(post_id: str) -> None:
    """投稿の詳細を表示する。"""
    post = _load_or_fail(post_id)
    console.print(f"[bold]{post.id}[/bold]  ({post.status.value})")
    console.print(f"トピック: {post.topic}")
    console.print(f"キーワード: {', '.join(post.keywords) or '-'}")
    console.print(f"トーン: {post.tone}")
    console.print(f"予定日: {post.scheduled_date or '-'}")
    console.print("")
    console.print("[bold]キャプション:[/bold]")
    console.print(post.caption or "(未生成)")
    console.print("")
    console.print("[bold]ハッシュタグ:[/bold]")
    console.print(" ".join(post.hashtags) if post.hashtags else "(未生成)")
    console.print("")
    console.print("[bold]画像:[/bold]")
    for i, img in enumerate(post.images):
        state = "編集済み" if img.edited else "元画像のまま"
        console.print(f"  [{i}] {img.original}  ({state})")
    console.print("")
    cl = post.checklist
    console.print("[bold]チェックリスト:[/bold]")
    console.print(f"  画像OK: {cl.image_ok}  キャプションOK: {cl.caption_ok}")
    console.print(f"  ハッシュタグOK: {cl.hashtag_ok}  権利関係OK: {cl.rights_ok}")
    console.print(f"  NGワードOK: {cl.ng_word_ok}")


@main.command()
@click.argument("post_id")
@click.option(
    "--caption-text",
    default=None,
    help="キャプション文を直接指定する(省略時は対話入力)",
)
@click.option(
    "--hashtags",
    "hashtags_raw",
    default=None,
    help="カンマ区切りのハッシュタグを直接指定する(省略時は対話入力)",
)
def caption(post_id: str, caption_text: str | None, hashtags_raw: str | None) -> None:
    """キャプションとハッシュタグを手入力で設定する(既存の内容は上書き)。"""
    post = _load_or_fail(post_id)

    image_paths = [
        storage.resolve_image_path(post.id, img.edited or img.original) for img in post.images
    ]

    console.print(format_context_for_input(post.topic, post.keywords, post.tone, image_paths))
    console.print("")

    if caption_text is None:
        console.print(
            "画像を確認しながらキャプション文を入力してください(複数行可)。空行で入力を終えます。"
        )
        lines: list[str] = []
        while True:
            line = click.prompt("キャプション", default="", show_default=False)
            if line == "":
                break
            lines.append(line)
        caption_text = "\n".join(lines)

    if hashtags_raw is None:
        hashtags_raw = click.prompt(
            "ハッシュタグ(カンマ区切り、#は省略可)", default="", show_default=False
        )

    review.set_caption(post, caption_text, parse_hashtags(hashtags_raw))
    storage.save(post)

    console.print("[green]キャプションを保存しました[/green]")
    console.print(post.caption or "(空)")
    console.print("")
    console.print(" ".join(post.hashtags) if post.hashtags else "(なし)")


@main.command()
@click.argument("post_id")
@click.option("--image-index", default=0, show_default=True, help="編集対象の画像番号(0始まり)")
@click.option("--preset", type=click.Choice(list(image_edit.PRESETS)), default=None)
@click.option("--enhance", is_flag=True, help="明るさ・彩度・シャープネスを自動補正")
@click.option("--bg-remove", is_flag=True, help="背景を除去する(要 rembg)")
@click.option("--watermark", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option(
    "--watermark-position",
    type=click.Choice(["bottom-right", "bottom-left", "top-right", "top-left", "center"]),
    default="bottom-right",
    show_default=True,
)
@click.option("--text", default=None, help="画像に合成するテキスト")
@click.option(
    "--text-position",
    type=click.Choice(["top", "center", "bottom"]),
    default="bottom",
    show_default=True,
)
def edit(
    post_id: str,
    image_index: int,
    preset: str | None,
    enhance: bool,
    bg_remove: bool,
    watermark: Path | None,
    watermark_position: str,
    text: str | None,
    text_position: str,
) -> None:
    """画像を編集する(何も指定しない場合は元画像をそのまま編集用にコピー)。"""
    post = _load_or_fail(post_id)
    if image_index >= len(post.images):
        raise click.ClickException(f"画像番号が範囲外です(0〜{len(post.images) - 1})")

    asset, img = edit_ops.load_current_image(post, image_index)

    applied: list[str] = []
    if preset:
        img = image_edit.resize_and_crop(img, preset)
        applied.append(f"preset:{preset}")
    if enhance:
        img = image_edit.auto_enhance(img)
        applied.append("enhance")
    if bg_remove:
        try:
            img = image_edit.remove_background(img)
        except RuntimeError as exc:
            raise click.ClickException(str(exc)) from exc
        applied.append("bg-remove")
    if watermark:
        img = image_edit.add_watermark(img, watermark, position=watermark_position)
        applied.append("watermark")
    if text:
        img = image_edit.add_text_overlay(img, text, position=text_position)
        applied.append("text")

    if not applied:
        console.print("[yellow]編集オプションが指定されていません。--preset/--enhance/--bg-remove/--watermark/--text のいずれかを指定してください。[/yellow]")
        return

    edit_ops.save_edited(post, asset, img, applied)
    storage.save(post)

    console.print(f"[green]編集しました:[/green] {asset.edited}  (適用: {', '.join(applied)})")
    warnings = image_edit.validate_instagram_size(img)
    for w in warnings:
        console.print(f"[yellow]注意:[/yellow] {w}")


@main.command(name="review")
@click.argument("post_id")
def review_interactive(post_id: str) -> None:
    """投稿前チェックリストを対話的に実施する。"""
    post = _load_or_fail(post_id)
    result = review.run_auto_checks(post)

    console.print(f"[bold]{post.id}[/bold] のチェックを開始します")

    if result.ng_word_hits:
        console.print(f"[red]NGワード検出:[/red] {', '.join(result.ng_word_hits)}")
    else:
        console.print("[green]NGワードは検出されませんでした[/green]")

    if result.image_warnings:
        for path, warnings in result.image_warnings.items():
            for w in warnings:
                console.print(f"[yellow]画像警告 ({path}):[/yellow] {w}")
    else:
        console.print("[green]画像サイズの警告はありません[/green]")

    cl = post.checklist
    cl.ng_word_ok = click.confirm(
        "NGワードチェックを完了としますか？", default=not result.ng_word_hits
    )
    cl.image_ok = click.confirm(
        "画像の内容・サイズを確認しましたか？", default=not result.image_warnings
    )
    cl.caption_ok = click.confirm(
        "キャプション文面を確認しましたか？", default=not result.caption_empty
    )
    cl.hashtag_ok = click.confirm(
        "ハッシュタグを確認しましたか？", default=not result.hashtags_empty
    )
    cl.rights_ok = click.confirm("画像の著作権・使用許諾に問題ないことを確認しましたか？", default=False)

    if post.status == PostStatus.DRAFT:
        post.status = PostStatus.IN_REVIEW
    storage.save(post)

    if cl.all_passed():
        if click.confirm("チェックが全て完了しました。この投稿を承認しますか？", default=True):
            review.approve(post)
            storage.save(post)
            console.print("[green]承認しました。次は `igtool schedule` または `igtool export` へ。[/green]")
    else:
        console.print("[yellow]未完了の項目があります。全て完了すると承認できます。[/yellow]")


@main.command()
@click.argument("post_id")
def approve(post_id: str) -> None:
    """チェックリストが完了している投稿を承認する。"""
    post = _load_or_fail(post_id)
    try:
        review.approve(post)
    except ValueError as exc:
        raise click.ClickException(f"{exc} `igtool review {post_id}` を先に実施してください。") from exc
    storage.save(post)
    console.print(f"[green]承認しました:[/green] {post.id}")


@main.command()
@click.argument("post_id")
@click.option("--date", "date_str", required=True, help="投稿予定日 (YYYY-MM-DD)")
@click.option("--time", "time_str", default=None, help="投稿予定時刻 (HH:MM、任意)")
def schedule(post_id: str, date_str: str, time_str: str | None) -> None:
    """承認済みの投稿に予定日を設定する。"""
    post = _load_or_fail(post_id)
    scheduled = f"{date_str} {time_str}" if time_str else date_str
    try:
        review.schedule(post, scheduled)
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
    storage.save(post)
    console.print(f"[green]予定日を設定しました:[/green] {post.id} -> {scheduled}")


@main.command()
@click.option("--year", type=int, default=None)
@click.option("--month", type=int, default=None)
def calendar(year: int | None, month: int | None) -> None:
    """月間の投稿予定カレンダーを表示する。"""
    default_year, default_month = calendar_view.today_year_month()
    year = year or default_year
    month = month or default_month
    posts = storage.list_posts()
    console.print(calendar_view.render_text_calendar(posts, year, month))


@main.command()
@click.argument("post_id")
def export(post_id: str) -> None:
    """承認済み投稿を手動投稿用のフォルダにエクスポートする(画像+キャプションテキスト)。"""
    post = _load_or_fail(post_id)
    if post.status not in (PostStatus.APPROVED, PostStatus.SCHEDULED, PostStatus.POSTED):
        if not click.confirm(
            f"この投稿はまだ承認されていません(現在: {post.status.value})。エクスポートを続けますか？",
            default=False,
        ):
            return

    export_dir = export_ops.export_post(post)

    console.print(f"[green]エクスポートしました:[/green] {export_dir}")
    console.print("画像とcaption.txtの内容をInstagramアプリにコピーして投稿してください。")
    console.print(f"投稿が完了したら `igtool mark-posted {post.id}` を実行してください。")


@main.command(name="mark-posted")
@click.argument("post_id")
def mark_posted(post_id: str) -> None:
    """手動投稿が完了した投稿に「投稿済み」のマークを付ける。"""
    post = _load_or_fail(post_id)
    review.mark_posted(post)
    storage.save(post)
    console.print(f"[green]投稿済みにしました:[/green] {post.id}")


@main.command()
@click.argument("post_id")
@click.option("--yes", is_flag=True, help="確認をスキップする")
def delete(post_id: str, yes: bool) -> None:
    """投稿ドラフトを削除する。"""
    if not yes and not click.confirm(f"{post_id} を削除します。よろしいですか？", default=False):
        return
    try:
        storage.delete(post_id)
    except storage.PostNotFoundError as exc:
        raise click.ClickException(str(exc)) from exc
    console.print(f"[green]削除しました:[/green] {post_id}")


if __name__ == "__main__":
    main()
