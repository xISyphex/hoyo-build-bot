"""Small game-style icons for the battle records image, drawn with Pillow so they never depend on a download:
Star Rail's orange stars and blue Starward star, Genshin's gold stars, ZZZ's comic stars and S / A / B rating
plates, cycle and clock marks, and medals. Each is drawn four times larger and scaled down for smooth edges."""

from __future__ import annotations

import math
from functools import lru_cache

from PIL import Image, ImageDraw, ImageFilter, ImageFont

SS = 4  # supersampling


def _gradient(size: tuple[int, int], top, bottom) -> Image.Image:
    grad = Image.linear_gradient("L").resize(size)
    return Image.composite(Image.new("RGBA", size, bottom + (255,)), Image.new("RGBA", size, top + (255,)), grad)


def _star_points(cx, cy, r, points: int, inner: float, rot: float = -math.pi / 2):
    out = []
    for i in range(points * 2):
        a = rot + i * math.pi / points
        rad = r if i % 2 == 0 else r * inner
        out.append((cx + rad * math.cos(a), cy + rad * math.sin(a)))
    return out


def _shape(size: int, polygon, top, bottom, outline=None, outline_w: int = 0, glow=None) -> Image.Image:
    """A polygon filled with a top-to-bottom gradient, with an optional outline and soft glow."""
    big = size * SS
    mask = Image.new("L", (big, big), 0)
    ImageDraw.Draw(mask).polygon(polygon, fill=255)
    out = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    if glow:
        halo = Image.new("RGBA", (big, big), glow + (0,))
        halo.putalpha(mask.filter(ImageFilter.GaussianBlur(big * 0.08)).point(lambda v: v * 0.7))
        out.alpha_composite(halo)
    if outline:
        ring = mask.filter(ImageFilter.MaxFilter(outline_w * SS * 2 + 1))
        out.paste(Image.new("RGBA", (big, big), outline + (255,)), (0, 0), ring)
    out.paste(_gradient((big, big), top, bottom), (0, 0), mask)
    return out.resize((size, size), Image.LANCZOS)


@lru_cache(maxsize=None)
def hsr_star(size: int, lit: bool = True) -> Image.Image:
    """Star Rail's four-pointed orange star (dim grey when not earned)."""
    b = size * SS
    poly = _star_points(b / 2, b / 2, b * 0.47, 4, 0.42)
    if not lit:
        return _shape(size, poly, (92, 88, 104), (66, 62, 78))
    star = _shape(size, poly, (255, 226, 160), (246, 150, 52), glow=(255, 170, 60))
    shine = Image.new("RGBA", (b, b), (0, 0, 0, 0))  # a small bright core like HoYoLAB's
    ImageDraw.Draw(shine).polygon(_star_points(b / 2, b / 2, b * 0.16, 4, 0.4), fill=(255, 248, 228, 200))
    star.alpha_composite(shine.resize((size, size), Image.LANCZOS))
    return star


@lru_cache(maxsize=None)
def starward(size: int) -> Image.Image:
    """The Starward star: blue four-pointed star with a white rim and a white heart."""
    b = size * SS
    out = _shape(size, _star_points(b / 2, b / 2, b * 0.46, 4, 0.34), (170, 196, 255), (96, 104, 236),
                 outline=(236, 240, 255), outline_w=max(1, size // 22), glow=(130, 150, 255))
    core = Image.new("RGBA", (b, b), (0, 0, 0, 0))
    ImageDraw.Draw(core).polygon(_star_points(b / 2, b / 2, b * 0.2, 4, 0.3, rot=-math.pi / 4), fill=(255, 255, 255, 235))
    out.alpha_composite(core.resize((size, size), Image.LANCZOS))
    return out


@lru_cache(maxsize=None)
def gi_star(size: int, lit: bool = True) -> Image.Image:
    """Genshin's five-pointed gold star."""
    b = size * SS
    poly = _star_points(b / 2, b * 0.53, b * 0.47, 5, 0.46)
    if not lit:
        return _shape(size, poly, (92, 88, 104), (66, 62, 78))
    return _shape(size, poly, (255, 236, 168), (226, 160, 60), glow=(255, 196, 90))


@lru_cache(maxsize=None)
def zzz_star(size: int, lit: bool = True) -> Image.Image:
    """ZZZ's chunky comic star: yellow with a thick black rim."""
    b = size * SS
    poly = _star_points(b / 2, b * 0.54, b * 0.4, 5, 0.5)
    if not lit:
        return _shape(size, poly, (80, 80, 80), (60, 60, 60), outline=(10, 10, 10), outline_w=max(1, size // 10))
    return _shape(size, poly, (255, 236, 80), (250, 190, 20), outline=(10, 10, 10), outline_w=max(1, size // 10))


def star(game: str, size: int, lit: bool = True) -> Image.Image:
    return {"hsr": hsr_star, "genshin": gi_star, "zzz": zzz_star}[game](size, lit)


@lru_cache(maxsize=None)
def cycles(size: int, color: tuple[int, int, int]) -> Image.Image:
    """A circular arrow, for turns / cycles."""
    b = size * SS
    img = Image.new("RGBA", (b, b), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    w = round(b * 0.12)
    m = b * 0.14
    start, end = -40, 250  # degrees, clockwise from three o'clock; the gap sits at the top right
    d.arc((m, m, b - m, b - m), start, end, fill=color + (255,), width=w)
    r = (b - 2 * m) / 2 - w / 2
    a = math.radians(end)  # arrowhead at the arc's end, pointing on round the circle
    px, py = b / 2 + r * math.cos(a), b / 2 + r * math.sin(a)
    tx, ty = -math.sin(a), math.cos(a)  # along the arc
    nx, ny = math.cos(a), math.sin(a)  # out from the centre
    s = b * 0.2
    d.polygon([(px + tx * s * 1.1, py + ty * s * 1.1), (px + nx * s, py + ny * s), (px - nx * s, py - ny * s)],
              fill=color + (255,))
    return img.resize((size, size), Image.LANCZOS)


@lru_cache(maxsize=None)
def clock(size: int, color: tuple[int, int, int]) -> Image.Image:
    """A stopwatch, for clear times."""
    b = size * SS
    img = Image.new("RGBA", (b, b), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    w = round(b * 0.1)
    cx, cy, r = b / 2, b * 0.56, b * 0.38
    d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=color + (255,), width=w)
    d.rounded_rectangle((cx - b * 0.1, b * 0.04, cx + b * 0.1, b * 0.15), radius=w // 2, fill=color + (255,))
    d.line((cx, cy, cx, cy - r * 0.6), fill=color + (255,), width=w)
    d.line((cx, cy, cx + r * 0.45, cy), fill=color + (255,), width=w)
    return img.resize((size, size), Image.LANCZOS)


@lru_cache(maxsize=None)
def score(size: int, color: tuple[int, int, int]) -> Image.Image:
    """A faceted gem, for points."""
    b = size * SS
    img = Image.new("RGBA", (b, b), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    top, mid, bot = b * 0.18, b * 0.4, b * 0.88
    outer = [(b * 0.26, top), (b * 0.74, top), (b * 0.94, mid), (b / 2, bot), (b * 0.06, mid)]
    d.polygon(outer, fill=color + (255,))
    light = tuple(min(255, v + 70) for v in color)
    d.polygon([(b * 0.26, top), (b * 0.74, top), (b * 0.62, mid), (b * 0.38, mid)], fill=light + (255,))
    d.polygon([(b * 0.38, mid), (b * 0.62, mid), (b / 2, bot)], fill=tuple(max(0, v - 40) for v in color) + (255,))
    return img.resize((size, size), Image.LANCZOS)


MEDAL_COLOURS = {"gold": ((255, 226, 140), (214, 150, 40)), "silver": ((236, 240, 248), (150, 160, 180)),
                 "bronze": ((236, 176, 128), (160, 92, 50))}


@lru_cache(maxsize=None)
def medal(size: int, kind: str) -> Image.Image:
    """A round medal on a ribbon, gold / silver / bronze."""
    top, bottom = MEDAL_COLOURS.get(kind.lower(), MEDAL_COLOURS["bronze"])
    b = size * SS
    img = Image.new("RGBA", (b, b), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.polygon([(b * 0.28, 0), (b * 0.44, 0), (b * 0.56, b * 0.4), (b * 0.4, b * 0.4)], fill=(196, 64, 84, 255))
    d.polygon([(b * 0.56, 0), (b * 0.72, 0), (b * 0.6, b * 0.4), (b * 0.44, b * 0.4)], fill=(80, 96, 200, 255))
    r = b * 0.32
    cx, cy = b / 2, b * 0.64
    mask = Image.new("L", (b, b), 0)
    ImageDraw.Draw(mask).ellipse((cx - r, cy - r, cx + r, cy + r), fill=255)
    img.paste(_gradient((b, b), top, bottom), (0, 0), mask)
    d.ellipse((cx - r * 0.72, cy - r * 0.72, cx + r * 0.72, cy + r * 0.72), outline=bottom + (255,), width=round(b * 0.04))
    d.polygon(_star_points(cx, cy, r * 0.48, 5, 0.45), fill=top + (255,))
    return img.resize((size, size), Image.LANCZOS)


RATING_COLOURS = {"S+": ((255, 210, 70), (255, 120, 30)), "S": ((255, 210, 70), (255, 140, 30)),
                  "A": ((220, 120, 255), (140, 60, 230)), "B": ((90, 200, 255), (40, 120, 230))}


def rating(letter: str, height: int, font: ImageFont.FreeTypeFont) -> Image.Image:
    """ZZZ's rating plate: a slanted plate in the rating's colour with a black rim and the letter on it."""
    top, bottom = RATING_COLOURS.get(letter, ((180, 180, 180), (110, 110, 110)))
    width = round(height * (1.2 + 0.32 * (len(letter) - 1)))
    b = (width * SS, height * SS)
    slant = b[1] * 0.28
    poly = [(slant, 0), (b[0], 0), (b[0] - slant, b[1]), (0, b[1])]
    mask = Image.new("L", b, 0)
    ImageDraw.Draw(mask).polygon(poly, fill=255)
    img = Image.new("RGBA", b, (0, 0, 0, 0))
    img.paste(Image.new("RGBA", b, (12, 12, 12, 255)), (0, 0), mask)
    inner = mask.filter(ImageFilter.MinFilter(SS * 2 + 1 if height < 30 else SS * 3 + 1))
    img.paste(_gradient(b, top, bottom), (0, 0), inner)
    img = img.resize((width, height), Image.LANCZOS)
    big = font.font_variant(size=round(height * 0.86))
    layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    ld.text((width / 2 + 1, height / 2 + 2), letter, font=big, fill=(12, 12, 12, 255), anchor="mm",
            stroke_width=max(1, height // 12), stroke_fill=(12, 12, 12, 255))
    ld.text((width / 2, height / 2 + 1), letter, font=big, fill=(255, 255, 255, 255), anchor="mm")
    sheared = layer.transform(layer.size, Image.AFFINE, (1, 0.22, -0.11 * height, 0, 1, 0), Image.BICUBIC)
    img.alpha_composite(sheared)
    return img


def top_tag(text: str, height: int, font: ImageFont.FreeTypeFont, fill=(250, 196, 40)) -> Image.Image:
    """A ZZZ-style slanted tag for a ranking, e.g. 'TOP 4.21%'."""
    f = font.font_variant(size=round(height * 0.7))
    width = round(f.getlength(text) + height * 1.1)
    b = (width * SS, height * SS)
    slant = b[1] * 0.3
    img = Image.new("RGBA", b, (0, 0, 0, 0))
    ImageDraw.Draw(img).polygon([(slant, 0), (b[0], 0), (b[0] - slant, b[1]), (0, b[1])], fill=fill + (255,))
    img = img.resize((width, height), Image.LANCZOS)
    ImageDraw.Draw(img).text((width / 2, height / 2 + 1), text, font=f, fill=(12, 12, 12, 255), anchor="mm")
    return img
