"""igtool: Instagram投稿業務を効率化するローカルCLI。

GUIで操作したい場合は `igtool-gui` を実行するとブラウザで使えるWebアプリが起動する。

主なコマンド:
    igtool new         投稿ドラフトを新規作成
    igtool list         投稿一覧を表示
    igtool show          投稿の詳細を表示
    igtool caption       Claude Code CLI経由でキャプション/ハッシュタグを自動生成(使えない場合は手入力)
    igtool edit           画像を編集(リサイズ/自動補正/背景除去/透かし/テキスト)
    igtool export         投稿用の画像とキャプションをエクスポート
    igtool mark-posted   手動投稿が完了した投稿にマークする
    igtool delete         投稿ドラフトを削除
"""

from __future__ import annotations

from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from . import config, edit_ops, export_ops, image_edit, storage
from .caption import (
    CaptionGenerationError,
    format_context_for_input,
    generate_caption_via_cli,
    parse_hashtags,
)
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
    """Instagram投稿の下書き作成・キャプション作成・画像編集を支援するCLI。"""
    config.ensure_dirs()


@main.command()
@click.option("--topic", required=True, help="投稿のテーマ・商品名など")
@click.option(
    "--image",
    "images",
    multiple=True,
    required=True,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="投稿に使う画像ファイル(複数指定可)",
)
def new(topic: str, images: tuple[Path, ...]) -> None:
    """投稿ドラフトを新規作成する。"""
    post = storage.create(topic=topic, image_paths=list(images))
    console.print(f"[green]作成しました:[/green] {post.id}")
    console.print(f"  画像 {len(post.images)} 枚を取り込みました")
    console.print(f"  次は [bold]igtool caption {post.id}[/bold] でキャプションを作成できます")


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
    table.add_column("更新日時")
    for p in posts:
        table.add_row(p.id, p.status.value, p.topic, p.updated_at)
    console.print(table)


@main.command()
@click.argument("post_id")
def show(post_id: str) -> None:
    """投稿の詳細を表示する。"""
    post = _load_or_fail(post_id)
    console.print(f"[bold]{post.id}[/bold]  ({post.status.value})")
    console.print(f"トピック: {post.topic}")
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


@main.command()
@click.argument("post_id")
@click.option("--notes", default="", help="AIへの追加指示(強調したい点など)")
@click.option("--hashtag-count", default=10, show_default=True)
@click.option("--manual", is_flag=True, help="AI生成を使わず手入力する")
@click.option("--caption-text", default=None, help="キャプション文を直接指定する")
@click.option("--hashtags", "hashtags_raw", default=None, help="カンマ区切りのハッシュタグを直接指定する")
def caption(
    post_id: str,
    notes: str,
    hashtag_count: int,
    manual: bool,
    caption_text: str | None,
    hashtags_raw: str | None,
) -> None:
    """画像を見てClaudeがキャプション/ハッシュタグを自動生成する。

    `claude` コマンドが使えない場合(Freeプランなど)は、Anthropic APIキーには
    フォールバックせず、そのまま手入力モードに切り替わる。--manualで最初から手入力も可。
    """
    post = _load_or_fail(post_id)

    if not post.images:
        raise click.ClickException("画像が登録されていません。先に `igtool new` で画像を追加してください。")

    primary = post.primary_image()
    image_path = storage.resolve_image_path(post.id, primary.edited or primary.original)

    hashtags: list[str] | None = None
    attempt_ai = caption_text is None and hashtags_raw is None and not manual

    if attempt_ai:
        console.print(f"画像を確認してキャプションを生成しています... ({image_path.name})")
        try:
            result = generate_caption_via_cli(
                topic=post.topic, image_path=image_path, hashtag_count=hashtag_count, notes=notes
            )
            caption_text = str(result["caption"])
            hashtags = list(result["hashtags"])
            console.print("[green]AIによる下書きを作成しました(内容は自由に手直しできます)[/green]")
        except CaptionGenerationError as exc:
            console.print(f"[yellow]AI生成を利用できません: {exc}[/yellow]")
            console.print("[yellow]手入力モードに切り替えます。[/yellow]")

    if caption_text is None or hashtags is None:
        image_paths = [
            storage.resolve_image_path(post.id, img.edited or img.original) for img in post.images
        ]
        console.print(format_context_for_input(post.topic, image_paths))
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

        if hashtags is None:
            if hashtags_raw is None:
                hashtags_raw = click.prompt(
                    "ハッシュタグ(カンマ区切り、#は省略可)", default="", show_default=False
                )
            hashtags = parse_hashtags(hashtags_raw)

    post.caption = caption_text
    post.hashtags = hashtags
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
@click.option(
    "--text-font",
    type=click.Choice(list(image_edit.FONTS)),
    default=image_edit.DEFAULT_FONT,
    show_default=True,
    help="テキスト合成に使うフォント",
)
@click.option("--text-size", default=56, show_default=True, help="テキストのフォントサイズ(px)")
@click.option(
    "--text-color", default="#ffffff", show_default=True, help="テキストの色(#rrggbb形式)"
)
@click.option(
    "--text-x",
    type=float,
    default=None,
    help="テキストの水平位置(0.0=左端〜1.0=右端の比率、省略時は中央/--text-positionに従う)",
)
@click.option(
    "--text-y",
    type=float,
    default=None,
    help="テキストの垂直位置(0.0=上端〜1.0=下端の比率、指定すると--text-positionより優先)",
)
@click.option("--illustrate", is_flag=True, help="写真をイラスト風(減色+輪郭線)に変換する")
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
    text_font: str,
    text_size: int,
    text_color: str,
    text_x: float | None,
    text_y: float | None,
    illustrate: bool,
) -> None:
    """画像を編集する(中央固定のクロップ。任意範囲を選びたい場合はGUIを使用)。"""
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
    if illustrate:
        img = image_edit.illustrate(img)
        applied.append("illustrate")
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
        img = image_edit.add_text_overlay(
            img,
            text,
            x=text_x,
            y=text_y,
            position=text_position,
            font=text_font,
            font_size=text_size,
            color=image_edit.parse_hex_color(text_color),
        )
        applied.append("text")

    if not applied:
        console.print("[yellow]編集オプションが指定されていません。--preset/--enhance/--bg-remove/--illustrate/--watermark/--text のいずれかを指定してください。[/yellow]")
        return

    edit_ops.save_edited(post, asset, img, applied)
    storage.save(post)

    console.print(f"[green]編集しました:[/green] {asset.edited}  (適用: {', '.join(applied)})")
    warnings = image_edit.validate_instagram_size(img)
    for w in warnings:
        console.print(f"[yellow]注意:[/yellow] {w}")


@main.command()
@click.argument("post_id")
def export(post_id: str) -> None:
    """投稿用の画像とキャプションテキストをエクスポートする(手動投稿用)。"""
    post = _load_or_fail(post_id)
    export_dir = export_ops.export_post(post)

    console.print(f"[green]エクスポートしました:[/green] {export_dir}")
    console.print("画像とcaption.txtの内容をInstagramアプリにコピーして投稿してください。")
    console.print(f"投稿が完了したら `igtool mark-posted {post.id}` を実行してください。")


@main.command(name="mark-posted")
@click.argument("post_id")
def mark_posted(post_id: str) -> None:
    """手動投稿が完了した投稿に「投稿済み」のマークを付ける。"""
    post = _load_or_fail(post_id)
    post.status = PostStatus.POSTED
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
