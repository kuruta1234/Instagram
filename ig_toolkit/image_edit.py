"""画像編集処理: リサイズ/トリミング/自動補正/背景除去/透かし/テキスト合成/イラスト化/サイズ検証。"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

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

# テキスト合成用に同梱している日本語対応フォント。
# PillowのImageFont.load_default()は日本語グリフを持たないため、
# 既定では必ずこちらを使う(文字化け/豆腐対策)。
FONTS_DIR = Path(__file__).resolve().parent / "assets" / "fonts"
FONTS: dict[str, Path] = {
    "gothic": FONTS_DIR / "IPAGothic.ttf",
    "mincho": FONTS_DIR / "IPAMincho.ttf",
}
DEFAULT_FONT = "gothic"


def parse_hex_color(value: str, default: tuple[int, int, int] = (255, 255, 255)) -> tuple[int, int, int]:
    """"#rrggbb" 形式の文字列をRGBタプルに変換する(パース不能時はdefaultを返す)。"""
    value = (value or "").strip().lstrip("#")
    if len(value) != 6:
        return default
    try:
        return (int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16))
    except ValueError:
        return default


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
    x: float | None = None,
    y: float | None = None,
    position: str = "bottom",
    font: str = DEFAULT_FONT,
    font_path: str | Path | None = None,
    font_size: int = 56,
    color: tuple[int, int, int] = (255, 255, 255),
    stroke_color: tuple[int, int, int] = (0, 0, 0),
    stroke_width: int = 3,
    padding: int = 48,
) -> Image.Image:
    """画像にテキストを合成する。

    x, y を指定すると、その座標(画像サイズに対する比率 0.0〜1.0)を
    テキストブロックの中心として任意の位置に配置する(ドラッグ配置用)。
    x, y を省略した場合は従来通り position("top"/"center"/"bottom")に従い、
    画像全体の横幅を基準に中央揃えする。

    font_path未指定時はfont(フォント名: "gothic"/"mincho")に対応する
    同梱の日本語対応フォントを使う。PillowのImageFont.load_default()は
    日本語グリフを含まず文字化けするため、フォールバックとしても使わない。
    """
    base = img.convert("RGBA")
    draw = ImageDraw.Draw(base)

    resolved_path = Path(font_path) if font_path else FONTS.get(font, FONTS[DEFAULT_FONT])
    try:
        pil_font = ImageFont.truetype(str(resolved_path), font_size)
    except OSError as exc:
        raise ValueError(f"フォントを読み込めませんでした: {resolved_path}") from exc

    max_width = base.width - 2 * padding
    lines = _wrap_text(text, pil_font, max_width, draw)
    line_widths = []
    line_heights = []
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=pil_font)
        line_widths.append(bbox[2] - bbox[0])
        line_heights.append(bbox[3])
    block_width = max(line_widths) if line_widths else 0
    total_height = sum(line_heights) + (len(lines) - 1) * 10

    free_placement = x is not None or y is not None
    if free_placement:
        center_x = base.width * (0.5 if x is None else max(0.0, min(1.0, x)))
        center_y = base.height * (0.5 if y is None else max(0.0, min(1.0, y)))
        block_left = center_x - block_width / 2
        cursor_y = center_y - total_height / 2
    else:
        if position == "top":
            cursor_y = padding
        elif position == "center":
            cursor_y = (base.height - total_height) // 2
        else:  # bottom
            cursor_y = base.height - total_height - padding

    for line, w, h in zip(lines, line_widths, line_heights):
        if free_placement:
            line_x = block_left + (block_width - w) / 2
        else:
            line_x = (base.width - w) / 2
        draw.text(
            (line_x, cursor_y),
            line,
            font=pil_font,
            fill=color,
            stroke_width=stroke_width,
            stroke_fill=stroke_color,
        )
        cursor_y += h + 10

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


def illustrate(
    img: Image.Image,
    colors: int = 24,
    edge_strength: int = 55,
    brightness: float = 1.08,
    saturation: float = 1.6,
    line_color: tuple[int, int, int] = (90, 65, 55),
) -> Image.Image:
    """写真を明るく鮮やかな配色+やわらかい輪郭線の「かわいいイラスト風」に変換する。

    OpenCV等の追加インストールなしで動作するよう、Pillow標準機能のみで実装した
    簡易カートゥーン化(彩度・明るさアップ+減色+輪郭線抽出)。colorsで配色の数
    (多いほど頬の赤みなど細かい色も残りやすい)、edge_strengthで輪郭線の出やすさ、
    brightness/saturationで明るさ・鮮やかさ、line_colorで輪郭線の色を調整できる。
    輪郭線は黒ではなくやわらかい焦げ茶色を既定にし、硬い印象にならないようにしている。
    """
    rgb = img.convert("RGB")

    # 1. 明るく鮮やかにして、かわいい印象のベースを作る
    vivid = ImageEnhance.Color(rgb).enhance(saturation)
    vivid = ImageEnhance.Brightness(vivid).enhance(brightness)

    # 2. 細部・ノイズを平滑化してベタ塗りに近づける
    smooth = vivid
    for _ in range(5):
        smooth = smooth.filter(ImageFilter.SMOOTH_MORE)

    # 3. 減色してポスター風のフラットな配色にする
    quantized = smooth.quantize(colors=max(4, colors), method=Image.MEDIANCUT).convert("RGB")

    # 4. 輪郭線を抽出し、閾値処理して「線画」を作る(画像の外周は誤検出として除外)。
    #    背景のざらつき(ノイズ)を輪郭と誤検出しないよう、あらかじめしっかりぼかしておく。
    gray = rgb.convert("L").filter(ImageFilter.GaussianBlur(1.2))
    gray = gray.filter(ImageFilter.MedianFilter(size=13))
    edges = gray.filter(ImageFilter.FIND_EDGES)
    edges = ImageOps.autocontrast(edges, cutoff=1)
    line_mask = edges.point(lambda p: 255 if p > (255 - edge_strength) else 0)
    line_mask = line_mask.filter(ImageFilter.MaxFilter(3))
    ImageDraw.Draw(line_mask).rectangle(
        [0, 0, line_mask.width - 1, line_mask.height - 1], outline=0, width=2
    )
    line_mask = line_mask.filter(ImageFilter.GaussianBlur(0.8))
    line_mask = line_mask.point(lambda p: 255 if p > 160 else 0)

    # 5. 配色の上にやわらかい色の輪郭線を重ねて完成
    result = quantized.copy()
    ink = Image.new("RGB", result.size, line_color)
    result.paste(ink, mask=line_mask)
    return result


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
