"""The build card: one image with the character art, stats, gear and weapon.

Pictures are downloaded once, shrunk, and kept on disk, so a card only needs
network access the first time a character or item shows up. Drawing runs in a
worker thread and takes a fraction of a second, even on a small VM.
"""

from __future__ import annotations

import asyncio
import hashlib
import io
import json
import logging
import math
import os
import random
from pathlib import Path

import aiohttp
from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter, ImageFont

from .effective import EffectiveStats, piece_count
from .face import find_face
from .embeds import ELEMENT_COLORS, GAME_LABELS, ZZZ_RARITY, _is_zero, _name
from . import stat_icons
from .models import CharacterBuild, Gear, PlayerProfile

log = logging.getLogger("hoyo-bot")

W, H = 1200, 720
ART_W = 400  # left column: character art, name and weapon
STATS_X, STATS_W = 420, 284
FADE_X = 300  # the art starts fading here and is gone by STATS_X
GEAR_X = 722
PAD = 24
FONT_DIR = Path(__file__).parent / "fonts"
TEXT = (238, 236, 246)
DIM = (176, 172, 196)
GOLD = (255, 209, 102)
TEAL = (94, 234, 212)  # Crit Value (or Speed Value)
EFFECTIVE = GOLD  # the effective substat count, and the substats it counts
PANEL = (255, 255, 255, 14)
LINE = (255, 255, 255, 22)
ART_MAX = 1100  # art is kept at most this tall
FULL_ART_MAX = 2600  # except ZZZ's, which the head close-up enlarges: kept at full size
ICON_MAX = 192
MINDSCAPE_H = 150  # ZZZ: the Mindscape picture's panel, bottom left where other games show the weapon
FACE_SIZE = 240  # ZZZ art is scaled so the face is this big
FACE_X, FACE_Y = 210, 380  # and its centre lands here


FONT_FILES = {"Regular": "Rajdhani-Medium.ttf", "SemiBold": "Rajdhani-SemiBold.ttf", "Bold": "Rajdhani-Bold.ttf"}
FONT_SCALE = 1.16  # Rajdhani is drawn small for its size; this matches the layout's sizes


def _font(weight: str, size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(str(FONT_DIR / FONT_FILES[weight]), round(size * FONT_SCALE))
    except OSError:
        return ImageFont.load_default(size)


class Fonts:
    def __init__(self) -> None:
        self.name = {s: _font("Bold", s) for s in (56, 50, 44, 38, 32)}
        self.meta = _font("SemiBold", 22)
        self.stat = _font("Regular", 24)
        self.stat_b = _font("Bold", 24)
        self.stat_s = _font("Regular", 20)
        self.small = _font("Regular", 18)
        self.small_b = _font("Bold", 18)
        self.slot = _font("Regular", 17)
        self.slot_b = _font("Bold", 14)
        self.count = _font("Bold", 14)
        self.main = _font("Bold", 24)
        self.sub = _font("Regular", 18)
        self.sub_b = _font("SemiBold", 18)
        self.wname = _font("Bold", 21)
        self.stamp = _font("Regular", 14)
        self.label = _font("Bold", 13)


FONTS: Fonts | None = None


def _accent(build: CharacterBuild) -> tuple[int, int, int]:
    color = ELEMENT_COLORS.get(build.element, GAME_LABELS[build.game]["color"])
    return (color >> 16 & 255, color >> 8 & 255, color & 255)


def _mix(a, b, t: float) -> tuple[int, int, int]:
    return tuple(round(x + (y - x) * t) for x, y in zip(a, b))


def _background(accent) -> Image.Image:
    """Dark backdrop with a soft glow of the element color behind the art."""
    small = Image.new("RGB", (W // 8, H // 8))
    px = small.load()
    dark, deep = (14, 12, 24), _mix((14, 12, 24), accent, 0.38)
    cx, cy = small.width * 0.16, small.height * 0.42
    for y in range(small.height):
        for x in range(small.width):
            d = math.hypot((x - cx) / small.width, (y - cy) / small.height)
            px[x, y] = _mix(deep, dark, min(d / 0.75, 1))
    return small.resize((W, H), Image.BILINEAR).convert("RGBA")


def mindscape_urls(build: CharacterBuild) -> tuple[str | None, str | None, int]:
    """ZZZ: the agent's Mindscape Cinema pictures for their Mindscape level: the picture shown, the next one, and
    how many thirds of the next one show over it. M0 the 1st, M1-2 a third / two thirds of the 2nd over it, M3 the
    2nd, M4-5 thirds of the 3rd, M6 the 3rd."""
    if build.game != "zzz" or not str(build.character_id).isdigit():
        return None, None, 0
    level = min(max(build.constellation, 0), 6)
    base, thirds = (3, 0) if level == 6 else (level // 3 + 1, level % 3)
    url = f"https://enka.network/ui/zzz/Mindscape_{build.character_id}_{{}}.png"
    return url.format(base), url.format(base + 1) if thirds else None, thirds


# Mindscape level colours, coolest to hottest like a flame's temperature: red, orange, yellow, white, blue; used for
# the M1-M6 tab beside the picture
MINDSCAPE_COLORS = {1: (232, 48, 32), 2: (255, 122, 24), 3: (255, 206, 52), 4: (255, 244, 226), 5: (150, 205, 255),
                    6: (70, 130, 255)}
TAB_W = 44  # ZZZ: the Mindscape bar's strip at the left of the picture at the left of the Mindscape picture
CHAMFER = 7  # the cut corners of the arcade screen


def _mindscape_bar(screen: Image.Image, level: int) -> None:
    """The strip over the left of the picture, frosted and darkened, holding a caution-style meter: one tall chamfered
    gauge filling from the bottom with diagonal hazard stripes in the level's colour, tick marks between the six
    levels, and a plate with the level under it."""
    h = screen.height
    stub = screen.crop((0, 0, TAB_W, h)).filter(ImageFilter.GaussianBlur(4))
    stub.alpha_composite(Image.new("RGBA", (TAB_W, h), (10, 8, 20, 200)))
    color = MINDSCAPE_COLORS.get(min(level, 6), (96, 92, 116)) if level else (96, 92, 116)
    rim = (200, 196, 220, 255)
    k = 4  # drawn at 4x and shrunk, for smooth slants
    layer = Image.new("RGBA", (TAB_W * k, h * k), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    x0, x1, top, bottom, c = 10, TAB_W - 11, 8, h - 34, 4
    frame = [(x0 + c, top), (x1, top), (x1, bottom - c), (x1 - c, bottom), (x0, bottom), (x0, top + c)]
    draw.polygon([(x * k, y * k) for x, y in frame], fill=(18, 14, 28, 255), outline=rim, width=k * 2)
    inner = ((x0 + 3) * k, (top + 3) * k, (x1 - 3) * k, (bottom - 3) * k)
    step = (bottom - top - 6) / 6
    if level:
        fill_top = (bottom - 3 - step * min(level, 6)) * k
        stripes = Image.new("RGBA", layer.size, color + (255,))
        dark = _mix(color, (0, 0, 0), 0.55) + (255,)
        sd = ImageDraw.Draw(stripes)
        span = (x1 - x0) * k
        for y in range(int(fill_top) - span, inner[3] + span, 8 * k):  # stripes rising to the right
            sd.polygon([(inner[0], y + 4 * k), (inner[0], y + 8 * k), (inner[2], y + 8 * k - span),
                        (inner[2], y + 4 * k - span)], fill=dark)
        cut = Image.new("L", layer.size, 0)
        ImageDraw.Draw(cut).rectangle((inner[0], fill_top, inner[2], inner[3]), fill=255)
        layer.paste(stripes, (0, 0), cut)
    for n in range(1, 6):  # tick marks between the levels
        y = (bottom - 3 - step * n) * k
        draw.rectangle(((x0 - 4) * k, y - k // 2, (x0 - 1) * k, y + k // 2), fill=rim)
        draw.rectangle(((x1 + 1) * k, y - k // 2, (x1 + 4) * k, y + k // 2), fill=rim)
    plate = (7 * k, (h - 28) * k, (TAB_W - 8) * k, (h - 8) * k)
    draw.rectangle(plate, fill=color + (255,) if level else (60, 56, 76, 255))
    draw.text(((plate[0] + plate[2]) / 2, (plate[1] + plate[3]) / 2), f"M{level}", font=_font("Bold", 16 * k),
              fill=(14, 10, 22, 255), anchor="mm")
    stub.alpha_composite(layer.resize((TAB_W, h), Image.LANCZOS))
    screen.paste(stub, (0, 0))


# Background behind each Mindscape picture (Syphex): M0 the card's dark panel, M3 black, M6 white
V_HALF = 0.4  # half the first slice's width at its wide end, as a share of the panel height
# Where each agent's face is in their Mindscape pictures (the 2nd and 3rd are drawn alike), as shares of the
# picture's width and height, read off the pictures by eye; the first slice opens around it
MINDSCAPE_FACES = {
    1011: (0.43, 0.27), 1021: (0.52, 0.33), 1031: (0.52, 0.37), 1041: (0.58, 0.38), 1061: (0.48, 0.45),
    1071: (0.33, 0.44), 1091: (0.54, 0.45), 1101: (0.5, 0.3), 1111: (0.49, 0.22), 1121: (0.38, 0.37),
    1131: (0.54, 0.55), 1141: (0.79, 0.28), 1151: (0.42, 0.33), 1161: (0.62, 0.3), 1181: (0.71, 0.41),
    1191: (0.71, 0.28), 1201: (0.19, 0.31), 1211: (0.6, 0.31), 1221: (0.64, 0.28), 1241: (0.6, 0.33),
    1251: (0.56, 0.33), 1261: (0.58, 0.26), 1271: (0.38, 0.22), 1281: (0.56, 0.37), 1291: (0.62, 0.3),
    1311: (0.52, 0.33), 1321: (0.31, 0.26), 1331: (0.44, 0.33), 1351: (0.71, 0.31), 1361: (0.56, 0.35),
    1371: (0.34, 0.37), 1381: (0.56, 0.48), 1391: (0.29, 0.28), 1401: (0.45, 0.3), 1411: (0.49, 0.54),
    1421: (0.6, 0.26), 1431: (0.3, 0.35), 1441: (0.6, 0.26), 1451: (0.22, 0.5), 1461: (0.62, 0.28),
    1481: (0.51, 0.31), 1491: (0.47, 0.33), 1501: (0.48, 0.41), 1511: (0.44, 0.37), 1521: (0.53, 0.41),
    1531: (0.53, 0.15), 1541: (0.81, 0.33), 1561: (0.35, 0.22), 1571: (0.45, 0.31), 1581: (0.47, 0.3),
    1591: (0.6, 0.31), 1611: (0.45, 0.33), 1621: (0.34, 0.35), 1631: (0.71, 0.31), 1641: (0.22, 0.39),
}
MINDSCAPE_BG = {1: (8, 6, 16, 200), 2: (0, 0, 0, 255), 3: (255, 255, 255, 255)}


def _content(pictures: list[Image.Image]) -> tuple[int, int, int, int] | None:
    """The part of the pictures that isn't see-through (they share one layout)."""
    boxes = [p.getchannel("A").point(lambda a: 255 if a > 40 else 0).getbbox() for p in pictures]
    boxes = [b for b in boxes if b]
    if not boxes:
        return None
    return min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes)


def _mindscape_panel(card: Image.Image, picture: Image.Image | None, box, level: int = 0,
                     upcoming: Image.Image | None = None, thirds: int = 0,
                     face: tuple[float, float] | None = None) -> None:
    """ZZZ: an arcade screen: the Mindscape bar at the left, the Mindscape Cinema picture beside it with scanlines, the
    next picture taking over a part per copy."""
    tx0, y0, x1, y1 = box
    tw, h = x1 - tx0, y1 - y0
    base = 3 if level >= 6 else max(level, 0) // 3 + 1  # which of the three pictures is shown
    screen = Image.new("RGBA", (tw, h), MINDSCAPE_BG[base])  # the picture runs under the bar too
    if picture is not None:
        _mindscape_picture(screen, picture, level, base, upcoming, thirds, face)
    for y in range(0, h, 3):  # CRT scanlines over the picture
        screen.alpha_composite(Image.new("RGBA", (tw - TAB_W, 1), (0, 0, 0, 32)), (TAB_W, y))
    _mindscape_bar(screen, level)
    # an arcade screen: corners cut like pixel art, a dark bezel with a neon trim in the level's colour, and the same
    # bezel between the bar and the picture
    c = CHAMFER
    outline = [(c, 0), (tw - 1 - c, 0), (tw - 1, c), (tw - 1, h - 1 - c), (tw - 1 - c, h - 1), (c, h - 1),
               (0, h - 1 - c), (0, c)]
    mask = Image.new("L", (tw * 4, h * 4), 0)
    ImageDraw.Draw(mask).polygon([(x * 4, y * 4) for x, y in outline], fill=255)
    mask = mask.resize((tw, h), Image.LANCZOS)
    screen.putalpha(ImageChops.multiply(screen.getchannel("A"), mask))
    neon = MINDSCAPE_COLORS.get(min(level, 6), (120, 116, 140))
    draw = ImageDraw.Draw(screen)
    draw.line(outline + [outline[0]], fill=(14, 10, 24, 255), width=5)
    draw.rectangle((TAB_W - 2, 0, TAB_W + 1, h), fill=(14, 10, 24, 255))
    inset = [(c + 1, 3), (tw - 4 - c + 2, 3), (tw - 4, c + 1), (tw - 4, h - 4 - c + 2), (tw - 4 - c + 2, h - 4),
             (c + 1, h - 4), (3, h - 4 - c + 2), (3, c + 1)]
    draw.line(inset + [inset[0]], fill=neon + (230,), width=1)
    draw.line([(TAB_W, 3), (TAB_W, h - 4)], fill=neon + (230,), width=1)
    card.alpha_composite(screen, (tx0, y0))


def _mindscape_picture(tile: Image.Image, picture: Image.Image, level: int, base: int,
                       upcoming: Image.Image | None, thirds: int, face: tuple[float, float] | None) -> None:
    """The Mindscape picture filling the tile, with the next one's slice over it."""
    w, h = tile.size
    picture = picture.convert("RGBA")
    nxt = upcoming.convert("RGBA") if upcoming is not None and thirds else None
    # the pictures have see-through margins; only their drawn part is zoomed to fill the panel
    pw, ph = picture.size
    area = _content([picture] + ([nxt.resize((pw, ph))] if nxt else [])) or (0, 0, pw, ph)
    if area[2] - area[0] < pw // 4 or area[3] - area[1] < ph // 4:  # nearly empty: keep the whole picture
        area = (0, 0, pw, ph)

    def fill(pic: Image.Image) -> Image.Image:
        k = pic.width / pw
        pic = pic.crop(tuple(round(v * k) for v in area))
        scale = max(w / pic.width, h / pic.height)
        pic = pic.resize((round(pic.width * scale), round(pic.height * scale)), Image.LANCZOS)
        left, top = (pic.width - w) // 2, (pic.height - h) // 2
        return pic.crop((left, top, left + w, top + h))

    tile.alpha_composite(fill(picture))
    # Like the game's Mindscape Cinema, each copy uncovers a part of the next picture: first a slice shaped like a
    # stretched V lying on its side, its wide end on the agent's face, then everything above it, then (the next level)
    # the rest
    if nxt is not None:
        aw, ah = area[2] - area[0], area[3] - area[1]
        scale = max(w / aw, h / ah)
        fx, fy = (face[0] * pw, face[1] * ph) if face else (area[0], area[1] + 0.7 * ah)  # unknown: wide end at left
        fx = (fx - area[0]) * scale - (aw * scale - w) / 2
        fy = (fy - area[1]) * scale - (ah * scale - h) / 2
        right = fx > w / 2
        # the V's point is in the corner diagonally across from the face, and its middle line runs through the face
        tip = (0 if right else w, -h * 0.02 if fy > h / 2 else h * 1.02)
        end = w if right else 0
        mid = tip[1] + (fy - tip[1]) * (end - tip[0]) / ((fx - tip[0]) or 1)
        mid = min(max(mid, -h * 0.1), h * 1.1)
        upper, lower = (end, mid - h * V_HALF), (end, mid + h * V_HALF)
        sides = (lower, tip) if right else (tip, lower)  # the points on the right edge, then the left
        region = (tip, upper, lower) if thirds == 1 else ((0, -h), (w, -h)) + sides
        cut = Image.new("L", (w * 4, h * 4), 0)
        ImageDraw.Draw(cut).polygon([(x * 4, y * 4) for x, y in region], fill=255)
        cut = cut.resize((w, h), Image.LANCZOS)
        tile.paste(Image.new("RGBA", (w, h), MINDSCAPE_BG[base + 1]), (0, 0), cut)  # the next picture's background
        over = fill(nxt)
        over.putalpha(ImageChops.multiply(over.getchannel("A"), cut))
        tile.alpha_composite(over)


def _fit_text(draw: ImageDraw.ImageDraw, text: str, font, width: int) -> str:
    if draw.textlength(text, font=font) <= width:
        return text
    while text and draw.textlength(text + "…", font=font) > width:
        text = text[:-1]
    return text.rstrip() + "…"


def _wrap(draw: ImageDraw.ImageDraw, text: str, font, width: int, lines: int, sep: str = " ") -> list[str]:
    out, current = [], ""
    for word in text.split(sep):
        trial = f"{current}{sep}{word}" if current else word
        if draw.textlength(trial, font=font) <= width or not current:
            current = trial
        else:
            out.append(current)
            current = word
    out.append(current)
    if len(out) > lines:
        out = out[: lines - 1] + [_fit_text(draw, sep.join(out[lines - 1 :]), font, width)]
    return out


def _star(draw: ImageDraw.ImageDraw, cx: float, cy: float, r: float, fill) -> None:
    points = []
    for i in range(10):
        angle = -math.pi / 2 + i * math.pi / 5
        rad = r if i % 2 == 0 else r * 0.45
        points.append((cx + rad * math.cos(angle), cy + rad * math.sin(angle)))
    draw.polygon(points, fill=fill)


def _rarity_width(draw, build: CharacterBuild, f) -> float:
    if build.game == "zzz":
        return draw.textlength(f"{ZZZ_RARITY.get(build.rarity, '?')}-Rank", font=f.meta)
    return build.rarity * 22 - 2


def _draw_rarity(draw, build: CharacterBuild, f, x: float, cy: float) -> None:
    if build.game == "zzz":
        draw.text((x, cy), f"{ZZZ_RARITY.get(build.rarity, '?')}-Rank", font=f.meta, fill=GOLD, anchor="lm")
    else:
        for i in range(build.rarity):
            _star(draw, x + 10 + i * 22, cy, 10, GOLD)


def _info_row(card: Image.Image, build: CharacterBuild, f, accent, light, y: int,
              element: Image.Image | None = None, path: Image.Image | None = None) -> None:
    """Element and path / specialty / weapon type symbols, level and rarity under the name, on a see-through
    backing so they read on any art. Without an element symbol the element's name is written instead."""
    draw = ImageDraw.Draw(card)
    if element is None and build.game == "genshin" and build.element == "Cryo":
        element = _tinted(_snowflake(), light)
    h = 38
    symbols = []
    for icon, is_path in ((element, False), (path, True)):
        if icon is not None:  # in its own colours, the grey weapon type icons a little brighter
            icon = icon.convert("RGBA")
            if is_path and build.game == "genshin":
                icon = Image.merge("RGBA", (*ImageEnhance.Brightness(icon.convert("RGB")).enhance(1.5).split(), icon.getchannel("A")))
            icon = icon.crop(icon.getchannel("A").getbbox() or (0, 0, icon.width, icon.height))
            scale = (h - 8) / max(icon.size)
            symbols.append(icon.resize((max(1, round(icon.width * scale)), max(1, round(icon.height * scale))), Image.LANCZOS))
    el = build.element.upper() if element is None else ""
    ew = draw.textlength(el, font=f.meta) + sum(s.width for s in symbols) + 8 * (len(symbols) - (not el))
    lv = f"Lv. {build.level}"
    lw = draw.textlength(lv, font=f.meta)
    rw = _rarity_width(draw, build, f)
    x0 = PAD + 4
    cy = y + h / 2
    dark = (12, 10, 20)
    # a slanted dark band with an element-coloured edge
    total = 18 + ew + 22 + lw + 22 + rw + 30
    band = Image.new("RGBA", card.size, (0, 0, 0, 0))
    bd = ImageDraw.Draw(band)
    sl = 14
    bd.polygon([(x0 - 8, y), (x0 + total + sl, y), (x0 + total, y + h), (x0 - 8, y + h)], fill=dark + (175,))
    bd.polygon([(x0 - 8, y), (x0 + 2, y), (x0 + 2, y + h), (x0 - 8, y + h)], fill=accent + (255,))
    bd.line((x0 - 8, y + h, x0 + total, y + h), fill=accent + (255,), width=2)
    _layer_onto(card, band)
    draw = ImageDraw.Draw(card)
    x = x0 + 16
    sx = x
    if el:
        draw.text((sx, cy), el, font=f.meta, fill=light, anchor="lm")
        sx += draw.textlength(el, font=f.meta) + 8
    for sym in symbols:
        card.alpha_composite(sym, (round(sx), round(cy - sym.height / 2)))
        sx += sym.width + 8
    x += ew
    x += 11
    _sparkle(draw, x, cy, 5, accent + (255,), 0.3)
    x += 11
    draw.text((x, cy), lv, font=f.meta, fill=TEXT, anchor="lm")
    x += lw
    x += 11
    _sparkle(draw, x, cy, 5, accent + (255,), 0.3)
    _draw_rarity(draw, build, f, x + 11, cy)


def _paste_art(card: Image.Image, art: Image.Image | None, face: tuple[float, float, float] | None = None) -> None:
    """Character art across the left column, fading out to the right before the stats box, so wide art (wings,
    weapons) never shows through it.

    face (ZZZ): the face's centre and size in the picture; every agent is scaled to the same face size and lined up
    on it, so each card shows the same head close-up whatever the picture's framing.
    """
    if art is None:
        return
    art = art.convert("RGBA")
    width = ART_W + 140
    if face:
        fx, fy, size = face
        k = size / FACE_SIZE  # picture pixels per card pixel
        left, top = fx - FACE_X * k, fy - FACE_Y * k
        # outside the picture comes out transparent
        art = art.crop((round(left), round(top), round(left + width * k), round(top + H * k))).resize((width, H), Image.LANCZOS)
        if k < 1:  # enlarged: a light sharpen keeps the line art crisp
            art = art.filter(ImageFilter.UnsharpMask(radius=1.2, percent=60, threshold=2))
    else:
        scale = (H + 60) / art.height
        if art.width * scale < width:
            scale = width / art.width
        art = art.resize((round(art.width * scale), round(art.height * scale)), Image.LANCZOS)
        left = max((art.width - width) // 2, 0)
        top = max((art.height - H) // 3, 0)
        art = art.crop((left, top, left + width, top + H))
    fade = Image.new("L", (width, 1))
    for x in range(width):
        fade.putpixel((x, 0), 255 if x < FADE_X else round(255 * max(0, 1 - (x - FADE_X) / (STATS_X - FADE_X))))
    art.putalpha(ImageChops.multiply(art.getchannel("A"), fade.resize(art.size)))
    card.alpha_composite(art, (0, 0))


def _shade(card: Image.Image, box, top_alpha: int, bottom_alpha: int) -> None:
    x0, y0, x1, y1 = box
    grad = Image.new("L", (1, y1 - y0))
    for y in range(y1 - y0):
        grad.putpixel((0, y), round(top_alpha + (bottom_alpha - top_alpha) * y / max(y1 - y0 - 1, 1)))
    layer = Image.new("RGBA", (x1 - x0, y1 - y0), (10, 8, 18, 255))
    layer.putalpha(grad.resize(layer.size))
    card.alpha_composite(layer, (x0, y0))


def _spaced(draw: ImageDraw.ImageDraw, xy, text: str, font, fill, spacing: float = 2.2, anchor: str = "lm") -> None:
    """Small caps label with letter spacing (Pillow has no tracking option)."""
    x, y = xy
    for ch in text:
        draw.text((x, y), ch, font=font, fill=fill, anchor=anchor)
        x += draw.textlength(ch, font=font) + spacing


def _layer_onto(card: Image.Image, layer: Image.Image) -> None:
    """Puts a card-sized drawing layer onto the card, blending only the part that has something drawn on it
    (blending the whole card for a small shape is most of the drawing time)."""
    box = layer.getbbox()
    if box:
        card.alpha_composite(layer.crop(box), box[:2])


def _panel(card: Image.Image, box, radius: int = 16, fill=PANEL) -> None:
    layer = Image.new("RGBA", card.size, (0, 0, 0, 0))
    ImageDraw.Draw(layer).rounded_rectangle(box, radius, fill=fill, outline=(255, 255, 255, 20))
    _layer_onto(card, layer)


def _icon(card: Image.Image, img: Image.Image | None, box) -> None:
    if img is None:
        return
    x0, y0, x1, y1 = box
    img = img.convert("RGBA")
    img.thumbnail((x1 - x0, y1 - y0), Image.LANCZOS)
    card.alpha_composite(img, (x0 + (x1 - x0 - img.width) // 2, y0 + (y1 - y0 - img.height) // 2))


def crit_value(build: CharacterBuild) -> float | None:
    """CRIT DMG + CRIT Rate × 2 over all gear: main stats (like a crit body or circlet) and substats."""
    total, seen = 0.0, False
    for piece in build.gear:
        for s in [piece.main, *piece.subs]:
            if s.name in ("CRIT Rate", "CRIT DMG"):
                seen = True
                value = float(s.value.rstrip("%").replace(",", ""))
                total += 2 * value if s.name == "CRIT Rate" else value
    return total if seen else None


# For characters that want no crit: the stat whose gear total stands in for Crit Value, best first.
VALUE_STATS = ("SPD", "ER", "Energy Regen", "Break Effect", "Effect Hit Rate", "Effect RES", "EM", "AP", "HP%",
               "ATK%", "DEF%")
VALUE_LABELS = {"SPD": "SPEED VALUE", "ER": "ENERGY VALUE", "Energy Regen": "ENERGY VALUE", "EM": "EM VALUE",
                "AP": "AP VALUE", "Break Effect": "BREAK VALUE", "Effect Hit Rate": "EHR VALUE",
                "Effect RES": "RES VALUE"}


def gear_value(build: CharacterBuild, wanted: set[str] | None) -> tuple[str, str] | None:
    """The badge above the effective substat count: Crit Value, or for characters that want no crit (like most
    supports, or ones like Sparkle that only want CRIT DMG), the gear total of the stat they want most, e.g. Speed
    Value."""
    if not wanted or {"CRIT Rate", "CRIT DMG"} <= wanted:
        cv = crit_value(build)
        return ("CRIT VALUE", f"{cv:.1f}") if cv is not None else None
    stat = next((n for n in VALUE_STATS if n in wanted), None)
    if stat is None:
        return None
    total, pct = 0.0, False
    for piece in build.gear:
        for s in [piece.main, *piece.subs]:
            if s.name == stat:
                pct = s.value.endswith("%")
                total += float(s.value.rstrip("%").replace(",", ""))
    if not total:
        return None
    label = VALUE_LABELS.get(stat, f"{stat.rstrip('%')} VALUE".upper())
    return label, f"{total:.1f}%" if pct else (f"{total:.1f}" if total % 1 else f"{total:.0f}")


def server_name(game: str, uid: str) -> str | None:
    """The game server a UID belongs to, read from its leading digits (None if unknown)."""
    if game == "zzz":
        if len(uid) == 8:
            return "China"
        return {"10": "America", "13": "Asia", "15": "Europe", "17": "TW/HK/MO"}.get(uid[:2])
    if len(uid) == 9:
        return {"6": "America", "7": "Europe", "8": "Asia", "9": "TW/HK/MO"}.get(uid[0], "China")
    return None


def draw_card(build: CharacterBuild, images: dict[str, Image.Image], uid: str | None = None,
              wanted: set[str] | None = None, face: tuple[float, float, float] | None = None) -> bytes:
    """wanted: the substats this character wants; they're counted and highlighted (left out if unknown).
    face: where the face is in the art (ZZZ), for the head close-up."""
    global FONTS
    FONTS = FONTS or Fonts()
    f = FONTS
    accent = _accent(build)
    light = _mix(accent, (255, 255, 255), 0.45)
    labels = GAME_LABELS[build.game]

    card = _background(accent)
    _paste_art(card, images.get(build.art_url or "") or images.get(build.icon_url or ""), face)
    _shade(card, (0, 0, W, 210), 215, 0)
    _shade(card, (0, H - 280, W, H), 0, 225)
    draw = ImageDraw.Draw(card)

    # Name, then element · level · constellation and the rarity.
    for size, font in f.name.items():
        if draw.textlength(build.name, font=font) <= ART_W - PAD or size == 32:
            break
    name = _fit_text(draw, build.name, font, ART_W - PAD)
    draw.text((PAD + 4, 28), name, font=font, fill=TEXT)
    y = 28 + font.size + 16
    _info_row(card, build, f, accent, light, y, images.get(build.element_icon or ""), images.get(build.path_icon or ""))

    _cons_marks(card, build, accent, light, images)

    # ZZZ: the Mindscape picture bottom left, the weapon at the foot of the stats column, and Crit Value and the
    # effective substat count side by side under the discs. Other games: the weapon bottom left, the two values
    # at the foot of the stats column.
    zzz = build.game == "zzz"
    if zzz:
        shown, upcoming, thirds = mindscape_urls(build)
        _mindscape_panel(card, images.get(shown or ""), (PAD, H - PAD - MINDSCAPE_H, ART_W - 6, H - PAD),
                         build.constellation, images.get(upcoming or ""), thirds,
                         MINDSCAPE_FACES.get(int(build.character_id)) if upcoming else None)
    weapon_box = None
    if build.weapon:
        w = build.weapon
        x0, x1 = (STATS_X, STATS_X + STATS_W) if zzz else (PAD, ART_W - 6)
        stat_lines = _wrap(ImageDraw.Draw(card), " · ".join(f"{_name(s)} {s.value}" for s in w.stats), f.small_b, x1 - x0 - 120, 2, " · ")
        name_lines = _wrap(ImageDraw.Draw(card), w.name, f.wname, x1 - x0 - 120, 2)
        box_h = 34 + 26 * len(name_lines) + 24 + 22 * len(stat_lines)
        box = weapon_box = (x0, H - PAD - max(box_h, 112), x1, H - PAD)
        _panel(card, box, 14, (8, 6, 16, 190))
        _icon(card, images.get(w.icon_url or ""), (box[0] + 10, box[1] + 10, box[0] + 96, box[3] - 10))
        tx = box[0] + 108
        tw = box[2] - tx - 12
        draw = ImageDraw.Draw(card)
        ty = box[1] + (box[3] - box[1] - box_h) // 2 + 14
        for line in name_lines:
            draw.text((tx, ty), line, font=f.wname, fill=TEXT)
            ty += 26
        draw.text((tx, ty + 2), f"{labels['refine']}{w.refinement} · Lv. {w.level}", font=f.small, fill=DIM)
        ty += 28
        for line in stat_lines:
            draw.text((tx, ty), _fit_text(draw, line, f.small_b, tw), font=f.small_b, fill=TEXT)
            ty += 22

    # Stats column: a titled panel, one banded row per stat with its icon, then Crit Value and the effective
    # substat count.
    stats = [s for s in build.stats if not _is_zero(s.value)]
    value = gear_value(build, wanted)
    effective = sum(piece_count(p, wanted) for p in build.gear) if wanted and build.gear else None
    badges = [b for b in ((*value, TEAL) if value else None,
                          ("EFFECTIVE SUBS", str(effective), EFFECTIVE) if effective is not None else None) if b]
    if zzz:
        footer_h = weapon_box[3] - weapon_box[1] if weapon_box else 0
    else:
        footer_h = 58 * len(badges) - (12 if badges else 0)
    # ATK% on gear raises the ATK total; a few totals have longer names than the gear lines
    wanted_totals = {TOTAL_NAMES.get(n, n.rstrip("%")) for n in wanted or ()}
    box = (STATS_X, PAD, STATS_X + STATS_W, (weapon_box[1] - 12 if weapon_box else H - PAD) if zzz else H - PAD)
    if zzz:
        footer_h = 0
    _panel(card, box)
    draw = ImageDraw.Draw(card)
    _spaced(draw, (box[0] + 18, box[1] + 20), "STATS", f.label, DIM)
    draw.line((box[0] + 18, box[1] + 34, box[0] + 54, box[1] + 34), fill=accent + (255,), width=2)
    top = box[1] + 44
    row_h = min(50, (box[3] - top - 12 - footer_h - (10 if footer_h else 0)) / max(len(stats), 1))
    bands = Image.new("RGBA", card.size, (0, 0, 0, 0))
    bd = ImageDraw.Draw(bands)
    y = top
    for i, s in enumerate(stats):
        if i % 2 == 0:
            bd.rounded_rectangle((box[0] + 8, y + 1, box[2] - 8, y + row_h - 1), 8, fill=(255, 255, 255, 10))
        y += row_h
    _layer_onto(card, bands)
    draw = ImageDraw.Draw(card)
    y = top
    for s in stats:
        mid = y + row_h / 2
        name = _name(s)
        dmg_color = ELEMENT_COLORS.get(name.split(" ")[0])
        orb = (dmg_color >> 16 & 255, dmg_color >> 8 & 255, dmg_color & 255) if dmg_color else accent
        card.alpha_composite(stat_icons.icon(name, 20, light, orb), (box[0] + 16, round(mid - 10)))
        room = box[2] - 18 - (box[0] + 46) - 10 - draw.textlength(s.value, font=f.stat_b)
        font = f.stat if draw.textlength(name, font=f.stat) <= room else f.stat_s  # long names step down a size
        color = EFFECTIVE if s.name in wanted_totals else TEXT
        draw.text((box[0] + 46, mid), _fit_text(draw, name, font, room), font=font, fill=color, anchor="lm")
        draw.text((box[2] - 18, mid), s.value, font=f.stat_b, fill=color, anchor="rm")
        y += row_h
    cols = 2
    gw = (W - PAD - GEAR_X - 12 * (cols - 1)) / cols
    if zzz:  # one column each, under the discs
        spots = [(round(GEAR_X + i * (gw + 12)), H - PAD - 46, round(GEAR_X + i * (gw + 12) + gw)) for i in range(cols)]
    else:
        spots = [(box[0] + 10, box[3] - 12 - footer_h + 58 * i, box[2] - 10) for i in range(len(badges))]
    for (label, value, color), (x0, y, x1) in zip(badges, spots):
        badge = (x0, y, x1, y + 46)
        _panel(card, badge, 10, color + (22,))
        draw = ImageDraw.Draw(card)
        draw.rounded_rectangle(badge, 10, outline=color + (110,), width=1)
        _spaced(draw, (badge[0] + 14, y + 23), label, f.label, color, anchor="lm")
        draw.text((badge[2] - 14, y + 23), value, font=f.stat_b, fill=color, anchor="rm")

    # Gear, two per row.
    gear = build.gear[:6]
    gear_bottom = H - PAD - (46 + 12 if zzz and badges else 0)
    if gear:
        rows = max(3, math.ceil(len(gear) / 2))
        gh = (gear_bottom - PAD - 12 * (rows - 1)) / rows
        for i, piece in enumerate(gear):
            x0 = GEAR_X + (i % cols) * (gw + 12)
            y0 = PAD + (i // cols) * (gh + 12)
            badge = piece.slot.rsplit(" ", 1)[-1] if build.game == "zzz" else None
            box = (round(x0), round(y0), round(x0 + gw), round(y0 + gh))
            _gear(card, piece, images.get(piece.piece_icon or ""), box, light, labels["max_level"], badge, wanted)
    else:
        draw.text((GEAR_X + 20, PAD + 20), f"No {labels['gear'].lower()} equipped.", font=f.stat, fill=DIM)

    if uid:
        server = server_name(build.game, uid)
        foot = f"{server} · UID {uid}" if server else f"UID {uid}"
        if build.source == "hoyolab":
            foot = f"via HoYoLAB · {foot}"
        # A small stamp in the image's own corner, outside the layout.
        ImageDraw.Draw(card).text((W - 8, H - 5), foot, font=f.stamp, fill=TEXT, anchor="rd")

    out = io.BytesIO()
    card.convert("RGB").save(out, "PNG", compress_level=3)  # quick to pack; optimize=True took longer than the drawing
    return out.getvalue()


TOTAL_NAMES = {"ER": "Energy Recharge", "EM": "Elemental Mastery", "AP": "Anomaly Proficiency"}
DOTS = 5  # room for this many upgrade dots after each substat value (the most any game allows)


def _slanted(card: Image.Image, xy, text: str, font, fill, slant: float = 0.22) -> None:
    """Text leaning right like italics (the bundled font has no italic), centred on x with its bottom at y."""
    w, h = round(font.getlength(text)) + 8, font.size + 8
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(layer).text((w / 2, h - 4), text, font=font, fill=fill, anchor="md")
    layer = layer.transform(layer.size, Image.AFFINE, (1, slant, -slant * h / 2, 0, 1, 0), Image.BICUBIC)
    card.alpha_composite(layer, (round(xy[0] - w / 2), round(xy[1] - h + 4)))


def _gear(card: Image.Image, piece: Gear, icon: Image.Image | None, box, light, max_level: int, badge: str | None,
          wanted: set[str] | None = None) -> None:
    """One piece: its picture, main stat and value, then the substats with a dot per roll. Substats the character
    wants are drawn in the effective color, with their rolls added up underneath."""
    f = FONTS
    _panel(card, box, 14, (0, 0, 0, 70))
    x0, y0, x1, y1 = box
    _icon(card, icon, (x0 + 10, y0 + 10, x0 + 66, y0 + 66))
    draw = ImageDraw.Draw(card)
    if badge:
        draw.ellipse((x0 + 48, y0 + 48, x0 + 72, y0 + 72), fill=(20, 18, 30), outline=light, width=2)
        draw.text((x0 + 60, y0 + 60), badge, font=f.slot_b, fill=TEXT, anchor="mm")
    tx = x0 + (80 if icon or badge else 14)
    draw.text((tx, y0 + 14), _fit_text(draw, _name(piece.main), f.slot, x1 - tx - 10), font=f.slot, fill=DIM)
    draw.text((tx, y0 + 34), piece.main.value, font=f.main, fill=light)
    if piece.level < max_level:
        lx = tx + draw.textlength(piece.main.value, font=f.main) + 10
        draw.text((lx, y0 + 40), f"+{piece.level}", font=f.slot, fill=DIM)
    y = y0 + 76
    count_h = 22 if wanted else 0
    step = min(27, (y1 - 10 - count_h - y) / max(len(piece.subs), 1))
    for s in piece.subs:
        mid = y + step / 2
        good = bool(wanted) and s.name in wanted
        color = EFFECTIVE if good else TEXT
        value_w = draw.textlength(s.value, font=f.sub_b)
        upgrades = min(max(s.rolls - 1, 0), DOTS)  # the first roll is the base value, not an upgrade
        value_x = x1 - 12 - DOTS * 7 - 4  # values line up, with the dots in their own column on the right
        label = _fit_text(draw, _name(s), f.sub, value_x - x0 - 22 - value_w)
        draw.text((x0 + 14, mid), label, font=f.sub_b if good else f.sub, fill=color, anchor="lm")
        draw.text((value_x, mid), s.value, font=f.sub_b, fill=color, anchor="rm")
        dx = value_x + 6
        for _ in range(upgrades):
            draw.ellipse((dx, mid - 3, dx + 6, mid + 3), fill=EFFECTIVE if good else light)
            dx += 7
        y += step
    if wanted and piece.subs:
        _slanted(card, ((x0 + x1) / 2, y1 - 8), str(piece_count(piece, wanted)), f.count, EFFECTIVE)


CONS_W, CONS_TOP, CONS_BOTTOM = 84, 160, H - PAD - 176  # the strip of six marks left of the art
BADGE_SCALE = 1.3  # the badge is drawn in a CONS_W-wide strip, then shown this much bigger
SS = 4  # marks are drawn this many times bigger and shrunk, for smooth edges


def _sparkle(draw: ImageDraw.ImageDraw, cx: float, cy: float, r: float, fill, waist: float = 0.22) -> None:
    pts = []
    for i in range(8):
        a = -math.pi / 2 + i * math.pi / 4
        rad = r if i % 2 == 0 else r * waist
        pts.append((cx + rad * math.cos(a), cy + rad * math.sin(a)))
    draw.polygon(pts, fill=fill)


def _neon_glow(img: Image.Image, draw_fn, radius: float) -> None:
    """Draw shapes on a layer, blur it and lay it over img twice: a neon halo under the sharp shapes drawn next."""
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw_fn(ImageDraw.Draw(layer))
    small = layer.resize((img.width // SS, img.height // SS), Image.BILINEAR).filter(ImageFilter.GaussianBlur(radius))
    halo = small.resize(img.size, Image.BICUBIC)
    img.alpha_composite(halo)
    img.alpha_composite(halo)


def _badge_geo(img: Image.Image) -> tuple[float, float, float]:
    """Centre and ring radius of the round badge at the top of the strip."""
    w = img.width
    return w / 2, w / 2 + 6 * SS, w * 0.36


NUMBER_STYLE = "outline"  # the badge number: "soft", "outline", "gradient" or "slant" (bold italics with a glow)


def _badge_number(img: Image.Image, cx: float, cy: float, n: int, accent, light, symbol: Image.Image | None = None) -> None:
    """The count in the middle of a badge; the element symbol goes under it (and over any glow, so the glow doesn't
    wash it out)."""
    label = str(n)
    dim = 1 if n else 0.45
    if NUMBER_STYLE == "slant":
        font = _font("Bold", 34 * SS)
        slant = (1, 0.22, -0.22 * cy, 0, 1, 0)  # shear around the badge centre
        text = Image.new("RGBA", img.size, (0, 0, 0, 0))
        ImageDraw.Draw(text).text((cx, cy), label, font=font, fill=(255, 255, 255, round(255 * dim)), anchor="mm")
        if n >= 3:
            glow = Image.new("RGBA", img.size, (0, 0, 0, 0))
            ImageDraw.Draw(glow).text((cx, cy), label, font=font, fill=light + (255,), anchor="mm")
            glow = glow.transform(img.size, Image.AFFINE, slant, Image.BICUBIC)
            small = glow.resize((img.width // SS, img.height // SS), Image.BILINEAR).filter(ImageFilter.GaussianBlur(n - 2))
            for _ in range(1 + (n >= 5)):
                img.alpha_composite(small.resize(img.size, Image.BICUBIC))
        if symbol is not None:
            img.alpha_composite(symbol)
        img.alpha_composite(text.transform(img.size, Image.AFFINE, slant, Image.BICUBIC))
        return
    if symbol is not None:
        img.alpha_composite(symbol)
    text = Image.new("RGBA", img.size, (0, 0, 0, 0))
    td = ImageDraw.Draw(text)
    if NUMBER_STYLE == "outline":  # dark element-tinted figure with a light rim, like the engraved symbol
        font = _font("Bold", 32 * SS)
        td.text((cx, cy), label, font=font, fill=_mix(accent, (10, 8, 18), 0.6) + (round(240 * dim),), anchor="mm",
                stroke_width=2 * SS, stroke_fill=_mix(light, (255, 255, 255), 0.5) + (round(255 * dim),))
    elif NUMBER_STYLE == "gradient":  # white at the top fading into the element colour, with a thin dark edge
        font = _font("SemiBold", 32 * SS)
        mask = Image.new("L", img.size, 0)
        ImageDraw.Draw(mask).text((cx, cy), label, font=font, fill=round(255 * dim), anchor="mm")
        box = mask.getbbox() or (0, 0, 1, 1)
        grad = Image.new("RGBA", img.size, (0, 0, 0, 0))
        gd = ImageDraw.Draw(grad)
        for yy in range(box[1], box[3] + 1):
            t = (yy - box[1]) / max(1, box[3] - box[1])
            gd.line((box[0], yy, box[2], yy), fill=_mix((255, 255, 255), light, t * 0.9) + (255,))
        td.text((cx, cy), label, font=font, fill=(0, 0, 0, 0), anchor="mm", stroke_width=SS, stroke_fill=(10, 8, 18, round(200 * dim)))
        grad.putalpha(mask)
        text.alpha_composite(grad)
    else:  # soft: an upright, slightly tinted off-white with a soft shadow
        font = _font("SemiBold", 32 * SS)
        td.text((cx, cy + SS), label, font=font, fill=(0, 0, 0, round(150 * dim)), anchor="mm")
        text = text.filter(ImageFilter.GaussianBlur(2 * SS))
        ImageDraw.Draw(text).text((cx, cy), label, font=font, fill=_mix(light, (255, 255, 255), 0.6) + (round(250 * dim),), anchor="mm")
    img.alpha_composite(text)


def _badge_core(img: Image.Image, cx: float, cy: float, r: float, n: int, accent, game: str, icon: Image.Image | None = None) -> Image.Image | None:
    """The disc in the middle of the badge. With an icon, returns the path / specialty / element symbol on its own
    layer for _badge_number; without one, the disc gets a small motif per game instead."""
    rc = r * 0.78
    draw = ImageDraw.Draw(img)
    deep = _mix((14, 12, 24), accent, 0.2 + 0.02 * n)
    edge = _mix(deep, accent, 0.5)
    steps = 30
    for k in range(steps):  # radial gradient, deep in the middle, element colour at the rim
        t = k / (steps - 1)
        rr = rc * (1 - t * 0.98)
        draw.ellipse((cx - rr, cy - rr, cx + rr, cy + rr), fill=_mix(edge, deep, t ** 0.7) + (245,))
    # the symbol, or a small motif per game
    rnd = random.Random(12)
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    symbol = None
    if icon is not None and BADGE_FILL in ("face", "weapon"):
        zoom = {"genshin": 0.62, "hsr": 0.85}.get(game, 1) if BADGE_FILL == "face" else 1
        _badge_picture(layer, icon, cx, cy, rc, n, deep, zoom)
    elif icon is not None:
        symbol = Image.new("RGBA", img.size, (0, 0, 0, 0))
        _badge_symbol(symbol, icon, cx, cy, rc, n, accent)
    elif BADGE_FILL == "plain":
        pass
    elif game == "genshin":  # a starry night sky
        for _ in range(26):
            a, d = rnd.uniform(0, 2 * math.pi), rc * math.sqrt(rnd.uniform(0, 0.9))
            x, y, s = cx + math.cos(a) * d, cy + math.sin(a) * d, rnd.choice((1, 1, 1.6)) * SS
            ld.ellipse((x - s, y - s, x + s, y + s), fill=(255, 255, 255, rnd.randint(90, 200)))
    elif game == "hsr":  # stars
        for _ in range(16):
            a, d = rnd.uniform(0, 2 * math.pi), rc * math.sqrt(rnd.uniform(0, 0.9))
            x, y, s = cx + math.cos(a) * d, cy + math.sin(a) * d, rnd.choice((1, 1.4)) * SS
            ld.ellipse((x - s, y - s, x + s, y + s), fill=(255, 255, 255, rnd.randint(90, 200)))
    else:  # ZZZ: halftone dots and CRT scanlines
        step = 5 * SS
        for gy in range(int(cy - rc), int(cy + rc), step):
            for gx in range(int(cx - rc), int(cx + rc), step):
                d = math.hypot(gx - cx, gy - cy)
                if d < rc * 0.95:
                    s = (d / rc) * step * 0.32
                    ld.ellipse((gx - s, gy - s, gx + s, gy + s), fill=accent + (110,))
        for yy in range(int(cy - rc), int(cy + rc), 3 * SS):
            ld.line((cx - rc, yy, cx + rc, yy), fill=(0, 0, 0, 60), width=SS)
    mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(mask).ellipse((cx - rc, cy - rc, cx + rc, cy + rc), fill=255)
    img.paste(layer, (0, 0), ImageChops.multiply(mask, layer.getchannel("A")))
    if symbol is not None:
        symbol.putalpha(ImageChops.multiply(mask, symbol.getchannel("A")))
    # glossy highlight on top and a thin rim
    gl = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(gl).ellipse((cx - rc * 0.7, cy - rc * 0.92, cx + rc * 0.7, cy - rc * 0.1), fill=(255, 255, 255, 34))
    img.alpha_composite(gl)
    ImageDraw.Draw(img).ellipse((cx - rc, cy - rc, cx + rc, cy + rc), outline=_mix(accent, (255, 255, 255), 0.5) + (150,), width=SS)
    return symbol


def _badge_picture(layer: Image.Image, pic: Image.Image, cx: float, cy: float, rc: float, n: int, deep, zoom: float = 1) -> None:
    """A picture (the character's face, or their weapon) filling the disc, dimmed so the number stays readable."""
    pic = pic.convert("RGBA")
    box = pic.getchannel("A").getbbox() or (0, 0, pic.width, pic.height)
    pic = pic.crop(box)
    if zoom < 1:  # close in on the face, at the top middle
        w = round(min(pic.size) * zoom)
        x0, y0 = (pic.width - w) // 2, round(pic.height * 0.04)
        pic = pic.crop((x0, y0, x0 + w, y0 + w))
    side = round(rc * 2)
    scale = side / min(pic.size)
    pic = pic.resize((max(side, round(pic.width * scale)), max(side, round(pic.height * scale))), Image.LANCZOS)
    left, top = (pic.width - side) // 2, min((pic.height - side) // 2, round(pic.height * 0.08))  # faces sit high
    pic = pic.crop((left, top, left + side, top + side))
    shade = Image.new("RGBA", pic.size, deep + (255,))
    shade.putalpha(pic.getchannel("A"))
    pic = Image.blend(pic, shade, 0.42 - 0.03 * n)
    layer.alpha_composite(pic, (round(cx - side / 2), round(cy - side / 2)))


def _badge_symbol(layer: Image.Image, icon: Image.Image, cx: float, cy: float, rc: float, n: int, accent) -> None:
    """The element symbol behind the count: a light outline with a dark fill, like it's engraved in the disc, so it
    shows on light and dark colours alike and the white text reads well over it."""
    shape = icon.convert("RGBA").getchannel("A")
    box = shape.getbbox()
    if not box:
        return
    shape = shape.crop(box)
    side = rc * 1.7
    scale = side / max(shape.size)
    shape = shape.resize((max(1, round(shape.width * scale)), max(1, round(shape.height * scale))), Image.LANCZOS)
    edge = shape.filter(ImageFilter.MaxFilter(2 * (SS // 2) + 3)).point(lambda v: v * (0.55 + 0.05 * n))
    glow = Image.new("RGBA", shape.size, _mix(accent, (255, 255, 255), 0.6) + (255,))
    glow.putalpha(edge)
    fill = Image.new("RGBA", shape.size, _mix(accent, (8, 6, 16), 0.72) + (255,))
    fill.putalpha(shape.point(lambda v: v * 0.8))
    pos = (round(cx - shape.width / 2), round(cy - shape.height / 2))
    layer.alpha_composite(glow, pos)
    layer.alpha_composite(fill, pos)


def _tinted(icon: Image.Image, color) -> Image.Image:
    """The icon's shape in one colour."""
    out = Image.new("RGBA", icon.size, color + (255,))
    out.putalpha(icon.convert("RGBA").getchannel("A"))
    return out


def _snowflake(size: int = 256) -> Image.Image:
    """A white six-armed snowflake, for Cryo (Enka has no Cryo icon to download)."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    c, w = size / 2, size // 14
    for k in range(6):
        a = math.radians(-90 + k * 60)
        ex, ey = c + math.cos(a) * c * 0.92, c + math.sin(a) * c * 0.92
        d.line((c, c, ex, ey), fill=(255, 255, 255, 255), width=w)
        for t, ln in ((0.5, 0.26), (0.72, 0.18)):  # the little branches
            bx, by = c + math.cos(a) * c * t, c + math.sin(a) * c * t
            for side in (-1, 1):
                b = a + side * math.radians(50)
                d.line((bx, by, bx + math.cos(b) * c * ln, by + math.sin(b) * c * ln), fill=(255, 255, 255, 255), width=w)
    d.ellipse((c - w * 1.6, c - w * 1.6, c + w * 1.6, c + w * 1.6), fill=(255, 255, 255, 255))
    return img


def _rays(d: ImageDraw.ImageDraw, cx: float, cy: float, r: float, color, count: int = 12, width: int = 2) -> None:
    for k in range(count):
        a = math.radians(k * 360 / count + 180 / count)
        d.line((cx + math.cos(a) * r, cy + math.sin(a) * r, cx + math.cos(a) * r * 1.3, cy + math.sin(a) * r * 1.3),
               fill=color + (255,), width=SS * width)


def _links(n: int) -> int:
    """How many of the six gaps between the ring's marks are lit: the ones up to the last mark, and at 6 the ring closes."""
    return 6 if n >= 6 else max(0, n - 1)


def _genshin_marks(img: Image.Image, n: int, accent, light, icon: Image.Image | None = None) -> None:
    """A constellation ring: six stars around the badge, joined along the ring as they're unlocked; star dust from C2,
    an inner glow from C3, an outer orbit from C4, twinkles from C5 and a starburst at C6."""
    cx, cy, r = _badge_geo(img)
    stars = [(cx + math.cos(math.radians(-90 + k * 60)) * r, cy + math.sin(math.radians(-90 + k * 60)) * r) for k in range(6)]
    rnd = random.Random(3)
    dust = []
    for _ in range(5 * max(0, n - 1)):
        a, d = rnd.uniform(0, 2 * math.pi), r * rnd.uniform(1.12, 1.35)
        dust.append((cx + math.cos(a) * d, cy + math.sin(a) * d, rnd.choice((1, 1, 1.5)) * SS))
    twinkles = [(cx + math.cos(math.radians(a)) * r * 1.3, cy + math.sin(math.radians(a)) * r * 1.3)
                for a in (-30, 150, 30, 210)[: {5: 2, 6: 4}.get(n, 0)]]

    def neon(d):
        if n >= 6:
            _rays(d, cx, cy, r, light, 8, 3)
        for k in range(_links(n)):
            d.arc((cx - r, cy - r, cx + r, cy + r), -90 + k * 60, -30 + k * 60, fill=accent + (255,), width=SS * (4 + 2 * n))
        for x, y in stars[:n]:
            d.ellipse((x - 9 * SS, y - 9 * SS, x + 9 * SS, y + 9 * SS), fill=accent + (255,))
        if n >= 3:
            ri = r * 0.78
            d.ellipse((cx - ri, cy - ri, cx + ri, cy + ri), outline=accent + (255,), width=SS * (n - 1))
        for x, y, s in dust:
            d.ellipse((x - s * 2, y - s * 2, x + s * 2, y + s * 2), fill=light + (255,))
    if n:
        _neon_glow(img, neon, min(7, 2 + n))
    draw = ImageDraw.Draw(img)
    if n >= 4:  # outer orbit with little planets
        ro = r * 1.2
        draw.ellipse((cx - ro, cy - ro, cx + ro, cy + ro), outline=light + (150,), width=SS)
        for k in range(n - 2):
            a = math.radians(20 + k * 360 / (n - 2))
            px, py = cx + math.cos(a) * ro, cy + math.sin(a) * ro
            draw.ellipse((px - 2 * SS, py - 2 * SS, px + 2 * SS, py + 2 * SS), fill=light + (255,))
    symbol = _badge_core(img, cx, cy, r, n, accent, "genshin", icon)
    draw = ImageDraw.Draw(img)
    draw.ellipse((cx - r, cy - r, cx + r, cy + r), outline=(255, 255, 255, 60), width=SS)
    for k in range(_links(n)):  # constellation lines along the ring
        draw.arc((cx - r, cy - r, cx + r, cy + r), -90 + k * 60, -30 + k * 60, fill=light + (255,), width=SS * 3)
    for i, (x, y) in enumerate(stars):
        if i < n:
            _sparkle(draw, x, y, 12 * SS, light + (255,))
            _sparkle(draw, x, y, 6 * SS, (255, 255, 255, 255), 0.3)
        else:
            draw.ellipse((x - 4 * SS, y - 4 * SS, x + 4 * SS, y + 4 * SS), fill=(40, 38, 50, 255), outline=(255, 255, 255, 110), width=SS)
    for x, y, s in dust:
        draw.ellipse((x - s, y - s, x + s, y + s), fill=(255, 255, 255, 230))
    for x, y in twinkles:
        _sparkle(draw, x, y, 7 * SS, (255, 255, 255, 255), 0.25)
    _badge_number(img, cx, cy, n, accent, light, symbol)


def _hsr_marks(img: Image.Image, n: int, accent, light, icon: Image.Image | None = None) -> None:
    """A Trailblaze rail ring: six stations around the badge, the track lit up to the last eidolon; light-speed streaks
    from E2, an inner glow from E3, an outer orbit from E4, comets from E5 and a burst at E6."""
    cx, cy, r = _badge_geo(img)
    ang = [-90 + k * 60 for k in range(6)]
    rnd = random.Random(8)
    streaks = [(rnd.uniform(0, 360), r * rnd.uniform(1.12, 1.32), rnd.uniform(10, 22)) for _ in range(3 * max(0, n - 1))]
    comets = [-40, 140][: {5: 1, 6: 2}.get(n, 0)]

    def neon(d):
        if n >= 6:
            _rays(d, cx, cy, r, light, 12, 2)
        if n > 1:
            d.arc((cx - r, cy - r, cx + r, cy + r), -90, -90 + 60 * _links(n), fill=accent + (255,), width=SS * (4 + 2 * n))
        for a in ang[:n]:
            x, y = cx + math.cos(math.radians(a)) * r, cy + math.sin(math.radians(a)) * r
            d.ellipse((x - 9 * SS, y - 9 * SS, x + 9 * SS, y + 9 * SS), fill=accent + (255,))
        if n >= 3:
            ri = r * 0.78
            d.ellipse((cx - ri, cy - ri, cx + ri, cy + ri), outline=accent + (255,), width=SS * (n - 1))
        for a0, rr, ln in streaks:
            d.arc((cx - rr, cy - rr, cx + rr, cy + rr), a0, a0 + ln, fill=light + (255,), width=SS * 2)
    if n:
        _neon_glow(img, neon, min(7, 2 + n))
    draw = ImageDraw.Draw(img)
    ro = r * 1.22
    if n >= 4:  # outer dashed orbit
        for k in range(24):
            draw.arc((cx - ro, cy - ro, cx + ro, cy + ro), k * 15, k * 15 + 7, fill=light + (170,), width=SS)
    for a in comets:
        for j in range(8):  # tail fading behind the head
            draw.arc((cx - ro, cy - ro, cx + ro, cy + ro), a - 6 * (j + 1), a - 6 * j, fill=light + (255 - 30 * j,), width=SS * max(1, 3 - j // 3))
        hx, hy = cx + math.cos(math.radians(a)) * ro, cy + math.sin(math.radians(a)) * ro
        draw.ellipse((hx - 3 * SS, hy - 3 * SS, hx + 3 * SS, hy + 3 * SS), fill=(255, 255, 255, 255))
    for a0, rr, ln in streaks:
        draw.arc((cx - rr, cy - rr, cx + rr, cy + rr), a0, a0 + ln, fill=(255, 255, 255, 220), width=SS)
    symbol = _badge_core(img, cx, cy, r, n, accent, "hsr", icon)
    draw = ImageDraw.Draw(img)
    for rr in (r * 0.93, r * 1.07):  # the two rails
        draw.ellipse((cx - rr, cy - rr, cx + rr, cy + rr), outline=(255, 255, 255, 110), width=SS)
    for k in range(36):  # sleepers
        a = math.radians(k * 10)
        draw.line((cx + math.cos(a) * r * 0.9, cy + math.sin(a) * r * 0.9, cx + math.cos(a) * r * 1.1, cy + math.sin(a) * r * 1.1),
                  fill=(255, 255, 255, 50), width=SS)
    if n > 1:
        for rr in (r * 0.93, r * 1.07):
            draw.arc((cx - rr, cy - rr, cx + rr, cy + rr), -90, -90 + 60 * _links(n), fill=light + (255,), width=SS * 2)
    for i, a in enumerate(ang):  # stations
        x, y = cx + math.cos(math.radians(a)) * r, cy + math.sin(math.radians(a)) * r
        s = 8 * SS
        pts = [(x, y - s), (x + s, y), (x, y + s), (x - s, y)]
        if i < n:
            draw.polygon(pts, fill=(255, 255, 255, 255), outline=light + (255,), width=SS * 2)
            draw.ellipse((x - 2.5 * SS, y - 2.5 * SS, x + 2.5 * SS, y + 2.5 * SS), fill=accent + (255,))
        else:
            s = 6 * SS
            draw.polygon([(x, y - s), (x + s, y), (x, y + s), (x - s, y)], fill=(70, 68, 86, 230), outline=(255, 255, 255, 150), width=SS)
    _badge_number(img, cx, cy, n, accent, light, symbol)


def _zzz_marks(img: Image.Image, n: int, accent, light, icon: Image.Image | None = None) -> None:
    """A ring badge that charges up with every mindscape: brighter glow, then sparks, an outer ring, lightning, and a burst at M6."""
    cx, cy, r = _badge_geo(img)
    segs = [(-90 + k * 60 + 4, -90 + (k + 1) * 60 - 4) for k in range(6)]
    rnd = random.Random(7)
    sparks = []
    for _ in range(3 * max(0, n - 1)):
        a = rnd.uniform(0, 2 * math.pi)
        d0 = r * rnd.uniform(1.12, 1.3)
        sparks.append((cx + math.cos(a) * d0, cy + math.sin(a) * d0, rnd.choice((1, 1.5, 2)) * SS))
    bolts = []
    for k in range({5: 2, 6: 4}.get(n, 0)):
        a = math.radians(-60 + k * (360 / max(1, {5: 2, 6: 4}[n])) + rnd.uniform(-20, 20))
        pts = [(cx + math.cos(a) * r, cy + math.sin(a) * r)]
        for j in range(1, 4):
            aa = a + (0.18 if j % 2 else -0.12)
            rad = r * (1 + 0.1 * j)
            pts.append((cx + math.cos(aa) * rad, cy + math.sin(aa) * rad))
        bolts.append(pts)

    def neon(d):
        if n >= 6:
            for k in range(12):
                a = math.radians(k * 30 + 15)
                d.line((cx + math.cos(a) * r * 1.0, cy + math.sin(a) * r * 1.0,
                        cx + math.cos(a) * r * 1.3, cy + math.sin(a) * r * 1.3), fill=light + (255,), width=SS * 2)
        for k in range(n):
            d.arc((cx - r, cy - r, cx + r, cy + r), *segs[k], fill=accent + (255,), width=SS * (6 + 2 * n))
        if n >= 3:
            ri = r * 0.78
            d.ellipse((cx - ri, cy - ri, cx + ri, cy + ri), outline=accent + (255,), width=SS * (n - 1))
        for x, y, s in sparks:
            d.ellipse((x - s * 2, y - s * 2, x + s * 2, y + s * 2), fill=light + (255,))
        for pts in bolts:
            d.line(pts, fill=light + (255,), width=SS * 4)
    if n:
        _neon_glow(img, neon, min(7, 2 + n))
        if n >= 5:
            _neon_glow(img, neon, 2)
    draw = ImageDraw.Draw(img)
    if n >= 4:  # outer dashed ring
        ro = r * 1.2
        ticks = 12 + 6 * (n - 4)
        for k in range(ticks):
            a0 = k * 360 / ticks
            draw.arc((cx - ro, cy - ro, cx + ro, cy + ro), a0, a0 + 360 / ticks * 0.5, fill=light + (210,), width=SS * 2)
    symbol = _badge_core(img, cx, cy, r, n, accent, "zzz", icon)
    draw = ImageDraw.Draw(img)
    for k, (a0, a1) in enumerate(segs):
        draw.arc((cx - r, cy - r, cx + r, cy + r), a0, a1, fill=light + (255,) if k < n else (255, 255, 255, 50), width=SS * 7)
        if k < n and n >= 6:
            draw.arc((cx - r, cy - r, cx + r, cy + r), a0 + 3, a1 - 3, fill=(255, 255, 255, 255), width=SS * 2)
    for x, y, s in sparks:
        draw.ellipse((x - s, y - s, x + s, y + s), fill=(255, 255, 255, 255))
    for pts in bolts:
        draw.line(pts, fill=(255, 255, 255, 255), width=SS)
    _badge_number(img, cx, cy, n, accent, light, symbol)


BADGE_FILL = "stars"  # behind the badge number: "face", "weapon", "symbol" (element), "stars" or "plain"


def _cons_marks(card: Image.Image, build: CharacterBuild, accent, light, images: dict[str, Image.Image]) -> None:
    """The six constellation / eidolon / mindscape marks down the left of the art, owned ones lit. With SHOW_BADGE the
    old round badge with the number sits above them (BADGE_FILL picks what's in its disc)."""
    if build.game == "zzz":  # the M1-M6 tab beside the Mindscape picture shows it
        return
    n = max(0, min(build.constellation, 6))
    if not SHOW_BADGE:
        _cons_column(card, build, n, accent, light, images, PAD + 26, CONS_TOP + 14)
        return
    icon = None
    if BADGE_FILL == "face":
        icon = images.get(build.icon_url or "")
    elif BADGE_FILL == "weapon" and build.weapon:
        icon = images.get(build.weapon.icon_url or "")
    elif BADGE_FILL == "symbol":
        icon = images.get(build.element_icon or "")
        if icon is None and build.game == "genshin" and build.element == "Cryo":
            icon = _snowflake()
    size = (CONS_W * SS, (CONS_BOTTOM - CONS_TOP) * SS)
    img = Image.new("RGBA", size, (0, 0, 0, 0))
    if build.game == "genshin":
        _genshin_marks(img, n, accent, light, icon)
    elif build.game == "hsr":
        _hsr_marks(img, n, accent, light, icon)
    else:
        _zzz_marks(img, n, accent, light, icon)
    img = img.resize((round(img.width / SS * BADGE_SCALE), round(img.height / SS * BADGE_SCALE)), Image.LANCZOS)
    card.alpha_composite(img, (PAD - 14, CONS_TOP - 8))
    if build.game == "zzz":  # the badge alone
        return
    badge_bottom = CONS_TOP - 8 + (CONS_W / 2 + 6 + CONS_W * 0.36 * 1.35) * BADGE_SCALE  # under the ring's outer orbit
    _cons_column(card, build, n, accent, light, images, PAD - 14 + img.width / 2, badge_bottom)


SHOW_BADGE = False  # Genshin and Star Rail: the round badge above the column (Syphex chose the column alone, 2026-10-14)
CONS_ICON = 40  # each constellation icon in the column


def _cons_column(card: Image.Image, build: CharacterBuild, n: int, accent, light, images: dict[str, Image.Image],
                 cx: float, top: float) -> None:
    """The six constellation / eidolon icons from top to bottom: unlocked ones lit in the character's colour on a
    glowing disc, locked ones dim grey. ZZZ's mindscapes have no icons, so like HoYoLAB they're numbered circles."""
    icons = [images.get(u) for u in build.cons_icons[:6]]
    icons += [None] * (6 - len(icons))
    bottom = H - PAD - 186  # above the weapon
    step = (bottom - top) / 6
    d = CONS_ICON + 10  # the disc around an icon
    for i, icon in enumerate(icons):
        cy = top + step * (i + 0.5)
        lit = i < n
        disc = Image.new("RGBA", (d * SS, d * SS), (0, 0, 0, 0))
        dd = ImageDraw.Draw(disc)
        dd.ellipse((SS, SS, d * SS - SS, d * SS - SS), fill=(_mix(accent, (10, 10, 18), 0.55) + (235,)) if lit else (22, 22, 30, 200),
                   outline=light + (255,) if lit else (255, 255, 255, 70), width=SS * 2)
        disc = disc.resize((d, d), Image.LANCZOS)
        if lit:
            glow = Image.new("RGBA", (d + 24, d + 24), (0, 0, 0, 0))
            ImageDraw.Draw(glow).ellipse((12, 12, d + 12, d + 12), fill=accent + (150,))
            glow = glow.filter(ImageFilter.GaussianBlur(6))
            card.alpha_composite(glow, (round(cx - d / 2 - 12), round(cy - d / 2 - 12)))
        card.alpha_composite(disc, (round(cx - d / 2), round(cy - d / 2)))
        if icon is None:  # a number instead, slanted like HoYoLAB's
            _slanted(card, (cx + 1, cy + FONTS.main.size / 2 - 1), str(i + 1), FONTS.main,
                     light + (255,) if lit else (150, 150, 162, 200))
            continue
        mark = icon.convert("RGBA").resize((CONS_ICON, CONS_ICON), Image.LANCZOS)
        alpha = mark.getchannel("A")
        if lit:  # the icon's own shading, washed in the character's light colour
            grey = mark.convert("L")
            tinted = Image.merge("RGB", [grey.point(lambda v, c=c: round(v * (0.35 + 0.65 * c / 255) + c * 0.25 * (1 - v / 255))) for c in light])
            mark = tinted.convert("RGBA")
            mark.putalpha(alpha)
        else:
            grey = mark.convert("L").point(lambda v: round(v * 0.45))
            mark = Image.merge("RGBA", (grey, grey, grey, alpha.point(lambda a: round(a * 0.6))))
        card.alpha_composite(mark, (round(cx - CONS_ICON / 2), round(cy - CONS_ICON / 2)))


class CardMaker:
    """Downloads (once) the pictures a card needs and draws it off the event loop."""

    def __init__(self, session: aiohttp.ClientSession, cache_dir: str, effective: EffectiveStats | None = None):
        self.session = session
        self.effective = effective
        self.dir = Path(cache_dir) / "images"
        self.failed: set[str] = set()
        self.cards: dict[str, bytes] = {}  # recent cards, so flipping back and forth is instant
        self.faces_path = Path(cache_dir) / "faces.json"
        self.faces: dict[str, list[float]] | None = None  # art url -> face centre and size, as shares of the picture

    async def render(self, profile: PlayerProfile, build: CharacterBuild) -> bytes:
        wanted = self.effective.wanted(build) if self.effective else None
        key = hashlib.sha1(repr((profile.uid, build, sorted(wanted or ()))).encode()).hexdigest()
        if key in self.cards:
            return self.cards[key]
        urls = {build.art_url, build.icon_url, build.path_icon, build.element_icon, build.weapon.icon_url if build.weapon else None}
        urls |= {p.piece_icon for p in build.gear} | set(build.cons_icons)
        urls.discard(None)
        art_max = FULL_ART_MAX if build.game == "zzz" else ART_MAX
        mindscape = set(mindscape_urls(build)[:2]) - {None}
        urls |= mindscape
        loaded = await asyncio.gather(*(self._image(u, art_max if u == build.art_url or u in mindscape else ICON_MAX) for u in urls))
        images = {u: img for u, img in zip(urls, loaded) if img is not None}
        face = await self._face(build, images) if build.game == "zzz" else None
        png = await asyncio.to_thread(draw_card, build, images, profile.uid, wanted, face)
        if len(self.cards) >= 40:
            self.cards.pop(next(iter(self.cards)))
        self.cards[key] = png
        return png

    async def render_records(self, game: str, uid: str, records, nickname: str | None = None) -> bytes:
        """The battle records image (see records_card)."""
        from .records_card import draw_records

        urls = list({m.icon_url for r in records for t in r.teams for m in t.members + ([t.bangboo] if t.bangboo else []) if m.icon_url}
                    | {r.medal for r in records if r.medal})
        art = list({t.art for r in records for t in r.teams if t.art})  # boss pictures, kept larger
        loaded = await asyncio.gather(*(self._image(u, ICON_MAX) for u in urls), *(self._image(u, ART_MAX) for u in art))
        images = {u: img for u, img in zip(urls + art, loaded) if img is not None}
        return await asyncio.to_thread(draw_records, game, uid, records, images, nickname)

    async def render_patch(self, info) -> bytes:
        """The /<game>-patch image (see patch_card)."""
        from .patch_card import draw_patch, image_urls

        now = info.now
        urls = image_urls(info, now)
        loaded = await asyncio.gather(*(self._image(u, ICON_MAX) for u in urls))
        images = {u: img for u, img in zip(urls, loaded) if img is not None}
        return await asyncio.to_thread(draw_patch, info, images, now)

    async def _face(self, build: CharacterBuild, images: dict[str, Image.Image]) -> tuple[float, float, float] | None:
        """Where the face is in a ZZZ agent's picture, found once per picture and kept in faces.json."""
        art = images.get(build.art_url or "")
        if art is None:
            return None
        if self.faces is None:
            try:
                self.faces = json.loads(self.faces_path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                self.faces = {}
        if build.art_url not in self.faces:
            x, y, size = await asyncio.to_thread(find_face, art, images.get(build.icon_url or ""), build.art_url)
            self.faces[build.art_url] = [x / art.width, y / art.height, size / art.height]  # shares, whatever the size
            try:
                self.faces_path.write_text(json.dumps(self.faces), encoding="utf-8")
            except OSError:
                log.exception("Could not save %s", self.faces_path)
        x, y, size = self.faces[build.art_url]
        return x * art.width, y * art.height, size * art.height

    async def _image(self, url: str, limit: int) -> Image.Image | None:
        """The picture, at most limit pixels on its longer side."""
        suffix = "-full" if limit == FULL_ART_MAX else ""  # kept apart from the smaller copy of the same picture
        path = self.dir / (hashlib.sha1(url.encode()).hexdigest() + suffix + ".png")
        if path.exists():
            return await asyncio.to_thread(_open, path)
        if url in self.failed:
            return None
        for source in filter(None, (url, mirror_url(url))):  # Enka uploads a new character's pictures late
            try:
                async with self.session.get(source, timeout=aiohttp.ClientTimeout(total=20)) as resp:
                    resp.raise_for_status()
                    data = await resp.read()
                return await asyncio.to_thread(_shrink_and_save, data, path, limit)
            except Exception as exc:
                log.warning("Could not load card image %s: %s", source, exc)
        self.failed.add(url)
        return None


def mirror_url(url: str) -> str | None:
    """The same game picture on Hakushin's asset host, for when Enka doesn't have it yet (new characters)."""
    for prefix, folder in (("https://enka.network/ui/zzz/", "zzz"), ("https://enka.network/ui/", "gi")):
        if url.startswith(prefix) and url.endswith(".png") and "/" not in url[len(prefix):]:
            return f"https://static.nanoka.cc/assets/{folder}/{url[len(prefix):-4]}.webp"
    return None


def _open(path: Path) -> Image.Image:
    with Image.open(path) as img:
        return img.convert("RGBA")


def _shrink_and_save(data: bytes, path: Path, limit: int) -> Image.Image:
    with Image.open(io.BytesIO(data)) as img:
        img = img.convert("RGBA")
    if max(img.size) > limit:
        img.thumbnail((limit, limit), Image.LANCZOS)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    img.save(tmp, "PNG")
    os.replace(tmp, path)
    return img
