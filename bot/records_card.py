"""The battle records image: one section per mode, with its headline numbers and the teams that were used. Each
character's portrait carries their copies and their weapon's (E2S1, C0R1, M6P1) at its top left."""

from __future__ import annotations

import io

from PIL import Image, ImageChops, ImageDraw, ImageFilter

from . import card as c
from . import record_icons as icons
from .records import Record, Team, copies_label

PAD = 28
GAP = 16
PORTRAIT = 104
PORTRAIT_GAP = 12
COLS = 3  # teams per row
TEAM_W = 4 * PORTRAIT + 3 * PORTRAIT_GAP + 32
W = 2 * PAD + COLS * TEAM_W + (COLS - 1) * GAP  # as wide as three teams of four need
TEAM_H = 66 + PORTRAIT + 18  # title and result rows, portraits, padding
STAGE_HEAD = 30  # the header over a stage in its own row (the King, Adversity Mode)
GAME_ACCENT = {"genshin": (232, 178, 92), "hsr": (150, 128, 255), "zzz": (250, 196, 40)}
GAME_TITLE = {"genshin": "Genshin Impact", "hsr": "Honkai: Star Rail", "zzz": "Zenless Zone Zero"}
RARITY_BG = {5: ((176, 120, 52), (98, 60, 30)), 4: ((128, 92, 196), (64, 44, 110))}


MODE_COLOUR = {  # each mode's own colour, for its header band
    "moc": (226, 84, 120), "pf": (96, 168, 255), "apoc": (240, 178, 72), "aa": (88, 214, 196),
    "sd": (80, 200, 255), "da": (255, 84, 60),
    "abyss": (110, 130, 255), "theater": (226, 140, 210), "stygian": (214, 92, 92),
}
STAR_TEXT = 0.95  # a star icon's size relative to the font


def _paste(card: Image.Image, icon: Image.Image, x: float, cy: float) -> float:
    """Pastes an icon with its left edge at x, centred on cy; returns its width."""
    card.alpha_composite(icon, (round(x), round(cy - icon.height / 2)))
    return icon.width


def _starry(card: Image.Image, game: str, xy, text: str, font, fill, anchor: str = "lm") -> None:
    """Text where each ★ is the game's star icon. anchor: "lm" or "rm"."""
    draw = ImageDraw.Draw(card)
    parts = text.split("★")
    size = round(font.size * STAR_TEXT)
    width = _starry_width(draw, text, font)
    x, y = xy[0] - (width if anchor == "rm" else 0), xy[1]
    for i, part in enumerate(parts):
        draw.text((x, y), part, font=font, fill=fill, anchor="lm")
        x += draw.textlength(part, font=font)
        if i < len(parts) - 1:
            _paste(card, icons.star(game, size), x + 1, y)
            x += size + 2


def _starry_width(draw: ImageDraw.ImageDraw, text: str, font) -> float:
    parts = text.split("★")
    return sum(draw.textlength(p, font=font) for p in parts) + (round(font.size * STAR_TEXT) + 2) * (len(parts) - 1)


def _chips(card: Image.Image, game: str, chips, x: float, cy: float, colour, light) -> None:
    """A node's results in a row, each with its icon."""
    f = c.FONTS
    draw = ImageDraw.Draw(card)
    for kind, value in chips:
        if kind == "stars":  # earned stars lit, the rest dim
            got, _, of = value.partition("/")
            got, of = int(got), int(of or got)
            for i in range(of):
                x += _paste(card, icons.star(game, 22, i < got), x, cy) + 2
        elif kind == "rating":
            x += _paste(card, icons.rating(value, 24, f.main), x, cy)
        else:
            icon = {"score": icons.score, "time": icons.clock}.get(kind)
            if icon:
                x += _paste(card, icon(20, colour), x, cy) + 6
            text = f"{value} cycle{'s' if value != '1' else ''}" if kind == "cycles" else value
            draw.text((x, cy), text, font=f.small_b, fill=c.DIM if kind == "text" else light, anchor="lm")
            x += draw.textlength(text, font=f.small_b)
        x += 16


def _tile(card: Image.Image, game: str, record: Record, label: str, value: str, right: float, y: int, colour, light,
          images: dict) -> float:
    """One headline number as a tile (icon, value, label) ending at x = right; returns its left edge."""
    f = c.FONTS
    draw = ImageDraw.Draw(card)
    key = label.lower()
    icon, text, suffix = None, value, ""
    if key == "stars":
        icon = icons.star(game, 30)
        text, _, rest = value.partition(" / ")
        suffix = f"/{rest}" if rest else ""
    elif key == "medals":  # Imaginarium Theater's star medals
        icon = icons.star(game, 28)
    elif key == "starward":
        icon, text = icons.starward(32), value.replace("★", "")
    elif key == "score":
        icon = icons.score(26, colour)
    elif key == "time":
        icon = icons.clock(26, colour)
    elif key == "rating":
        icon, text = icons.rating(value, 30, f.main), ""
    elif key in ("top", "adversity top"):
        icon, text = icons.top_tag(f"TOP {value}", 26, f.main), ""
        label = "Adversity rank" if key == "adversity top" else "Ranking"
    elif key == "medal":
        pic = images.get(record.medal or "")
        if pic is not None:
            pic = pic.convert("RGBA")
            icon = pic.resize((round(pic.width * 36 / pic.height), 36), Image.LANCZOS)
        else:
            icon = icons.medal(34, value)
    text_w = draw.textlength(text, font=f.main) + (draw.textlength(suffix, font=f.small) + 2 if suffix else 0)
    label_w = draw.textlength(label.upper(), font=f.label) * 1.15
    inner = max((icon.width + 8 if icon else 0) + text_w, label_w)
    left = right - inner - 24
    layer = Image.new("RGBA", card.size, (0, 0, 0, 0))
    ImageDraw.Draw(layer).rounded_rectangle((left, y, right, y + 58), 12, fill=colour + (22,), outline=colour + (70,))
    card.alpha_composite(layer)
    draw = ImageDraw.Draw(card)
    x = left + 12 + (inner - (icon.width + 8 if icon else 0) - text_w) / 2
    if icon:
        x += _paste(card, icon, x, y + 38) + 8
    if text:
        draw.text((x, y + 38), text, font=f.main, fill=c.TEXT, anchor="lm")
        x += draw.textlength(text, font=f.main) + 2
    if suffix:
        draw.text((x, y + 41), suffix, font=f.small, fill=c.DIM, anchor="lm")
    c._spaced(draw, (left + 12 + (inner - label_w) / 2, y + 14), label.upper(), f.label, c.DIM, 1.2)
    return left


def _art(card: Image.Image, pic: Image.Image, box) -> None:
    """A boss picture faded into the right side of a panel, behind everything else."""
    x0, y0, x1, y1 = box
    w, h = round((x1 - x0) * 0.62), y1 - y0
    pic = pic.convert("RGBA")
    scale = max(w / pic.width, h / pic.height)
    pic = pic.resize((round(pic.width * scale), round(pic.height * scale)), Image.LANCZOS)
    left = (pic.width - w) // 2
    pic = pic.crop((left, 0, left + w, h))
    fade = Image.linear_gradient("L").rotate(90, expand=True).transpose(Image.FLIP_LEFT_RIGHT).resize((w, h))
    fade = fade.point(lambda v: v * 0.5)
    rounded = Image.new("L", (x1 - x0, h), 0)
    ImageDraw.Draw(rounded).rounded_rectangle((0, 0, x1 - x0 - 1, h - 1), 16, fill=255)
    alpha = Image.composite(fade, Image.new("L", (w, h), 0), rounded.crop((x1 - x0 - w, 0, x1 - x0, h)))
    pic.putalpha(ImageChops.multiply(pic.getchannel("A"), alpha))
    card.alpha_composite(pic, (x1 - w, y0))


def _rows(record: Record) -> list[tuple[str, list[Team]]]:
    """The teams in rows of COLS; each stage (King, Adversity Mode) gets a row of its own under its header."""
    plain = [t for t in record.teams if not t.stage]
    rows = [("", plain[i:i + COLS]) for i in range(0, len(plain), COLS)]
    return rows + [(t.stage, [t]) for t in record.teams if t.stage]


HEAD = 92  # a section's header: title, season line and the headline tiles


def _section_height(record: Record) -> int:
    if record.empty or not record.teams:
        return HEAD + 44
    rows = _rows(record)
    return HEAD + sum(TEAM_H + (STAGE_HEAD if head else 0) for head, _ in rows) + (len(rows) - 1) * GAP + 16


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
        w = draw.textlength(label, font=f.small_b) + 14
        draw.rounded_rectangle((x - 4, y - 6, x - 4 + w, y + 20), 9, fill=(14, 12, 24, 235), outline=accent + (255,), width=1)
        draw.text((x - 4 + w / 2, y + 7), label, font=f.small_b, fill=c.TEXT, anchor="mm")
    if member.level:
        lv = f"Lv. {member.level}"
        shade = Image.new("RGBA", (PORTRAIT, 26), (0, 0, 0, 0))
        ImageDraw.Draw(shade).rounded_rectangle((0, 0, PORTRAIT - 1, 25), 10, fill=(0, 0, 0, 130))
        card.alpha_composite(shade, (x, y + PORTRAIT - 26))
        draw.text((x + PORTRAIT / 2, y + PORTRAIT - 13), lv, font=f.slot, fill=c.TEXT, anchor="mm")


def _team(card: Image.Image, game: str, team: Team, images: dict, box, accent, colour, light) -> None:
    f = c.FONTS
    x0, y0, x1, y1 = box
    c._panel(card, box, 16, (0, 0, 0, 80))
    art = images.get(team.art or "")
    if art is not None:
        _art(card, art, box)
    draw = ImageDraw.Draw(card)
    x = x0 + 14
    if team.label == "Starward":
        x += _paste(card, icons.starward(24), x - 2, y0 + 21) + 4
    draw.text((x, y0 + 20), c._fit_text(draw, team.label, f.stat_s, x1 - x - 14), font=f.stat_s, fill=c.TEXT, anchor="lm")
    if team.chips:  # this node's own stars / cycles / points, under its title
        _chips(card, game, team.chips, x0 + 14, y0 + 45, colour, light)
    members = team.members[:4]
    row_w = len(members) * PORTRAIT + max(0, len(members) - 1) * PORTRAIT_GAP
    x = x0 + (x1 - x0 - row_w) // 2
    for m in members:
        _portrait(card, game, m, images.get(m.icon_url or ""), x, y0 + 68, accent)
        x += PORTRAIT + PORTRAIT_GAP


def _band(card: Image.Image, box, colour) -> None:
    """The mode's colour washing in from the left of its header."""
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    fade = Image.linear_gradient("L").rotate(90, expand=True).resize((w, h)).point(lambda v: v * 0.3)
    band = Image.new("RGBA", (w, h), colour + (255,))
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, w - 1, h + 20), 20, fill=255)
    band.putalpha(ImageChops.multiply(fade, mask))
    card.alpha_composite(band, (x0, y0))


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
        colour = MODE_COLOUR.get(record.mode, accent)
        mode_light = c._mix(colour, (255, 255, 255), 0.5)
        c._panel(card, (PAD - 8, y, W - PAD + 8, y + h), 20, c.PANEL)
        _band(card, (PAD - 8, y, W - PAD + 8, y + HEAD - 8), colour)
        draw = ImageDraw.Draw(card)
        draw.rounded_rectangle((PAD - 8, y + 20, PAD - 3, y + 62), 2, fill=colour + (255,))
        draw.text((PAD + 8, y + 32), record.title, font=f.name[32], fill=c.TEXT, anchor="lm")
        if record.season:
            _starry(card, game, (PAD + 10, y + 64), c._fit_text(draw, record.season, f.small, 560), f.small, c.DIM)
        right = W - PAD - 4
        for label, value in reversed(record.headline):  # tiles on the right
            right = _tile(card, game, record, label, value, right, y + 14, colour, mode_light, images) - 10
        if record.empty or not record.teams:
            draw = ImageDraw.Draw(card)
            draw.text((PAD + 8, y + HEAD + 12), record.empty or "Nothing to show.", font=f.stat_s, fill=c.DIM, anchor="lm")
        else:
            by = y + HEAD
            col_w = TEAM_W
            for head, row in _rows(record):
                if head:  # a stage of its own: a header line across the section, the team centred under it
                    draw = ImageDraw.Draw(card)
                    tw = draw.textlength(head.upper(), font=f.label) * 1.15
                    mid = W / 2
                    draw.line((PAD + 8, by + 12, mid - tw / 2 - 14, by + 12), fill=colour + (140,), width=1)
                    draw.line((mid + tw / 2 + 14, by + 12, W - PAD - 8, by + 12), fill=colour + (140,), width=1)
                    c._spaced(draw, (mid - tw / 2, by + 12), head.upper(), f.label, mode_light, 1.2)
                    by += STAGE_HEAD
                row_w = len(row) * col_w + (len(row) - 1) * GAP
                bx = PAD + (W - 2 * PAD - row_w) // 2  # a short row sits in the middle
                for team in row:
                    _team(card, game, team, images, (bx, by, bx + col_w, by + TEAM_H), accent, colour, mode_light)
                    bx += col_w + GAP
                by += TEAM_H + GAP
        y += h + GAP

    out = io.BytesIO()
    card.convert("RGB").save(out, "PNG", optimize=True)
    return out.getvalue()
