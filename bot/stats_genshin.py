"""/genshin-stats in Genshin's own look, like its build card, records and patch card: dark glass panels lit gold
from the top left. The Traveler's name and Adventure Rank on top, the big numbers on panels, the world's numbers in
groups, each region's exploration as a bar, and every character owned on its rarity colour."""

from __future__ import annotations

import io

from PIL import Image, ImageDraw, ImageFilter

from . import card as c
from . import records_card as rc
from .records import Member
from .stats import Profile

W = 1200
PAD = 32
GAP = 16
HEAD = 146
BIG_H = 92
ROW_H = 28
REGION_H = 38  # a region's exploration bar
SECTION_HEAD = 46
TILE_GAP = 12
ACCENT = rc.GAME_ACCENT["genshin"]


def _section(card: Image.Image, title: str, y: int, count: str = "") -> None:
    f = c.FONTS
    draw = ImageDraw.Draw(card)
    draw.rounded_rectangle((PAD, y + 12, PAD + 4, y + 34), 2, fill=ACCENT + (255,))
    draw.text((PAD + 16, y + 23), title, font=f.stat_b, fill=c.TEXT, anchor="lm")
    if count:
        draw.text((PAD + 26 + draw.textlength(title, font=f.stat_b), y + 24), count, font=f.small, fill=c.DIM, anchor="lm")


def _big(card: Image.Image, box, label: str, value: str, light) -> None:
    f = c.FONTS
    c._panel(card, box, 16)
    x0, y0, x1, y1 = box
    draw = ImageDraw.Draw(card)
    mid = (x0 + x1) / 2
    c._spaced(draw, (mid - (draw.textlength(label.upper(), font=f.label) + 2.4 * (len(label) - 1)) / 2, y0 + 24),
              label.upper(), f.label, c.DIM, 2.4)
    font = f.name[44]
    draw.text((mid, y0 + 60), c._fit_text(draw, value, font, x1 - x0 - 24), font=font,
              fill=light if label.lower() == "achievements" else c.TEXT, anchor="mm")


def _group(card: Image.Image, box, title: str, rows: list[tuple[str, str]]) -> None:
    f = c.FONTS
    c._panel(card, box, 16)
    x0, y0, x1, y1 = box
    draw = ImageDraw.Draw(card)
    draw.text((x0 + 18, y0 + 24), title, font=f.small_b, fill=c.TEXT, anchor="lm")
    y = y0 + 46
    for label, value in rows:
        draw.text((x0 + 18, y + ROW_H / 2), label, font=f.small, fill=c.DIM, anchor="lm")
        draw.text((x1 - 18, y + ROW_H / 2), value, font=f.small_b, fill=c.TEXT, anchor="rm")
        y += ROW_H


def _group_h(rows: int) -> int:
    return 46 + rows * ROW_H + 10


def _region(card: Image.Image, x0: float, x1: float, y: float, name: str, explored: float, light) -> None:
    """A region's name and how much of it is explored, over a bar filled that far (gold when it's all done)."""
    f = c.FONTS
    draw = ImageDraw.Draw(card)
    draw.text((x0, y + 10), name, font=f.small_b, fill=c.TEXT, anchor="lm")
    done = explored >= 100
    draw.text((x1, y + 10), f"{explored:g}%", font=f.small_b, fill=light if done else c.DIM, anchor="rm")
    bar_y = y + 24
    layer = Image.new("RGBA", card.size, (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    ld.rounded_rectangle((x0, bar_y, x1, bar_y + 7), 4, fill=(255, 255, 255, 24))
    fx = x0 + (x1 - x0) * min(explored, 100) / 100
    if fx > x0 + 7:
        ld.rounded_rectangle((x0, bar_y, fx, bar_y + 7), 4, fill=(light if done else ACCENT) + (255,))
    c._layer_onto(card, layer)


def _per_row() -> int:
    return (W - 2 * PAD + TILE_GAP) // (rc.PORTRAIT + TILE_GAP)


def draw_stats(p: Profile, images: dict[str, Image.Image]) -> bytes:
    c.FONTS = c.FONTS or c.Fonts()
    f = c.FONTS
    light = c._mix(ACCENT, (255, 255, 255), 0.45)
    groups_h = max((_group_h(len(rows)) for _, rows in p.groups), default=0)
    region_rows = -(-len(p.regions) // 2)
    per_row = _per_row()
    unit_rows = -(-len(p.units) // per_row)
    height = (HEAD + BIG_H + GAP + (groups_h + GAP if p.groups else 0)
              + (SECTION_HEAD + region_rows * REGION_H + GAP if p.regions else 0)
              + (SECTION_HEAD + 8 + unit_rows * (rc.PORTRAIT + TILE_GAP) if p.units else 0) + PAD)
    card = Image.new("RGBA", (W, height), (14, 12, 24, 255))
    glow = Image.new("RGBA", (W, height), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse((-300, -260, 700, 300), fill=c._mix((14, 12, 24), ACCENT, 0.45) + (255,))
    ImageDraw.Draw(glow).ellipse((W - 420, -200, W + 300, 220), fill=c._mix((14, 12, 24), ACCENT, 0.25) + (255,))
    card.alpha_composite(glow.filter(ImageFilter.GaussianBlur(120)))
    draw = ImageDraw.Draw(card)

    # The name on the left, the Adventure Rank on the right
    c._spaced(draw, (PAD + 2, 40), "GENSHIN IMPACT  ·  TRAVELER PROFILE", f.label, light, 2.4)
    draw.text((PAD, 86), c._fit_text(draw, p.nickname or "Traveler", f.name[56], 700), font=f.name[56], fill=c.TEXT, anchor="lm")
    if p.level:
        label = p.level_label.upper()
        c._spaced(draw, (W - PAD - draw.textlength(label, font=f.label) - 2.4 * (len(label) - 1), 40), label, f.label, c.DIM, 2.4)
        draw.text((W - PAD, 86), str(p.level), font=f.name[56], fill=light, anchor="rm")
    server = c.server_name("genshin", p.uid)
    draw.text((W - PAD, 124), f"{server + ' · ' if server else ''}UID {p.uid}", font=f.stamp, fill=c.DIM, anchor="rm")

    y = HEAD
    n = max(1, len(p.headline))
    bw = (W - 2 * PAD - (n - 1) * GAP) / n
    for i, (label, value) in enumerate(p.headline):
        x = PAD + i * (bw + GAP)
        _big(card, (round(x), y, round(x + bw), y + BIG_H), label, value, light)
    y += BIG_H + GAP
    if p.groups:
        n = len(p.groups)
        gw = (W - 2 * PAD - (n - 1) * GAP) / n
        for i, (title, rows) in enumerate(p.groups):
            x = PAD + i * (gw + GAP)
            _group(card, (round(x), y, round(x + gw), y + groups_h), title, rows)
        y += groups_h + GAP
    if p.regions:
        _section(card, "Exploration", y)
        y += SECTION_HEAD
        cw = (W - 2 * PAD - 3 * GAP) / 2
        for i, r in enumerate(p.regions):
            x = PAD + (i % 2) * (cw + 3 * GAP)
            _region(card, x, x + cw, y + (i // 2) * REGION_H, r.name, r.explored, light)
        y += region_rows * REGION_H + GAP
    if p.units:
        _section(card, "Characters", y, str(len(p.units)))
        y += SECTION_HEAD + 8  # the copies pills stick out above the tiles
        row_w = per_row * rc.PORTRAIT + (per_row - 1) * TILE_GAP
        x0 = (W - row_w) // 2
        for i, u in enumerate(p.units):
            x = x0 + (i % per_row) * (rc.PORTRAIT + TILE_GAP)
            ty = y + (i // per_row) * (rc.PORTRAIT + TILE_GAP)
            rc._gi_portrait(card, "genshin", Member(u.name, u.icon, u.level, u.rarity, u.copies), images.get(u.icon or ""),
                            x, ty, ACCENT)

    out = io.BytesIO()
    card.convert("RGB").save(out, "PNG", compress_level=3)
    return out.getvalue()
