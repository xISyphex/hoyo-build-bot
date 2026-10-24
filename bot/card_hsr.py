"""The Star Rail build card as the Astral Express's navigation hologram: the character projected over a holo pad on
the bridge's star map, the light cone as a projected card, readouts in cyan, and the relics as worlds on a dashed
star-rail route."""
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
DEEP = (2, 16, 26)  # the bridge's dark teal
HOLO = (127, 243, 255)  # the projection's cyan
TEXT = (230, 250, 255)
DIM = (150, 210, 224)
FAINT = (82, 140, 156)
GOLD = (255, 211, 107)  # effective substats: a warm marker light among the cyan
PANEL = (3, 30, 42, 222)
CUT = 16  # the panels' cut corners
PAD = 24
ART_W = 520
STATS_X, STATS_W = 458, 250
GEAR_X = 724
LC_W, LC_H = 150, 210  # the light cone's full art, as a projected card
ROMAN = ("I", "II", "III", "IV", "V", "VI")
PATHS = {"Memory": "Remembrance", "Warrior": "Destruction", "Rogue": "Hunt", "Mage": "Erudition",
         "Shaman": "Harmony", "Warlock": "Nihility", "Knight": "Preservation", "Priest": "Abundance"}


def lc_art_url(build: CharacterBuild) -> str | None:
    """The light cone's full art (StarRailRes's portrait), from its preview picture's address."""
    url = build.weapon.icon_url if build.weapon else None
    return url.replace("/light_cone_preview/", "/light_cone_portrait/") if url and "/light_cone_preview/" in url else None


@functools.lru_cache(maxsize=None)
def _raj(weight: str, size: int):
    return base._font(weight, size)


def _cut(box, c: float = CUT) -> list[tuple[float, float]]:
    """A panel's outline with its top right and bottom left corners cut off, like the bridge's screens."""
    x0, y0, x1, y1 = box
    return [(x0, y0), (x1 - c, y0), (x1, y0 + c), (x1, y1), (x0 + c, y1), (x0, y1 - c)]


def _panel(card: Image.Image, box, fill=PANEL, edge: int = 120, title: str | None = None) -> None:
    """A hologram screen: dark glass with cut corners, a cyan rim, brighter brackets on two corners."""
    x0, y0, x1, y1 = (round(v) for v in box)
    w, h = (x1 - x0) * SS, (y1 - y0) * SS
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    shape = _cut((0, 0, w - 1, h - 1), CUT * SS)
    d.polygon(shape, fill=fill)
    d.line(shape + shape[:1], fill=HOLO + (edge,), width=SS)
    b = 22 * SS  # corner brackets
    d.line(((0, b), (0, 0), (b, 0)), fill=HOLO + (255,), width=2 * SS)
    d.line(((w - 1 - b, h - 1), (w - 1, h - 1), (w - 1, h - 1 - b)), fill=HOLO + (255,), width=2 * SS)
    card.alpha_composite(layer.resize((x1 - x0, y1 - y0), Image.LANCZOS), (x0, y0))
    if title:
        _spaced(ImageDraw.Draw(card), (x0 + 16, y0 + 18), title, _raj("Bold", 12), HOLO, 3.4)


def _spaced(draw, xy, text: str, font, fill, spacing: float = 3.0, anchor: str = "lm") -> float:
    x, y = xy
    for ch in text:
        draw.text((x, y), ch, font=font, fill=fill, anchor=anchor)
        x += draw.textlength(ch, font=font) + spacing
    return x


def _glow_text(card: Image.Image, xy, text: str, font, fill, spacing: float = 0, glow=HOLO, strength: float = 0.5) -> None:
    """Text with a faint halo, like light off a projection."""
    draw = ImageDraw.Draw(card)
    w = round(sum(draw.textlength(ch, font=font) + spacing for ch in text)) + 40
    h = font.size + 40
    mask = Image.new("L", (w, h), 0)
    md = ImageDraw.Draw(mask)
    _spaced(md, (20, 20 + font.size / 2), text, font, 255, spacing)
    halo = Image.new("RGBA", (w, h), glow + (255,))
    halo.putalpha(mask.filter(ImageFilter.GaussianBlur(7)).point(lambda v: round(v * strength)))
    card.alpha_composite(halo, (round(xy[0] - 20), round(xy[1] - 20)))
    _spaced(draw, (xy[0], xy[1] + font.size / 2), text, font, fill, spacing)


def _bridge(build: CharacterBuild) -> Image.Image:
    """The star map: dark teal glass lit from behind the character, a dot grid, a few stars and faint range rings."""
    small = Image.new("RGB", (W // 8, H // 8))
    px = small.load()
    for y in range(small.height):
        for x in range(small.width):
            d = math.hypot((x / small.width - 0.2) * 1.3, y / small.height - 0.55)
            px[x, y] = base._mix((14, 62, 84), DEEP, min(d / 0.6, 1))
    card = small.resize((W, H), Image.BICUBIC).convert("RGBA")
    layer = Image.new("RGBA", (W * 2, H * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for gx in range(0, W * 2, 44):  # the map's dot grid
        for gy in range(0, H * 2, 44):
            d.ellipse((gx - 1.6, gy - 1.6, gx + 1.6, gy + 1.6), fill=HOLO + (26,))
    rng = random.Random(build.character_id)
    for _ in range(110):
        x, y = rng.random() * W * 2, rng.random() * H * 2
        r = rng.choice((1, 1.4, 2, 2.6))
        d.ellipse((x - r, y - r, x + r, y + r), fill=(220, 252, 255, rng.randint(40, 170)))
    for r in (260, 420, 600):  # range rings around the projection
        d.ellipse((440 - r, 1100 - r * 0.42, 440 + r, 1100 + r * 0.42), outline=HOLO + (30,), width=2)
    card.alpha_composite(layer.resize((W, H), Image.LANCZOS))
    return card


def _pad(card: Image.Image, cx: float, cy: float, rx: float, ry: float) -> None:
    """The holo pad the character stands on: a lit ellipse, its rings, and a beam rising from it."""
    k = SS
    w, h = round(rx * 2 + 60), round(ry * 2 + 260)
    layer = Image.new("RGBA", (w * k, h * k), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    ex, ey = w / 2 * k, (h - ry - 30) * k
    beam = Image.new("L", (w * k, h * k), 0)  # the light rising from the pad, fading upwards
    bd = ImageDraw.Draw(beam)
    bd.polygon([(ex - rx * 0.9 * k, ey), (ex + rx * 0.9 * k, ey), (ex + rx * 0.55 * k, 0), (ex - rx * 0.55 * k, 0)], fill=60)
    grad = Image.linear_gradient("L").resize((w * k, h * k))
    beam = ImageChops.multiply(beam, grad)
    shine = Image.new("RGBA", (w * k, h * k), HOLO + (255,))
    shine.putalpha(beam)
    layer.alpha_composite(shine)
    d = ImageDraw.Draw(layer)
    d.ellipse((ex - rx * k, ey - ry * k, ex + rx * k, ey + ry * k), fill=HOLO + (46,), outline=HOLO + (190,), width=2 * k)
    for t, a in ((0.72, 110), (0.44, 80)):
        d.ellipse((ex - rx * t * k, ey - ry * t * k, ex + rx * t * k, ey + ry * t * k), outline=HOLO + (a,), width=k)
    for i in range(36):  # ticks around the rim
        ang = math.radians(i * 10)
        x, y = ex + math.cos(ang) * rx * k, ey + math.sin(ang) * ry * k
        x2, y2 = ex + math.cos(ang) * (rx + 10) * k, ey + math.sin(ang) * (ry + 4) * k
        d.line((x, y, x2, y2), fill=HOLO + (120,), width=k)
    layer = layer.resize((w, h), Image.LANCZOS)
    glow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse((w / 2 - rx, h - ry * 2 - 30, w / 2 + rx, h - 30), fill=HOLO + (90,))
    card.alpha_composite(glow.filter(ImageFilter.GaussianBlur(18)), (round(cx - w / 2), round(cy - (h - ry - 30))))
    card.alpha_composite(layer, (round(cx - w / 2), round(cy - (h - ry - 30))))


def _art(card: Image.Image, art: Image.Image | None) -> None:
    """The character, projected: fading out before the stats and at the very bottom, with scanlines across it and
    a cyan edge light."""
    if art is None:
        return
    art = art.convert("RGBA")
    scale = (H + 20) / art.height
    if art.width * scale < ART_W:
        scale = ART_W / art.width
    art = art.resize((round(art.width * scale), round(art.height * scale)), Image.LANCZOS)
    left = max((art.width - ART_W) // 2, 0)
    art = art.crop((left, 0, left + ART_W, H))
    fade = Image.new("L", (ART_W, H))
    fp = fade.load()
    for x in range(ART_W):
        fx = min(1, max(0, (ART_W - 30 - x) / 140))
        for y in range(0, H, 4):
            fy = min(1, max(0, (H - 10 - y) / 70))
            v = round(255 * fx * fy)
            for dy in range(4):
                if y + dy < H:
                    fp[x, y + dy] = v
    alpha = ImageChops.multiply(art.getchannel("A"), fade)
    lines = Image.new("L", (ART_W, H), 255)  # the projection's scanlines
    ld = ImageDraw.Draw(lines)
    for y in range(0, H, 3):
        ld.line((0, y, ART_W, y), fill=214)
    art.putalpha(ImageChops.multiply(alpha, lines))
    rim = Image.new("RGBA", art.size, HOLO + (255,))  # a cyan light hugging the outline
    rim.putalpha(alpha.filter(ImageFilter.GaussianBlur(9)).point(lambda v: round(v * 0.35)))
    card.alpha_composite(rim, (-40, 0))
    card.alpha_composite(art, (-40, 0))


def _symbol(icon: Image.Image | None, size: int) -> Image.Image | None:
    if icon is None:
        return None
    icon = icon.convert("RGBA")
    icon = icon.crop(icon.getchannel("A").getbbox() or (0, 0, icon.width, icon.height))
    k = size / max(icon.size)
    return icon.resize((max(1, round(icon.width * k)), max(1, round(icon.height * k))), Image.LANCZOS)


def _path_name(build: CharacterBuild) -> str:
    stem = (build.path_icon or "").rsplit("/", 1)[-1].rsplit(".", 1)[0]
    return PATHS.get(stem, stem).upper()


def _hexagon(cx: float, cy: float, r: float) -> list[tuple[float, float]]:
    return [(cx + r * math.cos(math.radians(a)), cy + r * math.sin(math.radians(a))) for a in range(0, 360, 60)]


def _header(card: Image.Image, build: CharacterBuild, accent, images) -> None:
    """The name, a status line (element, level, eidolon, Path) and the six eidolons as hex chips."""
    shade = Image.new("RGBA", (W, 190), (0, 0, 0, 0))  # keeps the header readable over bright art
    sd = ImageDraw.Draw(shade)
    for y in range(190):
        sd.line((0, y, STATS_X, y), fill=DEEP + (round(190 * (1 - y / 190) ** 1.4),))
    card.alpha_composite(shade)
    draw = ImageDraw.Draw(card)
    name = build.name.upper()
    for size, spacing in ((50, 7), (44, 6), (38, 5), (32, 4), (28, 3)):
        font = _raj("Bold", size)
        if sum(draw.textlength(ch, font=font) + spacing for ch in name) <= STATS_X - PAD - 20:
            break
    _glow_text(card, (PAD + 4, 16), name, font, (255, 255, 255), spacing, HOLO, 0.55)
    y = 16 + font.size + 20
    x = PAD + 6
    for icon in (_symbol(images.get(build.element_icon or ""), 24), _symbol(images.get(build.path_icon or ""), 22)):
        if icon is not None:
            card.alpha_composite(icon, (round(x), round(y - icon.height / 2)))
            x += icon.width + 8
    draw = ImageDraw.Draw(card)
    meta = _raj("SemiBold", 17)
    # the element and Path symbols say which they are; the element's name only when its symbol is missing
    parts = [(build.element.upper() if build.element_icon not in images else "", base._mix(accent, TEXT, 0.4)),
             (f"LV. {build.level}", TEXT), (f"E{build.constellation}", GOLD), (_path_name(build), DIM)]
    for i, (text, color) in enumerate(p for p in parts if p[0]):
        if i:
            draw.text((x + 6, y), "·", font=meta, fill=FAINT, anchor="lm")
            x += 16
        x = _spaced(draw, (x, y), text, meta, color, 1.6) + 2
    stars = Image.new("RGBA", ((build.rarity * 16 + 8) * SS, 16 * SS), (0, 0, 0, 0))  # the rarity, as small stars
    for i in range(build.rarity):
        base._star(ImageDraw.Draw(stars), (8 + i * 16) * SS, 8 * SS, 7 * SS, GOLD + (255,))
    card.alpha_composite(stars.resize((stars.width // SS, 16), Image.LANCZOS), (round(x + 8), round(y - 8)))
    _eidolon_chips(card, build, accent, images, PAD + 24, y + 42)


def _eidolon_chips(card: Image.Image, build: CharacterBuild, accent, images, x: float, cy: float) -> None:
    """Six hex chips holding the eidolon icons: unlocked ones lit solid cyan, the rest outlined."""
    n = max(0, min(build.constellation, 6))
    r, step = 21, 48
    k = SS
    layer = Image.new("RGBA", ((step * 6 + 20) * k, (2 * r + 20) * k), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    glow = Image.new("RGBA", (step * 6 + 20, 2 * r + 20), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    for i in range(6):
        hx, hy = (10 + r + i * step) * k, (10 + r) * k
        pts = _hexagon(hx, hy, r * k)
        if i < n:
            d.polygon(pts, fill=base._mix(HOLO, DEEP, 0.35) + (255,), outline=HOLO + (255,))
            gd.polygon(_hexagon(10 + r + i * step, 10 + r, r), fill=HOLO + (150,))
        else:
            d.polygon(pts, fill=(3, 30, 42, 200))
            d.line(pts + pts[:1], fill=HOLO + (90,), width=k)
    card.alpha_composite(glow.filter(ImageFilter.GaussianBlur(6)), (round(x - 10 - r), round(cy - 10 - r)))
    card.alpha_composite(layer.resize(glow.size, Image.LANCZOS), (round(x - 10 - r), round(cy - 10 - r)))
    icons = [images.get(u) for u in build.cons_icons[:6]] + [None] * 6
    for i in range(6):
        hx = x + i * step
        icon = icons[i]
        if icon is None:
            ImageDraw.Draw(card).text((hx, cy), ROMAN[i], font=_raj("Bold", 15), fill=DEEP if i < n else FAINT, anchor="mm")
            continue
        mark = icon.convert("RGBA").resize((28, 28), Image.LANCZOS)
        alpha = mark.getchannel("A")
        grey = mark.convert("L")
        if i < n:  # dark line art on the lit chip
            g = grey.point(lambda v: round(20 + v * 0.12))
            mark = Image.merge("RGBA", (g, g.point(lambda v: v + 14), g.point(lambda v: v + 22), alpha))
        else:
            g = grey.point(lambda v: round(v * 0.5))
            mark = Image.merge("RGBA", (g, g, g, alpha.point(lambda a: round(a * 0.6))))
        card.alpha_composite(mark, (round(hx - 14), round(cy - 14)))


def _light_cone(card: Image.Image, build: CharacterBuild, images, box) -> None:
    """The light cone's full art as a projected card on the left, its name, superimposition, level and stats on a
    plate beside it."""
    w = build.weapon
    x0, y0, x1, y1 = box
    art = images.get(lc_art_url(build) or "") or images.get(w.icon_url or "")
    cx0, cy0 = x0, y1 - LC_H
    plate = (x0 + LC_W - 8, y1 - 104, x1, y1)
    _panel(card, plate)
    if art is not None:
        pic = art.convert("RGBA")
        pic.thumbnail((LC_W - 12, LC_H - 12), Image.LANCZOS)
        frame = Image.new("RGBA", (LC_W, LC_H), (0, 0, 0, 0))
        fd = ImageDraw.Draw(frame)
        fd.rectangle((0, 0, LC_W - 1, LC_H - 1), fill=(3, 30, 42, 235))
        frame.alpha_composite(pic, ((LC_W - pic.width) // 2, (LC_H - pic.height) // 2))
        lines = Image.new("L", frame.size, 255)
        ld = ImageDraw.Draw(lines)
        for y in range(0, LC_H, 3):
            ld.line((0, y, LC_W, y), fill=226)
        frame.putalpha(ImageChops.multiply(frame.getchannel("A"), lines))
        fd = ImageDraw.Draw(frame)
        fd.rectangle((0, 0, LC_W - 1, LC_H - 1), outline=HOLO + (200,), width=1)
        for (ax, ay), (bx, by), (ex, ey) in (((0, 18), (0, 0), (18, 0)), ((LC_W - 19, LC_H - 1), (LC_W - 1, LC_H - 1), (LC_W - 1, LC_H - 19))):
            fd.line(((ax, ay), (bx, by), (ex, ey)), fill=HOLO + (255,), width=2)
        glow = Image.new("RGBA", (LC_W + 40, LC_H + 40), (0, 0, 0, 0))
        ImageDraw.Draw(glow).rectangle((20, 20, LC_W + 20, LC_H + 20), fill=HOLO + (70,))
        card.alpha_composite(glow.filter(ImageFilter.GaussianBlur(12)), (cx0 - 20, cy0 - 20))
        card.alpha_composite(frame, (cx0, cy0))
    draw = ImageDraw.Draw(card)
    tx, room = plate[0] + 22, plate[2] - plate[0] - 34
    name_font = _raj("Bold", 18)
    lines_ = base._wrap(draw, w.name, name_font, room, 2)
    y = plate[1] + 22
    for line in lines_:
        draw.text((tx, y), line, font=name_font, fill=TEXT, anchor="lm")
        y += 21
    _spaced(draw, (tx, y + 1), f"S{w.refinement} · LV. {w.level}", _raj("Bold", 14), HOLO, 1.4)
    y += 21
    stats = "  ".join(f"{_name(s)} {s.value}" for s in w.stats)
    draw.text((tx, y + 1), base._fit_text(draw, stats, _raj("Regular", 14), room), font=_raj("Regular", 14), fill=DIM, anchor="lm")


def _telemetry(card: Image.Image, build: CharacterBuild, box, wanted: set[str] | None) -> None:
    """The character's totals: each a row with its icon, and a thin light trace underneath."""
    _panel(card, box, title="TELEMETRY")
    x0, y0, x1, y1 = box
    stats = [s for s in build.stats if not _is_zero(s.value)]
    wanted_totals = {base.TOTAL_NAMES.get(n, n.rstrip("%")) for n in wanted or ()}
    top = y0 + 32
    row = min(44, (y1 - 8 - top) / max(len(stats), 1))
    name_font, small_font, value_font = _raj("SemiBold", 18), _raj("SemiBold", 15), _raj("Bold", 21)
    traces = Image.new("RGBA", (x1 - x0, y1 - y0), (0, 0, 0, 0))
    td = ImageDraw.Draw(traces)
    for i in range(len(stats)):
        ty = round(top + row * (i + 1) - 3 - y0)
        for x in range(14, x1 - x0 - 14):
            a = round(110 * max(0, 1 - (x - 14) / ((x1 - x0) * 0.75)))
            if a:
                td.point((x, ty), fill=HOLO + (a,))
    card.alpha_composite(traces, (x0, y0))
    draw = ImageDraw.Draw(card)
    for i, s in enumerate(stats):
        mid = top + row * (i + 0.5) - 1
        name = _name(s)
        good = s.name in wanted_totals
        dmg = ELEMENT_COLORS.get(name.split(" ")[0])
        orb = (dmg >> 16 & 255, dmg >> 8 & 255, dmg & 255) if dmg else HOLO
        card.alpha_composite(stat_icons.icon(name, 16, GOLD if good else HOLO, orb), (x0 + 14, round(mid - 8)))
        draw = ImageDraw.Draw(card)
        room = x1 - 14 - (x0 + 38) - 8 - draw.textlength(s.value, font=value_font)
        font = name_font if draw.textlength(name, font=name_font) <= room else small_font
        draw.text((x0 + 38, mid), base._fit_text(draw, name, font, room), font=font, fill=GOLD if good else DIM, anchor="lm")
        draw.text((x1 - 14, mid), s.value, font=value_font, fill=GOLD if good else TEXT, anchor="rm")


def _readout(card: Image.Image, build: CharacterBuild, box, wanted: set[str] | None) -> None:
    """Crit Value (or the value the character lives on), the effective substat count and the relic sets."""
    _panel(card, box)
    x0, y0, x1, y1 = box
    draw = ImageDraw.Draw(card)
    value = base.gear_value(build, wanted)
    effective = sum(piece_count(p, wanted) for p in build.gear) if wanted and build.gear else None
    y = y0 + 22
    rows = [r for r in ((value[0], value[1], TEXT) if value else None,
                        ("EFFECTIVE SUBS", str(effective), GOLD) if effective is not None else None) if r]
    for label, text, color in rows:
        _spaced(draw, (x0 + 16, y), label, _raj("Bold", 13), DIM, 2)
        draw.text((x1 - 16, y), text, font=_raj("Bold", 24), fill=color, anchor="rm")
        y += 28
    sets = build.set_bonuses[:3]
    if sets:
        if rows:
            draw.line((x0 + 14, y - 8, x1 - 14, y - 8), fill=HOLO + (40,), width=1)
            y += 4
        for line in sets:
            count, _, name = line.partition(" ")
            draw.text((x0 + 16, y), count, font=_raj("Bold", 15), fill=HOLO, anchor="lm")
            cw = draw.textlength(count, font=_raj("Bold", 15)) + 6
            draw.text((x0 + 16 + cw, y), base._fit_text(draw, name, _raj("SemiBold", 15), x1 - x0 - 32 - cw),
                      font=_raj("SemiBold", 15), fill=TEXT, anchor="lm")
            y += 19


def _readout_h(build: CharacterBuild, wanted: set[str] | None) -> int:
    rows = bool(base.gear_value(build, wanted)) + bool(wanted and build.gear)
    sets = min(len(build.set_bonuses), 3)
    return (8 + 28 * rows + (4 if rows and sets else 0) + 19 * sets + 8) if rows or sets else 0


def _route(card: Image.Image, centres: list[tuple[float, float]]) -> None:
    """The dashed star-rail route joining the relics' worlds in order, drawn under their panels."""
    k = SS
    layer = Image.new("RGBA", (W * k, H * k), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for (ax, ay), (bx, by) in zip(centres, centres[1:]):
        dist = math.dist((ax, ay), (bx, by))
        steps = max(int(dist / 7), 1)
        for s in range(0, steps, 2):
            t0, t1 = s / steps, min((s + 1) / steps, 1)
            d.line(((ax + (bx - ax) * t0) * k, (ay + (by - ay) * t0) * k, (ax + (bx - ax) * t1) * k, (ay + (by - ay) * t1) * k),
                   fill=HOLO + (120,), width=2 * k)
    card.alpha_composite(layer.resize((W, H), Image.LANCZOS))


def _world(card: Image.Image, piece: Gear, icon: Image.Image | None, box, wanted: set[str] | None) -> None:
    """One relic as a world on the route: its picture in a dashed ring, the main stat, and the substats with a small
    marker per upgrade. Wanted substats are lit gold and their rolls are counted in the corner."""
    _panel(card, box)
    x0, y0, x1, y1 = box
    k = SS
    d = 58
    ring = Image.new("RGBA", ((d + 8) * k, (d + 8) * k), (0, 0, 0, 0))
    rd = ImageDraw.Draw(ring)
    c = ring.width / 2
    rd.ellipse((c - d / 2 * k, c - d / 2 * k, c + d / 2 * k, c + d / 2 * k), fill=HOLO + (16,))
    for a in range(0, 360, 12):  # dashed rim
        rd.arc((c - d / 2 * k, c - d / 2 * k, c + d / 2 * k, c + d / 2 * k), a, a + 7, fill=HOLO + (230,), width=k)
    ring = ring.resize((d + 8, d + 8), Image.LANCZOS)
    rx, ry = x0 + 10, y0 + 10
    card.alpha_composite(ring, (rx, ry))
    base._icon(card, icon, (rx + 10, ry + 10, rx + d - 2, ry + d - 2))
    draw = ImageDraw.Draw(card)
    tx = rx + d + 16
    label = _name(piece.main).upper()
    while label and sum(draw.textlength(ch, font=_raj("Bold", 12)) + 1.4 for ch in label) > x1 - tx - 44:
        label = label[:-1]  # clear of the effective count in the corner
    _spaced(draw, (tx, y0 + 26), label, _raj("Bold", 12), DIM, 1.4)
    draw.text((tx, y0 + 50), piece.main.value, font=_raj("Bold", 27), fill=TEXT, anchor="lm")
    if piece.level < base.GAME_LABELS["hsr"]["max_level"]:
        lx = tx + draw.textlength(piece.main.value, font=_raj("Bold", 27)) + 8
        draw.text((lx, y0 + 54), f"+{piece.level}", font=_raj("SemiBold", 14), fill=FAINT, anchor="lm")
    if wanted and piece.subs:
        count = piece_count(piece, wanted)
        draw.text((x1 - 20, y0 + 22), str(count), font=_raj("Bold", 20), fill=GOLD if count else FAINT, anchor="rm")
    y = y0 + d + 22
    rows = piece.subs[:4]
    step = min(34, (y1 - 8 - y) / max(len(rows), 1))
    name_font, name_b, value_font = _raj("SemiBold", 16), _raj("Bold", 16), _raj("Bold", 18)
    marks = Image.new("RGBA", ((x1 - x0) * k, (y1 - y0) * k), (0, 0, 0, 0))
    md = ImageDraw.Draw(marks)
    for i, s in enumerate(rows):
        mid = y + step * (i + 0.5)
        good = bool(wanted) and s.name in wanted
        color = GOLD if good else TEXT
        draw = ImageDraw.Draw(card)
        draw.line((x0 + 12, mid - step / 2, x1 - 12, mid - step / 2), fill=HOLO + (34,), width=1)
        vw = draw.textlength(s.value, font=value_font)
        upgrades = min(max(s.rolls - 1, 0), 5)
        label = base._fit_text(draw, _name(s), name_b if good else name_font, x1 - 14 - vw - upgrades * 8 - 14 - (x0 + 14))
        draw.text((x0 + 14, mid), label, font=name_b if good else name_font, fill=GOLD if good else DIM, anchor="lm")
        draw.text((x1 - 14, mid), s.value, font=value_font, fill=color, anchor="rm")
        mx = x1 - 14 - vw - 10
        for _ in range(upgrades):  # small upward triangles, one per upgrade
            px, py = (mx - x0) * k, (mid - y0) * k
            md.polygon([(px, py - 4 * k), (px + 3.4 * k, py + 2.6 * k), (px - 3.4 * k, py + 2.6 * k)], fill=(GOLD if good else HOLO) + (255,))
            mx -= 8
    card.alpha_composite(marks.resize((x1 - x0, y1 - y0), Image.LANCZOS), (x0, y0))


def draw_card(build: CharacterBuild, images: dict[str, Image.Image], uid: str | None = None,
              wanted: set[str] | None = None, face=None) -> bytes:
    base.FONTS = base.FONTS or base.Fonts()
    accent = base._accent(build)
    card = _bridge(build)
    _pad(card, 300, 566, 150, 30)  # above the light cone's plate
    _art(card, images.get(build.art_url or "") or images.get(build.icon_url or ""))
    _header(card, build, accent, images)
    if build.weapon:
        _light_cone(card, build, images, (PAD, H - PAD - LC_H, STATS_X - 14, H - PAD))

    # middle: the telemetry and the readout under it
    x0, x1 = STATS_X, STATS_X + STATS_W
    rh = _readout_h(build, wanted)
    bottom = H - PAD
    if rh:
        _readout(card, build, (x0, bottom - rh, x1, bottom), wanted)
        bottom -= rh + 12
    _telemetry(card, build, (x0, PAD, x1, bottom), wanted)

    # right: the relics as worlds on the route, staggered a little like stops on a map
    gear = build.gear[:6]
    gw = (W - PAD - GEAR_X - 14) / 2
    gh = (H - 2 * PAD - 2 * 12 - 14) / 3
    boxes = []
    for i in range(len(gear)):
        col, row = i % 2, i // 2
        gx = GEAR_X + col * (gw + 14)
        gy = PAD + row * (gh + 12) + (14 if col else 0)
        boxes.append((round(gx), round(gy), round(gx + gw), round(gy + gh)))
    order = [0, 1, 3, 2, 4, 5][:len(boxes)]  # a zigzag, like a route between worlds
    _route(card, [(boxes[i][0] + 44, boxes[i][1] + 44) for i in order if i < len(boxes)])
    for piece, box in zip(gear, boxes):
        _world(card, piece, images.get(piece.piece_icon or ""), box, wanted)
    if not gear:
        _panel(card, (GEAR_X, PAD, W - PAD, PAD + 80))
        ImageDraw.Draw(card).text((GEAR_X + 20, PAD + 44), "No relics equipped.", font=_raj("SemiBold", 20), fill=DIM, anchor="lm")

    if uid:
        server = base.server_name(build.game, uid)
        foot = f"{server} · UID {uid}" if server else f"UID {uid}"
        if build.source == "hoyolab":
            foot = f"via HoYoLAB · {foot}"
        ImageDraw.Draw(card).text((W - 8, H - 3), foot.upper(), font=_raj("SemiBold", 13), fill=FAINT, anchor="rd")

    out = io.BytesIO()
    card.convert("RGB").save(out, "PNG", compress_level=3)
    return out.getvalue()
