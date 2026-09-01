"""画像編集処理: リサイズ/トリミング/自動補正/背景除去/透かし/テキスト合成/サイズ検証。"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFont, ImageOps

# Instagram推奨サイズ(長辺1080px基準)
PRESETS: dict[str, tuple[int, int]] = {
    "square": (1080, 1080),  # 1:1
    "portrait": (1080, 1350),  # 4:5 (フィード縦長の上限)
    "landscape": (1080, 566),  # 1.91:1 (フィード横長の上限)
    "story": (1080, 1920),  # 9:16 (ストーリーズ/リール)
}

MIN_RATIO = 0.8  # 4:5
MAX_RATIO = 1.91  # 1.91:1
MIN_LONG_EDGE = 320


def load_image(path: Path) -> Image.Image:
    img = Image.open(path)
    img = ImageOps.exif_transpose(img)  # スマホ写真の回転情報を正しく反映
    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGB")
    return img


def resize_and_crop(img: Image.Image, preset: str) -> Image.Image:
    if preset not in PRESETS:
        raise ValueError(f"未知のプリセットです: {preset} (選択肢: {', '.join(PRESETS)})")
    size = PRESETS[preset]
    return ImageOps.fit(img, size, method=Image.LANCZOS, centering=(0.5, 0.5))


def crop_and_resize(
    img: Image.Image,
    x: float,
    y: float,
    width: float,
    height: float,
    target_size: tuple[int, int] | None = None,
) -> Image.Image:
    """任意の矩形(元画像のピクセル座標)で切り抜き、必要なら指定サイズにリサイズする。

    中央固定のresize_and_cropと異なり、切り抜き位置・拡大縮小はGUI側(例: Cropper.js)で
    ユーザーが自由に指定した値をそのまま使う。
    """
    img_w, img_h = img.size
    x = max(0, min(round(x), img_w - 1))
    y = max(0, min(round(y), img_h - 1))
    width = max(1, min(round(width), img_w - x))
    height = max(1, min(round(height), img_h - y))

    cropped = img.crop((x, y, x + width, y + height))
    if target_size:
        cropped = cropped.resize(target_size, Image.LANCZOS)
    return cropped


def auto_enhance(img: Image.Image) -> Image.Image:
    """明るさ・コントラスト・彩度・シャープネスを自動で軽く整える簡易AI補正。"""
    rgb = img.convert("RGB") if img.mode == "RGBA" else img
    rgb = ImageOps.autocontrast(rgb, cutoff=1)
    rgb = ImageEnhance.Color(rgb).enhance(1.15)
    rgb = ImageEnhance.Contrast(rgb).enhance(1.05)
    rgb = ImageEnhance.Sharpness(rgb).enhance(1.15)
    if img.mode == "RGBA":
        rgb = rgb.convert("RGBA")
        rgb.putalpha(img.getchannel("A"))
    return rgb


def remove_background(img: Image.Image) -> Image.Image:
    """背景を除去して透過PNGにする。要 `pip install rembg onnxruntime`。"""
    try:
        from rembg import remove
    except ImportError as exc:
        raise RuntimeError(
            "背景除去機能を使うには追加パッケージが必要です: pip install rembg onnxruntime"
        ) from exc
    return remove(img)


def add_watermark(
    img: Image.Image,
    watermark_path: Path,
    position: str = "bottom-right",
    margin: int = 24,
    scale: float = 0.15,
    opacity: float = 0.8,
) -> Image.Image:
    base = img.convert("RGBA")
    mark = Image.open(watermark_path).convert("RGBA")

    target_w = max(1, int(base.width * scale))
    ratio = target_w / mark.width
    mark = mark.resize((target_w, max(1, int(mark.height * ratio))), Image.LANCZOS)

    if opacity < 1.0:
        alpha = mark.getchannel("A").point(lambda a: int(a * opacity))
        mark.putalpha(alpha)

    positions = {
        "bottom-right": (base.width - mark.width - margin, base.height - mark.height - margin),
        "bottom-left": (margin, base.height - mark.height - margin),
        "top-right": (base.width - mark.width - margin, margin),
        "top-left": (margin, margin),
        "center": ((base.width - mark.width) // 2, (base.height - mark.height) // 2),
    }
    if position not in positions:
        raise ValueError(f"未知の位置指定です: {position} (選択肢: {', '.join(positions)})")

    composed = base.copy()
    composed.alpha_composite(mark, dest=positions[position])
    return composed


def add_text_overlay(
    img: Image.Image,
    text: str,
    position: str = "bottom",
    font_path: str | None = None,
    font_size: int = 56,
    color: tuple[int, int, int] = (255, 255, 255),
    stroke_color: tuple[int, int, int] = (0, 0, 0),
    stroke_width: int = 3,
    padding: int = 48,
) -> Image.Image:
    base = img.convert("RGBA")
    draw = ImageDraw.Draw(base)

    try:
        font = ImageFont.truetype(font_path, font_size) if font_path else ImageFont.load_default(
            size=font_size
        )
    except (OSError, TypeError):
        font = ImageFont.load_default()

    max_width = base.width - 2 * padding
    lines = _wrap_text(text, font, max_width, draw)
    line_heights = [draw.textbbox((0, 0), line, font=font)[3] for line in lines]
    total_height = sum(line_heights) + (len(lines) - 1) * 10

    if position == "top":
        y = padding
    elif position == "center":
        y = (base.height - total_height) // 2
    else:  # bottom
        y = base.height - total_height - padding

    for line, h in zip(lines, line_heights):
        bbox = draw.textbbox((0, 0), line, font=font)
        w = bbox[2] - bbox[0]
        x = (base.width - w) // 2
        draw.text(
            (x, y),
            line,
            font=font,
            fill=color,
            stroke_width=stroke_width,
            stroke_fill=stroke_color,
        )
        y += h + 10

    return base


def _wrap_text(text: str, font, max_width: int, draw: ImageDraw.ImageDraw) -> list[str]:
    lines: list[str] = []
    for raw_line in text.splitlines() or [""]:
        current = ""
        for ch in raw_line:
            trial = current + ch
            bbox = draw.textbbox((0, 0), trial, font=font)
            if bbox[2] - bbox[0] > max_width and current:
                lines.append(current)
                current = ch
            else:
                current = trial
        lines.append(current)
    return lines


def validate_instagram_size(img: Image.Image) -> list[str]:
    warnings: list[str] = []
    w, h = img.size
    ratio = w / h
    if ratio < MIN_RATIO or ratio > MAX_RATIO:
        warnings.append(
            f"アスペクト比 {ratio:.2f} がInstagram推奨範囲({MIN_RATIO}〜{MAX_RATIO})外です"
        )
    if min(w, h) < MIN_LONG_EDGE:
        warnings.append(f"解像度が低すぎます ({w}x{h})。長辺1080px以上を推奨します")
    return warnings


def save_image(img: Image.Image, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if img.mode == "RGBA" and dest.suffix.lower() in (".jpg", ".jpeg"):
        img = img.convert("RGB")
    img.save(dest, quality=92)
    return dest
