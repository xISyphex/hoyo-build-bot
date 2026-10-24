"""The Star Rail build card as a star chart: a navigation console in deep space, thin gold linework, an astrolabe
ring behind the character, the eidolons as a constellation that lights up star by star, and the relics in orbits."""
from __future__ import annotations

import functools
import io
import math
import random

from PIL import Image, ImageChops, ImageDraw, ImageFilter

from . import card as base
from . import stat_icons
from .effective import piece_count
from .embeds import ELEMENT_COLORS, _is_zero, _name
from .models import CharacterBuild, Gear

W, H = base.W, base.H
SS = 3  # shapes are drawn this many times bigger, then shrunk, for smooth edges
SPACE = (6, 10, 28)  # the deep blue behind everything
NEBULA = (40, 30, 92)
GOLD = (232, 195, 122)  # the chart's linework
PALE = (255, 227, 163)  # big numbers
TEXT = (238, 234, 248)
DIM = (178, 170, 206)
FAINT = (120, 114, 150)
EFFECTIVE = (159, 240, 255)  # effective substats, in the cyan of a navigation light
PANEL = (13, 17, 44, 214)
CHAMFER = 14
ART_W = 560  # the art's strip, fading out before the stats column
FADE = (330, 470)
STATS_X, STATS_W = 470, 252
GEAR_X = 740
PAD = 24
ROMAN = ("I", "II", "III", "IV", "V", "VI")
PATHS = {"Memory": "Remembrance", "Warrior": "Destruction", "Rogue": "The Hunt", "Mage": "Erudition",
         "Shaman": "Harmony", "Warlock": "Nihility", "Knight": "Preservation", "Priest": "Abundance"}
# Where the six eidolon stars sit in their constellation, in a 250 x 170 box (a loose ring, like a real figure)
CONSTELLATION = ((26, 44), (96, 16), (170, 40), (214, 104), (146, 150), (62, 128))


@functools.lru_cache(maxsize=None)
def _cinzel(size: int, weight: int = 700):
    """Cinzel (OFL): Roman inscription capitals, for the name and the chart's titles."""
    try:
        font = base.ImageFont.truetype(str(base.FONT_DIR / "Cinzel-Variable.ttf"), size)
        font.set_variation_by_axes([weight])
        return font
    except OSError:
        return base.ImageFont.load_default(size)


@functools.lru_cache(maxsize=None)
def _raj(weight: str, size: int):
    return base._font(weight, size)


def _chamfer(box, c: float = CHAMFER) -> list[tuple[float, float]]:
    """A panel's outline with its top left and bottom right corners cut off."""
    x0, y0, x1, y1 = box
    return [(x0 + c, y0), (x1, y0), (x1, y1 - c), (x1 - c, y1), (x0, y1), (x0, y0 + c)]


def _panel(card: Image.Image, box, fill=PANEL, edge: int = 96) -> None:
    """A chart panel: dark glass with cut corners, a thin gold rim and a light catching its top edge."""
    x0, y0, x1, y1 = box
    w, h = (x1 - x0) * SS, (y1 - y0) * SS
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    shape = _chamfer((0, 0, w - 1, h - 1), CHAMFER * SS)
    d.polygon(shape, fill=fill)
    d.line(shape + shape[:1], fill=GOLD + (edge,), width=SS)
    layer = layer.resize((x1 - x0, y1 - y0), Image.LANCZOS)
    shine = Image.new("L", (x1 - x0, 1))  # brightest in the middle of the top edge
    for x in range(x1 - x0):
        shine.putpixel((x, 0), round(230 * max(0, 1 - abs(x / max(x1 - x0 - 1, 1) - 0.5) * 2.2)))
    top = Image.new("RGBA", (x1 - x0, 1), GOLD + (255,))
    top.putalpha(shine)
    layer.alpha_composite(top, (0, 0))
    card.alpha_composite(layer, (x0, y0))


def _sparkle(d: ImageDraw.ImageDraw, cx: float, cy: float, r: float, fill, waist: float = 0.2) -> None:
    """A four-pointed star."""
    w = r * waist
    d.polygon([(cx, cy - r), (cx + w, cy - w), (cx + r, cy), (cx + w, cy + w), (cx, cy + r), (cx - w, cy + w),
               (cx - r, cy), (cx - w, cy - w)], fill=fill)


def _space(build: CharacterBuild, accent) -> Image.Image:
    """Deep space: a nebula in the element's colour behind the character, a faint chart grid and a field of stars
    (the same stars every time for the same character)."""
    small = Image.new("RGB", (W // 8, H // 8))
    px = small.load()
    glow = base._mix(NEBULA, accent, 0.28)
    for y in range(small.height):
        for x in range(small.width):
            d = math.hypot((x / small.width - 0.22) * 1.25, y / small.height - 0.52)
            corner = math.hypot(x / small.width - 0.92, y / small.height - 0.08)
            c = base._mix(glow, SPACE, min(d / 0.62, 1))
            px[x, y] = base._mix((26, 48, 96), c, min(corner / 0.45, 1))
    card = small.resize((W, H), Image.BICUBIC).convert("RGBA")
    layer = Image.new("RGBA", (W * 2, H * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for x in range(0, W * 2, 80):
        d.line((x, 0, x, H * 2), fill=(255, 255, 255, 7), width=2)
    for y in range(0, H * 2, 80):
        d.line((0, y, W * 2, y), fill=(255, 255, 255, 7), width=2)
    rng = random.Random(build.character_id)
    for _ in range(260):
        x, y = rng.random() * W * 2, rng.random() * H * 2
        r = rng.choice((0.9, 1.2, 1.5, 2, 2.6))
        d.ellipse((x - r, y - r, x + r, y + r), fill=(255, 255, 255, rng.randint(50, 210)))
    for _ in range(7):  # a few bright ones with a glint
        x, y = rng.random() * W * 2, rng.random() * H * 2
        _sparkle(d, x, y, rng.uniform(6, 11), (255, 250, 235, 200), 0.12)
    card.alpha_composite(layer.resize((W, H), Image.LANCZOS))
    return card


def _astrolabe(card: Image.Image, cx: float, cy: float) -> None:
    """The navigation ring behind the character: rings, a dashed orbit and a dial of ticks."""
    k = SS
    size = 640
    layer = Image.new("RGBA", (size * k, size * k), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    c = size * k / 2

    def ring(r, color, width=1):
        d.ellipse((c - r * k, c - r * k, c + r * k, c + r * k), outline=color, width=width * k)

    ring(300, GOLD + (92,))
    ring(292, GOLD + (40,))
    ring(196, EFFECTIVE + (36,))
    for i in range(120):  # the dashed orbit
        if i % 2:
            continue
        a0 = math.radians(i * 3)
        d.arc((c - 250 * k, c - 250 * k, c + 250 * k, c + 250 * k), math.degrees(a0), math.degrees(a0) + 1.2,
              fill=GOLD + (110,), width=k)
    for i in range(72):  # the dial
        a = math.radians(i * 5)
        r1 = 300 - (14 if i % 6 == 0 else 7)
        d.line((c + math.cos(a) * r1 * k, c + math.sin(a) * r1 * k, c + math.cos(a) * 300 * k, c + math.sin(a) * 300 * k),
               fill=GOLD + (120 if i % 6 == 0 else 70,), width=k)
    for a in (35, 155, 260):  # small planets riding the orbits
        x, y = c + math.cos(math.radians(a)) * 250 * k, c + math.sin(math.radians(a)) * 250 * k
        d.ellipse((x - 4 * k, y - 4 * k, x + 4 * k, y + 4 * k), fill=PALE + (200,))
    layer = layer.resize((size, size), Image.LANCZOS)
    card.alpha_composite(layer, (round(cx - size / 2), round(cy - size / 2)))


def _art(card: Image.Image, art: Image.Image | None) -> None:
    """The character over the left of the chart, fading out before the stats."""
    if art is None:
        return
    art = art.convert("RGBA")
    scale = (H + 40) / art.height
    if art.width * scale < ART_W:
        scale = ART_W / art.width
    art = art.resize((round(art.width * scale), round(art.height * scale)), Image.LANCZOS)
    left = max((art.width - ART_W) // 2, 0)
    top = max((art.height - H) // 3, 0)
    art = art.crop((left, top, left + ART_W, top + H))
    fade = Image.new("L", (ART_W, 1))
    for x in range(ART_W):
        fade.putpixel((x, 0), round(255 * min(1, max(0, (FADE[1] - x) / (FADE[1] - FADE[0])))))
    art.putalpha(ImageChops.multiply(art.getchannel("A"), fade.resize(art.size)))
    card.alpha_composite(art, (-40, 0))


def _vignette(card: Image.Image, box, alpha: int) -> None:
    """A soft dark pool behind text drawn over the art."""
    x0, y0, x1, y1 = box
    mask = Image.new("L", ((x1 - x0) // 4, (y1 - y0) // 4), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, mask.width - 1, mask.height - 1), fill=alpha)
    mask = mask.filter(ImageFilter.GaussianBlur(mask.width / 7)).resize((x1 - x0, y1 - y0), Image.BICUBIC)
    layer = Image.new("RGBA", mask.size, SPACE + (255,))
    layer.putalpha(mask)
    card.alpha_composite(layer, (x0, y0))


def _gold_text(card: Image.Image, xy, text: str, font) -> None:
    """Text in a white-to-gold gradient, like engraved metal, with a soft shadow under it."""
    draw = ImageDraw.Draw(card)
    x0, y0, x1, y1 = draw.textbbox(xy, text, font=font)
    w, h = x1 - x0 + 8, y1 - y0 + 8
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).text((xy[0] - x0 + 4, xy[1] - y0 + 4), text, font=font, fill=255)
    shadow = Image.new("RGBA", (w, h), (0, 0, 0, 255))
    shadow.putalpha(mask.filter(ImageFilter.GaussianBlur(4)).point(lambda v: v * 0.8))
    card.alpha_composite(shadow, (x0 - 4, y0 - 1))
    grad = Image.new("RGBA", (w, h))
    for y in range(h):
        t = y / max(h - 1, 1)
        grad.paste(base._mix((255, 255, 255), GOLD, min(t * 1.3, 1)) + (255,), (0, y, w, y + 1))
    grad.putalpha(mask)
    card.alpha_composite(grad, (x0 - 4, y0 - 4))


def _spaced(draw, xy, text: str, font, fill, spacing: float = 3.0, anchor: str = "lm") -> float:
    x, y = xy
    for ch in text:
        draw.text((x, y), ch, font=font, fill=fill, anchor=anchor)
        x += draw.textlength(ch, font=font) + spacing
    return x


def _path_name(build: CharacterBuild) -> str:
    stem = (build.path_icon or "").rsplit("/", 1)[-1].rsplit(".", 1)[0]
    name = PATHS.get(stem, stem)
    return name if name.startswith("The ") or not name else f"The {name}"


def _symbol(icon: Image.Image | None, size: int) -> Image.Image | None:
    if icon is None:
        return None
    icon = icon.convert("RGBA")
    icon = icon.crop(icon.getchannel("A").getbbox() or (0, 0, icon.width, icon.height))
    k = size / max(icon.size)
    return icon.resize((max(1, round(icon.width * k)), max(1, round(icon.height * k))), Image.LANCZOS)


def _title(card: Image.Image, build: CharacterBuild, accent, images) -> None:
    """The name in engraved capitals, then the element and Path symbols, level, eidolon and rarity."""
    draw = ImageDraw.Draw(card)
    name = build.name.upper()
    for size in (52, 46, 40, 34, 30):
        font = _cinzel(size)
        if draw.textlength(name, font=font) <= STATS_X - PAD - 30:
            break
    name = base._fit_text(draw, name, font, STATS_X - PAD - 30)
    _vignette(card, (-120, -90, 480, 200), 170)
    _gold_text(card, (PAD + 8, 22), name, font)
    y = 22 + font.size + 14
    draw = ImageDraw.Draw(card)
    x = PAD + 10
    meta = _raj("SemiBold", 19)
    for icon in (_symbol(images.get(build.element_icon or ""), 26), _symbol(images.get(build.path_icon or ""), 24)):
        if icon is not None:
            card.alpha_composite(icon, (round(x), round(y + 13 - icon.height / 2)))
            x += icon.width + 8
    draw = ImageDraw.Draw(card)
    parts = [(build.element, accent), (f"Lv. {build.level}", TEXT), (f"E{build.constellation}", PALE), (_path_name(build), DIM)]
    for i, (text, color) in enumerate(p for p in parts if p[0]):
        if i:
            _sparkle(draw, x + 7, y + 13, 4.5, GOLD + (220,), 0.25)
            x += 16
        draw.text((x, y + 13), text, font=meta, fill=color, anchor="lm")
        x += draw.textlength(text, font=meta) + 2
    layer = Image.new("RGBA", (build.rarity * 22 * SS, 22 * SS), (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    for i in range(build.rarity):
        _sparkle(ld, (11 + i * 20) * SS, 11 * SS, 9 * SS, PALE + (255,), 0.24)
    card.alpha_composite(layer.resize((layer.width // SS, 22), Image.LANCZOS), (PAD + 8, round(y + 30)))


def _eidolons(card: Image.Image, build: CharacterBuild, accent, images, box) -> None:
    """The six eidolons as a constellation: each a star chart node holding its icon, joined in unlock order.
    Unlocked ones shine and their links are drawn bright; the rest stay faint pencil marks."""
    x0, y0 = box[:2]
    n = max(0, min(build.constellation, 6))
    icons = [images.get(u) for u in build.cons_icons[:6]] + [None] * 6
    _vignette(card, (x0 - 90, y0 - 60, x0 + 340, y0 + 250), 200)
    draw = ImageDraw.Draw(card)
    _spaced(draw, (x0 + 6, y0), "EIDOLONS", _cinzel(13, 700), GOLD, 3.2)
    pts = [(x0 + px, y0 + 24 + py) for px, py in CONSTELLATION]
    k = SS
    lw, lh = 290, 230
    layer = Image.new("RGBA", (lw * k, lh * k), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    ox, oy = x0 - 20, y0
    for i in range(5):
        (ax, ay), (bx, by) = pts[i], pts[i + 1]
        lit = i + 1 < n
        a, b = ((ax - ox) * k, (ay - oy) * k), ((bx - ox) * k, (by - oy) * k)
        if lit:
            d.line((a, b), fill=PALE + (235,), width=2 * k)
        else:  # dashed
            steps = int(math.dist(a, b) / (7 * k))
            for s in range(0, steps, 2):
                t0, t1 = s / steps, min((s + 1) / steps, 1)
                d.line(((a[0] + (b[0] - a[0]) * t0, a[1] + (b[1] - a[1]) * t0), (a[0] + (b[0] - a[0]) * t1, a[1] + (b[1] - a[1]) * t1)),
                       fill=GOLD + (90,), width=k)
    layer = layer.resize((lw, lh), Image.LANCZOS)
    glow = Image.new("RGBA", (lw, lh), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    for i, (x, y) in enumerate(pts[:n]):
        gd.ellipse((x - ox - 30, y - oy - 30, x - ox + 30, y - oy + 30), fill=base._mix(accent, PALE, 0.4) + (120,))
    card.alpha_composite(glow.filter(ImageFilter.GaussianBlur(10)), (ox, oy))
    card.alpha_composite(layer, (ox, oy))
    r = 21
    for i, (x, y) in enumerate(pts):
        lit = i < n
        node = Image.new("RGBA", (2 * r * k + 8 * k, 2 * r * k + 8 * k), (0, 0, 0, 0))
        nd = ImageDraw.Draw(node)
        c = node.width / 2
        nd.ellipse((c - r * k, c - r * k, c + r * k, c + r * k), fill=(base._mix(accent, SPACE, 0.55) + (240,)) if lit else (12, 14, 34, 230),
                   outline=PALE + (255,) if lit else GOLD + (90,), width=(2 if lit else 1) * k)
        if lit:  # a second, finer ring
            nd.ellipse((c - (r + 4) * k, c - (r + 4) * k, c + (r + 4) * k, c + (r + 4) * k), outline=GOLD + (150,), width=k)
        node = node.resize((node.width // k, node.height // k), Image.LANCZOS)
        card.alpha_composite(node, (round(x - node.width / 2), round(y - node.height / 2)))
        icon = icons[i]
        if icon is not None:
            mark = icon.convert("RGBA").resize((30, 30), Image.LANCZOS)
            alpha = mark.getchannel("A")
            grey = mark.convert("L")
            if lit:
                mark = Image.merge("RGB", [grey.point(lambda v, c=c: round(v * (0.4 + 0.6 * c / 255) + c * 0.2 * (1 - v / 255))) for c in PALE]).convert("RGBA")
                mark.putalpha(alpha)
            else:
                g = grey.point(lambda v: round(v * 0.42))
                mark = Image.merge("RGBA", (g, g, g, alpha.point(lambda a: round(a * 0.55))))
            card.alpha_composite(mark, (round(x - 15), round(y - 15)))
        draw = ImageDraw.Draw(card)
        draw.text((x, y + r + 12), ROMAN[i], font=_cinzel(11, 700), fill=PALE if lit else FAINT, anchor="mm")


def _stats(card: Image.Image, build: CharacterBuild, box, wanted: set[str] | None) -> None:
    """The character's totals, one row each, with a small gold icon and a hairline under it."""
    _panel(card, box)
    x0, y0, x1, y1 = box
    draw = ImageDraw.Draw(card)
    _spaced(draw, (x0 + 18, y0 + 18), "ATTRIBUTES", _cinzel(12, 700), GOLD, 3)
    stats = [s for s in build.stats if not _is_zero(s.value)]
    wanted_totals = {base.TOTAL_NAMES.get(n, n.rstrip("%")) for n in wanted or ()}
    top = y0 + 34
    row = min(40, (y1 - 10 - top) / max(len(stats), 1))
    name_font, small_font, value_font = _raj("Regular", 19), _raj("Regular", 16), _raj("Bold", 21)
    for i, s in enumerate(stats):
        mid = top + row * (i + 0.5)
        name = _name(s)
        good = s.name in wanted_totals
        dmg = ELEMENT_COLORS.get(name.split(" ")[0])
        orb = (dmg >> 16 & 255, dmg >> 8 & 255, dmg & 255) if dmg else GOLD
        card.alpha_composite(stat_icons.icon(name, 16, GOLD, orb), (x0 + 16, round(mid - 8)))
        draw = ImageDraw.Draw(card)
        room = x1 - 16 - (x0 + 42) - 8 - draw.textlength(s.value, font=value_font)
        font = name_font if draw.textlength(name, font=name_font) <= room else small_font
        draw.text((x0 + 42, mid), base._fit_text(draw, name, font, room), font=font, fill=EFFECTIVE if good else DIM, anchor="lm")
        draw.text((x1 - 16, mid), s.value, font=value_font, fill=EFFECTIVE if good else TEXT, anchor="rm")
        if i < len(stats) - 1:
            draw.line((x0 + 14, mid + row / 2, x1 - 14, mid + row / 2), fill=(255, 255, 255, 18), width=1)


def _weapon(card: Image.Image, build: CharacterBuild, box, images) -> None:
    """The light cone, tilted a little with a gold halo, its name, superimposition, level and stats."""
    _panel(card, box)
    x0, y0, x1, y1 = box
    w = build.weapon
    icon = images.get(w.icon_url or "")
    tx = x0 + 14
    if icon is not None:
        pic = icon.convert("RGBA")
        pic.thumbnail((64, y1 - y0 - 20), Image.LANCZOS)
        pic = pic.rotate(-5, expand=True, resample=Image.BICUBIC)
        halo = Image.new("RGBA", (pic.width + 24, pic.height + 24), (0, 0, 0, 0))
        halo.alpha_composite(Image.new("RGBA", pic.size, GOLD + (255,)), (12, 12))
        halo.putalpha(ImageChops.multiply(halo.getchannel("A"), Image.new("L", halo.size, 0).copy()) if False else halo.getchannel("A"))
        mask = Image.new("L", halo.size, 0)
        mask.paste(pic.getchannel("A"), (12, 12))
        halo.putalpha(mask.filter(ImageFilter.GaussianBlur(6)).point(lambda v: v * 0.55))
        cy = (y0 + y1) / 2
        card.alpha_composite(halo, (round(x0 + 12 - 12), round(cy - pic.height / 2 - 12)))
        card.alpha_composite(pic, (round(x0 + 12), round(cy - pic.height / 2)))
        tx = x0 + 12 + pic.width + 12
    draw = ImageDraw.Draw(card)
    room = x1 - tx - 12
    name_font = _raj("Bold", 19)
    lines = base._wrap(draw, w.name, name_font, room, 2)
    stats = " · ".join(f"{_name(s)} {s.value}" for s in w.stats)
    block = 22 * len(lines) + 22 + 20
    y = (y0 + y1) / 2 - block / 2 + 10
    for line in lines:
        draw.text((tx, y), line, font=name_font, fill=TEXT, anchor="lm")
        y += 22
    draw.text((tx, y + 1), f"S{w.refinement} · Lv. {w.level}", font=_raj("SemiBold", 16), fill=GOLD, anchor="lm")
    y += 21
    draw.text((tx, y + 1), base._fit_text(draw, stats, _raj("Regular", 15), room), font=_raj("Regular", 15), fill=DIM, anchor="lm")


def _readings(card: Image.Image, build: CharacterBuild, box, wanted: set[str] | None) -> None:
    """Crit Value (or the value the character lives on), the effective substat count and the relic sets."""
    _panel(card, box)
    x0, y0, x1, y1 = box
    draw = ImageDraw.Draw(card)
    value = base.gear_value(build, wanted)
    effective = sum(piece_count(p, wanted) for p in build.gear) if wanted and build.gear else None
    rows = []
    if value:
        rows.append((value[0].title().replace("Crit", "Crit"), value[1], PALE))
    if effective is not None:
        rows.append(("Effective Subs", str(effective), EFFECTIVE))
    y = y0 + 22
    for label, text, color in rows:
        draw.text((x0 + 16, y), label, font=_raj("SemiBold", 17), fill=DIM, anchor="lm")
        draw.text((x1 - 16, y), text, font=_raj("Bold", 24), fill=color, anchor="rm")
        y += 28
    sets = build.set_bonuses[:3]
    if sets and y + 6 < y1:
        draw.line((x0 + 14, y - 6, x1 - 14, y - 6), fill=(255, 255, 255, 18), width=1)
        room = x1 - x0 - 30
        y += 6
        for line in sets:
            count, _, name = line.partition(" ")
            if y > y1 - 12:
                break
            draw.text((x0 + 16, y), count, font=_raj("Bold", 15), fill=GOLD, anchor="lm")
            cw = draw.textlength(count, font=_raj("Bold", 15)) + 6
            draw.text((x0 + 16 + cw, y), base._fit_text(draw, name, _raj("Regular", 15), room - cw), font=_raj("Regular", 15),
                      fill=TEXT, anchor="lm")
            y += 19


def _relic(card: Image.Image, piece: Gear, icon: Image.Image | None, box, accent, wanted: set[str] | None) -> None:
    """One relic: its picture inside an orbit, the main stat, then the substats with a small star per upgrade.
    Wanted substats are lit in cyan, and their rolls are counted in the top right corner."""
    _panel(card, box)
    x0, y0, x1, y1 = box
    k = SS
    d = 70  # the orbit
    orbit = Image.new("RGBA", ((d + 10) * k, (d + 10) * k), (0, 0, 0, 0))
    od = ImageDraw.Draw(orbit)
    c = orbit.width / 2
    od.ellipse((c - d / 2 * k, c - d / 2 * k, c + d / 2 * k, c + d / 2 * k), fill=(255, 255, 255, 8), outline=GOLD + (110,), width=k)
    od.ellipse((c - (d / 2 + 5) * k, c - (d / 2 + 5) * k, c + (d / 2 + 5) * k, c + (d / 2 + 5) * k), outline=GOLD + (36,), width=k)
    px, py = c + math.cos(math.radians(-38)) * d / 2 * k, c + math.sin(math.radians(-38)) * d / 2 * k
    od.ellipse((px - 3.5 * k, py - 3.5 * k, px + 3.5 * k, py + 3.5 * k), fill=PALE + (255,))
    orbit = orbit.resize((d + 10, d + 10), Image.LANCZOS)
    ox, oy = x0 + 10, y0 + 10
    card.alpha_composite(orbit, (ox, oy))
    base._icon(card, icon, (ox + 11, oy + 11, ox + d - 1, oy + d - 1))
    draw = ImageDraw.Draw(card)
    tx = ox + d + 18
    draw.text((tx, y0 + 30), base._fit_text(draw, _name(piece.main), _raj("SemiBold", 16), x1 - tx - 40), font=_raj("SemiBold", 16), fill=DIM, anchor="lm")
    draw.text((tx, y0 + 58), piece.main.value, font=_raj("Bold", 30), fill=PALE, anchor="lm")
    if piece.level < base.GAME_LABELS["hsr"]["max_level"]:
        lx = tx + draw.textlength(piece.main.value, font=_raj("Bold", 30)) + 8
        draw.text((lx, y0 + 62), f"+{piece.level}", font=_raj("Regular", 15), fill=FAINT, anchor="lm")
    if wanted and piece.subs:
        count = piece_count(piece, wanted)
        layer = Image.new("RGBA", (16 * k, 16 * k), (0, 0, 0, 0))
        _sparkle(ImageDraw.Draw(layer), 8 * k, 8 * k, 7 * k, (EFFECTIVE if count else FAINT) + (255,), 0.22)
        draw.text((x1 - 14, y0 + 22), str(count), font=_raj("Bold", 20), fill=EFFECTIVE if count else FAINT, anchor="rm")
        cw = draw.textlength(str(count), font=_raj("Bold", 20))
        card.alpha_composite(layer.resize((16, 16), Image.LANCZOS), (round(x1 - 14 - cw - 20), y0 + 14))
    y = y0 + d + 26
    rows = piece.subs[:4]
    step = min(30, (y1 - 10 - y) / max(len(rows), 1))
    name_font, name_b, value_font = _raj("Regular", 17), _raj("Bold", 17), _raj("Bold", 18)
    stars = Image.new("RGBA", card.size, (0, 0, 0, 0))
    sd = None
    for i, s in enumerate(rows):
        mid = y + step * (i + 0.5)
        good = bool(wanted) and s.name in wanted
        color = EFFECTIVE if good else TEXT
        draw = ImageDraw.Draw(card)
        if i:
            draw.line((x0 + 14, mid - step / 2, x1 - 14, mid - step / 2), fill=(255, 255, 255, 14), width=1)
        value_x = x1 - 14
        vw = draw.textlength(s.value, font=value_font)
        upgrades = min(max(s.rolls - 1, 0), 5)
        marks_w = upgrades * 10
        label = base._fit_text(draw, _name(s), name_b if good else name_font, value_x - vw - marks_w - 12 - (x0 + 14))
        draw.text((x0 + 14, mid), label, font=name_b if good else name_font, fill=color if good else DIM, anchor="lm")
        draw.text((value_x, mid), s.value, font=value_font, fill=color, anchor="rm")
        if upgrades:
            if sd is None:
                stars = Image.new("RGBA", ((x1 - x0) * k, (y1 - y0) * k), (0, 0, 0, 0))
                sd = ImageDraw.Draw(stars)
            sx = value_x - vw - 8 - 4
            for _ in range(upgrades):
                _sparkle(sd, (sx - x0) * k, (mid - y0) * k, 4.2 * k, (EFFECTIVE if good else GOLD) + (255,), 0.26)
                sx -= 10
    if sd is not None:
        card.alpha_composite(stars.resize((x1 - x0, y1 - y0), Image.LANCZOS), (x0, y0))


def draw_card(build: CharacterBuild, images: dict[str, Image.Image], uid: str | None = None,
              wanted: set[str] | None = None, face=None) -> bytes:
    base.FONTS = base.FONTS or base.Fonts()
    accent = base._accent(build)
    card = _space(build, accent)
    _astrolabe(card, 230, 390)
    _art(card, images.get(build.art_url or "") or images.get(build.icon_url or ""))
    _title(card, build, accent, images)
    _eidolons(card, build, accent, images, (PAD + 8, H - 214))

    # middle: the totals, the light cone, the readings
    x0, x1 = STATS_X, STATS_X + STATS_W
    bottom = H - PAD
    readings_h = 0
    if base.gear_value(build, wanted) or wanted or build.set_bonuses:
        rows = bool(base.gear_value(build, wanted)) + bool(wanted and build.gear)
        readings_h = 16 + 28 * rows + (12 + 19 * min(len(build.set_bonuses), 3) if build.set_bonuses else 0)
        _readings(card, build, (x0, bottom - readings_h, x1, bottom), wanted)
        bottom -= readings_h + 12
    if build.weapon:
        _weapon(card, build, (x0, bottom - 104, x1, bottom), images)
        bottom -= 104 + 12
    _stats(card, build, (x0, PAD, x1, bottom), wanted)

    # right: the relics, two per row
    gear = build.gear[:6]
    gw = (W - PAD - GEAR_X - 12) / 2
    gh = (H - PAD - PAD - 24) / 3
    for i, piece in enumerate(gear):
        gx = GEAR_X + (i % 2) * (gw + 12)
        gy = PAD + (i // 2) * (gh + 12)
        _relic(card, piece, images.get(piece.piece_icon or ""), (round(gx), round(gy), round(gx + gw), round(gy + gh)), accent, wanted)
    if not gear:
        _panel(card, (GEAR_X, PAD, W - PAD, PAD + 80))
        ImageDraw.Draw(card).text((GEAR_X + 20, PAD + 40), "No relics equipped.", font=_raj("SemiBold", 20), fill=DIM, anchor="lm")

    if uid:
        server = base.server_name(build.game, uid)
        foot = f"{server} · UID {uid}" if server else f"UID {uid}"
        if build.source == "hoyolab":
            foot = f"via HoYoLAB · {foot}"
        ImageDraw.Draw(card).text((W - 8, H - 4), foot, font=_raj("Regular", 14), fill=FAINT, anchor="rd")

    out = io.BytesIO()
    card.convert("RGB").save(out, "PNG", compress_level=3)
    return out.getvalue()
