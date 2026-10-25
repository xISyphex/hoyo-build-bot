"""/zzz-patch drawn as the same retro dashboard as ZZZ's build card and records: a console with screws, the version
and its time left on the top screen over a caution-striped progress gauge, and each running channel a panel with its
S-rank on a CRT monitor, a nameplate with element and specialty warning lamps, the A-ranks on little monitors and its
time left on a readout. The ones coming next sit on small cartridges at the bottom."""

from __future__ import annotations

import datetime as dt
import io
import re

from PIL import Image, ImageDraw

from . import card as base
from . import card_zzz as z
from . import patch_card as pc
from . import record_icons as icons
from . import records_zzz as rz
from .embeds import ELEMENT_COLORS
from .patch import KINDS, Banner, Patch, version_start
from .records_card import GAME_ACCENT

W = 1200
PAD = 24
GAP = 14
COLS = 2
CARD_W = (W - 2 * PAD - (COLS - 1) * GAP) // COLS
CARD_H = 214
HEAD_H = 176  # the top screen: version, time left and the gauge
SECTION_HEAD = 48
ART_W = 150  # the S-rank's monitor
SMALL = 58  # an A-rank's monitor
NEXT_H = 88
STRIPE = GAME_ACCENT["zzz"]  # the caution stripes' yellow
ELEMENT_NAMES = {"AuricInk": "Auric Ink", "Lumiflux": "Lumen"}  # the icon's name -> ELEMENT_COLORS' name


def _mark_color(url: str):
    """An element lamp lights in the element's colour, a specialty lamp amber."""
    found = re.search(r"/Icon(\w+)\.webp$", url)
    if not found:
        return z.AMBER
    colour = ELEMENT_COLORS.get(ELEMENT_NAMES.get(found[1], found[1]), 0xB8B8B8)
    return (colour >> 16 & 255, colour >> 8 & 255, colour & 255)


def _lamps(card: Image.Image, urls: list[str], images: dict, x: float, cy: float, d: float = 30) -> float:
    """The unit's element and specialty as warning lamps, their sockets d across in a row from x, centred on cy;
    returns the row's width (socket edge to socket edge)."""
    size = round(d * 44 / 32)  # z._lamp draws a 32 px socket on a 44 px tile
    pad = (size - d) / 2
    start = x
    for url in urls:
        symbol = images.get(url)
        if symbol is None:
            continue
        tile = Image.new("RGBA", (44, 44), (0, 0, 0, 0))
        z._lamp(tile, symbol, 22, 22, _mark_color(url))
        card.alpha_composite(tile.resize((size, size), Image.LANCZOS), (round(x - pad), round(cy - size / 2)))
        x += d + 6
    return x - start - 6 if x > start else 0


def _screen(card: Image.Image, icon: Image.Image | None, box, top: bool, weapon: bool) -> None:
    """An item on a little CRT: glass tinted by rank (gold S, purple A), the picture on it, scanlines."""
    sx0, sy0, sx1, sy1 = z._bezel(card, box, 10 if top else 8, 5 if top else 4, (10, 10, 18))
    w, h = sx1 - sx0, sy1 - sy0
    hi, lo = rz.RARITY_GLASS[5 if top else 4]
    grad = Image.linear_gradient("L").resize((w, h))
    glass = Image.composite(Image.new("RGBA", (w, h), lo + (255,)), Image.new("RGBA", (w, h), hi + (255,)), grad)
    if icon is not None:
        glass.alpha_composite(pc._fit(icon, w, h, weapon))
    mask = Image.new("L", (w * 4, h * 4), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, w * 4 - 1, h * 4 - 1), (7 if top else 5) * 4, fill=255)
    card.paste(glass, (sx0, sy0), mask.resize((w, h), Image.LANCZOS))
    z._scanlines(card, (sx0, sy0, sx1, sy1), 30)


def _stripes(w: int, h: int) -> Image.Image:
    """Diagonal caution stripes, yellow on black."""
    k = z.SS
    tile = Image.new("RGBA", (w * k, h * k), (16, 14, 10, 255))
    d = ImageDraw.Draw(tile)
    step = 14 * k
    for x in range(-h * k, w * k + h * k, step):
        d.polygon([(x, h * k), (x + step / 2, h * k), (x + step / 2 + h * k, 0), (x + h * k, 0)], fill=STRIPE + (255,))
    return tile.resize((w, h), Image.LANCZOS)


def _gauge(card: Image.Image, patch: Patch, now: dt.datetime, x0: int, x1: int, y: int) -> None:
    """How far through the version we are: a track filled with caution stripes up to now, ticks under it, a red
    pointer at now, and a mark where the second half's channels open."""
    draw = ImageDraw.Draw(card)
    h = 14
    draw.rectangle((x0, y, x1, y + h), fill=(40, 38, 52))
    start, end = version_start(patch), patch.end
    for i in range(21):
        tx = x0 + (x1 - x0) * i / 20
        draw.line((tx, y + h + 3, tx, y + h + (9 if i % 5 == 0 else 6)), fill=z.SILK if i % 5 == 0 else (90, 88, 108))
    if not (start and end and end > start):
        return
    done = min(1.0, max(0.0, (now - start) / (end - start)))
    fx = x0 + round((x1 - x0) * done)
    if fx > x0:
        card.alpha_composite(_stripes(fx - x0, h), (x0, y))
    halves = sorted({b.start for b in patch.banners if b.version == patch.version and b.start > start + dt.timedelta(days=3)})
    for when in halves[:1]:
        tx = x0 + round((x1 - x0) * (when - start) / (end - start))
        draw.rectangle((tx - 1, y - 6, tx + 1, y + h + 6), fill=base.TEXT)
        z._silk(draw, (tx, y + h + 24), f"PHASE 2 · {pc._day(when, patch.server).upper()}", centre=True)
    draw.polygon([(fx, y - 1), (fx - 7, y - 11), (fx + 7, y - 11)], fill=(255, 92, 72))
    z._silk(draw, (x0, y + h + 24), pc._day(start, patch.server).upper())
    day = pc._day(end, patch.server).upper()
    z._silk(draw, (x1 - sum(draw.textlength(ch, font=z.FONTS.silk) for ch in day) - 2.4 * (len(day) - 1), y + h + 24), day)


def _header(card: Image.Image, patch: Patch, now: dt.datetime) -> None:
    sx0, sy0, sx1, sy1 = z._bezel(card, (PAD, PAD, W - PAD, PAD + HEAD_H), 12, 5)
    draw = ImageDraw.Draw(card)
    z._silk(draw, (sx0 + 20, sy0 + 24), "ZENLESS ZONE ZERO")
    draw.text((sx0 + 18, sy0 + 76), f"VERSION {patch.version}", font=z._rubik(50, 800), fill=base.TEXT, anchor="ls")
    right = sx1 - 20
    if patch.end:
        label = "ENDS IN"
        z._silk(draw, (right - sum(draw.textlength(ch, font=z.FONTS.silk) for ch in label) - 2.4 * (len(label) - 1), sy0 + 24), label)
        left = pc._short(patch.end - now).upper()
        font = z._rubik(46, 800)
        draw.text((right, sy0 + 76), left, font=font, fill=z.AMBER, anchor="rs")
        clock = icons.clock(34, z.AMBER)
        card.alpha_composite(clock, (round(right - draw.textlength(left, font=font) - 14 - clock.width), sy0 + 60 - clock.height // 2))
        draw.text((right, sy0 + 100), pc._stamp(patch.end, patch.server).upper(), font=z.FONTS.tiny, fill=z.SILK, anchor="rs")
    else:
        draw.text((right, sy0 + 76), "END NOT ANNOUNCED", font=z.FONTS.mid, fill=z.SILK, anchor="rs")
    _gauge(card, patch, now, sx0 + 20, sx1 - 20, sy0 + 122)


def _ends(card: Image.Image, box, text: str) -> None:
    """A small readout: ENDS IN printed on the left, the time left lit on the right."""
    sx0, sy0, sx1, sy1 = z._bezel(card, box, 9, 4)
    draw = ImageDraw.Draw(card)
    mid = (sy0 + sy1) / 2
    z._silk(draw, (sx0 + 12, mid + 4), "ENDS IN")
    draw.text((sx1 - 12, mid + 1), text.upper(), font=z.FONTS.sub, fill=z.TEAL, anchor="rm")


def _banner(card: Image.Image, b: Banner, images: dict, box, now: dt.datetime) -> None:
    x0, y0, x1, y1 = box
    z._bezel(card, box, 14, 0, z.BODY_DARK)
    weapon = b.kind in pc.WEAPON_KINDS
    tops = [i for i in b.items if i[1]] or [(n, True, None) for n in b.featured]
    rest = [i for i in b.items if not i[1]]
    n = max(1, min(2, len(tops)))
    aw = ART_W if n == 1 else 108
    ax = x0 + 12
    for _, _, icon in tops[:2]:
        _screen(card, images.get(icon or ""), (ax, y0 + 12, ax + aw, y1 - 12), True, weapon)
        ax += aw + 8
    tx = ax + 6
    # The nameplate: lamps, then the name
    top = tops[0][0] if tops else "?"
    px0, py0, px1, py1 = z._bezel(card, (tx, y0 + 12, x1 - 12, y0 + 68), 10, 5)
    mid = (py0 + py1) / 2
    d = 30
    lx = px0 + (py1 - py0 - d) / 2  # as far in from the left as from the top and bottom
    lw = _lamps(card, b.traits.get(top, []), images, lx, mid, d)
    draw = ImageDraw.Draw(card)
    nx = lx + lw + 16 if lw else px0 + 10
    if lw:
        draw.line((nx - 8, py0 + 8, nx - 8, py1 - 8), fill=(40, 38, 52), width=1)
    names = " & ".join(t[0] for t in tops).upper() or "?"
    room = px1 - nx - 12
    font = next((f for f in (z._rubik(s, 800) for s in (28, 24, 20)) if draw.textlength(names, font=f) <= room), z._rubik(20, 800))
    light = base._mix(z.AMBER, (255, 255, 255), 0.35)
    draw.text((nx + 4, mid + 1), base._fit_text(draw, names, font, room), font=font, fill=light, anchor="lm")
    # The A-ranks on little monitors, their names printed under them
    sx = tx
    for _, _, icon in rest[:5]:
        if sx + SMALL > x1 - 12:
            break
        _screen(card, images.get(icon or ""), (sx, y0 + 80, sx + SMALL, y0 + 80 + SMALL), False, weapon)
        sx += SMALL + 8
    if rest:
        line = ", ".join(r[0] for r in rest).upper()
        z._silk(draw, (tx + 2, y0 + 80 + SMALL + 20), base._fit_text(draw, line, z.FONTS.silk, x1 - 24 - tx - 200))
    _ends(card, (x1 - 12 - 190, y1 - 12 - 40, x1 - 12, y1 - 12), pc._short(b.end - now))


def _upcoming(card: Image.Image, upcoming: list[Banner], images: dict, server, y: int) -> None:
    draw = ImageDraw.Draw(card)
    x = PAD
    for b in upcoming:
        top = next((i for i in b.items if i[1]), (b.featured[0], True, b.icon))
        name = base._fit_text(draw, top[0].upper(), z.FONTS.small, 170)
        marks = [u for u in b.traits.get(top[0], []) if u in images]
        day = f"FROM {pc._day(b.start, server).upper()}"
        dw = sum(draw.textlength(ch, font=z.FONTS.silk) for ch in day) + 2.4 * (len(day) - 1)
        lamps = len(marks) * 26 - 6 + 8 if marks else 0  # the lamps after the name, on its line
        w = round(12 + 64 + 12 + max(draw.textlength(name, font=z.FONTS.small) + lamps, dw) + 16)
        if x + w > W - PAD:
            break
        z._bezel(card, (x, y, x + w, y + NEXT_H), 12, 0, z.BODY_DARK)
        _screen(card, images.get(top[2] or ""), (x + 12, y + 12, x + 76, y + 76), True, b.kind in pc.WEAPON_KINDS)
        draw = ImageDraw.Draw(card)
        draw.text((x + 88, y + 31), name, font=z.FONTS.small, fill=base.TEXT, anchor="lm")
        _lamps(card, marks, images, x + 88 + draw.textlength(name, font=z.FONTS.small) + 8, y + 31, 20)
        z._silk(draw, (x + 89, y + 62), day)
        x += w + GAP


def draw_patch(patch: Patch, images: dict[str, Image.Image], now: dt.datetime | None = None) -> bytes:
    base.FONTS = base.FONTS or base.Fonts()
    z.FONTS = z.FONTS or z.Fonts()
    now = now or dt.datetime.now(dt.timezone.utc)
    running = [one for b in patch.banners if b.start <= now < b.end for one in pc._split(b)]
    sections = [(k, [b for b in running if b.kind == k]) for k in KINDS["zzz"]]
    sections = [(k, bs) for k, bs in sections if bs]
    upcoming = sorted((one for b in patch.banners if b.start > now and b.featured for one in pc._split(b)),
                      key=lambda b: b.start)[:6]
    rows = pc._rows
    height = PAD + HEAD_H + GAP + sum(SECTION_HEAD + rows(len(bs)) * (CARD_H + GAP) for _, bs in sections) + PAD
    if not sections:
        height += 60
    if upcoming:
        height += SECTION_HEAD + NEXT_H + GAP
    card = rz._console(W, height)
    _header(card, patch, now)

    y = PAD + HEAD_H + GAP
    for kind, banners in sections:
        rz._pilot(card, PAD + 14, y + 22, z.AMBER)
        ImageDraw.Draw(card).text((PAD + 34, y + 32), kind.upper(), font=z._rubik(24, 800), fill=base.TEXT, anchor="ls")
        y += SECTION_HEAD
        for i, b in enumerate(banners):
            bx = PAD + (i % COLS) * (CARD_W + GAP)
            by = y + (i // COLS) * (CARD_H + GAP)
            _banner(card, b, images, (bx, by, bx + CARD_W, by + CARD_H), now)
        y += rows(len(banners)) * (CARD_H + GAP)
    if not sections:
        ImageDraw.Draw(card).text((PAD + 8, y + 30), "No channels are running right now.", font=z.FONTS.sub, fill=z.SILK, anchor="lm")
        y += 60
    if upcoming:
        rz._pilot(card, PAD + 14, y + 22, z.SILK)
        ImageDraw.Draw(card).text((PAD + 34, y + 32), "COMING NEXT", font=z._rubik(24, 800), fill=base.TEXT, anchor="ls")
        _upcoming(card, upcoming, images, patch.server, y + SECTION_HEAD)

    out = io.BytesIO()
    card.convert("RGB").save(out, "PNG", compress_level=3)
    return out.getvalue()
