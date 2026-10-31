"""/hsr-patch drawn as the same navigation hologram as Star Rail's build card and records: the bridge's star map
behind cyan holo screens with cut corners. The version and its time left sit on the top screen over the version's
star-rail route (stations at its start, its second phase and its end, the train lit where we are now). Each running
warp is a screen with its 5-star on a gold projected tile, its name with element and Path symbols, the 4-stars on
small purple tiles and its time left on a readout. The ones coming next sit on small screens at the bottom."""

from __future__ import annotations

import datetime as dt
import io

from PIL import Image, ImageDraw, ImageFilter

from . import card as base
from . import card_hsr as h
from . import patch_card as pc
from . import record_icons as icons
from . import records_hsr as rh
from .patch import KINDS, Banner, Patch, version_start

W = 1200
PAD = 24
GAP = 14
COLS = 2
CARD_W = (W - 2 * PAD - (COLS - 1) * GAP) // COLS
CARD_H = 214
HEAD_H = 176  # the top screen: version, time left and the route
SECTION_HEAD = 48
ART_W = 150  # the 5-star's tile
SMALL = 58  # a 4-star's tile
NEXT_H = 88
SS = h.SS
HOLO, TEXT, DIM, FAINT, GOLD, DEEP = h.HOLO, h.TEXT, h.DIM, h.FAINT, h.GOLD, h.DEEP
SECTION_LIGHT = {"Character warps": HOLO, "Light cone warps": GOLD}


def _tile(card: Image.Image, icon: Image.Image | None, box, top: bool, weapon: bool) -> None:
    """An item projected on a tile with a cut corner, lit gold (5-star) or purple (4-star), with a cyan rim."""
    x0, y0, x1, y1 = (round(v) for v in box)
    w, hh = x1 - x0, y1 - y0
    hi, lo = rh.RARITY_GLOW[5 if top else 4]
    grad = Image.linear_gradient("L").resize((w, hh))
    glass = Image.composite(Image.new("RGBA", (w, hh), lo + (255,)), Image.new("RGBA", (w, hh), hi + (255,)), grad)
    if icon is not None:
        glass.alpha_composite(pc._fit(icon, w, hh, weapon))
    cut = 12 if top else 8
    shape = h._cut((0, 0, w * SS - 1, hh * SS - 1), cut * SS)
    mask = Image.new("L", (w * SS, hh * SS), 0)
    ImageDraw.Draw(mask).polygon(shape, fill=255)
    glass.putalpha(mask.resize((w, hh), Image.LANCZOS))
    card.alpha_composite(glass, (x0, y0))
    rim = Image.new("RGBA", (w * SS, hh * SS), (0, 0, 0, 0))
    ImageDraw.Draw(rim).line(shape + shape[:1], fill=HOLO + (150,), width=SS)
    card.alpha_composite(rim.resize((w, hh), Image.LANCZOS), (x0, y0))


def _marks(card: Image.Image, urls: list[str], images: dict, x: float, cy: float, size: int) -> float:
    """The unit's element and Path symbols in a row from x, centred on cy; returns the row's width."""
    start = x
    for url in urls:
        icon = h._symbol(images.get(url), size)
        if icon is None:
            continue
        card.alpha_composite(icon, (round(x), round(cy - icon.height / 2)))
        x += icon.width + 6
    return x - start - 6 if x > start else 0


def _spaced_w(draw, text: str, font, spacing: float) -> float:
    return sum(draw.textlength(ch, font=font) + spacing for ch in text) - spacing if text else 0


def _diamond(draw, cx: float, cy: float, d: float, fill) -> None:
    draw.polygon([(cx, cy - d), (cx + d, cy), (cx, cy + d), (cx - d, cy)], fill=fill)


def _route(card: Image.Image, patch: Patch, now: dt.datetime, x0: int, x1: int, y: int) -> None:
    """How far through the version we are, as a star-rail route: the stretch travelled solid and glowing, the rest
    dashed; stations at the start, the second phase and the end, and the train's light at now."""
    start, end = version_start(patch), patch.end
    k = SS
    layer = Image.new("RGBA", ((x1 - x0 + 40) * k, 60 * k), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    ox, cy = 20, 20  # the layer's left margin and the route's height in it
    X = lambda x: (x - x0 + ox) * k
    done = min(1.0, max(0.0, (now - start) / (end - start))) if start and end and end > start else 0.0
    fx = x0 + (x1 - x0) * done
    steps = max(int((x1 - fx) / 7), 1)
    for s in range(0, steps, 2):  # the stretch still ahead, dashed
        a, b = fx + (x1 - fx) * s / steps, fx + (x1 - fx) * min(s + 1, steps) / steps
        d.line((X(a), cy * k, X(b), cy * k), fill=HOLO + (120,), width=2 * k)
    glow = Image.new("RGBA", (layer.width // k, layer.height // k), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    if fx > x0:  # the stretch travelled, solid
        d.line((X(x0), cy * k, X(fx), cy * k), fill=HOLO + (255,), width=4 * k)
        gd.line((ox, cy, fx - x0 + ox, cy), fill=HOLO + (170,), width=8)
    halves = []
    if start and end and end > start:
        halves = sorted({b.start for b in patch.banners if b.version == patch.version and b.start > start + dt.timedelta(days=3)})[:1]
    stations = [x0, x1] + [x0 + (x1 - x0) * (w - start) / (end - start) for w in halves]
    for sx in stations:  # the stations: rings, filled once passed
        r = 9
        passed = sx <= fx
        d.ellipse((X(sx) - r * k, (cy - r) * k, X(sx) + r * k, (cy + r) * k), fill=(HOLO if passed else DEEP) + (255,),
                  outline=HOLO + (255,), width=2 * k)
        if passed:
            d.ellipse((X(sx) - 4 * k, (cy - 4) * k, X(sx) + 4 * k, (cy + 4) * k), fill=DEEP + (255,))
    if start and end and end > start:  # the train: a lit gold waypoint
        gd.ellipse((fx - x0 + ox - 16, cy - 16, fx - x0 + ox + 16, cy + 16), fill=GOLD + (190,))
        _diamond(d, X(fx), cy * k, 12 * k, GOLD + (255,))
        _diamond(d, X(fx), cy * k, 5 * k, (255, 255, 255, 255))
    card.alpha_composite(glow.filter(ImageFilter.GaussianBlur(6)), (x0 - ox, y - cy))
    card.alpha_composite(layer.resize(glow.size, Image.LANCZOS), (x0 - ox, y - cy))
    draw = ImageDraw.Draw(card)
    f = h._raj("Bold", 13)
    if not (start and end and end > start):
        return
    h._spaced(draw, (x0 - 4, y + 30), pc._day(start, patch.clock).upper(), f, DIM, 2)
    day = pc._day(end, patch.clock).upper()
    h._spaced(draw, (x1 + 4 - _spaced_w(draw, day, f, 2), y + 30), day, f, DIM, 2)
    for when, sx in zip(halves, stations[2:]):
        text = f"PHASE 2 · {pc._day(when, patch.clock).upper()}"
        h._spaced(draw, (sx - _spaced_w(draw, text, f, 2) / 2, y + 30), text, f, TEXT, 2)


def _header(card: Image.Image, patch: Patch, now: dt.datetime) -> None:
    x0, y0, x1, y1 = PAD, PAD, W - PAD, PAD + HEAD_H
    rh._box(card, (x0, y0, x1, y1))
    draw = ImageDraw.Draw(card)
    h._spaced(draw, (x0 + 26, y0 + 26), "HONKAI: STAR RAIL", h._raj("SemiBold", 17), DIM, 1.8)
    h._top_text(card, (x0 + 24, y0 + 40), f"VERSION {patch.version}", h._raj("Bold", 44), (255, 255, 255), 6)
    draw = ImageDraw.Draw(card)
    right = x1 - 26
    label = h._raj("Bold", 13)
    if patch.end:
        h._spaced(draw, (right - _spaced_w(draw, "ENDS IN", label, 3.4), y0 + 26), "ENDS IN", label, HOLO, 3.4)
        left = pc._short(patch.end - now).upper()
        font = h._raj("Bold", 44)
        draw.text((right, y0 + 64), left, font=font, fill=HOLO, anchor="rm")
        clock = icons.clock(32, HOLO)
        card.alpha_composite(clock, (round(right - draw.textlength(left, font=font) - 14 - clock.width), y0 + 64 - clock.height // 2))
        stamp = pc._stamp(patch.end, patch.clock).upper()
        sf = h._raj("SemiBold", 14)
        h._spaced(draw, (right - _spaced_w(draw, stamp, sf, 1.4), y0 + 98), stamp, sf, FAINT, 1.4)
    else:
        draw.text((right, y0 + 64), "END NOT ANNOUNCED", font=h._raj("Bold", 22), fill=DIM, anchor="rm")
    zf = h._raj("SemiBold", 14)
    h._spaced(draw, (x0 + 26, y0 + 98), pc._zone_label(patch).upper(), zf, FAINT, 1.4)
    _route(card, patch, now, x0 + 40, x1 - 40, y0 + 126)


def _ends(card: Image.Image, box, text: str) -> None:
    """A small readout: ENDS IN spaced on the left, the time left in cyan on the right."""
    x0, y0, x1, y1 = box
    layer = Image.new("RGBA", card.size, (0, 0, 0, 0))
    ImageDraw.Draw(layer).polygon(h._cut(box, 8), fill=(2, 16, 26, 215), outline=HOLO + (100,))
    base._layer_onto(card, layer)
    draw = ImageDraw.Draw(card)
    mid = (y0 + y1) / 2
    h._spaced(draw, (x0 + 12, mid + 1), "ENDS IN", h._raj("Bold", 11), DIM, 2.4)
    draw.text((x1 - 12, mid + 1), text.upper(), font=h._raj("Bold", 20), fill=HOLO, anchor="rm")


def _banner(card: Image.Image, b: Banner, images: dict, box, now: dt.datetime) -> None:
    x0, y0, x1, y1 = box
    rh._box(card, box, rh.TEAM_FILL, 100, 12)
    weapon = b.kind in pc.WEAPON_KINDS
    tops = [i for i in b.items if i[1]] or [(n, True, None) for n in b.featured]
    rest = [i for i in b.items if not i[1]]
    n = max(1, min(2, len(tops)))
    aw = ART_W if n == 1 else 108
    ax = x0 + 14
    for _, _, icon in tops[:2]:
        _tile(card, images.get(icon or ""), (ax, y0 + 14, ax + aw, y1 - 14), True, weapon)
        ax += aw + 8
    tx = ax + 10
    # The name: a waypoint, the element and Path symbols, then the name
    draw = ImageDraw.Draw(card)
    top = tops[0][0] if tops else "?"
    cy = y0 + 38
    _diamond(draw, tx + 5, cy, 5, HOLO)
    mw = _marks(card, b.traits.get(top, []), images, tx + 20, cy, 26)
    nx = tx + 20 + (mw + 10 if mw else 0)
    names = _plain(" & ".join(t[0] for t in tops).upper() or "?", h._raj("Bold", 26))
    room = x1 - 18 - nx
    for size, spacing in ((26, 2.4), (23, 2), (20, 1.6), (18, 1.2)):
        font = h._raj("Bold", size)
        if _spaced_w(draw, names, font, spacing) <= room:
            break
    else:
        names = base._fit_text(draw, names, font, room - spacing * len(names))
    h._spaced(draw, (nx, cy + 1), names, font, (255, 255, 255), spacing)
    # The 4-stars on small tiles, their names under them
    sx = tx
    for _, _, icon in rest[:5]:
        if sx + SMALL > x1 - 14:
            break
        _tile(card, images.get(icon or ""), (sx, y0 + 70, sx + SMALL, y0 + 70 + SMALL), False, weapon)
        sx += SMALL + 8
    if rest:
        line = _plain(", ".join(r[0] for r in rest).upper(), h._raj("SemiBold", 14))
        lf = h._raj("SemiBold", 14)
        draw = ImageDraw.Draw(card)
        h._spaced(draw, (tx + 1, y0 + 70 + SMALL + 18), base._fit_text(draw, line, lf, x1 - 18 - tx - 1.2 * len(line)), lf, DIM, 1.2)
    _ends(card, (x1 - 16 - 180, y1 - 16 - 34, x1 - 16, y1 - 16), pc._short(b.end - now))


def _plain(text: str, font) -> str:
    """The text with any letter the font has no glyph for swapped for one it has (HoYoLAB writes "Aeon ・ Aha"),
    instead of an empty box."""
    blank = font.getmask("\U0010FFFD")
    missing = lambda ch: not ch.isspace() and (m := font.getmask(ch)).size == blank.size and bytes(m) == bytes(blank)
    return "".join(SWAPS.get(ch, "·") if missing(ch) else ch for ch in text)


SWAPS = {"：": ":", "「": '"', "」": '"', "『": '"', "』": '"', "～": "~"}


NEW_H = 116  # the new character's screen, on a row of its own
SUB_HEAD = 30  # a small title over a row (RERUN, LIGHT CONES)


def _next_item(draw, b: Banner, images: dict, server, big: bool) -> tuple:
    """A coming banner with what its screen shows, and the screen's width."""
    nf, df = h._raj("Bold", 28 if big else 19), h._raj("Bold", 13 if big else 12)
    tile = NEW_H - 24 if big else 64
    top = next((i for i in b.items if i[1]), (b.featured[0], True, b.icon))
    name = base._fit_text(draw, _plain(top[0].upper(), nf), nf, 520 if big else 230)
    marks = [u for u in b.traits.get(top[0], []) if u in images]
    day = f"FROM {pc._day(b.start, server).upper()}"
    nw = _spaced_w(draw, name, nf, 2 if big else 1.4)
    marks_w = len(marks) * (34 if big else 26) + 4 if marks else 0  # the symbols after the name, on its line
    w = round(12 + tile + 14 + max(nw + marks_w, _spaced_w(draw, day, df, 2.4)) + 24)
    return (b, top, name, marks, day, nw, big, min(w, W - 2 * PAD))


def _next_layout(draw, upcoming: list[Banner], images: dict, server):
    """Where everything coming next goes: the first new character on a row of its own, then the other characters
    (reruns) and the light cones, each under a small title, in rows that wrap. Returns the pieces and the height."""
    chars = [b for b in upcoming if b.kind not in pc.WEAPON_KINDS]
    cones = [b for b in upcoming if b.kind in pc.WEAPON_KINDS]
    groups = [("", chars[:1], True), ("RERUN", chars[1:], False), ("LIGHT CONES", cones, False)]
    pieces, y = [], 0
    for title, banners, big in groups:
        if not banners:
            continue
        if title:
            pieces.append(("title", title, PAD, y))
            y += SUB_HEAD
        x, hh = PAD, NEW_H if big else NEXT_H
        for b in banners:
            item = _next_item(draw, b, images, server, big)
            if x > PAD and x + item[-1] > W - PAD:
                x, y = PAD, y + hh + GAP
            pieces.append(("screen", item, x, y))
            x += item[-1] + GAP
        y += hh + GAP
    return pieces, y


def _upcoming(card: Image.Image, upcoming: list[Banner], images: dict, server, y0: int) -> None:
    pieces, _ = _next_layout(ImageDraw.Draw(card), upcoming, images, server)
    for kind, item, x, y in pieces:
        y += y0
        draw = ImageDraw.Draw(card)
        if kind == "title":  # a small spaced label with a waypoint, like the readouts'
            _diamond(draw, x + 8, y + 10, 4, FAINT)
            h._spaced(draw, (x + 20, y + 11), item, h._raj("Bold", 13), DIM, 3.4)
            continue
        b, top, name, marks, day, nw, big, w = item
        hh = NEW_H if big else NEXT_H
        tile = hh - 24
        nf, df = h._raj("Bold", 28 if big else 19), h._raj("Bold", 13 if big else 12)
        rh._box(card, (x, y, x + w, y + hh), rh.TEAM_FILL, 100, 12 if big else 10)
        _tile(card, images.get(top[2] or ""), (x + 12, y + 12, x + 12 + tile, y + 12 + tile), True, b.kind in pc.WEAPON_KINDS)
        draw = ImageDraw.Draw(card)
        tx, ny = x + 12 + tile + 14, y + (44 if big else 32)
        h._spaced(draw, (tx, ny), name, nf, (255, 255, 255) if big else TEXT, 2 if big else 1.4)
        _marks(card, marks, images, tx + nw + 10, ny, 26 if big else 20)
        h._spaced(draw, (tx + 1, y + (80 if big else 60)), day, df, DIM, 2.4)


def _section(card: Image.Image, title: str, light, y: int) -> None:
    """A section's title with a status light before it, like the records' modes."""
    draw = ImageDraw.Draw(card)
    draw.rectangle((PAD + 6, y + 12, PAD + 9, y + 38), fill=light)
    glow = Image.new("RGBA", (40, 60), (0, 0, 0, 0))
    ImageDraw.Draw(glow).rectangle((18, 18, 21, 44), fill=light + (200,))
    card.alpha_composite(glow.filter(ImageFilter.GaussianBlur(5)), (PAD + 6 - 18, y - 6))
    h._top_text(card, (PAD + 22, y + 10), title.upper(), h._raj("Bold", 26), (255, 255, 255), 3)


def draw_patch(patch: Patch, images: dict[str, Image.Image], now: dt.datetime | None = None) -> bytes:
    base.FONTS = base.FONTS or base.Fonts()
    now = now or dt.datetime.now(dt.timezone.utc)
    running = [one for b in patch.banners if b.start <= now < b.end for one in pc._split(b)]
    sections = [(k, [b for b in running if b.kind == k]) for k in KINDS["hsr"]]
    sections = [(k, bs) for k, bs in sections if bs]
    upcoming = sorted((one for b in patch.banners if b.start > now and b.featured for one in pc._split(b)),
                      key=lambda b: b.start)[:9]
    rows = pc._rows
    height = PAD + HEAD_H + GAP + sum(SECTION_HEAD + rows(len(bs)) * (CARD_H + GAP) for _, bs in sections) + PAD
    if not sections:
        height += 60
    if upcoming:
        height += SECTION_HEAD + _next_layout(ImageDraw.Draw(Image.new("RGB", (1, 1))), upcoming, images, patch.clock)[1]
    card = rh._starmap(W, height, f"hsr-{patch.version}")
    _header(card, patch, now)

    y = PAD + HEAD_H + GAP
    for kind, banners in sections:
        _section(card, kind, SECTION_LIGHT.get(kind, HOLO), y)
        y += SECTION_HEAD
        for i, b in enumerate(banners):
            bx = PAD + (i % COLS) * (CARD_W + GAP)
            by = y + (i // COLS) * (CARD_H + GAP)
            _banner(card, b, images, (bx, by, bx + CARD_W, by + CARD_H), now)
        y += rows(len(banners)) * (CARD_H + GAP)
    if not sections:
        ImageDraw.Draw(card).text((PAD + 8, y + 30), "No warps are running right now.", font=h._raj("SemiBold", 20), fill=DIM, anchor="lm")
        y += 60
    if upcoming:
        _section(card, "Coming next", FAINT, y)
        _upcoming(card, upcoming, images, patch.clock, y + SECTION_HEAD)

    out = io.BytesIO()
    card.convert("RGB").save(out, "PNG", compress_level=3)
    return out.getvalue()
