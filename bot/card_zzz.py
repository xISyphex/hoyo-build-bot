"""The ZZZ build card as a retro dashboard: a CRT monitor with the agent, a VFD nameplate, the Mindscape screen,
two dial gauges, a stat readout, the W-Engine module and six disc cartridges."""
from __future__ import annotations

import io
import math
import re

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


def effective_max(wanted: set[str]) -> int:
    """The most effective rolls a set of six discs can have: on each disc, as many wanted substats as fit beside
    the best main stat for it, each with its first roll, and every upgrade going into one of them."""
    total = 0
    for options in MAINS.values():
        fit = max(min(4, len((wanted & SUBSTATS) - {main})) for main in options)
        total += fit + UPGRADES if fit else 0
    return total


def _vfd(size: int):
    return base.ImageFont.truetype(str(base.FONT_DIR / "VT323-Regular.ttf"), size)


class Fonts:
    def __init__(self) -> None:
        self.name = {s: _vfd(s) for s in (52, 46, 40, 34)}
        self.big = _vfd(44)
        self.mid = _vfd(30)
        self.read = _vfd(28)
        self.sub = _vfd(23)
        self.small = _vfd(20)
        self.tiny = _vfd(16)
        self.silk = base._font("Bold", 12)
        self.label = base._font("SemiBold", 17)
        self.slot = base._font("Bold", 15)


FONTS: Fonts | None = None


def _glow_text(card: Image.Image, xy, text: str, font, color, anchor: str = "la", glow: float = 5) -> None:
    """Text lit like a vacuum fluorescent display: a soft halo under the sharp glyphs."""
    layer = Image.new("RGBA", card.size, (0, 0, 0, 0))
    ImageDraw.Draw(layer).text(xy, text, font=font, fill=color + (255,), anchor=anchor)
    box = layer.getbbox()
    if box:
        pad = round(glow * 3)
        box = (max(box[0] - pad, 0), max(box[1] - pad, 0), min(box[2] + pad, W), min(box[3] + pad, H))
        halo = layer.crop(box).filter(ImageFilter.GaussianBlur(glow))
        halo.putalpha(halo.getchannel("A").point(lambda a: min(255, a * 1.4)))
        card.alpha_composite(halo, box[:2])
    card.alpha_composite(layer)


def _bezel(card: Image.Image, box, r: int = 12, inset: int = 6, screen=GLASS) -> tuple[int, int, int, int]:
    """A panel cut into the console: a raised rim lit from above, and a dark screen inside it. Returns the screen."""
    x0, y0, x1, y1 = box
    layer = Image.new("RGBA", ((x1 - x0) * SS, (y1 - y0) * SS), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    w, h = layer.size
    d.rounded_rectangle((0, 0, w - 1, h - 1), r * SS, fill=(48, 46, 60, 255))
    d.rounded_rectangle((0, 2 * SS, w - 1, h - 1), r * SS, fill=(12, 11, 16, 255))  # the rim's shadowed lower edge
    d.rounded_rectangle((SS, SS, w - 1 - SS, h - 1 - SS), (r - 1) * SS, fill=(36, 34, 46, 255))
    i = inset * SS
    d.rounded_rectangle((i, i, w - 1 - i, h - 1 - i), max(r - inset, 3) * SS, fill=screen + (255,))
    card.alpha_composite(layer.resize((x1 - x0, y1 - y0), Image.LANCZOS), (x0, y0))
    return x0 + inset, y0 + inset, x1 - inset, y1 - inset


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


def _console(accent) -> Image.Image:
    """The console body: dark plastic, a faint grain, and a thin accent stripe along the top like a model trim."""
    card = Image.new("RGBA", (W, H), BODY + (255,))
    grad = Image.linear_gradient("L").resize((W, H))
    dark = Image.new("RGBA", (W, H), BODY_DARK + (255,))
    card = Image.composite(dark, card, grad)
    noise = Image.effect_noise((W // 2, H // 2), 18).resize((W, H)).point(lambda v: max(0, v - 128) // 6)
    card.alpha_composite(Image.merge("RGBA", (noise, noise, noise, noise)))
    d = ImageDraw.Draw(card)
    d.rectangle((0, 0, W, 3), fill=accent + (255,))
    d.rectangle((0, 4, W, 5), fill=base._mix(accent, BODY, 0.6) + (255,))
    for x, y in ((9, 13), (W - 9, 13), (9, H - 9), (W - 9, H - 9)):
        _screw(card, x, y)
    return card


def _monitor(card: Image.Image, art: Image.Image | None, face, box, accent) -> None:
    """The agent on a CRT: a head close-up when the face is known, scanlines and a dark vignette on the glass."""
    sx0, sy0, sx1, sy1 = _bezel(card, box, 18, 10, (10, 10, 18))
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
    glass.putalpha(mask.resize((w, h), Image.LANCZOS))
    card.alpha_composite(glass, (sx0, sy0))
    _scanlines(card, (sx0, sy0, sx1, sy1), 34)
    # a glare across the top left of the glass
    glare = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(glare).ellipse((-w * 0.4, -h * 0.5, w * 0.7, h * 0.35), fill=(255, 255, 255, 14))
    card.alpha_composite(glare.filter(ImageFilter.GaussianBlur(20)), (sx0, sy0))


def _specialty(build: CharacterBuild) -> str | None:
    """The specialty's name, read off its icon's file name (IconAttack.png -> ATTACK)."""
    m = re.search(r"Icon([A-Za-z]+)\.\w+$", build.path_icon or "")
    return m.group(1).upper() if m else None


def _nameplate(card: Image.Image, build: CharacterBuild, box, accent, images) -> None:
    """The agent as a TV programme listing: a channel block in the element colour with its symbol, an ON AIR
    lamp, the name as the programme title, specialty and level as the episode line, and the rank as a rating."""
    f = FONTS
    sx0, sy0, sx1, sy1 = _bezel(card, box, 10, 5)
    draw = ImageDraw.Draw(card)
    dark = (14, 12, 20)
    # the channel block
    ch = (sx0 + 6, sy0 + 6, sx0 + 70, sy1 - 6)
    draw.rounded_rectangle(ch, 6, fill=accent + (255,))
    draw.rounded_rectangle((ch[0], ch[1], ch[2], ch[1] + 16), 6, fill=base._mix(accent, (0, 0, 0), 0.35) + (255,))
    draw.rectangle((ch[0], ch[1] + 10, ch[2], ch[1] + 16), fill=base._mix(accent, (0, 0, 0), 0.35) + (255,))
    _silk(draw, ((ch[0] + ch[2]) / 2, ch[1] + 12), "CH", (240, 238, 248), True)
    icon = images.get(build.element_icon or "")
    if icon is not None:
        icon = icon.convert("RGBA")
        icon = icon.crop(icon.getchannel("A").getbbox() or (0, 0, *icon.size))
        icon.thumbnail((24, 24), Image.LANCZOS)
        backing = Image.new("RGBA", card.size, (0, 0, 0, 0))  # a dark disc so the symbol reads on its own colour
        cx, cy = (ch[0] + ch[2]) / 2, ch[1] + 33
        ImageDraw.Draw(backing).ellipse((cx - 15, cy - 15, cx + 15, cy + 15), fill=dark + (255,))
        card.alpha_composite(backing)
        card.alpha_composite(icon, (round(cx - icon.width / 2), round(cy - icon.height / 2)))
    draw = ImageDraw.Draw(card)
    el = build.element.upper()
    el_font = f.small if draw.textlength(el, font=f.small) <= ch[2] - ch[0] - 6 else f.tiny  # ELECTRIC, PHYSICAL
    draw.text(((ch[0] + ch[2]) / 2, ch[3] - 9), base._fit_text(draw, el, el_font, ch[2] - ch[0] - 4), font=el_font,
              fill=dark, anchor="mm")
    # the listing
    tx, tx1 = ch[2] + 12, sx1 - 12
    draw.ellipse((tx, sy0 + 9, tx + 9, sy0 + 18), fill=(255, 64, 64, 255))
    _silk(draw, (tx + 15, sy0 + 18), "ON AIR", (255, 120, 110))
    rank = f"{ZZZ_RARITY.get(build.rarity, '?')}-RANK"
    rw = draw.textlength(rank, font=f.small) + 14
    rate = (tx1 - rw, sy0 + 5, tx1, sy0 + 23)
    draw.rectangle(rate, outline=base.GOLD + (255,), width=2)
    draw.text(((rate[0] + rate[2]) / 2, (rate[1] + rate[3]) / 2), rank, font=f.small, fill=base.GOLD, anchor="mm")
    room = tx1 - tx
    font = next((fn for fn in f.name.values() if draw.textlength(build.name.upper(), font=fn) <= room), f.name[34])
    font = f.name[46] if font.size > f.name[46].size else font
    light = base._mix(accent, (255, 255, 255), 0.35)
    _glow_text(card, (tx, sy0 + 58), base._fit_text(draw, build.name.upper(), font, room), font, light, "ls", 5)
    episode = " · ".join(p for p in (_specialty(build), f"LV.{build.level}") if p)
    ImageDraw.Draw(card).text((tx, sy1 - 10), episode, font=f.small, fill=SILK, anchor="lm")


def _dial(card: Image.Image, box, label: str, value: str, fraction: float, color, top: str | None = None) -> None:
    """An analog gauge: a 240-degree scale, a needle at the fraction and the value on a small readout under it."""
    f = FONTS
    sx0, sy0, sx1, sy1 = _bezel(card, box, 12, 6, (14, 13, 20))
    w, h = sx1 - sx0, sy1 - sy0
    k = SS
    layer = Image.new("RGBA", (w * k, h * k), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    cx, cy, r = w / 2 * k, (h * 0.46) * k, min(w * 0.4, h * 0.4) * k
    start, sweep = 150, 240
    d.arc((cx - r, cy - r, cx + r, cy + r), start, start + sweep, fill=(60, 58, 74, 255), width=round(3 * k))
    d.arc((cx - r, cy - r, cx + r, cy + r), start, start + sweep * fraction, fill=color + (255,), width=round(5 * k))
    for i in range(11):
        a = math.radians(start + sweep * i / 10)
        r0 = r - (12 if i % 5 == 0 else 7) * k
        d.line((cx + r0 * math.cos(a), cy + r0 * math.sin(a), cx + (r - 4 * k) * math.cos(a), cy + (r - 4 * k) * math.sin(a)),
               fill=(200, 196, 220, 255) if i % 5 == 0 else (120, 116, 140, 255), width=round(1.5 * k))
    a = math.radians(start + sweep * min(max(fraction, 0), 1))
    tip = (cx + (r - 14 * k) * math.cos(a), cy + (r - 14 * k) * math.sin(a))
    side = math.radians(90)
    bw = 3 * k
    d.polygon([tip, (cx + bw * math.cos(a + side), cy + bw * math.sin(a + side)),
               (cx - 10 * k * math.cos(a), cy - 10 * k * math.sin(a)),
               (cx + bw * math.cos(a - side), cy + bw * math.sin(a - side))], fill=(255, 92, 72, 255))
    d.ellipse((cx - 6 * k, cy - 6 * k, cx + 6 * k, cy + 6 * k), fill=(70, 68, 84, 255), outline=(20, 18, 26, 255), width=k)
    card.alpha_composite(layer.resize((w, h), Image.LANCZOS), (sx0, sy0))
    draw = ImageDraw.Draw(card)
    # the value, then the most possible in small type after it, centred together under the needle
    most = f" /{top}" if top else ""
    vw, mw = draw.textlength(value, font=f.mid), draw.textlength(most, font=f.tiny)
    vx = sx0 + (w - vw - mw) / 2
    _glow_text(card, (vx, sy1 - 30), value, f.mid, color, "lm", 4)
    if most:
        draw.text((vx + vw, sy1 - 27), most, font=f.tiny, fill=SILK, anchor="lm")
    _silk(draw, (sx0 + w / 2, sy1 - 6), label, SILK, True)


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
        _glow_text(card, (sx1 - 12, mid), s.value, f.read, color, "rm", 3)


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
        _glow_text(card, (tx, y), line, f.sub, light, "lm", 3)
        y += 20
    draw.text((tx, y), f"P{w.refinement} · LV. {w.level}", font=f.small, fill=SILK, anchor="lm")
    y += 22
    for s in stats:
        draw.text((tx, y), _name(s).upper(), font=f.small, fill=SILK, anchor="lm")
        _glow_text(card, (sx1 - 12, y), s.value, f.sub, base.TEXT, "rm", 2)
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
    draw.text((tx, sy0 + 18), base._fit_text(draw, _name(piece.main).upper(), f.sub, sx1 - tx - (52 if counter else 8)),
              font=f.sub, fill=SILK, anchor="lm")
    _glow_text(card, (tx, sy0 + 52), piece.main.value, f.big, light, "lm", 5)
    if piece.level < max_level:
        draw.text((tx + draw.textlength(piece.main.value, font=f.big) + 8, sy0 + 58), f"+{piece.level}", font=f.sub,
                  fill=SILK, anchor="lm")
    if counter:  # the effective roll count on a small counter, top right
        n = str(piece_count(piece, wanted))
        cnt = (sx1 - 44, sy0 + 6, sx1 - 6, sy0 + 36)
        draw.rounded_rectangle(cnt, 5, fill=(24, 18, 8, 255), outline=(90, 66, 20, 255))
        _glow_text(card, ((cnt[0] + cnt[2]) / 2, (cnt[1] + cnt[3]) / 2), n, f.mid, AMBER, "mm", 3)
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
        _glow_text(card, (value_x, mid), s.value, f.sub, color, "rm", 2 if good else 0.1)
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
    card = _console(accent)
    draw = ImageDraw.Draw(card)

    # left: the monitor, the nameplate and the Mindscape screen
    _monitor(card, images.get(build.art_url or "") or images.get(build.icon_url or ""), face, (16, 16, 404, 424), accent)
    _nameplate(card, build, (16, 432, 404, 524), accent, images)
    shown, upcoming, thirds = base.mindscape_urls(build)
    _bezel(card, (16, 532, 404, 704), 12, 0, BODY_DARK)
    base._mindscape_panel(card, images.get(shown or ""), (22, 538, 398, 698), build.constellation,
                          images.get(upcoming or ""), thirds,
                          base.MINDSCAPE_FACES.get(int(build.character_id)) if upcoming else None, accent)

    # middle: two dials, the readout and the W-Engine
    value = base.gear_value(build, wanted)
    effective = sum(piece_count(p, wanted) for p in build.gear) if wanted and build.gear else None
    dials = []
    if value:
        label, text = value
        try:
            amount = float(text.replace(",", ""))
        except ValueError:
            amount = 0
        top = VALUE_MAX.get(label)
        dials.append((label, text, amount / top if top else 0, TEAL, f"{top:g}" if top else None))
    if effective is not None:
        top = effective_max(wanted)
        dials.append(("EFFECTIVE SUBS", str(effective), effective / top if top else 0, AMBER, str(top)))
    mx0, mx1 = 420, 704
    top = 16
    if dials:
        dw = (mx1 - mx0 - 10 * (len(dials) - 1)) / len(dials)
        for i, (label, text, frac, color, most) in enumerate(dials):
            x = round(mx0 + i * (dw + 10))
            _dial(card, (x, 16, round(x + dw), 164), label, text, min(frac, 1), color, most)
        top = 172
    weapon_top = H - 16 - 140 if build.weapon else H - 16
    _readout(card, build, (mx0, top, mx1, weapon_top - 8), accent, wanted)
    if build.weapon:
        _weapon(card, build, (mx0, weapon_top, mx1, H - 16), accent, images)

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
        _glow_text(card, (sx0 + 16, sy0 + 34), "NO DISCS EQUIPPED", f.mid, SILK, "lm", 3)

    if uid:
        server = base.server_name(build.game, uid)
        foot = f"{server} · UID {uid}" if server else f"UID {uid}"
        if build.source == "hoyolab":
            foot = f"via HoYoLAB · {foot}"
        ImageDraw.Draw(card).text((W - 8, H - 3), foot, font=base.FONTS.stamp, fill=SILK, anchor="rd")

    out = io.BytesIO()
    card.convert("RGB").save(out, "PNG", compress_level=3)
    return out.getvalue()
