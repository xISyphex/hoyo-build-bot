"""The battle records image: one section per mode, with its headline numbers and the teams that were used. Each
character's portrait carries their copies and their weapon's (E2S1, C0R1, M6P1) at its top left."""

from __future__ import annotations

import io

from PIL import Image, ImageDraw, ImageFilter

from . import card as c
from .records import Record, Team, copies_label

W = 1200
PAD = 28
GAP = 16
PORTRAIT = 80
PORTRAIT_GAP = 8
COLS = 3  # teams per row
TEAM_H = 62 + PORTRAIT + 14  # title and result rows, portraits, padding
STAGE_HEAD = 30  # the header over a stage in its own row (the King, Adversity Mode)
GAME_ACCENT = {"genshin": (232, 178, 92), "hsr": (150, 128, 255), "zzz": (250, 196, 40)}
GAME_TITLE = {"genshin": "Genshin Impact", "hsr": "Honkai: Star Rail", "zzz": "Zenless Zone Zero"}
RARITY_BG = {5: ((176, 120, 52), (98, 60, 30)), 4: ((128, 92, 196), (64, 44, 110))}


def _starry(draw: ImageDraw.ImageDraw, xy, text: str, font, fill, anchor: str = "lm") -> None:
    """Text where each ★ is drawn as a star shape (the card font has no star). anchor: "lm" or "rm"."""
    parts = text.split("★")
    star_w = font.size * 0.62
    width = sum(draw.textlength(p, font=font) for p in parts) + star_w * (len(parts) - 1)
    x, y = xy[0] - (width if anchor == "rm" else 0), xy[1]
    for i, part in enumerate(parts):
        draw.text((x, y), part, font=font, fill=fill, anchor="lm")
        x += draw.textlength(part, font=font)
        if i < len(parts) - 1:
            c._star(draw, x + star_w / 2, y - 1, font.size * 0.27, fill)
            x += star_w


def _starry_width(draw: ImageDraw.ImageDraw, text: str, font) -> float:
    parts = text.split("★")
    return sum(draw.textlength(p, font=font) for p in parts) + font.size * 0.62 * (len(parts) - 1)


def _rows(record: Record) -> list[tuple[str, list[Team]]]:
    """The teams in rows of COLS; each stage (King, Adversity Mode) gets a row of its own under its header."""
    plain = [t for t in record.teams if not t.stage]
    rows = [("", plain[i:i + COLS]) for i in range(0, len(plain), COLS)]
    return rows + [(t.stage, [t]) for t in record.teams if t.stage]


def _section_height(record: Record) -> int:
    if record.empty or not record.teams:
        return 64 + 50
    rows = _rows(record)
    return 64 + 12 + sum(TEAM_H + (STAGE_HEAD if head else 0) for head, _ in rows) + (len(rows) - 1) * GAP + 8


def _portrait(card: Image.Image, game: str, member, icon: Image.Image | None, x: int, y: int, accent) -> None:
    f = c.FONTS
    top, bottom = RARITY_BG.get(member.rarity, ((70, 70, 84), (40, 40, 50)))
    tile = Image.new("RGBA", (PORTRAIT, PORTRAIT), (0, 0, 0, 0))
    grad = Image.linear_gradient("L").resize((PORTRAIT, PORTRAIT))
    colour = Image.composite(Image.new("RGBA", tile.size, bottom + (255,)), Image.new("RGBA", tile.size, top + (255,)), grad)
    mask = Image.new("L", tile.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, PORTRAIT - 1, PORTRAIT - 1), 14, fill=255)
    tile.paste(colour, (0, 0), mask)
    if icon is not None:
        pic = icon.convert("RGBA")
        scale = max(PORTRAIT / pic.width, PORTRAIT / pic.height)
        pic = pic.resize((round(pic.width * scale), round(pic.height * scale)), Image.LANCZOS)
        pic = pic.crop(((pic.width - PORTRAIT) // 2, 0, (pic.width - PORTRAIT) // 2 + PORTRAIT, PORTRAIT))
        layer = Image.new("RGBA", tile.size, (0, 0, 0, 0))
        layer.alpha_composite(pic)
        layer.putalpha(Image.composite(layer.getchannel("A"), Image.new("L", tile.size, 0), mask))
        tile.alpha_composite(layer)
    ImageDraw.Draw(tile).rounded_rectangle((0, 0, PORTRAIT - 1, PORTRAIT - 1), 14, outline=(255, 255, 255, 40), width=1)
    card.alpha_composite(tile, (x, y))
    draw = ImageDraw.Draw(card)
    label = copies_label(game, member)
    if label:  # copies at the top left
        w = draw.textlength(label, font=f.label) + 12
        draw.rounded_rectangle((x - 4, y - 6, x - 4 + w, y + 14), 8, fill=(14, 12, 24, 235), outline=accent + (255,), width=1)
        draw.text((x - 4 + w / 2, y + 4), label, font=f.label, fill=c.TEXT, anchor="mm")
    if member.level:
        lv = f"Lv. {member.level}"
        shade = Image.new("RGBA", (PORTRAIT, 20), (0, 0, 0, 0))
        ImageDraw.Draw(shade).rounded_rectangle((0, 0, PORTRAIT - 1, 19), 8, fill=(0, 0, 0, 140))
        card.alpha_composite(shade, (x, y + PORTRAIT - 20))
        draw.text((x + PORTRAIT / 2, y + PORTRAIT - 10), lv, font=f.stamp, fill=c.TEXT, anchor="mm")


def _team(card: Image.Image, game: str, team: Team, images: dict, box, accent, light) -> None:
    f = c.FONTS
    x0, y0, x1, y1 = box
    c._panel(card, box, 16, (0, 0, 0, 80))
    draw = ImageDraw.Draw(card)
    draw.text((x0 + 14, y0 + 20), c._fit_text(draw, team.label, f.stat_s, x1 - x0 - 28), font=f.stat_s, fill=c.TEXT, anchor="lm")
    if team.result:  # this node's own cycles / points, under its title
        _starry(draw, (x0 + 14, y0 + 44), team.result, f.small_b, light)
    members = team.members[:4]
    row_w = len(members) * PORTRAIT + max(0, len(members) - 1) * PORTRAIT_GAP
    x = x0 + (x1 - x0 - row_w) // 2
    for m in members:
        _portrait(card, game, m, images.get(m.icon_url or ""), x, y0 + 64, accent)
        x += PORTRAIT + PORTRAIT_GAP


def draw_records(game: str, uid: str, records: list[Record], images: dict[str, Image.Image],
                 nickname: str | None = None) -> bytes:
    c.FONTS = c.FONTS or c.Fonts()
    f = c.FONTS
    accent = GAME_ACCENT[game]
    light = c._mix(accent, (255, 255, 255), 0.45)
    height = 120 + sum(_section_height(r) + GAP for r in records) + PAD - GAP
    card = Image.new("RGBA", (W, height), (14, 12, 24, 255))
    glow = Image.new("RGBA", (W, height), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse((-300, -260, 700, 300), fill=c._mix((14, 12, 24), accent, 0.4) + (255,))
    card.alpha_composite(glow.filter(ImageFilter.GaussianBlur(120)))
    draw = ImageDraw.Draw(card)

    draw.text((PAD, 40), "Battle Records", font=f.name[44], fill=c.TEXT, anchor="lm")
    sub = GAME_TITLE[game] + (f"  ·  {nickname}" if nickname else "")
    draw.text((PAD + 2, 84), sub, font=f.meta, fill=light, anchor="lm")
    server = c.server_name(game, uid)
    draw.text((W - PAD, 84), f"{server + ' · ' if server else ''}UID {uid}", font=f.stamp, fill=c.DIM, anchor="rm")

    y = 120
    for record in records:
        h = _section_height(record)
        c._panel(card, (PAD - 8, y, W - PAD + 8, y + h), 20, c.PANEL)
        draw = ImageDraw.Draw(card)
        draw.rectangle((PAD - 8, y + 18, PAD - 4, y + 50), fill=accent + (255,))
        draw.text((PAD + 8, y + 26), record.title, font=f.main, fill=c.TEXT, anchor="lm")
        if record.season:
            _starry(draw, (PAD + 8, y + 50), c._fit_text(draw, record.season, f.small, 560), f.small, c.DIM)
        x = W - PAD - 8
        for label, value in reversed(record.headline):  # numbers on the right, label above value
            w = max(_starry_width(draw, value, f.main), draw.textlength(label.upper(), font=f.label) * 1.15) + 8
            _starry(draw, (x, y + 24), value, f.main, light, anchor="rm")
            c._spaced(draw, (x - w + 8, y + 50), label.upper(), f.label, c.DIM, 1.2)
            x -= w + 22
        if record.empty or not record.teams:
            draw.text((PAD + 8, y + 86), record.empty or "Nothing to show.", font=f.stat_s, fill=c.DIM, anchor="lm")
        else:
            by = y + 76
            col_w = (W - 2 * PAD - (COLS - 1) * GAP) // COLS
            for head, row in _rows(record):
                if head:  # a stage of its own: a header line across the section, the team centred under it
                    draw = ImageDraw.Draw(card)
                    tw = draw.textlength(head.upper(), font=f.label) * 1.15
                    mid = W / 2
                    draw.line((PAD + 8, by + 12, mid - tw / 2 - 14, by + 12), fill=accent + (120,), width=1)
                    draw.line((mid + tw / 2 + 14, by + 12, W - PAD - 8, by + 12), fill=accent + (120,), width=1)
                    c._spaced(draw, (mid - tw / 2, by + 12), head.upper(), f.label, light, 1.2)
                    by += STAGE_HEAD
                row_w = len(row) * col_w + (len(row) - 1) * GAP
                bx = PAD + (W - 2 * PAD - row_w) // 2  # a short row sits in the middle
                for team in row:
                    _team(card, game, team, images, (bx, by, bx + col_w, by + TEAM_H), accent, light)
                    bx += col_w + GAP
                by += TEAM_H + GAP
        y += h + GAP

    out = io.BytesIO()
    card.convert("RGB").save(out, "PNG", optimize=True)
    return out.getvalue()
