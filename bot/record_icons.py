"""Small game-style icons for the battle records image, drawn with Pillow so they never depend on a download:
Star Rail's orange stars and blue Starward star, Genshin's gold stars, ZZZ's round badges and S / A / B rating
plates, clock and gem marks, chess pieces and burning ranking badges. Each is drawn four times larger and scaled down for smooth edges."""

from __future__ import annotations

import math
from functools import lru_cache

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

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
    """ZZZ's round orange badge with a dark three-bladed mark (grey when not earned)."""
    b = size * SS
    img = Image.new("RGBA", (b, b), (0, 0, 0, 0))
    mask = Image.new("L", (b, b), 0)
    ImageDraw.Draw(mask).ellipse((SS, SS, b - SS, b - SS), fill=255)
    top, bottom, ink = ((255, 222, 70), (246, 128, 8), (70, 34, 0)) if lit else ((128, 128, 132), (82, 82, 88), (34, 34, 38))
    img.paste(Image.new("RGBA", (b, b), (16, 12, 8, 255)), (0, 0), mask)
    inner = mask.filter(ImageFilter.MinFilter(SS * 2 + 1 if size < 40 else SS * 3 + 1))
    img.paste(_gradient((b, b), top, bottom), (0, 0), inner)
    d = ImageDraw.Draw(img)
    c, r = b / 2, b * 0.3
    w = round(b * 0.07)
    d.ellipse((c - r, c - r, c + r, c + r), outline=ink + (255,), width=w)
    for k in range(3):  # three curved blades turning round the middle
        a0 = math.radians(-90 + 120 * k)
        pts = []
        for t in range(9):
            ang = a0 + t / 8 * math.radians(70)
            rad = b * (0.08 + 0.2 * t / 8)
            pts.append((c + rad * math.cos(ang), c + rad * math.sin(ang)))
        for t in range(8, -1, -1):
            ang = a0 + t / 8 * math.radians(70) + math.radians(28)
            rad = b * (0.08 + 0.2 * t / 8)
            pts.append((c + rad * math.cos(ang), c + rad * math.sin(ang)))
        d.polygon(pts, fill=ink + (255,))
    return img.resize((size, size), Image.LANCZOS)


CHESS_COLOURS = {"gold": ((255, 232, 150), (214, 150, 40)), "silver": ((236, 240, 252), (150, 160, 190)),
                 "bronze": ((236, 184, 140), (160, 96, 56))}


@lru_cache(maxsize=None)
def chess(height: int, kind: str) -> Image.Image:
    """A chess piece standing in for Anomaly Arbitration's rank piece, when HoYoLAB's own picture can't be had."""
    top, bottom = next((v for k, v in CHESS_COLOURS.items() if k in kind.lower()), ((206, 196, 255), (120, 100, 220)))
    w, h = round(height * 0.55) * SS, height * SS
    mask = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(mask)
    cx = w / 2
    d.polygon([(cx, 0), (cx + w * 0.16, h * 0.16), (cx, h * 0.3), (cx - w * 0.16, h * 0.16)], fill=255)  # the crest
    d.ellipse((cx - w * 0.2, h * 0.24, cx + w * 0.2, h * 0.46), fill=255)  # head
    d.polygon([(cx - w * 0.13, h * 0.42), (cx + w * 0.13, h * 0.42), (cx + w * 0.22, h * 0.78), (cx - w * 0.22, h * 0.78)], fill=255)
    d.rounded_rectangle((cx - w * 0.3, h * 0.48, cx + w * 0.3, h * 0.54), radius=w * 0.03, fill=255)  # collar
    d.rounded_rectangle((cx - w * 0.42, h * 0.78, cx + w * 0.42, h * 0.9), radius=w * 0.04, fill=255)  # base
    d.rounded_rectangle((cx - w * 0.48, h * 0.88, cx + w * 0.48, h - SS), radius=w * 0.04, fill=255)
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    img.paste(Image.new("RGBA", (w, h), (20, 16, 34, 255)), (0, 0), mask.filter(ImageFilter.MaxFilter(SS * 2 + 1)))
    img.paste(_gradient((w, h), top, bottom), (0, 0), mask)
    shine = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(shine).ellipse((cx - w * 0.1, h * 0.28, cx - w * 0.02, h * 0.38), fill=(255, 255, 255, 170))
    img.alpha_composite(shine)
    return img.resize((w // SS, height), Image.LANCZOS)


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


def _percent(text: str) -> float | None:
    try:
        return float(text.strip().rstrip("%"))
    except ValueError:
        return None


def _heat(percent: str) -> float:
    """Kept for callers that size things by the flame: the tail is part of the badge now, so nothing sticks out."""
    return 0.0


# Sampled from the in-game top-ranking badge Syphex shared: sky blue, periwinkle, pearl pink, white, mint, butter, peach
HOLO = ((150, 228, 248), (135, 212, 240), (149, 196, 253), (148, 160, 240), (222, 196, 220), (248, 240, 250), (255, 255, 255),
        (229, 255, 238), (255, 255, 204), (254, 214, 190), (232, 230, 196), (200, 244, 212))
GOLD = ((255, 240, 168), (252, 204, 72), (238, 160, 36), (252, 214, 96))


def _bands(size: tuple[int, int], stops, angle: float = 25) -> Image.Image:
    """A colour gradient through the stops, running diagonally across."""
    w, h = size
    strip = Image.new("RGB", (len(stops) * 64, 1))
    px = strip.load()
    for x in range(strip.width):
        t = x / (strip.width - 1) * (len(stops) - 1)
        i = min(int(t), len(stops) - 2)
        a, b = stops[i], stops[i + 1]
        px[x, 0] = tuple(round(a[k] + (b[k] - a[k]) * (t - i)) for k in range(3))
    lean = math.tan(math.radians(angle))  # the bands lean like "/" by this much
    span = w + round(h * abs(lean))
    grad = strip.resize((span, h), Image.BILINEAR)
    out = grad.transform((w, h), Image.AFFINE, (1, -lean, h * abs(lean), 0, 1, 0), Image.BILINEAR)
    return out.convert("RGBA")


def _curve(p0, p1, p2, steps: int = 12) -> list[tuple[float, float]]:
    """Points along a quadratic Bezier curve."""
    return [((1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t * t * p2[0],
             (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t * t * p2[1]) for t in (i / steps for i in range(steps + 1))]


def rank_badge(percent: str, height: int, font: ImageFont.FreeTypeFont) -> tuple[Image.Image, tuple[int, int]]:
    """The ranking as a badge whose right end burns out into a flame, like the game's own: a round left end, a nick
    in the top corner, a flame tongue licking right, a round bite under it and a hooked lower lip. Holographic for the
    top 1% and better, gold (with a smaller flame) otherwise. Returns the picture and where the badge's top left is."""
    p = _percent(percent)
    holo = p is not None and p <= 1
    f = font.font_variant(size=round(height * 0.76))
    pw = round(f.getlength(percent) + height * 0.85)  # the body holding the number
    k = 1.0 if holo else 0.72  # how far the flame reaches
    tail = round(height * 1.08 * k) + 2
    W, H = (pw + tail) * SS, height * SS
    X = pw * SS  # where the flame starts
    T = tail * SS
    mask = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(mask)
    d.ellipse((0, 0, H - 1, H - 1), fill=255)  # the round left end
    d.rectangle((H / 2, 0, X, H - 1), fill=255)
    u = H * k  # flame unit: the flame's shapes scale with it
    tip = (X + u * 1.05, H * 0.34)
    path = [(X, 0)]
    path += _curve((X, 0), (X + u * 0.1, H * 0.04), (X + u * 0.14, H * 0.28))  # the nick dipping into the top edge
    path += _curve((X + u * 0.14, H * 0.28), (X + u * 0.42, -H * 0.04), tip)  # the tongue's back, out to its tip
    path += _curve(tip, (X + u * 0.7, H * 0.52), (X + u * 0.44, H * 0.5))  # its underside, curling back
    path += [(X + u * 0.88, H * 0.74)]  # the lower lip's point
    path += _curve((X + u * 0.88, H * 0.74), (X + u * 0.6, H * 1.02), (X, H - 1))
    d.polygon(path, fill=255)
    r = H * 0.17  # the round bite between tongue and lip, open to the right
    c = (X + u * 0.4, H * 0.66)
    d.ellipse((c[0] - r, c[1] - r, c[0] + r, c[1] + r), fill=0)
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    fill = _bands((W, H), HOLO if holo else GOLD, 35 if holo else 20)
    if holo:  # a bright sheen across, like foil catching the light
        sheen = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(sheen).polygon([(W * 0.42, 0), (W * 0.62, 0), (W * 0.5, H), (W * 0.3, H)], fill=(255, 255, 255, 110))
        fill.alpha_composite(sheen.filter(ImageFilter.GaussianBlur(SS * 4)))
    img.paste(fill, (0, 0), mask)
    img = img.resize((pw + tail, height), Image.LANCZOS)
    ImageDraw.Draw(img).text((pw / 2 + height * 0.06, height / 2 + 1), percent, font=f, fill=(10, 8, 8, 255), anchor="mm")
    return img, (0, 0)


