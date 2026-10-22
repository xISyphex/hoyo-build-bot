"""The ZZZ build card as a retro dashboard: a CRT monitor with the agent, a VFD nameplate, the Mindscape screen,
two dial gauges, a stat readout, the W-Engine module and six disc cartridges."""
from __future__ import annotations

import functools
import io

from PIL import Image, ImageChops, ImageDraw, ImageFilter

from . import card as base
from . import stat_icons
from .effective import piece_count
from .embeds import ELEMENT_COLORS, ZZZ_RARITY, _is_zero, _name
from .models import CharacterBuild, Gear

W, H = base.W, base.H
BODY = (30, 28, 38)  # the console's plastic
BODY_DARK = (17, 16, 23)
GLASS = (7, 7, 11)  # the dark screens set into it
SILK = (150, 146, 168)  # silkscreen labels printed on the console
AMBER = (255, 184, 64)  # effective substats, like an amber warning lamp
TEAL = base.TEAL
SS = 4

# The most each dial can show: every roll of a fully upgraded S-rank set in that stat. Crit Value: 41 crit rolls
# (both crit substats on every disc, with all five upgrades, but only one beside a crit main on disc 4) at 4.8 each,
# plus the 48% CRIT DMG main stat (Syphex). The others count the substat roll and the best main stats the same way.
VALUE_MAX = {"CRIT VALUE": 4.8 * 41 + 48, "AP VALUE": 9 * 30 + 92, "ATK VALUE": 3 * 18 + 90, "HP VALUE": 3 * 18 + 90,
             "DEF VALUE": 4.8 * 18 + 144, "ENERGY VALUE": 60}
SUBSTATS = {"HP", "ATK", "DEF", "HP%", "ATK%", "DEF%", "CRIT Rate", "CRIT DMG", "PEN", "AP"}
# Main stats on each disc slot; a substat can't be the same as its disc's main stat
MAINS = {1: ["HP"], 2: ["ATK"], 3: ["DEF"], 4: ["HP%", "ATK%", "DEF%", "CRIT Rate", "CRIT DMG", "AP"],
         5: ["HP%", "ATK%", "DEF%", "PEN Ratio", "DMG Bonus"], 6: ["HP%", "ATK%", "DEF%", "AM", "Impact", "ER"]}
UPGRADES = 5  # a disc's upgrades on the way to +15, each adding a roll to one of its four substats


def value_fraction(label: str, text: str) -> float:
    """How full the value gauge is: the value (like "100.8" or "100.0%") over its best possible total."""
    top = VALUE_MAX.get(label)
    try:
        amount = float(text.rstrip("%").replace(",", ""))
    except ValueError:
        return 0
    return min(max(amount / top, 0), 1) if top else 0


def effective_max(wanted: set[str]) -> int:
    """The most effective rolls a set of six discs can have: on each disc, as many wanted substats as fit beside
    the best main stat for it, each with its first roll, and every upgrade going into one of them."""
    total = 0
    for options in MAINS.values():
        fit = max(min(4, len((wanted & SUBSTATS) - {main})) for main in options)
        total += fit + UPGRADES if fit else 0
    return total


@functools.lru_cache(maxsize=None)
def _rubik(size: int, weight: int = 700, italic: bool = False):
    """Rubik (OFL), a free stand-in for ZZZ's in-game type: heavy, geometric, with softly rounded corners."""
    name = "Rubik-Italic-Variable.ttf" if italic else "Rubik-Variable.ttf"
    try:
        font = base.ImageFont.truetype(str(base.FONT_DIR / name), size)
        font.set_variation_by_axes([weight])
        return font
    except OSError:
        return base.ImageFont.load_default(size)


class Fonts:
    def __init__(self) -> None:
        self.name = {s: _rubik(s, 800) for s in (40, 36, 32, 28)}
        self.big = _rubik(34, 700)
        self.mid = _rubik(24, 700)
        self.mid_i = _rubik(24, 800, True)
        self.read = _rubik(21, 600)
        self.sub = _rubik(18, 600)
        self.small = _rubik(16, 600)
        self.tiny = _rubik(13, 600)
        self.silk = _rubik(11, 700)
        self.label = _rubik(15, 600)
        self.slot = _rubik(13, 700)
        self.plate = _rubik(10, 600)
        self.plate_s = _rubik(9, 600)
        self.count = _rubik(14, 700)


FONTS: Fonts | None = None


def _text(card: Image.Image, xy, text: str, font, color, anchor: str = "la") -> None:
    ImageDraw.Draw(card).text(xy, text, font=font, fill=color, anchor=anchor)


def _bezel(card: Image.Image, box, r: int = 12, inset: int = 6, screen=GLASS, bump=None) -> tuple[int, int, int, int]:
    """A panel cut into the console: a raised rim lit from above, and a dark screen inside it. Returns the screen.
    bump: (cx, cy, radius) of a round housing the rim grows out to, one outline with the panel's (the screen stays
    clear of it)."""
    x0, y0, x1, y1 = box
    if bump:
        bx, by, br = bump
        pad = 12  # room for the fillet blur, so the layer's edge never flattens the circle
        x0, y0, x1, y1 = min(x0, round(bx - br) - pad), min(y0, round(by - br) - pad), max(x1, round(bx + br) + pad), max(y1, round(by + br) + pad)
    w, h = (x1 - x0) * SS, (y1 - y0) * SS
    px0, py0, px1, py1 = ((v - o) * SS for v, o in zip(box, (x0, y0, x0, y0)))

    def shape(grow: float, dy: float = 0) -> Image.Image:
        """The rim's outline shrunk by grow: the rounded panel, joined to the bump with a smooth curve."""
        m = Image.new("L", (w, h), 0)
        d = ImageDraw.Draw(m)
        d.rounded_rectangle((px0 + grow, py0 + grow + dy, px1 - 1 - grow, py1 - 1 - grow), max(r * SS - grow, 1), fill=255)
        if bump:
            cx, cy, rr = (bx - x0) * SS, (by - y0) * SS + dy, br * SS - grow
            d.ellipse((cx - rr, cy - rr, cx + rr, cy + rr), fill=255)
            exact = m.copy()  # the blur only fills the inner corners; the outer edges stay exactly round and straight
            fillet = m.filter(ImageFilter.GaussianBlur(5 * SS)).point(lambda v: 255 if v > 110 else 0)
            m = ImageChops.lighter(exact, fillet)
        return m

    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    outline = shape(0)
    layer.paste((48, 46, 60, 255), (0, 0), outline)
    layer.paste((12, 11, 16, 255), (0, 0), ImageChops.multiply(outline, shape(0, 2 * SS)))  # shadowed lower edge
    layer.paste((36, 34, 46, 255), (0, 0), shape(SS))
    i = inset * SS
    hole = Image.new("L", (w, h), 0)
    ImageDraw.Draw(hole).rounded_rectangle((px0 + i, py0 + i, px1 - 1 - i, py1 - 1 - i), max(r - inset, 3) * SS, fill=255)
    if bump:
        ImageDraw.Draw(hole).ellipse(((bx - x0 - br) * SS, (by - y0 - br) * SS, (bx - x0 + br) * SS, (by - y0 + br) * SS), fill=0)
    layer.paste(screen + (255,), (0, 0), hole)
    card.alpha_composite(layer.resize((x1 - x0, y1 - y0), Image.LANCZOS), (x0, y0))
    bx0, by0, bx1, by1 = box
    return bx0 + inset, by0 + inset, bx1 - inset, by1 - inset


def _scanlines(card: Image.Image, box, alpha: int = 40) -> None:
    x0, y0, x1, y1 = box
    lines = Image.new("RGBA", (x1 - x0, y1 - y0), (0, 0, 0, 0))
    d = ImageDraw.Draw(lines)
    for y in range(0, y1 - y0, 3):
        d.line((0, y, x1 - x0, y), fill=(0, 0, 0, alpha))
    card.alpha_composite(lines, (x0, y0))


def _screw(card: Image.Image, cx: int, cy: int) -> None:
    layer = Image.new("RGBA", (14 * SS, 14 * SS), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.ellipse((0, 0, 14 * SS - 1, 14 * SS - 1), fill=(14, 13, 19, 255))
    d.ellipse((SS, SS, 13 * SS - 1, 13 * SS - 1), fill=(70, 68, 84, 255))
    d.line((3 * SS, 10 * SS, 10 * SS, 3 * SS), fill=(20, 18, 26, 255), width=SS * 2)
    card.alpha_composite(layer.resize((14, 14), Image.LANCZOS), (cx - 7, cy - 7))


def _silk(draw: ImageDraw.ImageDraw, xy, text: str, color=SILK, centre: bool = False) -> None:
    """A small letter-spaced label, as if printed on the console."""
    x, y = xy
    if centre:
        x -= (sum(draw.textlength(ch, font=FONTS.silk) for ch in text) + 2.4 * (len(text) - 1)) / 2
    base._spaced(draw, (x, y), text, FONTS.silk, color, 2.4, "ls")


def _console() -> Image.Image:
    """The console body: dark plastic with a faint grain, and a screw in each corner."""
    card = Image.new("RGBA", (W, H), BODY + (255,))
    grad = Image.linear_gradient("L").resize((W, H))
    dark = Image.new("RGBA", (W, H), BODY_DARK + (255,))
    card = Image.composite(dark, card, grad)
    noise = Image.effect_noise((W // 2, H // 2), 18).resize((W, H)).point(lambda v: max(0, v - 128) // 6)
    card.alpha_composite(Image.merge("RGBA", (noise, noise, noise, noise)))
    for x, y in ((9, 13), (W - 9, 13), (9, H - 9), (W - 9, H - 9)):
        _screw(card, x, y)
    return card


def _monitor(card: Image.Image, art: Image.Image | None, face, box, accent, bump=None) -> None:
    """The agent on a CRT: a head close-up when the face is known, scanlines and a dark vignette on the glass.
    bump: a round housing grown out of the frame (see _bezel); the glass stops short of it."""
    sx0, sy0, sx1, sy1 = _bezel(card, box, 18, 10, (10, 10, 18), bump)
    w, h = sx1 - sx0, sy1 - sy0
    glass = Image.new("RGBA", (w, h), (12, 12, 22, 255))
    # a faint glow of the element colour behind the agent
    glow = Image.radial_gradient("L").resize((w, h)).point(lambda v: 255 - v)
    glass.alpha_composite(Image.merge("RGBA", (*Image.new("RGB", (w, h), accent).split(), glow.point(lambda v: v // 4))))
    if art is not None:
        art = art.convert("RGBA")
        if face:
            fx, fy, size = face
            k = size / 200  # picture pixels per screen pixel: the face is about 200 px across
            left, top = fx - w * 0.5 * k, fy - h * 0.42 * k
            pic = art.crop((round(left), round(top), round(left + w * k), round(top + h * k))).resize((w, h), Image.LANCZOS)
            if k < 1:
                pic = pic.filter(ImageFilter.UnsharpMask(radius=1.2, percent=60, threshold=2))
        else:
            scale = max(w / art.width, (h + 40) / art.height)
            pic = art.resize((round(art.width * scale), round(art.height * scale)), Image.LANCZOS)
            left = (pic.width - w) // 2
            pic = pic.crop((left, 0, left + w, h))
        glass.alpha_composite(pic)
    vignette = Image.radial_gradient("L").resize((w, h)).point(lambda v: max(0, v - 90) * 255 // 165)
    glass.alpha_composite(Image.merge("RGBA", (*Image.new("RGB", (w, h), (0, 0, 0)).split(), vignette.point(lambda v: v * 3 // 4))))
    mask = Image.new("L", (w * SS, h * SS), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, w * SS - 1, h * SS - 1), 22 * SS, fill=255)
    if bump:
        bx, by, br = ((bump[0] - sx0) * SS, (bump[1] - sy0) * SS, bump[2] * SS)
        ImageDraw.Draw(mask).ellipse((bx - br, by - br, bx + br, by + br), fill=0)
    glass.putalpha(mask.resize((w, h), Image.LANCZOS))
    lines = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    _scanlines(lines, (0, 0, w, h), 34)
    glass.alpha_composite(lines)  # on the glass only, not on the housing
    glass.putalpha(mask.resize((w, h), Image.LANCZOS))
    card.alpha_composite(glass, (sx0, sy0))
    # a glare across the top left of the glass
    glare = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(glare).ellipse((-w * 0.4, -h * 0.5, w * 0.7, h * 0.35), fill=(255, 255, 255, 14))
    card.alpha_composite(glare.filter(ImageFilter.GaussianBlur(20)), (sx0, sy0))


def _lamp(card: Image.Image, symbol: Image.Image, cx: float, cy: float, color) -> None:
    """A dashboard warning lamp: a round dark socket with the symbol lit up in one colour, glowing. Drawn on one
    supersampled tile so the symbol sits exactly in the socket's middle."""
    k, half = SS, 22
    n = 2 * half * k
    tile = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    ImageDraw.Draw(tile).ellipse((n / 2 - 16 * k, n / 2 - 16 * k, n / 2 + 16 * k, n / 2 + 16 * k), fill=(4, 4, 7, 255),
                                 outline=(50, 48, 64, 255), width=k)
    im = symbol.convert("RGBA")
    im = im.crop(im.getchannel("A").point(lambda v: 255 if v > 40 else 0).getbbox() or (0, 0, *im.size))
    scale = 20 * k / max(im.size)  # fit 20 x 20, growing small icons too
    im = im.resize((max(1, round(im.width * scale)), max(1, round(im.height * scale))), Image.LANCZOS)
    lit = Image.new("RGBA", im.size, color + (255,))
    lit.putalpha(im.getchannel("A"))
    glow = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    glow.alpha_composite(lit, ((n - im.width) // 2, (n - im.height) // 2))
    halo = glow.filter(ImageFilter.GaussianBlur(4 * k))
    tile.alpha_composite(halo)
    tile.alpha_composite(halo)
    tile.alpha_composite(glow)
    card.alpha_composite(tile.resize((2 * half, 2 * half), Image.LANCZOS), (round(cx) - half, round(cy) - half))


RANK_LAMP = (382, 410, 26)  # the rank lamp's centre and glass radius, on the monitor's bottom right corner
RANK_HOUSING = 9  # the frame round the lamp's glass
BLOCK_LETTERS = {  # squared rank letters on a 10 x 12 grid with chamfered corners: an outline, then any holes
    "A": ([(2, 0), (8, 0), (10, 2), (10, 12), (7, 12), (7, 8), (3, 8), (3, 12), (0, 12), (0, 2)], [(3, 3), (7, 3), (7, 5.5), (3, 5.5)]),
    "S": ([(2, 0), (10, 0), (10, 3), (3, 3), (3, 4.5), (8, 4.5), (10, 6.5), (10, 10), (8, 12), (0, 12), (0, 9), (7, 9),
           (7, 7.5), (2, 7.5), (0, 5.5), (0, 2)],),
}
RANK_GLASS = {  # per rank: the ring under the glass, each colour channel's (centre value, fall-off divisor) and the ink
    "S": ((40, 30, 10, 255), ((255, 8), (240, 3), (140, 2)), (90, 44, 0, 235)),
    "A": ((30, 14, 44, 255), ((225, 4), (170, 2), (255, 8)), (52, 12, 86, 235)),
}


def _rank_lamp(card: Image.Image, build: CharacterBuild, cx: float, cy: float, r: float = 26) -> None:
    """The rank as a big dome lamp set into the monitor's frame: a glowing glass dome (gold for S, purple for A)
    with a shine on it and the letter printed on the glass in italics."""
    k = SS
    size = round(2 * r + 12)
    c = size * k / 2
    layer = Image.new("RGBA", (size * k, size * k), (0, 0, 0, 0))
    dome = r * k

    def disc(radius, fill, dx=0, dy=0):
        ImageDraw.Draw(layer).ellipse((c - radius + dx, c - radius + dy, c + radius + dx, c + radius + dy), fill=fill)

    letter = ZZZ_RARITY.get(build.rarity, "?")
    ring, tint, ink = RANK_GLASS.get(letter, RANK_GLASS["S"])
    disc(dome + 2 * k, ring)
    # the glass dome: bright in the middle, deeper towards its edge
    glass = Image.radial_gradient("L").resize((round(2 * dome),) * 2)
    lens = Image.merge("RGBA", tuple(glass.point(lambda v, top=top, fall=fall: top - v // fall) for top, fall in tint)
                       + (Image.new("L", glass.size, 0),))
    lmask = Image.new("L", glass.size, 0)
    ImageDraw.Draw(lmask).ellipse((0, 0, glass.width - 1, glass.height - 1), fill=255)
    lens.putalpha(lmask)
    layer.alpha_composite(lens, (round(c - dome), round(c - dome)))
    text = Image.new("RGBA", layer.size, (0, 0, 0, 0))
    shape = BLOCK_LETTERS.get(letter)
    if shape:  # a squared block letter, 10 x 12 units, centred on the glass
        u = r * 0.075 * k
        outer, *holes = shape
        mask = Image.new("L", layer.size, 0)
        md = ImageDraw.Draw(mask)
        md.polygon([(c + (x - 5) * u, c + (y - 6) * u) for x, y in outer], fill=255)
        for hole in holes:
            md.polygon([(c + (x - 5) * u, c + (y - 6) * u) for x, y in hole], fill=0)
        text.paste(ink, (0, 0), mask)
    else:
        ImageDraw.Draw(text).text((c, c + 2 * k), letter, font=base._font("Bold", round(r * 1.35) * k), fill=ink, anchor="mm")
    slant = 0.2  # italics: lean the letter right, pivoting on its middle
    layer.alpha_composite(text.transform(text.size, Image.AFFINE, (1, slant, -slant * c, 0, 1, 0), Image.BICUBIC))
    shine = Image.new("RGBA", layer.size, (0, 0, 0, 0))  # the shine on the glass, top left
    ImageDraw.Draw(shine).ellipse((c - dome * 0.7, c - dome * 0.8, c + dome * 0.1, c - dome * 0.25), fill=(255, 255, 255, 150))
    layer.alpha_composite(shine.filter(ImageFilter.GaussianBlur(2 * k)))
    card.alpha_composite(layer.resize((size, size), Image.LANCZOS), (round(cx - size / 2), round(cy - size / 2)))


def _nameplate(card: Image.Image, build: CharacterBuild, box, accent, images) -> None:
    """An instrument cluster: the name on the display, the element (in its colour) and the specialty (amber) as
    warning lamps in round sockets, and the level beside them."""
    f = FONTS
    sx0, sy0, sx1, sy1 = _bezel(card, box, 10, 5)
    light = base._mix(accent, (255, 255, 255), 0.35)
    lx, mid = sx0 + 24, (sy0 + sy1) / 2
    for y, (url, color) in zip((mid - 19, mid + 19), ((build.element_icon, accent), (build.path_icon, AMBER))):
        symbol = images.get(url or "")
        if symbol is not None:
            _lamp(card, symbol, lx, y, color)
    tx = lx + 28
    draw = ImageDraw.Draw(card)
    draw.line((tx - 6, sy0 + 10, tx - 6, sy1 - 10), fill=(40, 38, 52), width=1)
    room = sx1 - tx - 12
    font = next((fn for fn in f.name.values() if draw.textlength(build.name.upper(), font=fn) <= room), f.name[28])
    _text(card, (tx + 6, sy0 + 44), base._fit_text(draw, build.name.upper(), font, room), font, light, "ls")
    y = sy1 - 17
    ImageDraw.Draw(card).text((tx + 7, y), "LV", font=f.small, fill=SILK, anchor="lm")
    _text(card, (tx + 31, y), str(build.level), f.mid, light, "lm")


PLATE_SHORT = {"CRIT RATE": "CR", "CRIT DMG": "CD"}


def _gauges(card: Image.Image, box, strips, counts) -> None:
    """Linear strip gauges, like a fuel and a temperature gauge: per strip (label, value, fraction, colour, max) a
    filled track with ticks and a red pointer, the value at the right. Under them, one plate per effective substat
    with its roll count."""
    f = FONTS
    sx0, sy0, sx1, sy1 = _bezel(card, box, 12, 6, (14, 13, 20))
    draw = ImageDraw.Draw(card)
    y = sy0 + 18
    for label, value, frac, color, top in strips:
        _silk(draw, (sx0 + 10, y), label)
        x = sx1 - 10
        if top:
            draw.text((x, y + 1), f"/{top}", font=f.tiny, fill=SILK, anchor="rs")
            x -= draw.textlength(f"/{top}", font=f.tiny) + 4
        draw.text((x, y + 1), value, font=f.sub, fill=color, anchor="rs")
        gx0, gx1, gy = sx0 + 12, sx1 - 12, y + 12
        draw.rectangle((gx0, gy, gx1, gy + 6), fill=(40, 38, 52))
        draw.rectangle((gx0, gy, gx0 + (gx1 - gx0) * frac, gy + 6), fill=color)
        for i in range(11):
            tx = gx0 + (gx1 - gx0) * i / 10
            draw.line((tx, gy + 8, tx, gy + (12 if i % 5 == 0 else 10)), fill=SILK if i % 5 == 0 else (90, 88, 108))
        px = gx0 + (gx1 - gx0) * frac
        draw.polygon([(px, gy - 1), (px - 5, gy - 8), (px + 5, gy - 8)], fill=(255, 92, 72))
        y += 46
    if not counts:
        return
    gap, h = 6, 33
    w = (sx1 - sx0 - 20 - gap * (len(counts) - 1)) / len(counts)
    py = sy1 - 6 - h
    for i, (name, n) in enumerate(counts):
        x = sx0 + 10 + i * (w + gap)
        draw.rounded_rectangle((x, py, x + w, py + h), 4, fill=(24, 22, 32), outline=(52, 50, 66))

        def width(text, font):
            return sum(draw.textlength(ch, font=font) for ch in text) + 0.5 * (len(text) - 1)
        if width(name, f.plate_s) > w - 4:
            name = PLATE_SHORT.get(name, name)  # narrow plates: the short forms players use
        font = next((fn for fn in (f.plate, f.plate_s) if width(name, fn) <= w - 4), f.plate_s)
        base._spaced(draw, (x + w / 2 - width(name, font) / 2, py + 9), name, font, SILK, 0.5, "lm")
        draw.text((x + w / 2, py + 24), str(n), font=f.count, fill=AMBER, anchor="mm")


def _readout(card: Image.Image, build: CharacterBuild, box, accent, wanted) -> None:
    """The stat readout: a dark screen with one line per stat, its icon, the name and the value lit up."""
    f = FONTS
    sx0, sy0, sx1, sy1 = _bezel(card, box, 12, 6)
    draw = ImageDraw.Draw(card)
    _silk(draw, (sx0 + 12, sy0 + 18), "AGENT STATUS")
    draw.line((sx0 + 12, sy0 + 25, sx1 - 12, sy0 + 25), fill=(50, 48, 64, 255), width=1)
    stats = [s for s in build.stats if not _is_zero(s.value)]
    totals = {base.TOTAL_NAMES.get(n, n.rstrip("%")) for n in wanted or ()}
    top, step = sy0 + 32, min(34, (sy1 - sy0 - 40) / max(len(stats), 1))
    light = base._mix(accent, (255, 255, 255), 0.35)
    for i, s in enumerate(stats):
        mid = top + step * (i + 0.5)
        name = _name(s)
        dmg = ELEMENT_COLORS.get(name.split(" ")[0])
        orb = (dmg >> 16 & 255, dmg >> 8 & 255, dmg & 255) if dmg else accent
        card.alpha_composite(stat_icons.icon(name, 18, SILK, orb), (sx0 + 12, round(mid - 9)))
        color = AMBER if s.name in totals else light
        value_w = draw.textlength(s.value, font=f.read)
        draw.text((sx0 + 38, mid), base._fit_text(draw, name.upper(), f.small, sx1 - sx0 - 70 - value_w), font=f.small,
                  fill=SILK, anchor="lm")
        _text(card, (sx1 - 12, mid), s.value, f.read, color, "rm")


def _weapon(card: Image.Image, build: CharacterBuild, box, accent, images) -> None:
    f = FONTS
    sx0, sy0, sx1, sy1 = _bezel(card, box, 12, 6)
    draw = ImageDraw.Draw(card)
    w = build.weapon
    pic = (sx0 + 10, sy0 + 10, sx0 + 92, sy1 - 10)
    draw.rounded_rectangle(pic, 8, fill=(20, 19, 28, 255), outline=(50, 48, 64, 255))
    base._icon(card, images.get(w.icon_url or ""), (pic[0] + 4, pic[1] + 4, pic[2] - 4, pic[3] - 4))
    tx, room = pic[2] + 12, sx1 - pic[2] - 22
    lines = base._wrap(draw, w.name.upper(), f.sub, room, 2)
    stats = w.stats[:2]
    block = 20 * len(lines) + 22 + 20 * len(stats)  # centred top to bottom beside the picture
    y = (sy0 + sy1 - block) / 2 + 10
    light = base._mix(accent, (255, 255, 255), 0.35)
    for line in lines:
        _text(card, (tx, y), line, f.sub, light, "lm")
        y += 20
    draw.text((tx, y), f"P{w.refinement} · LV. {w.level}", font=f.small, fill=SILK, anchor="lm")
    y += 22
    for s in stats:
        draw.text((tx, y), _name(s).upper(), font=f.small, fill=SILK, anchor="lm")
        _text(card, (sx1 - 12, y), s.value, f.sub, base.TEXT, "rm")
        y += 20


def _cartridge(card: Image.Image, piece: Gear, icon, box, accent, max_level: int, wanted) -> None:
    """A disc as a cartridge: slot number on a lit key, the main stat on a readout, substats with LEDs per upgrade,
    spread over the whole cartridge."""
    f = FONTS
    sx0, sy0, sx1, sy1 = _bezel(card, box, 12, 5)
    draw = ImageDraw.Draw(card)
    light = base._mix(accent, (255, 255, 255), 0.35)
    base._icon(card, icon, (sx0 + 6, sy0 + 6, sx0 + 70, sy0 + 70))
    slot = piece.slot.rsplit(" ", 1)[-1]
    key = (sx0 + 52, sy0 + 52, sx0 + 76, sy0 + 76)
    draw.rounded_rectangle(key, 5, fill=accent + (255,), outline=(14, 12, 20, 255), width=2)
    draw.text(((key[0] + key[2]) / 2, (key[1] + key[3]) / 2 + 1), slot, font=f.slot, fill=(14, 12, 20), anchor="mm")
    tx = sx0 + 86
    counter = bool(wanted and piece.subs)
    room, main = sx1 - tx - (40 if counter else 8), _name(piece.main).upper()
    font = f.sub if draw.textlength(main, font=f.sub) <= room else f.small
    draw.text((tx, sy0 + 18), base._fit_text(draw, main, font, room), font=font, fill=SILK, anchor="lm")
    _text(card, (tx, sy0 + 52), piece.main.value, f.big, light, "lm")
    if piece.level < max_level:
        draw.text((tx + draw.textlength(piece.main.value, font=f.big) + 8, sy0 + 58), f"+{piece.level}", font=f.sub,
                  fill=SILK, anchor="lm")
    if counter:  # the effective roll count in the top right corner, without a box
        n = str(piece_count(piece, wanted))
        _text(card, (sx1 - 25, sy0 + 21), n, f.mid, AMBER, "mm")
    y = sy0 + 86
    draw.line((sx0 + 8, y - 4, sx1 - 8, y - 4), fill=(44, 42, 58, 255), width=1)
    step = min(36, (sy1 - 6 - y) / 4)  # rows spread over the cartridge, the same for every disc
    y += max(0, (sy1 - 6 - y) - step * 4) / 2
    leds_x = sx1 - 10 - base.DOTS * 8
    for s in piece.subs:
        mid = y + step / 2
        good = bool(wanted) and s.name in wanted
        color = AMBER if good else base.TEXT
        value_x = leds_x - 8
        room = value_x - draw.textlength(s.value, font=f.sub) - 8 - (sx0 + 10)
        draw.text((sx0 + 10, mid), base._fit_text(draw, _name(s).upper(), f.sub, room), font=f.sub,
                  fill=AMBER if good else SILK, anchor="lm")
        _text(card, (value_x, mid), s.value, f.sub, color, "rm")
        ups = min(max(s.rolls - 1, 0), base.DOTS)
        for i in range(base.DOTS):  # one LED per possible upgrade, the used ones lit
            x = leds_x + i * 8
            fill = (AMBER if good else light) if i < ups else (40, 38, 52)
            draw.rectangle((x, mid - 5, x + 5, mid + 5), fill=fill + (255,))
        y += step


def draw_card(build: CharacterBuild, images: dict[str, Image.Image], uid: str | None = None,
              wanted: set[str] | None = None, face: tuple[float, float, float] | None = None) -> bytes:
    global FONTS
    FONTS = FONTS or Fonts()
    base.FONTS = base.FONTS or base.Fonts()
    f = FONTS
    accent = base._accent(build)
    card = _console()

    # left: the monitor, the nameplate and the Mindscape screen
    lx, ly, lr = RANK_LAMP
    _monitor(card, images.get(build.art_url or "") or images.get(build.icon_url or ""), face, (16, 16, 404, 424), accent,
             (lx, ly, lr + RANK_HOUSING))
    _nameplate(card, build, (16, 432, round(lx - lr - RANK_HOUSING - 10), 524), accent, images)  # clear of the lamp
    _rank_lamp(card, build, lx, ly, lr)  # set in the monitor's frame, over its bottom right corner
    shown, upcoming, thirds = base.mindscape_urls(build)
    _bezel(card, (16, 532, 404, 704), 12, 0, BODY_DARK)
    base._mindscape_panel(card, images.get(shown or ""), (22, 538, 398, 698), build.constellation,
                          images.get(upcoming or ""), thirds,
                          base.MINDSCAPE_FACES.get(int(build.character_id)) if upcoming else None, accent,
                          lambda size: _rubik(size, 800, True))

    # middle: the W-Engine, the readout and two dials
    value = base.gear_value(build, wanted)
    effective = sum(piece_count(p, wanted) for p in build.gear) if wanted and build.gear else None
    strips = []
    if value:
        label, text = value
        top = VALUE_MAX.get(label)
        strips.append((label, text, value_fraction(label, text), TEAL, f"{top:g}" if top else None))
    counts = []
    if effective is not None:
        top = effective_max(wanted)
        strips.append(("EFFECTIVE SUBS", str(effective), min(effective / top, 1) if top else 0, AMBER, str(top)))
        rolls = {}
        for p in build.gear:
            for s in p.subs:
                if s.name in wanted:
                    rolls[_name(s).upper()] = rolls.get(_name(s).upper(), 0) + max(s.rolls, 1)
        counts = sorted(rolls.items(), key=lambda kv: -kv[1])
    mx0, mx1 = 420, 704
    bottom = H - 16  # the readout on top, then the W-Engine, the gauges at the foot
    if strips:
        _gauges(card, (mx0, H - 16 - 148, mx1, H - 16), strips, counts)
        bottom = H - 16 - 156
    if build.weapon:
        _weapon(card, build, (mx0, bottom - 140, mx1, bottom), accent, images)
        bottom -= 148
    _readout(card, build, (mx0, 16, mx1, bottom), accent, wanted)

    # right: the disc cartridges, two per row
    gx0, gx1, gy0, gy1 = 720, W - 16, 16, H - 22  # room under the discs for the UID stamp
    gear = build.gear[:6]
    cw = (gx1 - gx0 - 10) / 2
    ch = (gy1 - gy0 - 20) / 3
    for i, piece in enumerate(gear):
        x0 = gx0 + (i % 2) * (cw + 10)
        y0 = gy0 + (i // 2) * (ch + 10)
        _cartridge(card, piece, images.get(piece.piece_icon or ""), (round(x0), round(y0), round(x0 + cw), round(y0 + ch)),
                   accent, base.GAME_LABELS["zzz"]["max_level"], wanted)
    if not gear:
        sx0, sy0, _, _ = _bezel(card, (gx0, gy0, gx1, gy0 + 80), 12, 6)
        _text(card, (sx0 + 16, sy0 + 34), "NO DISCS EQUIPPED", f.mid, SILK, "lm")

    if uid:
        server = base.server_name(build.game, uid)
        foot = f"{server} · UID {uid}" if server else f"UID {uid}"
        if build.source == "hoyolab":
            foot = f"via HoYoLAB · {foot}"
        ImageDraw.Draw(card).text((W - 8, H - 3), foot, font=f.tiny, fill=SILK, anchor="rd")

    out = io.BytesIO()
    card.convert("RGB").save(out, "PNG", compress_level=3)
    return out.getvalue()
