"""PWA 아이콘 placeholder 생성.

`#191F28` 배경 + 흰색 'DB' 글자. 정식 브랜드 아이콘이 나오면 교체한다.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parents[1] / "frontend" / "public" / "icons"
OUT.mkdir(parents=True, exist_ok=True)

BG = (25, 31, 40, 255)     # #191F28
FG = (249, 250, 251, 255)  # #F9FAFB


def _load_font(size: int) -> ImageFont.ImageFont:
    candidates = [
        "arial.ttf",
        "arialbd.ttf",
        "C:\\Windows\\Fonts\\arialbd.ttf",
        "C:\\Windows\\Fonts\\arial.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVu-Sans-Bold.ttf",
    ]
    for c in candidates:
        try:
            return ImageFont.truetype(c, size)
        except Exception:
            continue
    return ImageFont.load_default()


def make_square(size: int, filename: str) -> None:
    img = Image.new("RGBA", (size, size), BG)
    draw = ImageDraw.Draw(img)
    font = _load_font(int(size * 0.42))
    text = "DB"
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    draw.text(
        ((size - tw) / 2 - bbox[0], (size - th) / 2 - bbox[1]),
        text,
        fill=FG,
        font=font,
    )
    path = OUT / filename
    img.save(path)
    print(f"wrote {path}")


if __name__ == "__main__":
    make_square(192, "icon-192.png")
    make_square(512, "icon-512.png")
    make_square(180, "apple-touch-icon.png")
