"""Drawn images: lab photos (JPEG with EXIF capture date) and a pasted signature on a NOC page."""

import io
import random
from pathlib import Path

import fitz  # PyMuPDF
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from docverf.synthetic.model import Photo

SIZE = (1200, 900)
RENDER_DPI = 150


def _colour(rng: random.Random, low: int, high: int) -> tuple[int, int, int]:
    return rng.randint(low, high), rng.randint(low, high), rng.randint(low, high)


def draw_lab(photo: Photo) -> Image.Image:
    """A simple lab: sign with the room label, desks, and exactly `equipment_count` computers.

    Everything is drawn from `photo.seed`, so equal photos are byte-identical files."""
    rng = random.Random(photo.seed)
    width, height = SIZE
    wall = _colour(rng, 150, 235)
    horizon = rng.randint(330, 470)
    img = Image.new("RGB", SIZE, wall)
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, horizon, width, height], fill=_colour(rng, 70, 150))  # floor
    draw.rectangle([0, 0, width, 55], fill=_colour(rng, 215, 245))  # ceiling strip
    for _ in range(rng.randint(2, 4)):  # ceiling lights
        x = rng.randint(40, width - 240)
        draw.rectangle([x, 12, x + 190, 36], fill=(255, 255, 240))
    wx = rng.randint(width // 2, width - 330)  # window
    draw.rectangle([wx, 100, wx + 260, 100 + rng.randint(140, 200)], fill=_colour(rng, 150, 220))
    draw.rectangle([40, 190, 40 + rng.randint(260, 360), 190 + 110], fill=(245, 245, 245))  # board
    for _ in range(rng.randint(3, 5)):  # cabinets, posters, panels: large light or dark blocks
        bw, bh = rng.randint(150, 450), rng.randint(120, 350)
        bx, by = rng.randint(0, width - bw), rng.randint(60, horizon)
        shade = rng.choice([rng.randint(20, 70), rng.randint(215, 250)])
        draw.rectangle([bx, by, bx + bw, by + bh], fill=(shade, shade, min(shade + 15, 255)))
    draw.rectangle([30, 75, 520, 150], fill=_colour(rng, 20, 90))  # sign plate
    draw.text(
        (50, 88), photo.room_label, fill=(255, 255, 255), font=ImageFont.load_default(size=44)
    )

    count = photo.equipment_count
    rows = 2 if count <= 12 else 3
    per_row = [count // rows + (1 if r < count % rows else 0) for r in range(rows)]
    band = (height - horizon - 60) / rows
    for r, n in enumerate(per_row):
        scale = 0.8 + 0.22 * r  # nearer rows are bigger
        desk_y = int(horizon + 40 + band * r + band * 0.45)
        desk = _colour(rng, 110, 170)
        draw.rectangle([30, desk_y, width - 30, desk_y + int(26 * scale)], fill=desk)
        slot = (width - 120) / n
        for i in range(n):
            cx = int(60 + slot * (i + 0.5) + rng.randint(-8, 8))
            w, h = int(rng.randint(62, 88) * scale), int(rng.randint(46, 64) * scale)
            draw.ellipse([cx - 22, desk_y + 24, cx + 22, desk_y + 70], fill=_colour(rng, 30, 90))
            draw.rectangle([cx - w // 2, desk_y - h, cx + w // 2, desk_y - 4], fill=(28, 28, 34))
            screen = [cx - w // 2 + 5, desk_y - h + 5, cx + w // 2 - 5, desk_y - 12]
            draw.rectangle(screen, fill=_colour(rng, 40, 255))
            draw.rectangle([cx - 8, desk_y - 4, cx + 8, desk_y + 2], fill=(60, 60, 60))  # stand
            draw.rectangle(
                [cx - w // 3, desk_y + 4, cx + w // 3, desk_y + 12], fill=(225, 225, 225)
            )

    img = img.filter(ImageFilter.GaussianBlur(0.7))
    noise = np.random.default_rng(photo.seed)
    # a brightness ramp in a random direction (uneven lighting), plus grain
    angle, strength = rng.uniform(0, 6.28), rng.uniform(25, 60)
    yy, xx = np.mgrid[0:height, 0:width]
    ramp = strength * (np.cos(angle) * (xx / width - 0.5) + np.sin(angle) * (yy / height - 0.5))
    lit = (
        np.asarray(img).astype(np.float32)
        + ramp[..., None]
        + noise.normal(0, 7, (height, width, 3))
    )
    pixels = np.clip(lit, 0, 255).astype(np.uint8)
    return Image.fromarray(pixels)  # grain keeps the Laplacian variance above BLUR_THRESHOLD


def save_lab_photo(photo: Photo, path: Path) -> None:
    taken = f"{photo.capture_date:%Y:%m:%d} 10:{photo.seed % 50 + 5:02d}:00"
    exif = Image.Exif()
    exif[0x0132] = taken  # DateTime
    exif[0x8769] = {0x9003: taken, 0x9004: taken}  # DateTimeOriginal / DateTimeDigitized
    draw_lab(photo).save(path, "JPEG", quality=88, exif=exif)


def signature_image(seed: int, width: int = 420) -> Image.Image:
    """A handwritten-looking signature (RGBA), drawn at 3x and shrunk for smooth edges."""
    rng = random.Random(seed)
    scale, w, h = 3, width, width * 2 // 5
    img = Image.new("RGBA", (w * scale, h * scale), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    ink = (20 + rng.randint(0, 20), 30 + rng.randint(0, 20), 100 + rng.randint(0, 50), 255)
    for stroke in range(rng.randint(2, 3)):
        phase, amp, freq = rng.uniform(0, 6.28), rng.randint(18, 40), rng.uniform(0.02, 0.05)
        y0 = h * scale * (0.35 + 0.12 * stroke)
        points = [
            (x, y0 + amp * scale * np.sin(freq * x / scale * 3 + phase) + rng.randint(-5, 5))
            for x in range(int(w * scale * 0.05), int(w * scale * 0.95), 6)
        ]
        draw.line(points, fill=ink, width=5 * scale // 2, joint="curve")
    underline = [(w * scale * 0.1, h * scale * 0.85), (w * scale * 0.9, h * scale * 0.78)]
    draw.line(underline, fill=ink, width=4 * scale // 2)
    return img.resize((w, h), Image.Resampling.LANCZOS)


def paste_signature_pdf(source_pdf: Path, out_pdf: Path, seed: int) -> list[float]:
    """Rasterise page 1 of the NOC, paste a signature image above the officer caption, save as PDF.

    The page goes through a lossy JPEG first and the signature arrives from a separate image, so
    the pasted region has a different compression history (what ELA / noise analysis look for).
    Returns the pasted region as a normalised [x1, y1, x2, y2] box (TRD §5.2 BBox)."""
    with fitz.open(str(source_pdf)) as doc:
        page = doc[0]
        pix = page.get_pixmap(dpi=RENDER_DPI)
        page_rect = page.rect
        anchors = page.search_for("Authorised Officer")
    base = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    buffer = io.BytesIO()
    base.save(buffer, "JPEG", quality=70)
    base = Image.open(io.BytesIO(buffer.getvalue())).convert("RGB")

    sig = signature_image(seed, width=int(pix.width * 0.26))
    k = RENDER_DPI / 72
    if anchors:
        x, y = int(anchors[-1].x0 * k), int(anchors[-1].y0 * k) - sig.height - 6
    else:
        x, y = int(pix.width * 0.6), int(pix.height * 0.8)
    x, y = max(x, 0), max(y, 0)
    base.paste(sig, (x, y), sig)
    bbox = [
        round(v, 3)
        for v in (
            x / pix.width,
            y / pix.height,
            (x + sig.width) / pix.width,
            (y + sig.height) / pix.height,
        )
    ]

    buffer = io.BytesIO()
    base.save(buffer, "JPEG", quality=92)
    with fitz.open() as out:
        out.new_page(width=page_rect.width, height=page_rect.height).insert_image(
            page_rect, stream=buffer.getvalue()
        )
        out.save(str(out_pdf))
    return bbox
