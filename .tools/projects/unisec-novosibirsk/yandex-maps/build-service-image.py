from __future__ import annotations

import argparse
import html
import json
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps


CANVAS_SIZE = (1080, 1080)
FONT_PATH = Path(r"C:\Windows\Fonts\seguisb.ttf")


def xp(value: str) -> bytes:
    """Encode Windows XP EXIF fields with their required UTF-16LE terminator."""
    return value.encode("utf-16le") + b"\x00\x00"


def build_xmp(title: str, description: str, keywords: list[str]) -> bytes:
    title_xml = html.escape(title)
    description_xml = html.escape(description)
    subjects = "".join(
        f"<rdf:li>{html.escape(keyword)}</rdf:li>" for keyword in keywords
    )
    packet = f'''<?xpacket begin="\ufeff" id="W5M0MpCehiHzreSzNTczkc9d"?>
<x:xmpmeta xmlns:x="adobe:ns:meta/">
  <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
    <rdf:Description rdf:about=""
      xmlns:dc="http://purl.org/dc/elements/1.1/"
      xmlns:photoshop="http://ns.adobe.com/photoshop/1.0/">
      <dc:title><rdf:Alt><rdf:li xml:lang="x-default">{title_xml}</rdf:li></rdf:Alt></dc:title>
      <dc:description><rdf:Alt><rdf:li xml:lang="x-default">{description_xml}</rdf:li></rdf:Alt></dc:description>
      <dc:subject><rdf:Bag>{subjects}</rdf:Bag></dc:subject>
      <photoshop:Headline>{title_xml}</photoshop:Headline>
    </rdf:Description>
  </rdf:RDF>
</x:xmpmeta>
<?xpacket end="w"?>'''
    return packet.encode("utf-8")


def split_title(title: str) -> str:
    words = title.split()
    if len(words) == 2:
        return "\n".join(words)
    midpoint = (len(words) + 1) // 2
    return " ".join(words[:midpoint]) + "\n" + " ".join(words[midpoint:])


def fit_title(
    draw: ImageDraw.ImageDraw, title: str, max_width: int
) -> tuple[str, ImageFont.FreeTypeFont]:
    display_title = split_title(title)
    for size in range(96, 59, -2):
        font = ImageFont.truetype(str(FONT_PATH), size=size)
        box = draw.multiline_textbbox((0, 0), display_title, font=font, spacing=4)
        if box[2] - box[0] <= max_width and box[3] - box[1] <= 205:
            return display_title, font
    return display_title, ImageFont.truetype(str(FONT_PATH), size=60)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--title", required=True)
    parser.add_argument("--description", required=True)
    parser.add_argument("--keywords", required=True)
    args = parser.parse_args()

    keywords = [item.strip() for item in args.keywords.split(";") if item.strip()]
    args.output.parent.mkdir(parents=True, exist_ok=True)

    with Image.open(args.source) as source:
        canvas = ImageOps.fit(source.convert("RGB"), CANVAS_SIZE, method=Image.Resampling.LANCZOS)

    measure = ImageDraw.Draw(canvas)
    display_title, font = fit_title(measure, args.title, max_width=860)

    typography_band = Image.new("RGBA", CANVAS_SIZE, (0, 0, 0, 0))
    band_draw = ImageDraw.Draw(typography_band)
    band_top = 490
    band_bottom = 880
    fade = 85
    for y in range(band_top, band_bottom + 1):
        if y < band_top + fade:
            alpha = round(178 * (y - band_top) / fade)
        elif y > band_bottom - fade:
            alpha = round(178 * (band_bottom - y) / fade)
        else:
            alpha = 178
        band_draw.line((0, y, CANVAS_SIZE[0], y), fill=(4, 17, 21, alpha))
    canvas = Image.alpha_composite(canvas.convert("RGBA"), typography_band).convert("RGB")
    draw = ImageDraw.Draw(canvas)
    text_box = draw.multiline_textbbox(
        (0, 0), display_title, font=font, spacing=4, align="center"
    )
    text_width = text_box[2] - text_box[0]
    text_height = text_box[3] - text_box[1]
    text_x = (CANVAS_SIZE[0] - text_width) / 2 - text_box[0]
    text_y = 690 - text_height / 2 - text_box[1]
    draw.multiline_text(
        (text_x, text_y),
        display_title,
        font=font,
        fill=(255, 255, 255),
        spacing=4,
        align="center",
        stroke_width=0,
    )

    exif = canvas.getexif()
    exif[305] = "UNISEC Yandex Maps image builder"
    exif[306] = datetime.now().strftime("%Y:%m:%d %H:%M:%S")
    exif[315] = "UNISEC"
    exif[37510] = b"UNICODE\x00" + args.description.encode("utf-16le")
    exif[40091] = xp(args.title)
    exif[40092] = xp(args.description)
    exif[40093] = xp("UNISEC")
    exif[40094] = xp("; ".join(keywords))
    exif[40095] = xp(args.title)

    xmp = build_xmp(args.title, args.description, keywords)
    canvas.save(
        args.output,
        format="JPEG",
        quality=90,
        optimize=True,
        progressive=True,
        subsampling="4:2:0",
        exif=exif.tobytes(),
        xmp=xmp,
    )

    preview_dir = args.output.parent / "previews"
    preview_dir.mkdir(exist_ok=True)
    for size in (320, 180, 96):
        preview = canvas.resize((size, size), Image.Resampling.LANCZOS)
        preview.save(
            preview_dir / f"{args.output.stem}-{size}px.jpg",
            format="JPEG",
            quality=88,
            optimize=True,
        )
    desktop_preview = ImageOps.fit(
        canvas, (320, 180), method=Image.Resampling.LANCZOS, centering=(0.5, 0.5)
    )
    desktop_preview.save(
        preview_dir / f"{args.output.stem}-320x180.jpg",
        format="JPEG",
        quality=88,
        optimize=True,
    )
    carousel_preview = ImageOps.fit(
        canvas, (130, 96), method=Image.Resampling.LANCZOS, centering=(0.5, 0.5)
    )
    carousel_preview.save(
        preview_dir / f"{args.output.stem}-130x96.jpg",
        format="JPEG",
        quality=88,
        optimize=True,
    )

    metadata = {
        "title": args.title,
        "description": args.description,
        "keywords": keywords,
        "visible_text": display_title,
        "dimensions": list(CANVAS_SIZE),
        "format": "JPEG",
        "color_space": "sRGB",
        "metadata_embedded": ["EXIF", "XMP Dublin Core", "XMP Photoshop Headline"],
    }
    args.output.with_suffix(".metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    with Image.open(args.output) as check:
        assert check.size == CANVAS_SIZE
        assert args.title.encode("utf-8") in check.info["xmp"]
        assert check.getexif()[40091].decode("utf-16le").rstrip("\x00") == args.title

    print(args.output)


if __name__ == "__main__":
    main()
