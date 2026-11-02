"""/zzz-stats drawn as the same retro dashboard as ZZZ's build card, records and patch card: a console with screws,
the Proxy's name on the top screen with the Inter-Knot level on a readout, the big numbers on bezel readouts, the
smaller ones on a screen of their own, and every agent owned on a little CRT monitor."""

from __future__ import annotations

import io

from PIL import Image, ImageDraw

from . import card as base
from . import card_zzz as z
from . import records_zzz as rz
from .records import Member
from .stats import Profile

W = 1200
PAD = 24
GAP = 14
HEAD_H = 120
BIG_H = 92
SECTION_HEAD = 48
ROW_H = 30
MON_W, MON_H = 100, 108  # an agent's monitor
MON_GAP = 10


def _silk_w(draw, text: str) -> float:
    return sum(draw.textlength(ch, font=z.FONTS.silk) for ch in text) + 2.4 * (len(text) - 1)


def _header(card: Image.Image, p: Profile) -> None:
    sx0, sy0, sx1, sy1 = z._bezel(card, (PAD, PAD, W - PAD, PAD + HEAD_H), 12, 5)
    draw = ImageDraw.Draw(card)
    z._silk(draw, (sx0 + 20, sy0 + 24), "ZENLESS ZONE ZERO  ·  PROXY PROFILE")
    name = (p.nickname or "Proxy").upper()
    draw.text((sx0 + 18, sy0 + 74), base._fit_text(draw, name, z._rubik(46, 800), 620), font=z._rubik(46, 800),
              fill=base.TEXT, anchor="ls")
    if p.title:
        z._silk(draw, (sx0 + 20, sy0 + 98), p.title.upper(), z.AMBER)
    right = sx1 - 20
    if p.level:
        label = p.level_label.upper()
        z._silk(draw, (right - _silk_w(draw, label), sy0 + 24), label)
        draw.text((right, sy0 + 74), str(p.level), font=z._rubik(46, 800), fill=z.AMBER, anchor="rs")
    server = base.server_name("zzz", p.uid)
    stamp = f"{server + ' · ' if server else ''}UID {p.uid}".upper()
    z._silk(draw, (right - _silk_w(draw, stamp), sy0 + 98), stamp)


def _big(card: Image.Image, box, label: str, value: str) -> None:
    """A headline number on a bezel readout: the label printed above, the value lit."""
    sx0, sy0, sx1, sy1 = z._bezel(card, box, 10, 5)
    draw = ImageDraw.Draw(card)
    cx = (sx0 + sx1) / 2
    text = label.upper()
    z._silk(draw, (cx, sy0 + 18), text, centre=True)
    font = z._rubik(36, 700)
    for size in (36, 30, 24):
        font = z._rubik(size, 700)
        if draw.textlength(value, font=font) <= sx1 - sx0 - 20:
            break
    color = z.AMBER if label.lower() == "achievements" else z.TEAL
    draw.text((cx, (sy0 + 20 + sy1) / 2 + 2), base._fit_text(draw, value, font, sx1 - sx0 - 20), font=font, fill=color, anchor="mm")


def _group(card: Image.Image, box, title: str, rows: list[tuple[str, str]]) -> None:
    """A screen of printed labels and lit values, under a pilot lamp and the group's name."""
    x0, y0, x1, y1 = box
    sx0, sy0, sx1, sy1 = z._bezel(card, box, 12, 0, z.BODY_DARK)
    rz._pilot(card, x0 + 24, y0 + 26, z.AMBER)
    draw = ImageDraw.Draw(card)
    draw.text((x0 + 42, y0 + 34), title.upper(), font=z._rubik(18, 800), fill=base.TEXT, anchor="ls")
    y = y0 + 52
    for label, value in rows:
        draw.line((x0 + 18, y + ROW_H - 4, x1 - 18, y + ROW_H - 4), fill=(44, 42, 56), width=1)
        z._silk(draw, (x0 + 20, y + ROW_H / 2 + 2), label.upper())
        draw.text((x1 - 20, y + ROW_H / 2 - 2), base._fit_text(draw, value, z.FONTS.sub, (x1 - x0) / 2), font=z.FONTS.sub,
                  fill=z.TEAL, anchor="rm")
        y += ROW_H


def _group_h(rows: int) -> int:
    return 52 + rows * ROW_H + 14


def _per_row() -> int:
    return (W - 2 * PAD + MON_GAP) // (MON_W + MON_GAP)


def draw_stats(p: Profile, images: dict[str, Image.Image]) -> bytes:
    base.FONTS = base.FONTS or base.Fonts()
    z.FONTS = z.FONTS or z.Fonts()
    groups_h = max((_group_h(len(rows)) for _, rows in p.groups), default=0)
    per_row = _per_row()
    unit_rows = -(-len(p.units) // per_row)
    height = (PAD + HEAD_H + GAP + BIG_H + GAP + (groups_h + GAP if p.groups else 0)
              + (SECTION_HEAD + unit_rows * (MON_H + MON_GAP) if p.units else 0) + PAD)
    card = rz._console(W, height)
    _header(card, p)

    y = PAD + HEAD_H + GAP
    n = max(1, len(p.headline))
    bw = (W - 2 * PAD - (n - 1) * GAP) / n
    for i, (label, value) in enumerate(p.headline):
        x = PAD + i * (bw + GAP)
        _big(card, (round(x), y, round(x + bw), y + BIG_H), label, value)
    y += BIG_H + GAP
    if p.groups:
        n = len(p.groups)
        gw = (W - 2 * PAD - (n - 1) * GAP) / n
        for i, (title, rows) in enumerate(p.groups):
            x = PAD + i * (gw + GAP)
            _group(card, (round(x), y, round(x + gw), y + groups_h), title, rows)
        y += groups_h + GAP
    if p.units:
        rz._pilot(card, PAD + 14, y + 22, z.AMBER)
        draw = ImageDraw.Draw(card)
        draw.text((PAD + 34, y + 32), "AGENTS", font=z._rubik(24, 800), fill=base.TEXT, anchor="ls")
        z._silk(draw, (PAD + 34 + draw.textlength("AGENTS", font=z._rubik(24, 800)) + 12, y + 31), str(len(p.units)))
        y += SECTION_HEAD
        row_w = per_row * MON_W + (per_row - 1) * MON_GAP
        x0 = (W - row_w) // 2
        for i, u in enumerate(p.units):
            x = x0 + (i % per_row) * (MON_W + MON_GAP)
            ty = y + (i // per_row) * (MON_H + MON_GAP)
            rz._monitor(card, Member(u.name, u.icon, u.level, u.rarity, u.copies), images.get(u.icon or ""), x, ty, MON_W, MON_H)

    out = io.BytesIO()
    card.convert("RGB").save(out, "PNG", compress_level=3)
    return out.getvalue()
