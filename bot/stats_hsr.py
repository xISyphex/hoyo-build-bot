"""/hsr-stats drawn as the same navigation hologram as Star Rail's build card and records: the bridge's star map
behind cyan holo screens with cut corners. The Trailblazer's name and level on the top screen, the big numbers on
readouts, the smaller ones on screens of their own, and every character owned on projected tiles."""

from __future__ import annotations

import io

from PIL import Image, ImageDraw, ImageFilter

from . import card as base
from . import card_hsr as h
from . import records_hsr as rh
from .records import Member
from .stats import Profile

W = 1200
PAD = 24
GAP = 14
HEAD_H = 112
BIG_H = 96  # a headline readout
SECTION_HEAD = 48
ROW_H = 30  # a line on a group's screen
TILE_GAP = 10
HOLO, TEXT, DIM, FAINT, GOLD = h.HOLO, h.TEXT, h.DIM, h.FAINT, h.GOLD


def _spaced_w(draw, text: str, font, spacing: float) -> float:
    return sum(draw.textlength(ch, font=font) + spacing for ch in text) - spacing if text else 0


def _section(card: Image.Image, title: str, light, y: int, count: str = "") -> None:
    """A section's title with a status light before it, like the records' modes."""
    draw = ImageDraw.Draw(card)
    draw.rectangle((PAD + 6, y + 12, PAD + 9, y + 38), fill=light)
    glow = Image.new("RGBA", (40, 60), (0, 0, 0, 0))
    ImageDraw.Draw(glow).rectangle((18, 18, 21, 44), fill=light + (200,))
    card.alpha_composite(glow.filter(ImageFilter.GaussianBlur(5)), (PAD + 6 - 18, y - 6))
    font = h._raj("Bold", 26)
    h._top_text(card, (PAD + 22, y + 10), title.upper(), font, (255, 255, 255), 3)
    if count:
        draw = ImageDraw.Draw(card)
        x = PAD + 22 + _spaced_w(draw, title.upper(), font, 3) + 14
        h._spaced(draw, (x, y + 27), count, h._raj("Bold", 18), DIM, 2)


def _header(card: Image.Image, p: Profile) -> None:
    x0, y0, x1, y1 = PAD, PAD, W - PAD, PAD + HEAD_H
    rh._box(card, (x0, y0, x1, y1))
    draw = ImageDraw.Draw(card)
    h._spaced(draw, (x0 + 26, y0 + 26), "HONKAI: STAR RAIL  ·  TRAILBLAZER PROFILE", h._raj("SemiBold", 17), DIM, 1.8)
    name = (p.nickname or "Trailblazer").upper()
    h._top_text(card, (x0 + 24, y0 + 42), base._fit_text(draw, name, h._raj("Bold", 44), 640), h._raj("Bold", 44), (255, 255, 255), 6)
    draw = ImageDraw.Draw(card)
    right = x1 - 26
    if p.level:
        label = p.level_label.upper()
        lf = h._raj("Bold", 13)
        h._spaced(draw, (right - _spaced_w(draw, label, lf, 3.4), y0 + 26), label, lf, HOLO, 3.4)
        draw.text((right, y0 + 64), str(p.level), font=h._raj("Bold", 44), fill=HOLO, anchor="rm")
    server = base.server_name("hsr", p.uid)
    stamp = f"{server + ' · ' if server else ''}UID {p.uid}".upper()
    sf = h._raj("SemiBold", 14)
    h._spaced(draw, (right - _spaced_w(draw, stamp, sf, 1.4), y0 + 96), stamp, sf, FAINT, 1.4)


def _big(card: Image.Image, box, label: str, value: str) -> None:
    """A headline number: a screen with the spaced label over the value, both centred."""
    rh._box(card, box, h.PANEL, 120, 12)
    x0, y0, x1, y1 = box
    draw = ImageDraw.Draw(card)
    mid = (x0 + x1) / 2
    lf = h._raj("Bold", 13)
    text = label.upper()
    h._spaced(draw, (mid - _spaced_w(draw, text, lf, 3) / 2, y0 + 22), text, lf, DIM, 3)
    font = h._raj("Bold", 40)
    for size in (40, 34, 28, 24, 20, 18):  # Memory of Chaos's progress is a phrase, not a number
        font = h._raj("Bold", size)
        if draw.textlength(value, font=font) <= x1 - x0 - 24:
            break
    draw.text((mid, (y0 + 30 + y1) / 2 + 2), base._fit_text(draw, value, font, x1 - x0 - 24), font=font,
              fill=GOLD if label.lower() == "achievements" else HOLO, anchor="mm")


def _group(card: Image.Image, box, title: str, rows: list[tuple[str, str]]) -> None:
    """A screen of label / value lines under a waypoint and the group's name."""
    rh._box(card, box, rh.TEAM_FILL, 100, 12)
    x0, y0, x1, y1 = box
    draw = ImageDraw.Draw(card)
    cy = y0 + 24
    rh_d = 5
    draw.polygon([(x0 + 18, cy - rh_d), (x0 + 18 + rh_d, cy), (x0 + 18, cy + rh_d), (x0 + 18 - rh_d, cy)], fill=HOLO)
    h._spaced(draw, (x0 + 32, cy), title.upper(), h._raj("Bold", 17), TEXT, 1.6)
    lf, vf = h._raj("SemiBold", 16), h._raj("Bold", 18)
    y = y0 + 52
    for label, value in rows:
        draw.line((x0 + 18, y + ROW_H - 4, x1 - 18, y + ROW_H - 4), fill=(24, 70, 86), width=1)
        draw.text((x0 + 20, y + ROW_H / 2 - 2), label, font=lf, fill=DIM, anchor="lm")
        draw.text((x1 - 20, y + ROW_H / 2 - 2), base._fit_text(draw, value, vf, (x1 - x0) / 2), font=vf, fill=TEXT, anchor="rm")
        y += ROW_H


def _group_h(rows: int) -> int:
    return 52 + rows * ROW_H + 12


def _per_row() -> int:
    return (W - 2 * PAD + TILE_GAP) // (rh.TILE_W + TILE_GAP)


def draw_stats(p: Profile, images: dict[str, Image.Image]) -> bytes:
    base.FONTS = base.FONTS or base.Fonts()
    groups_h = max((_group_h(len(rows)) for _, rows in p.groups), default=0)
    per_row = _per_row()
    unit_rows = -(-len(p.units) // per_row)
    height = (PAD + HEAD_H + GAP + BIG_H + GAP + (groups_h + GAP if p.groups else 0)
              + (SECTION_HEAD + unit_rows * (rh.TILE_H + TILE_GAP) if p.units else 0) + PAD)
    card = rh._starmap(W, height, f"stats-{p.uid}")
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
        _section(card, "Characters", HOLO, y, str(len(p.units)))
        y += SECTION_HEAD
        row_w = per_row * rh.TILE_W + (per_row - 1) * TILE_GAP
        x0 = (W - row_w) // 2
        for i, u in enumerate(p.units):
            x = x0 + (i % per_row) * (rh.TILE_W + TILE_GAP)
            ty = y + (i // per_row) * (rh.TILE_H + TILE_GAP)
            member = Member(u.name, u.icon, u.level, u.rarity, u.copies)
            rh._tile(card, member, images.get(u.icon or ""), x, ty)

    out = io.BytesIO()
    card.convert("RGB").save(out, "PNG", compress_level=3)
    return out.getvalue()
