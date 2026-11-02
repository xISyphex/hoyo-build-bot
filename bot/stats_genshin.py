"""/genshin-stats in Genshin's own look, like its build card, records and patch card: dark glass panels lit gold
from the top left. The Traveler's name card behind the header with their profile picture, name, signature, Adventure
Rank and World Level, the big numbers on panels, the world's numbers in groups, each region's exploration as a bar,
and the name cards they show off."""

from __future__ import annotations

import io

from PIL import Image, ImageDraw, ImageFilter

from . import card as c
from . import records_card as rc
from .stats import Profile
from .stats_card import banner, cover, round_avatar

W = 1200
PAD = 32
GAP = 16
HEAD_H = 196  # the header panel
HEAD = PAD + HEAD_H + GAP
BIG_H = 92
ROW_H = 28
REGION_H = 38  # a region's exploration bar
SECTION_HEAD = 46
NC_W, NC_H = 212, 101  # a showcased name card
NC_GAP = 19
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


def _header(card: Image.Image, p: Profile, images, light) -> None:
    f = c.FONTS
    box = (PAD, PAD, W - PAD, PAD + HEAD_H)
    c._panel(card, box, 18)
    mask = Image.new("L", (box[2] - box[0], box[3] - box[1]), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, mask.width - 1, mask.height - 1), 18, fill=255)
    banner(card, images.get(p.banner or ""), box, mask)
    layer = Image.new("RGBA", card.size, (0, 0, 0, 0))
    ImageDraw.Draw(layer).rounded_rectangle(box, 18, outline=ACCENT + (90,), width=2)
    c._layer_onto(card, layer)
    cy = (box[1] + box[3]) / 2
    r = 62
    round_avatar(card, images.get(p.avatar or ""), box[0] + 34 + r, cy, r, light)
    draw = ImageDraw.Draw(card)
    x = box[0] + 34 + 2 * r + 34
    c._spaced(draw, (x + 2, box[1] + 40), "GENSHIN IMPACT  ·  TRAVELER PROFILE", f.label, light, 2.4)
    draw.text((x, box[1] + 86), c._fit_text(draw, p.nickname or "Traveler", f.name[50], 560), font=f.name[50], fill=c.TEXT,
              anchor="lm")
    if p.signature:
        lines = c._wrap(draw, p.signature.replace("\n", " "), f.small, 560, 2)
        for i, line in enumerate(lines):
            draw.text((x + 2, box[1] + 128 + i * 24), line, font=f.small, fill=c.DIM, anchor="lm")
    right = box[2] - 32
    if p.level:
        label = p.level_label.upper()
        c._spaced(draw, (right - draw.textlength(label, font=f.label) - 2.4 * (len(label) - 1), box[1] + 40), label,
                  f.label, c.DIM, 2.4)
        draw.text((right, box[1] + 86), str(p.level), font=f.name[50], fill=light, anchor="rm")
    if p.world_level:  # World Level on a line of its own under the Adventure Rank
        label, value = p.world_level
        vw = draw.textlength(value, font=f.stat_b)
        draw.text((right, box[1] + 128), value, font=f.stat_b, fill=c.TEXT, anchor="rm")
        text = label.upper()
        c._spaced(draw, (right - vw - 12 - draw.textlength(text, font=f.label) - 2.4 * (len(text) - 1), box[1] + 129), text,
                  f.label, c.DIM, 2.4)
    server = c.server_name("genshin", p.uid)
    draw.text((right, box[3] - 28), f"{server + ' · ' if server else ''}UID {p.uid}", font=f.stamp, fill=c.DIM, anchor="rm")


def _namecard(card: Image.Image, pic: Image.Image | None, x: int, y: int) -> None:
    if pic is None:
        return
    art = cover(pic, NC_W, NC_H, 0.5)
    mask = Image.new("L", (NC_W, NC_H), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, NC_W - 1, NC_H - 1), 10, fill=255)
    art.putalpha(mask)
    card.alpha_composite(art, (x, y))
    layer = Image.new("RGBA", card.size, (0, 0, 0, 0))
    ImageDraw.Draw(layer).rounded_rectangle((x, y, x + NC_W - 1, y + NC_H - 1), 10, outline=(255, 255, 255, 40))
    c._layer_onto(card, layer)


def draw_stats(p: Profile, images: dict[str, Image.Image]) -> bytes:
    c.FONTS = c.FONTS or c.Fonts()
    light = c._mix(ACCENT, (255, 255, 255), 0.45)
    groups_h = max((_group_h(len(rows)) for _, rows in p.groups), default=0)
    region_rows = -(-len(p.regions) // 2)
    cards = [images[u] for u in p.namecards if u in images]
    per_row = (W - 2 * PAD + NC_GAP) // (NC_W + NC_GAP)
    card_rows = -(-len(cards) // per_row)
    height = (HEAD + BIG_H + GAP + (groups_h + GAP if p.groups else 0)
              + (SECTION_HEAD + region_rows * REGION_H + GAP if p.regions else 0)
              + (SECTION_HEAD + card_rows * (NC_H + NC_GAP) if cards else 0) + PAD)
    card = Image.new("RGBA", (W, height), (14, 12, 24, 255))
    glow = Image.new("RGBA", (W, height), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse((-300, -260, 700, 300), fill=c._mix((14, 12, 24), ACCENT, 0.45) + (255,))
    ImageDraw.Draw(glow).ellipse((W - 420, -200, W + 300, 220), fill=c._mix((14, 12, 24), ACCENT, 0.25) + (255,))
    card.alpha_composite(glow.filter(ImageFilter.GaussianBlur(120)))
    _header(card, p, images, light)

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
    if cards:
        _section(card, "Name Cards", y)
        y += SECTION_HEAD
        for i, pic in enumerate(cards):
            row = i // per_row
            in_row = min(per_row, len(cards) - row * per_row)
            x0 = (W - (in_row * NC_W + (in_row - 1) * NC_GAP)) // 2
            _namecard(card, pic, x0 + (i % per_row) * (NC_W + NC_GAP), y + row * (NC_H + NC_GAP))

    out = io.BytesIO()
    card.convert("RGB").save(out, "PNG", compress_level=3)
    return out.getvalue()
