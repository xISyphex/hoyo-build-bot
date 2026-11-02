"""/zzz-stats drawn as the same retro dashboard as ZZZ's build card, records and patch card: a console with screws,
the Proxy's calling card lit up on the top screen with their profile picture on a little monitor, name, title badge,
signature and Inter-Knot level, the big numbers on bezel readouts, and the smaller ones and showcased medals on screens
of their own."""

from __future__ import annotations

import io

from PIL import Image, ImageDraw

from . import card as base
from . import card_zzz as z
from . import records_zzz as rz
from .stats import Profile
from .stats_card import banner, cover

W = 1200
PAD = 24
GAP = 14
HEAD_H = 196
AVATAR = 132
MEDAL_ROW = 44
BIG_H = 92
SECTION_HEAD = 48
ROW_H = 30
SILK_LIGHT = (200, 196, 214)
SS = 4


def _silk_w(draw, text: str) -> float:
    return sum(draw.textlength(ch, font=z.FONTS.silk) for ch in text) + 2.4 * (len(text) - 1)


def _title_badge(card: Image.Image, text: str, colors, x: float, cy: float) -> None:
    """The player's title on a slanted plate filled with its two colours, like in game."""
    font = z._rubik(17, 800, italic=True)
    draw = ImageDraw.Draw(card)
    w = round(draw.textlength(text, font=font) + 34)
    hh = 28
    a, b = colors if colors else ("e6e9ea", "8ea3ae")
    ca, cb = tuple(int(a[i:i + 2], 16) for i in (0, 2, 4)), tuple(int(b[i:i + 2], 16) for i in (0, 2, 4))
    grad = Image.new("RGBA", (w, hh))
    for gx in range(w):
        t = gx / max(w - 1, 1)
        ImageDraw.Draw(grad).line((gx, 0, gx, hh), fill=tuple(round(p + (q - p) * t) for p, q in zip(ca, cb)) + (255,))
    mask = Image.new("L", (w * SS, hh * SS), 0)
    ImageDraw.Draw(mask).polygon([(8 * SS, 0), (w * SS, 0), (w * SS - 8 * SS, hh * SS), (0, hh * SS)], fill=255)
    grad.putalpha(mask.resize((w, hh), Image.LANCZOS))
    card.alpha_composite(grad, (round(x), round(cy - hh / 2)))
    lum = sum(ca) / 3
    ImageDraw.Draw(card).text((x + w / 2, cy), text, font=font, fill=(20, 18, 26) if lum > 140 else (255, 255, 255), anchor="mm")


def _header(card: Image.Image, p: Profile, images) -> None:
    sx0, sy0, sx1, sy1 = z._bezel(card, (PAD, PAD, W - PAD, PAD + HEAD_H), 12, 5)
    mask = Image.new("L", (sx1 - sx0, sy1 - sy0), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, mask.width - 1, mask.height - 1), 6, fill=255)
    banner(card, images.get(p.banner or ""), (sx0, sy0, sx1, sy1), mask, shade=z.GLASS, right=0.62)
    z._scanlines(card, (sx0, sy0, sx1, sy1), 30)
    # the profile picture on a little monitor of its own
    cy = (sy0 + sy1) / 2
    ax0 = sx0 + 24
    mx0, my0, mx1, my1 = z._bezel(card, (ax0, round(cy - AVATAR / 2), ax0 + AVATAR, round(cy + AVATAR / 2)), 12, 6)
    pic = images.get(p.avatar or "")
    if pic is not None:
        art = cover(pic, mx1 - mx0, my1 - my0)
        m = Image.new("L", art.size, 0)
        ImageDraw.Draw(m).rounded_rectangle((0, 0, art.width - 1, art.height - 1), 6, fill=255)
        art.putalpha(Image.composite(art.getchannel("A"), m, m))
        card.alpha_composite(art, (mx0, my0))
    draw = ImageDraw.Draw(card)
    tx = ax0 + AVATAR + 28
    z._silk(draw, (tx + 2, sy0 + 26), "ZENLESS ZONE ZERO  ·  PROXY PROFILE")
    name = (p.nickname or "Proxy").upper()
    draw.text((tx, sy0 + 78), base._fit_text(draw, name, z._rubik(46, 800), 560), font=z._rubik(46, 800),
              fill=base.TEXT, anchor="ls")
    y = sy0 + 104
    if p.title:
        _title_badge(card, p.title, p.title_colors, tx, y)
        y += 34
    if p.signature:
        draw = ImageDraw.Draw(card)
        sf = z._rubik(17, 500)
        lines = base._wrap(draw, p.signature.replace("\n", " "), sf, 560, 1 if p.title else 2)
        for i, line in enumerate(lines):
            draw.text((tx + 2, y + 6 + i * 22), line, font=sf, fill=SILK_LIGHT, anchor="lm")
    draw = ImageDraw.Draw(card)
    right = sx1 - 22
    if p.level:
        label = p.level_label.upper()
        z._silk(draw, (right - _silk_w(draw, label), sy0 + 26), label)
        draw.text((right, sy0 + 78), str(p.level), font=z._rubik(46, 800), fill=z.AMBER, anchor="rs")
    server = base.server_name("zzz", p.uid)
    stamp = f"{server + ' · ' if server else ''}UID {p.uid}".upper()
    z._silk(draw, (right - _silk_w(draw, stamp), sy1 - 22), stamp)


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


def _medals(card: Image.Image, box, medals, images) -> None:
    """The medals the Proxy shows off: each one's emblem, name and number."""
    x0, y0, x1, y1 = box
    z._bezel(card, box, 12, 0, z.BODY_DARK)
    rz._pilot(card, x0 + 24, y0 + 26, z.AMBER)
    draw = ImageDraw.Draw(card)
    draw.text((x0 + 42, y0 + 34), "MEDALS", font=z._rubik(18, 800), fill=base.TEXT, anchor="ls")
    y = y0 + 50
    for m in medals:
        icon = images.get(m.icon or "")
        if icon is not None:
            pic = icon.convert("RGBA")
            pic.thumbnail((MEDAL_ROW - 4, MEDAL_ROW - 4), Image.LANCZOS)
            card.alpha_composite(pic, (x0 + 18 + (MEDAL_ROW - pic.width) // 2, y + (MEDAL_ROW - pic.height) // 2))
        draw = ImageDraw.Draw(card)
        draw.text((x0 + 26 + MEDAL_ROW, y + MEDAL_ROW / 2), base._fit_text(draw, m.name, z._rubik(16, 600), (x1 - x0) - 150),
                  font=z._rubik(16, 600), fill=SILK_LIGHT, anchor="lm")
        draw.text((x1 - 20, y + MEDAL_ROW / 2), m.value, font=z.FONTS.sub, fill=z.TEAL, anchor="rm")
        y += MEDAL_ROW


def _medals_h(n: int) -> int:
    return 50 + n * MEDAL_ROW + 14


def draw_stats(p: Profile, images: dict[str, Image.Image]) -> bytes:
    base.FONTS = base.FONTS or base.Fonts()
    z.FONTS = z.FONTS or z.Fonts()
    panels = [("group", title, rows) for title, rows in p.groups] + ([("medals", "Medals", p.medals)] if p.medals else [])
    row_h = max([_group_h(len(rows)) for kind, _, rows in panels if kind == "group"]
                + [_medals_h(len(p.medals)) if p.medals else 0], default=0)
    height = PAD + HEAD_H + GAP + BIG_H + (GAP + row_h if panels else 0) + PAD
    card = rz._console(W, height)
    _header(card, p, images)

    y = PAD + HEAD_H + GAP
    n = max(1, len(p.headline))
    bw = (W - 2 * PAD - (n - 1) * GAP) / n
    for i, (label, value) in enumerate(p.headline):
        x = PAD + i * (bw + GAP)
        _big(card, (round(x), y, round(x + bw), y + BIG_H), label, value)
    y += BIG_H + GAP
    if panels:
        n = len(panels)
        gw = (W - 2 * PAD - (n - 1) * GAP) / n
        for i, (kind, title, rows) in enumerate(panels):
            box = (round(PAD + i * (gw + GAP)), y, round(PAD + i * (gw + GAP) + gw), y + row_h)
            if kind == "medals":
                _medals(card, box, rows, images)
            else:
                _group(card, box, title, rows)

    out = io.BytesIO()
    card.convert("RGB").save(out, "PNG", compress_level=3)
    return out.getvalue()
