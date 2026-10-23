"""ZZZ's battle records drawn as the same retro dashboard as its build card: a console with screws, each mode a
panel cut into it, the totals on small readout screens, each team a cartridge holding its agents on little CRT
monitors, and the ratings on dome lamps."""

from __future__ import annotations

import io

from PIL import Image, ImageDraw, ImageFilter

from . import card as base
from . import card_zzz as z
from . import record_icons
from . import records_card as rc
from .records import Member, Record, Team, copies_label

W = rc.W  # as wide as the other games' records
PAD = 24
GAP = 14
INNER = 16  # a mode panel's padding round its teams
MON_W, MON_H = 104, 108  # an agent's monitor, near square so a round icon's square loses little
MON_GAP = 10
BANGBOO = 68
HEAD = 88  # a mode panel's header
LABEL_H = 34  # a team's name over its monitors
CHIPS_H = 40  # a team's results under them
TEAM_H = LABEL_H + 8 + MON_H + 10 + CHIPS_H
STAGE_H = 40  # the line over a stage of its own (Adversity Mode)
SIDE_W = 150  # a stage's own numbers, as readouts beside its cartridge
MODE_LAMP = {"sd": (94, 200, 255), "da": (255, 86, 86)}  # each mode's pilot lamp
RARITY_GLASS = {5: ((150, 108, 30), (40, 28, 8)), 4: ((104, 58, 150), (28, 14, 44))}  # S gold, A purple: top, bottom
LETTERS = {5: "S", 4: "A"}


def _console(w: int, h: int) -> Image.Image:
    """The console body: dark plastic with a faint grain, and a screw in each corner."""
    card = Image.new("RGBA", (w, h), z.BODY + (255,))
    grad = Image.linear_gradient("L").resize((w, h))
    card = Image.composite(Image.new("RGBA", (w, h), z.BODY_DARK + (255,)), card, grad)
    noise = Image.effect_noise((w // 2, h // 2), 18).resize((w, h)).point(lambda v: max(0, v - 128) // 6)
    card.alpha_composite(Image.merge("RGBA", (noise, noise, noise, noise)))
    for x, y in ((11, 11), (w - 11, 11), (11, h - 11), (w - 11, h - 11)):
        z._screw(card, x, y)
    return card


def _pilot(card: Image.Image, cx: float, cy: float, color) -> None:
    """A small round pilot lamp, lit."""
    draw = ImageDraw.Draw(card)
    draw.ellipse((cx - 9, cy - 9, cx + 9, cy + 9), fill=(4, 4, 7), outline=(50, 48, 64))
    glow = Image.new("RGBA", (40, 40), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse((14, 14, 26, 26), fill=color + (255,))
    card.alpha_composite(glow.filter(ImageFilter.GaussianBlur(4)), (round(cx - 20), round(cy - 20)))
    draw.ellipse((cx - 5, cy - 5, cx + 5, cy + 5), fill=base._mix(color, (255, 255, 255), 0.3))


def _sockets(card: Image.Image, cx: float, cy: float, lit: int, total: int = 3, r: int = 9) -> float:
    """Stars as a row of round lamps, the earned ones lit amber. Returns the row's width."""
    draw = ImageDraw.Draw(card)
    step = 2 * r + 6
    x = cx - (total * step - 6) / 2 + r
    for i in range(total):
        draw.ellipse((x - r, cy - r, x + r, cy + r), fill=(4, 4, 7), outline=(50, 48, 64))
        if i < lit:
            draw.ellipse((x - r + 3, cy - r + 3, x + r - 3, cy + r - 3), fill=z.AMBER)
        x += step
    return total * step - 6


def _stars(value: str) -> tuple[int, int] | None:
    """'2/3' -> (2, 3)."""
    try:
        got, of = value.replace(" ", "").split("/")
        return int(got), int(of)
    except ValueError:
        return None


UNLABELLED = {"score", "time", "rating"}  # plain numbers, no printed label (Syphex's pick)
VALUE_COLOR = {"score": z.AMBER, "top": z.TEAL, "time": z.TEAL, "stars": z.AMBER}


def _readout_w(draw: ImageDraw.ImageDraw, label: str, value: str) -> int:
    if label.lower() == "rating":
        return 64
    shown = len(label) * 9 if label.lower() not in UNLABELLED else 0
    return round(max(draw.textlength(value, font=z.FONTS.read), shown) + 36)


def _readout(card: Image.Image, box, label: str, value: str, big: bool = False, foil: bool = False) -> None:
    """A small screen with a printed label over the value (the rating on a dome lamp, stars as lamps). big: the
    taller readouts beside a stage's cartridge. foil: the value (or the rating lamp) in platinum foil."""
    sx0, sy0, sx1, sy1 = z._bezel(card, box, 10, 5)
    draw = ImageDraw.Draw(card)
    cx = (sx0 + sx1) / 2
    key = label.lower()
    if key in UNLABELLED or big:  # the readouts beside a stage show just their value
        mid = (sy0 + sy1) / 2
    else:
        z._silk(draw, (cx, sy0 + 14), label.upper(), centre=True)
        mid = (sy0 + 18 + sy1) / 2
    if key == "rating":
        _rating(card, value, cx, mid, 24 if big else 20, foil)
        return
    stars = _stars(value) if key == "stars" else None
    if stars:
        _sockets(card, cx, mid, *stars, r=13 if big else 9)
        return
    font = z._rubik(30, 700) if big else z.FONTS.read
    if foil:
        _foil_text(card, (cx, mid + 1), value, font, "mm")
        return
    draw.text((cx, mid + 1), value, font=font, fill=VALUE_COLOR.get(key, base.TEXT), anchor="mm")


def _rating(card: Image.Image, letter: str, cx: float, cy: float, r: float, holo: bool = False) -> None:
    """A rating on a dome lamp (S+ printed on the glass), in platinum foil for a top-1% player."""
    z.dome_lamp(card, letter, cx, cy, r, holo)


def _button(card: Image.Image, box, text: str, lit: bool) -> None:
    """A small TV push button: amber when the agent has copies beyond the first, grey otherwise."""
    k = z.SS
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    face = z.AMBER if lit else (70, 66, 86)
    layer = Image.new("RGBA", (w * k, h * k), (0, 0, 0, 0))
    grad = Image.linear_gradient("L").resize((w * k, h * k))
    top, bottom = base._mix(face, (255, 255, 255), 0.3), base._mix(face, (0, 0, 0), 0.35)
    fill = Image.composite(Image.new("RGBA", grad.size, bottom + (255,)), Image.new("RGBA", grad.size, top + (255,)), grad)
    mask = Image.new("L", grad.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, w * k - 1, h * k - 1), 4 * k, fill=255)
    layer.paste(fill, (0, 0), mask)
    d = ImageDraw.Draw(layer)
    d.rounded_rectangle((0, 0, w * k - 1, h * k - 1), 4 * k, outline=(10, 8, 16, 255), width=k)
    d.text((w * k / 2, h * k / 2 + k / 2), text, font=z._rubik(12 * k, 800, True),
           fill=(14, 10, 22, 255) if lit else (200, 196, 220, 255), anchor="mm")
    card.alpha_composite(layer.resize((w, h), Image.LANCZOS), (x0, y0))


def _monitor(card: Image.Image, member: Member, icon: Image.Image | None, x: int, y: int, w: int, h: int,
             button: bool = True) -> None:
    """An agent on a little CRT: the picture on glass tinted by rarity (gold S, purple A), scanlines, the level
    printed under it and the Mindscape on a push button."""
    sx0, sy0, sx1, sy1 = z._bezel(card, (x, y, x + w, y + h), 9, 4, (10, 10, 18))
    gw, gh = sx1 - sx0, sy1 - sy0
    top, bottom = RARITY_GLASS.get(member.rarity, ((70, 66, 86), (20, 18, 28)))
    grad = Image.linear_gradient("L").resize((gw, gh))
    glass = Image.composite(Image.new("RGBA", (gw, gh), bottom + (255,)), Image.new("RGBA", (gw, gh), top + (255,)), grad)
    if icon is not None:
        glass.alpha_composite(rc._cover(icon, gw, gh, top=False))  # HoYoLAB's square agent picture, uncropped
    shade = Image.linear_gradient("L").resize((gw, 30)).point(lambda v: min(235, round(v * 1.6)))  # dark under the level
    strip = Image.new("RGBA", (gw, 30), (6, 6, 10, 255))
    strip.putalpha(shade)
    glass.alpha_composite(strip, (0, gh - 30))
    mask = Image.new("L", (gw, gh), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, gw - 1, gh - 1), 5, fill=255)
    card.paste(glass, (sx0, sy0), mask)
    z._scanlines(card, (sx0, sy0, sx1, sy1), 34)
    draw = ImageDraw.Draw(card)
    if member.level:
        draw.text((sx0 + 6, sy1 - 9), "LV", font=z.FONTS.silk, fill=(196, 192, 214), anchor="ls")
        draw.text((sx0 + 23, sy1 - 8), str(member.level), font=z._rubik(14, 700), fill=base.TEXT, anchor="ls")
    label = copies_label("zzz", member) if button else ""
    if label:
        bw = round(draw.textlength(label, font=z._rubik(12, 800, True))) + 14
        _button(card, (sx0 + 4, sy0 + 4, sx0 + 4 + bw, sy0 + 22), label, bool(member.copies))


def _percent(value: str) -> float:
    """'0.85%' -> 0.85 (100 when it isn't a percentage)."""
    try:
        return float(value.strip().rstrip("%"))
    except ValueError:
        return 100.0


SCORE_GOLD, SCORE_PURPLE, SCORE_BLUE = (255, 204, 96), (200, 150, 255), (112, 176, 255)  # S, A, B
# Per mode: a team's score from which it shows in platinum foil, then gold, then purple (below: blue)
SCORE_TIERS = {"sd": (50000, 25000, 0), "da": (65000, 20000, 14000)}


def score_tier(mode: str, value: str) -> str:
    """'platinum', 'gold', 'purple' or 'blue' for a team's score in this mode (Syphex's thresholds)."""
    try:
        score = int(value.replace(",", ""))
    except ValueError:
        score = 0
    platinum, gold, purple = SCORE_TIERS.get(mode, SCORE_TIERS["sd"])
    return "platinum" if score >= platinum else "gold" if score >= gold else "purple" if score >= purple else "blue"


def _score_text(card: Image.Image, xy, value: str, font, mode: str) -> None:
    """A team's score in its tier's colour; platinum is the holographic foil of the top-ranking badge."""
    tier = score_tier(mode, value)
    if tier == "platinum":
        _foil_text(card, xy, value, font, "lm")
    else:
        fill = {"gold": SCORE_GOLD, "purple": SCORE_PURPLE, "blue": SCORE_BLUE}[tier]
        ImageDraw.Draw(card).text(xy, value, font=font, fill=fill, anchor="lm")


def _foil_text(card: Image.Image, xy, value: str, font, anchor: str) -> None:
    """Text in the holographic foil of the top-ranking badge."""
    mask = Image.new("L", card.size, 0)
    ImageDraw.Draw(mask).text(xy, value, font=font, fill=255, anchor=anchor)
    box = mask.getbbox()
    if not box:
        return
    foil = record_icons._bands((box[2] - box[0], box[3] - box[1]), record_icons.HOLO, 35)
    card.paste(foil, box[:2], mask.crop(box))


def _chips(card: Image.Image, chips: list[tuple[str, str]], cx: float, cy: float, mode: str) -> None:
    """A team's results in a row: the rating lamp, the stars as lamps, the score and time as printed readings."""
    draw = ImageDraw.Draw(card)
    f = z.FONTS
    parts = []  # (width, drawer)
    for kind, value in chips:
        if kind == "rating":
            continue  # the score's colour tells the rating
        if kind == "stars" and _stars(value):
            got, of = _stars(value)
            w = of * 20 - 6
            parts.append((w, lambda x, got=got, of=of, w=w: _sockets(card, x + w / 2, cy, got, of, 7)))
        else:
            label = "" if kind in UNLABELLED else kind.upper()
            lw = sum(draw.textlength(ch, font=f.silk) for ch in label) + 2.4 * (len(label) - 1) + 8 if label else 0
            w = lw + draw.textlength(value, font=f.mid)
            color = VALUE_COLOR.get(kind, base.TEXT)

            def put(x, kind=kind, label=label, value=value, lw=lw, color=color):
                if label:
                    z._silk(draw, (x, cy + 4), label)
                if kind == "score":
                    _score_text(card, (x + lw, cy + 1), value, f.mid, mode)
                else:
                    draw.text((x + lw, cy + 1), value, font=f.mid, fill=color, anchor="lm")
            parts.append((w, put))
    pad, gap = 12, 10  # each result on its own dark see-through pill, so it reads on any boss picture
    total = sum(w + 2 * pad for w, _ in parts) + gap * (len(parts) - 1)
    x = cx - total / 2
    pill = Image.new("RGBA", card.size, (0, 0, 0, 0))
    pd = ImageDraw.Draw(pill)
    for w, _ in parts:
        pd.rounded_rectangle((x, cy - 15, x + w + 2 * pad, cy + 15), radius=15, fill=(8, 8, 14, 175), outline=(255, 255, 255, 28))
        x += w + 2 * pad + gap
    card.alpha_composite(pill)
    x = cx - total / 2
    for w, put in parts:
        put(x + pad)
        x += w + 2 * pad + gap


def _team(card: Image.Image, team: Team, images: dict, box, mode: str) -> None:
    """A team as a cartridge: its name, its agents (and Bangboo) on monitors, its results under them."""
    x0, y0, x1, y1 = box
    sx0, sy0, sx1, sy1 = z._bezel(card, box, 12, 5)
    art = images.get(team.art or "")
    if art is not None:
        rc._art(card, art, (sx0, sy0, sx1, sy1))
    draw = ImageDraw.Draw(card)
    room = sx1 - sx0 - 24
    draw.text((sx0 + 12, sy0 + LABEL_H / 2 + 1), base._fit_text(draw, team.label, z._rubik(17, 700), room),
              font=z._rubik(17, 700), fill=base.TEXT, anchor="lm")
    draw.line((sx0 + 8, sy0 + LABEL_H, sx1 - 8, sy0 + LABEL_H), fill=(44, 42, 58), width=1)
    members = team.members[:4]
    row = len(members) * MON_W + max(0, len(members) - 1) * MON_GAP + (MON_GAP + BANGBOO if team.bangboo else 0)
    x = round((sx0 + sx1 - row) / 2)
    top = sy0 + LABEL_H + 8
    for m in members:
        _monitor(card, m, images.get(m.icon_url or ""), x, top, MON_W, MON_H)
        x += MON_W + MON_GAP
    if team.bangboo:  # smaller, on the same bottom line
        b = team.bangboo
        _monitor(card, b, images.get(b.icon_url or ""), x, top + MON_H - BANGBOO, BANGBOO, BANGBOO, button=False)
    if team.chips:
        _chips(card, team.chips, (sx0 + sx1) / 2, sy1 - CHIPS_H / 2 - 2, mode)


def _stage_line(card: Image.Image, text: str, y: float, x0: float, x1: float, color) -> None:
    draw = ImageDraw.Draw(card)
    w = sum(draw.textlength(ch, font=z.FONTS.silk) for ch in text) + 2.4 * (len(text) - 1)
    mid = (x0 + x1) / 2
    z._silk(draw, (mid, y + 4), text, color, centre=True)
    draw.line((x0, y, mid - w / 2 - 14, y), fill=base._mix(color, z.BODY, 0.55), width=1)
    draw.line((mid + w / 2 + 14, y, x1, y), fill=base._mix(color, z.BODY, 0.55), width=1)


def _rows(record: Record) -> list[tuple[str, list[Team]]]:
    return rc._rows(record)


def _section_h(record: Record) -> int:
    if record.empty or not record.teams:
        return HEAD + 50
    rows = _rows(record)
    return HEAD + sum(TEAM_H + GAP + (STAGE_H if head else 0) for head, _ in rows) - GAP + INNER


def draw_records(uid: str, records: list[Record], images: dict[str, Image.Image], nickname: str | None = None) -> bytes:
    base.FONTS = base.FONTS or base.Fonts()
    z.FONTS = z.FONTS or z.Fonts()
    f = z.FONTS
    top = PAD + 84 + GAP
    height = top + sum(_section_h(r) + GAP for r in records) - GAP + PAD
    card = _console(W, height)

    # the header: a nameplate across the top
    sx0, sy0, sx1, sy1 = z._bezel(card, (PAD, PAD, W - PAD, PAD + 84), 12, 5)
    draw = ImageDraw.Draw(card)
    draw.text((sx0 + 18, sy0 + 34), "BATTLE RECORDS", font=z._rubik(32, 800), fill=base.TEXT, anchor="ls")
    z._silk(draw, (sx0 + 20, sy0 + 58), "ZENLESS ZONE ZERO" + (f"  ·  {nickname.upper()}" if nickname else ""))
    server = base.server_name("zzz", uid)
    draw.text((sx1 - 16, sy0 + 58), f"{server + ' · ' if server else ''}UID {uid}", font=f.tiny, fill=z.SILK, anchor="rs")

    y = top
    for record in records:
        h = _section_h(record)
        color = MODE_LAMP.get(record.mode, z.AMBER)
        z._bezel(card, (PAD, y, W - PAD, y + h), 14, 0, z.BODY_DARK)
        draw = ImageDraw.Draw(card)
        _pilot(card, PAD + 26, y + 34, color)
        draw.text((PAD + 44, y + 44), record.title.upper(), font=z._rubik(28, 800), fill=base.TEXT, anchor="ls")
        if record.season:
            z._silk(draw, (PAD + 46, y + 68), base._fit_text(draw, record.season.upper(), f.silk, 520))
        right = W - PAD - INNER
        top1 = any(label.lower() == "top" and _percent(value) <= 1 for label, value in record.headline)
        for label, value in reversed(record.headline):
            w = _readout_w(draw, label, value)
            _readout(card, (right - w, y + 14, right, y + 74), label, value, foil=top1 and label.lower() in ("score", "rating"))
            right -= w + 10
        if record.empty or not record.teams:
            draw = ImageDraw.Draw(card)
            draw.text((PAD + INNER + 8, y + HEAD + 18), record.empty or "Nothing to show.", font=f.small, fill=z.SILK, anchor="lm")
            y += h + GAP
            continue
        by = y + HEAD
        col_w = (W - 2 * PAD - 2 * INNER - 2 * GAP) // 3
        for head, row in _rows(record):
            if head:
                _stage_line(card, head.upper(), by + STAGE_H / 2 - 4, PAD + INNER, W - PAD - INNER, color)
                by += STAGE_H
            row_w = len(row) * col_w + (len(row) - 1) * GAP
            bx = (W - row_w) // 2
            for team in row:
                if team.plight:
                    rc._shimmer(card, (bx, by, bx + col_w, by + TEAM_H))
                _team(card, team, images, (bx, by, bx + col_w, by + TEAM_H), record.mode)
                edge = bx - 2 * GAP
                for label, value in reversed(team.left):
                    _readout(card, (edge - SIDE_W, by + 30, edge, by + TEAM_H - 30), label, value, True)
                    edge -= SIDE_W + 12
                edge = bx + col_w + 2 * GAP
                for label, value in team.right:
                    _readout(card, (edge, by + 30, edge + SIDE_W, by + TEAM_H - 30), label, value, True)
                    edge += SIDE_W + 12
                bx += col_w + GAP
            by += TEAM_H + GAP
        y += h + GAP

    out = io.BytesIO()
    card.convert("RGB").save(out, "PNG", compress_level=3)
    return out.getvalue()
