"""The battle records image: one section per mode, with its headline numbers and the teams that were used. Each
character's portrait carries their copies and their weapon's (E2S1, C0R1, M6P1) at its top left."""

from __future__ import annotations

import io
import re

from PIL import Image, ImageChops, ImageDraw, ImageFilter

from . import card as c
from . import record_icons as icons
from .records import Record, Team, copies_label

PAD = 28
GAP = 16
PORTRAIT = 104
PORTRAIT_GAP = 12
COLS = 3  # teams per row
BANGBOO = 64  # ZZZ's Bangboo, smaller beside the agents
TEAM_W = 4 * PORTRAIT + 3 * PORTRAIT_GAP + 32
W = 2 * PAD + COLS * TEAM_W + (COLS - 1) * GAP  # as wide as three teams of four need
TAB_H = 36  # the box's title, as a tab clipped to its top-left corner
ROW_GAP = 12  # the same space between the title tab, the results row and the portraits, and under the portraits
# How far each game's portraits reach above / below their spot: Star Rail's copies pill sticks out on top, its tile is taller
LIFT = {"hsr": 10, "genshin": 6, "zzz": 10}  # Genshin's copies pill sits like Star Rail's
DROP = {"hsr": 4, "zzz": 4}  # Star Rail's and ZZZ's tiles are taller (HSR_H)


def _portrait_top(game: str, chips: bool = True) -> int:
    """Where the portraits go, so every gap is the same (the results row only when there is one)."""
    return TAB_H + ROW_GAP + (CHIP_H + ROW_GAP if chips else 0) + LIFT.get(game, 0)


def _team_h(game: str, chips: bool = True) -> int:
    return _portrait_top(game, chips) + PORTRAIT + DROP.get(game, 0) + ROW_GAP + 4


def _has_chips(record: Record) -> bool:
    """Whether the section's boxes have a results row; without one (Memory of Chaos) they're shorter."""
    return any(t.chips for t in record.teams)
STAGE_HEAD = 44  # the header over a stage in its own row (the King, Adversity Mode)
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


CHIP_H, CHIP_PAD = 28, 9  # each result sits in its own dark pill, readable over any boss art


def _chips(card: Image.Image, game: str, chips, x: float, cy: float, colour, light) -> None:
    """A node's results in a row, each in a dark pill with its icon."""
    f = c.FONTS
    fg = Image.new("RGBA", card.size, (0, 0, 0, 0))  # the contents, drawn first so the pills can be sized to them
    draw = ImageDraw.Draw(fg)
    spans = []
    for kind, value in chips:
        start = x = x + CHIP_PAD
        if kind == "stars":  # earned stars lit, the rest dim
            got, _, of = value.partition("/")
            got, of = int(got), int(of or got)
            for i in range(of):
                x += _paste(fg, icons.star(game, 22, i < got), x, cy) + 2
            x -= 2
        elif kind == "rating":
            x += _paste(fg, icons.rating(value, 24, f.main), x, cy)
        else:
            icon = {"score": icons.score, "time": icons.clock}.get(kind)
            if icon:
                x += _paste(fg, icon(20, colour), x, cy) + 6
            text = f"{value} cycle{'s' if value != '1' else ''}" if kind == "cycles" else value
            draw.text((x, cy), text, font=f.small_b, fill=c.DIM if kind == "text" else light, anchor="lm")
            x += draw.textlength(text, font=f.small_b)
        spans.append((start - CHIP_PAD, x + CHIP_PAD))
        x += CHIP_PAD + 6
    pills = Image.new("RGBA", card.size, (0, 0, 0, 0))
    pd = ImageDraw.Draw(pills)
    for left, right in spans:
        pd.rounded_rectangle((left, cy - CHIP_H / 2, right, cy + CHIP_H / 2), CHIP_H // 2,
                             fill=(10, 10, 16, 200), outline=colour + (110,), width=1)
    c._layer_onto(card, pills)
    c._layer_onto(card, fg)


def _tile(card: Image.Image, game: str, record: Record, label: str, value: str, right: float, y: int, colour, light,
          images: dict, from_left: bool = False) -> float:
    """One headline number as a tile (icon, value, label) ending at x = right; returns its left edge. With from_left,
    the tile starts at x = right instead and its right edge is returned."""
    f = c.FONTS
    draw = ImageDraw.Draw(card)
    key = label.lower()
    icon, text, suffix, flames = None, value, "", None
    if key in ("stars", "adversity stars"):
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
        icon, text = icons.rating(value, 48, f.main), ""
    elif key in ("top", "adversity top"):
        flames, offset = icons.rank_badge(value, 28, f.main)
        icon, text = Image.new("RGBA", (flames.width - 2 * offset[0] - round(28 * 0.6 * icons._heat(value)), 28)), ""
        label = "Adversity rank" if key == "adversity top" else "Ranking"
    elif key == "medal":
        icon = _rank_piece(record, value, 40, images)
    text_w = draw.textlength(text, font=f.main) + (draw.textlength(suffix, font=f.small) + 2 if suffix else 0)
    shown = key not in ICON_ONLY.get(game, ())  # some numbers speak for themselves with their icon
    label_w = draw.textlength(label.upper(), font=f.label) * 1.15 if shown else 0
    inner = max((icon.width + 8 if icon else 0) + text_w, label_w)
    vy = y + 38 if shown else y + 29  # the value row; centred when there's no label
    left = right - inner - 24
    if from_left:
        left, right = right, right + inner + 24
    layer = Image.new("RGBA", card.size, (0, 0, 0, 0))
    ImageDraw.Draw(layer).rounded_rectangle((left, y, right, y + 58), 12, fill=colour + (22,), outline=colour + (70,))
    c._layer_onto(card, layer)
    draw = ImageDraw.Draw(card)
    x = left + 12 + (inner - (icon.width + 8 if icon else 0) - text_w) / 2
    if flames is not None:  # the ranking badge burns past its spot
        card.alpha_composite(flames, (round(x - offset[0]), round(vy - 14 - offset[1])))
        draw = ImageDraw.Draw(card)
        x += icon.width + 8
    elif icon:
        x += _paste(card, icon, x, vy) + 8
    if text:
        draw.text((x, vy), text, font=f.main, fill=c.TEXT, anchor="lm")
        x += draw.textlength(text, font=f.main) + 2
    if suffix:
        draw.text((x, vy + 3), suffix, font=f.small, fill=c.DIM, anchor="lm")
    if shown:
        c._spaced(draw, (left + 12 + (inner - label_w) / 2, y + 14), label.upper(), f.label, c.DIM, 1.2)
    return right if from_left else left


SIDE_W = 170  # a tall tile beside the King / Adversity Mode box
RANK_PIECE = 92  # Anomaly Arbitration's rank piece; its tile is just big enough to hold it
RANK_TILE = RANK_PIECE + 2 * 18
SNUG = ("medal", "rank", "cycles")  # side tiles kept to that same small square


HUG_PAD = 14  # padding round a side tile that hugs what's in it


def _hugged(game: str, label: str, value: str) -> Image.Image | None:
    """What sits in a side tile that wraps itself round its content: the stars in a row, or the ranking badge."""
    key = label.lower()
    if key == "stars":  # every star there is to earn, the missing ones greyed out
        got, _, of = value.partition("/")
        got, of = int(got), int(of or got)
        size, gap = 46, 8
        pic = Image.new("RGBA", (of * size + (of - 1) * gap, size), (0, 0, 0, 0))
        for i in range(of):
            pic.alpha_composite(icons.star(game, size, i < got), (i * (size + gap), 0))
        return pic
    if key == "top":
        return icons.rank_badge(value, 40, c.FONTS.main)[0]
    return None


def _side_w(game: str, label: str, value: str) -> int:
    if (pic := _hugged(game, label, value)) is not None:
        return pic.width + 2 * HUG_PAD
    return RANK_TILE if label.lower() in SNUG else SIDE_W
# Numbers shown with their icon alone, no label over them (Syphex's picks)
ICON_ONLY = {"hsr": {"stars", "score", "starward", "floor", "rank"},
             "zzz": {"stars", "score", "rating", "top", "adversity top", "time"},
             "genshin": {"time", "medals", "mode", "stars"}}


def _rank_piece(record: Record, kind: str, height: int, images: dict) -> Image.Image:
    """Anomaly Arbitration's rank: HoYoLAB's own chess piece picture, or a drawn piece when it couldn't be had."""
    pic = images.get(record.medal or "")
    if pic is not None:
        pic = pic.convert("RGBA")
        box = pic.getbbox()  # trim empty margins so the piece fills its spot
        pic = pic.crop(box) if box else pic
        scale = height / max(pic.width, pic.height)  # fits a height x height square, however wide the piece is
        return pic.resize((max(1, round(pic.width * scale)), max(1, round(pic.height * scale))), Image.LANCZOS)
    return icons.chess(height, kind)


def _side_tile(card: Image.Image, game: str, record: Record, label: str, value: str, box, colour, images: dict) -> None:
    """A stage's own number, big: label on top, a large icon, the value under it."""
    f = c.FONTS
    key = label.lower()
    mid_y = (box[1] + box[3]) / 2
    hug = _hugged(game, label, value)
    if hug is not None:  # a pill wrapped round its content, level with the middle of the stage's box
        h = hug.height + 2 * HUG_PAD
        box = (box[0], round(mid_y - h / 2), box[0] + hug.width + 2 * HUG_PAD, round(mid_y + h / 2))
        layer = Image.new("RGBA", card.size, (0, 0, 0, 0))
        ImageDraw.Draw(layer).rounded_rectangle(box, h // 2, fill=colour + (26,), outline=colour + (90,), width=2)
        c._layer_onto(card, layer)
        card.alpha_composite(hug, (box[0] + HUG_PAD, box[1] + HUG_PAD))
        return
    if key in SNUG:  # a snug square, level with the middle of the stage's box
        box = (box[0], round(mid_y - RANK_TILE / 2), box[2], round(mid_y + RANK_TILE / 2))
    x0, y0, x1, y1 = box
    layer = Image.new("RGBA", card.size, (0, 0, 0, 0))
    ImageDraw.Draw(layer).rounded_rectangle(box, 16, fill=colour + (26,), outline=colour + (90,), width=2)
    c._layer_onto(card, layer)
    draw = ImageDraw.Draw(card)
    mid = (x0 + x1) / 2
    label = "Ranking" if key == "top" else label
    shown = key not in ICON_ONLY.get(game, ())
    lw = draw.textlength(label.upper(), font=f.label) * 1.15
    if shown:
        c._spaced(draw, (mid - lw / 2, y0 + 22), label.upper(), f.label, c.DIM, 1.2)
    top = y0 + 40 if shown else y0 + 8  # where the content area starts
    icon, text = None, value
    if key in ("medal", "rank"):
        icon = _rank_piece(record, value, RANK_PIECE, images)
        card.alpha_composite(icon, (round(mid - icon.width / 2), round((y0 + y1) / 2 - icon.height / 2)))
        return
    big = f.name[56]
    if icon is None:  # just the number, very large (cycles)
        draw.text((mid, (top + y1 - 6) / 2), text, font=big, fill=c.TEXT, anchor="mm")
        return
    iy = top + (y1 - top - (44 if text else 0)) / 2
    card.alpha_composite(icon, (round(mid - icon.width / 2), round(iy - icon.height / 2)))
    if text:
        draw.text((mid, y1 - 28), text, font=f.name[38], fill=c.TEXT, anchor="mm")


def _shimmer(card: Image.Image, box) -> None:
    """Plight mode: a red shimmering glow around the box."""
    x0, y0, x1, y1 = box
    m = 26
    w, h = x1 - x0 + 2 * m, y1 - y0 + 2 * m
    glow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.rounded_rectangle((m - 6, m - 6, w - m + 6, h - m + 6), 22, outline=(255, 36, 56, 255), width=14)
    glow = glow.filter(ImageFilter.GaussianBlur(10))
    sheen = Image.linear_gradient("L").rotate(-60, expand=True).resize((w, h))  # brighter towards the top left
    sheen = sheen.point(lambda v: round(120 + 135 * abs(((v / 255) * 3) % 2 - 1)))  # bands, like light moving across
    glow.putalpha(ImageChops.multiply(glow.getchannel("A"), sheen))
    card.alpha_composite(glow, (x0 - m, y0 - m))
    edge = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(edge).rounded_rectangle((m, m, w - m - 1, h - m - 1), 16, outline=(255, 110, 124, 255), width=3)
    edge.putalpha(ImageChops.multiply(edge.getchannel("A"), sheen))
    card.alpha_composite(edge, (x0 - m, y0 - m))


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


STAGE_FONT = c._font("Bold", 22)
CROWN = 28  # the crowns either side of "KING"


def _stage_head(card: Image.Image, head: str, y: int, colour, light) -> None:
    """A stage's header: its name in big spaced capitals across a line, the King's between two crowns."""
    draw = ImageDraw.Draw(card)
    text = head.upper()
    tw = sum(draw.textlength(ch, font=STAGE_FONT) + 3 for ch in text) - 3
    crowned = head == "King"
    side = (CROWN + 12) if crowned else 0
    mid = W / 2
    half = tw / 2 + side
    draw.line((PAD + 8, y, mid - half - 16, y), fill=colour + (140,), width=1)
    draw.line((mid + half + 16, y, W - PAD - 8, y), fill=colour + (140,), width=1)
    c._spaced(draw, (mid - tw / 2, y), text, STAGE_FONT, light, 3)
    if crowned:
        crown = icons.crown(CROWN)
        card.alpha_composite(crown, (int(mid - half), int(y - CROWN / 2 - 2)))
        card.alpha_composite(crown, (int(mid + tw / 2 + 12), int(y - CROWN / 2 - 2)))


def _rows(record: Record) -> list[tuple[str, list[Team]]]:
    """The teams in rows of COLS; each stage (King, Adversity Mode) gets a row of its own under its header."""
    plain = [t for t in record.teams if not t.stage]
    rows = [("", plain[i:i + COLS]) for i in range(0, len(plain), COLS)]
    return rows + [(t.stage, [t]) for t in record.teams if t.stage]


HEAD = 92  # a section's header: title, season line and the headline tiles


def _section_height(game: str, record: Record) -> int:
    if record.empty or not record.teams:
        return HEAD + 44
    rows = _rows(record)
    return HEAD + sum(_team_h(game, _has_chips(record)) + (STAGE_HEAD if head else 0) for head, _ in rows) + (len(rows) - 1) * GAP + 16


def _cover(icon: Image.Image, w: int, h: int, top: bool = True) -> Image.Image:
    """The picture scaled to fill w x h, cropped from the top (faces sit high) or the middle."""
    pic = icon.convert("RGBA")
    scale = max(w / pic.width, h / pic.height)
    pic = pic.resize((round(pic.width * scale), round(pic.height * scale)), Image.LANCZOS)
    left = (pic.width - w) // 2
    upper = 0 if top else (pic.height - h) // 2
    return pic.crop((left, upper, left + w, upper + h))


def _masked(layer: Image.Image, mask: Image.Image) -> Image.Image:
    layer.putalpha(ImageChops.multiply(layer.getchannel("A"), mask))
    return layer


def _portrait(card: Image.Image, game: str, member, icon: Image.Image | None, x: int, y: int, accent) -> None:
    if game == "hsr":
        _hsr_portrait(card, member, icon, x, y, accent)
    elif game == "zzz":
        _zzz_portrait(card, member, icon, x, y - 4, accent, PORTRAIT, height=HSR_H)  # as tall as Star Rail's
    else:
        _gi_portrait(card, game, member, icon, x, y, accent)


def _rarity_tile(w: int, h: int, rarity: int) -> Image.Image:
    top, bottom = RARITY_BG.get(rarity, ((70, 70, 84), (40, 40, 50)))
    grad = Image.linear_gradient("L").resize((w, h))
    return Image.composite(Image.new("RGBA", (w, h), bottom + (255,)), Image.new("RGBA", (w, h), top + (255,)), grad)


LEVEL_SHADE = 130  # how dark the band behind a portrait's level is (of 255)
HSR_H = PORTRAIT + 8  # Star Rail's portraits are a little taller than wide, like HoYoLAB's


def _hsr_portrait(card: Image.Image, member, icon, x: int, y: int, accent) -> None:
    """HoYoLAB's Star Rail portrait: rarity colour behind the art, square corners but a rounded top right, and a
    see-through black level band across the bottom."""
    f = c.FONTS
    w, h = PORTRAIT, HSR_H
    tile = _rarity_tile(w, h, member.rarity)
    if icon is not None:
        tile.alpha_composite(_cover(icon, w, h))
    band = Image.new("RGBA", (w, 24), (0, 0, 0, LEVEL_SHADE))
    tile.alpha_composite(band, (0, h - 24))
    ImageDraw.Draw(tile).text((w / 2, h - 12), f"Lv. {member.level}" if member.level else "", font=f.slot, fill=c.TEXT, anchor="mm")
    mask = Image.new("L", (w * 4, h * 4), 0)
    md = ImageDraw.Draw(mask)
    md.rounded_rectangle((0, 0, w * 4 - 1, h * 4 - 1), 22 * 4, fill=255, corners=(False, True, False, False))
    mask = mask.resize((w, h), Image.LANCZOS)
    card.alpha_composite(_masked(tile, mask), (x, y - 4))
    _copies(card, "hsr", member, x, y - 4, accent)


def _zzz_portrait(card: Image.Image, member, icon, x: int, y: int, accent, size: int, copies: bool = True,
                  height: int | None = None) -> None:
    """HoYoLAB's ZZZ portrait: the agent's picture (with the outfit they wear) on its rarity colour in a thick dark
    rounded frame, size wide and height tall (square unless given), the copies at the top left."""
    w, h = size, height or size
    big = size > 80
    frame, radius = (5, 18) if big else (4, 14)
    tile = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(tile).rounded_rectangle((0, 0, w - 1, h - 1), radius, fill=(40, 40, 44, 255), outline=(70, 70, 76, 255), width=1)
    iw, ih = w - 2 * frame, h - 2 * frame
    pic = _rarity_tile(iw, ih, member.rarity)  # gold S, purple A, like the other games
    if icon is not None:
        pic.alpha_composite(_cover(icon, iw, ih, top=False))
    if member.level:  # a see-through level band along the bottom of the picture
        band_h = 22 if big else 18
        pic.alpha_composite(Image.new("RGBA", (iw, band_h), (0, 0, 0, LEVEL_SHADE)), (0, ih - band_h))
        ImageDraw.Draw(pic).text((iw / 2, ih - band_h / 2), f"Lv. {member.level}", font=c.FONTS.slot, fill=c.TEXT, anchor="mm")
    mask = Image.new("L", (iw * 4, ih * 4), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, iw * 4 - 1, ih * 4 - 1), (13 if big else 10) * 4, fill=255)
    tile.alpha_composite(_masked(pic, mask.resize((iw, ih), Image.LANCZOS)), (frame, frame))
    pill = (COPY_STYLE or COPY_STYLES["zzz"]) != "slant"
    label = copies_label("zzz", member) if copies and not pill else ""
    if label:  # over the frame too, trimmed by its outer rounded corner
        plate = Image.new("RGBA", tile.size, (0, 0, 0, 0))
        _slant_plate(plate, label, -3, 0, accent, _copy_parts("zzz", member))
        outer = Image.new("L", (w * 4, h * 4), 0)
        ImageDraw.Draw(outer).rounded_rectangle((0, 0, w * 4 - 1, h * 4 - 1), radius * 4, fill=255)
        tile.alpha_composite(_masked(plate, outer.resize((w, h), Image.LANCZOS)))
    card.alpha_composite(tile, (x, y))
    if copies and pill:
        _copies(card, "zzz", member, x, y, accent)


# Copies text in the colour of what they're copies of: gold 5-star / S, purple 4-star / A, blue 3-star / B
RARITY_TEXT = {5: (255, 204, 96), 4: (200, 150, 255), 3: (112, 176, 255)}


def _copy_parts(game: str, member) -> list[tuple[str, tuple]]:
    """The copies label in pieces, each in its rarity's colour: [("E2", gold), ("S1", purple)]."""
    label = copies_label(game, member)
    parts = re.findall(r"[A-Z]\d+", label) or [label]
    rarities = [member.rarity, getattr(member, "weapon_rarity", None)]
    return [(p, RARITY_TEXT.get(rarities[i] if i < 2 else None, c.TEXT)) for i, p in enumerate(parts)]


SPLIT_W = 9  # room for the S-shaped line between a badge's two parts


def _split_line(height: int, slash: bool = False) -> Image.Image:
    """A thin white line shaped like a stretched S, curving at the top and bottom (or a straight /, for ZZZ)."""
    k = 4
    w, h = SPLIT_W * k, height * k
    img = Image.new("L", (w, h), 0)
    pts = [(w * 0.2, h), (w * 0.8, 0)] if slash else []
    for i in range(41 if not slash else 0):
        t = i / 40
        # a cubic curve from the top right to the bottom left, its ends bent back the other way
        p0, p1, p2, p3 = (w * 0.78, 0), (w * 0.05, h * 0.38), (w * 0.95, h * 0.62), (w * 0.22, h)
        x = (1 - t) ** 3 * p0[0] + 3 * (1 - t) ** 2 * t * p1[0] + 3 * (1 - t) * t * t * p2[0] + t ** 3 * p3[0]
        y = (1 - t) ** 3 * p0[1] + 3 * (1 - t) ** 2 * t * p1[1] + 3 * (1 - t) * t * t * p2[1] + t ** 3 * p3[1]
        pts.append((x, y))
    ImageDraw.Draw(img).line(pts, fill=255, width=round(1.4 * k), joint="curve")
    mask = img.resize((SPLIT_W, height), Image.LANCZOS)
    out = Image.new("RGBA", mask.size, (255, 255, 255, 0))
    out.putalpha(mask.point(lambda v: v * 0.85))
    return out


def _parts_width(draw: ImageDraw.ImageDraw, parts, font) -> float:
    return sum(draw.textlength(p, font=font) for p, _ in parts) + SPLIT_W * (len(parts) - 1)


def _parts_text(draw: ImageDraw.ImageDraw, centre: tuple[float, float], parts, font, card=None, height: int = 22,
                slash: bool = False) -> None:
    """Pieces of text side by side, centred together on centre, an S-shaped line between them (on card)."""
    x = centre[0] - _parts_width(draw, parts, font) / 2
    for i, (text, colour) in enumerate(parts):
        if i:
            if card is not None:
                card.alpha_composite(_split_line(height, slash), (round(x), round(centre[1] - height / 2)))
            x += SPLIT_W
        draw.text((x, centre[1]), text, font=font, fill=colour, anchor="lm")
        x += draw.textlength(text, font=font)


def _slant_plate(card: Image.Image, label: str, x: float, y: float, accent, parts=None) -> None:
    """A dark slanted plate with a colour stripe, its left edge at x."""
    f = c.FONTS
    draw = ImageDraw.Draw(card)
    parts = parts or [(label, c.TEXT)]
    w = _parts_width(draw, parts, f.small_b) + 22
    sl = 7
    draw.polygon([(x + sl, y), (x + w + sl, y), (x + w, y + 24), (x, y + 24)], fill=(14, 12, 24, 240))
    draw.polygon([(x + sl, y), (x + 6 + sl, y), (x + 6, y + 24), (x, y + 24)], fill=accent + (255,))
    _parts_text(draw, (x + 10 + (w - 10) / 2 + sl / 2, y + 12), parts, f.small_b, card, 18, slash=True)


def _gi_portrait(card: Image.Image, game: str, member, icon, x: int, y: int, accent) -> None:
    f = c.FONTS
    tile = Image.new("RGBA", (PORTRAIT, PORTRAIT), (0, 0, 0, 0))
    mask = Image.new("L", tile.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, PORTRAIT - 1, PORTRAIT - 1), 14, fill=255)
    tile.paste(_rarity_tile(PORTRAIT, PORTRAIT, member.rarity), (0, 0), mask)
    if icon is not None:
        layer = Image.new("RGBA", tile.size, (0, 0, 0, 0))
        layer.alpha_composite(_cover(icon, PORTRAIT, PORTRAIT))
        tile.alpha_composite(_masked(layer, mask))
    ImageDraw.Draw(tile).rounded_rectangle((0, 0, PORTRAIT - 1, PORTRAIT - 1), 14, outline=(255, 255, 255, 40), width=1)
    card.alpha_composite(tile, (x, y))
    draw = ImageDraw.Draw(card)
    _copies(card, game, member, x, y, accent)
    if member.level:
        shade = Image.new("RGBA", (PORTRAIT, 26), (0, 0, 0, 0))
        ImageDraw.Draw(shade).rounded_rectangle((0, 0, PORTRAIT - 1, 25), 10, fill=(0, 0, 0, LEVEL_SHADE))
        card.alpha_composite(shade, (x, y + PORTRAIT - 26))
        draw.text((x + PORTRAIT / 2, y + PORTRAIT - 13), f"Lv. {member.level}", font=f.slot, fill=c.TEXT, anchor="mm")


COPY_STYLE: str | None = None  # force one style for every game (previews); otherwise COPY_STYLES picks per game
COPY_STYLES = {"hsr": "pill", "zzz": "pill", "genshin": "pill"}  # pill, split, tab, slant, band, stack (Syphex's picks)


def _copies(card: Image.Image, game: str, member, x: int, y: int, accent) -> None:
    """The character's and weapon's copies (E2S1) on a portrait, in COPY_STYLE."""
    f = c.FONTS
    label = copies_label(game, member)
    if not label:
        return
    draw = ImageDraw.Draw(card)
    char, weapon = re.match(r"([A-Z]\d+)?([A-Z]\d+)?", label).groups() if re.match(r"[A-Z]\d+", label) else (label, None)
    dark = (14, 12, 24, 235)
    style = COPY_STYLE or COPY_STYLES.get(game, "pill")
    if style == "split":  # the character's copies on the colour, the weapon's on dark, joined
        cw = draw.textlength(char, font=f.small_b) + 12
        ww = draw.textlength(weapon, font=f.small_b) + 12 if weapon else 0
        draw.rounded_rectangle((x - 4, y - 6, x - 4 + cw + ww, y + 20), 6, fill=dark, outline=accent + (255,), width=1)
        draw.rounded_rectangle((x - 4, y - 6, x - 4 + cw, y + 20), 6, fill=accent + (255,))
        draw.text((x - 4 + cw / 2, y + 7), char, font=f.small_b, fill=(14, 12, 24), anchor="mm")
        if weapon:
            draw.text((x - 4 + cw + ww / 2, y + 7), weapon, font=f.small_b, fill=c.TEXT, anchor="mm")
    elif style == "tab":  # a tab tucked into the portrait's corner, rounded on its free corner only
        w = draw.textlength(label, font=f.small_b) + 14
        layer = Image.new("RGBA", (PORTRAIT, PORTRAIT), (0, 0, 0, 0))
        ld = ImageDraw.Draw(layer)
        ld.rounded_rectangle((-20, -20, w, 24), 10, fill=accent + (240,))
        mask = Image.new("L", layer.size, 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, PORTRAIT - 1, PORTRAIT - 1), 14, fill=255)
        layer.putalpha(ImageChops.multiply(layer.getchannel("A"), mask))
        card.alpha_composite(layer, (x, y))
        draw.text((x + w / 2, y + 12), label, font=f.small_b, fill=(14, 12, 24), anchor="mm")
    elif style == "slant":  # a slanted plate with a colour stripe
        w = draw.textlength(label, font=f.small_b) + 22
        sl = 7
        draw.polygon([(x - 4 + sl, y - 6), (x - 4 + w + sl, y - 6), (x - 4 + w, y + 20), (x - 4, y + 20)], fill=dark)
        draw.polygon([(x - 4 + sl, y - 6), (x + 2 + sl, y - 6), (x + 2, y + 20), (x - 4, y + 20)], fill=accent + (255,))
        draw.text((x + 6 + (w - 10) / 2 + sl / 2, y + 7), label, font=f.small_b, fill=c.TEXT, anchor="mm")
    elif style == "band":  # in the bottom band, left of the level (the level moves right)
        pass  # drawn with the level, see _portrait
    elif style == "stack":  # two small squares down the left edge
        for i, part in enumerate(p for p in (char, weapon) if p):
            w = draw.textlength(part, font=f.small_b) + 10
            top = y - 6 + i * 26
            draw.rounded_rectangle((x - 4, top, x - 4 + w, top + 23), 5,
                                   fill=accent + (255,) if i == 0 else dark, outline=accent + (255,), width=1)
            draw.text((x - 4 + w / 2, top + 12), part, font=f.small_b, fill=(14, 12, 24) if i == 0 else c.TEXT, anchor="mm")
    else:  # pill
        parts = _copy_parts(game, member)
        w = _parts_width(draw, parts, f.small_b) + 14
        draw.rounded_rectangle((x - 4, y - 6, x - 4 + w, y + 20), 9, fill=dark, outline=accent + (255,), width=1)
        _parts_text(draw, (x - 4 + w / 2, y + 7), parts, f.small_b, card, 20)


def _team(card: Image.Image, game: str, team: Team, images: dict, box, accent, colour, light) -> None:
    f = c.FONTS
    x0, y0, x1, y1 = box
    c._panel(card, box, 16, (0, 0, 0, 80))
    art = images.get(team.art or "")
    if art is not None:
        _art(card, art, box)
    draw = ImageDraw.Draw(card)
    star = icons.starward(24) if team.label == "Starward" else None
    title = c._fit_text(draw, team.label, f.stat_s, x1 - x0 - 80)
    tab_w = round(16 + (star.width + 6 if star else 0) + draw.textlength(title, font=f.stat_s) + 18)
    tab = Image.new("RGBA", card.size, (0, 0, 0, 0))  # dark, tinted with the mode's colour, clipped to the corner
    ImageDraw.Draw(tab).rounded_rectangle((x0, y0, x0 + tab_w, y0 + TAB_H), 15, fill=c._mix(colour, (12, 12, 18), 0.78) + (235,),
                                          corners=(True, False, True, False))
    ImageDraw.Draw(tab).line((x0 + 15, y0 + TAB_H, x0 + tab_w - 15, y0 + TAB_H), fill=colour + (150,), width=2)
    c._layer_onto(card, tab)
    draw = ImageDraw.Draw(card)
    x = x0 + 16
    if star:
        x += _paste(card, star, x - 2, y0 + TAB_H / 2) + 6
    draw.text((x, y0 + TAB_H / 2), title, font=f.stat_s, fill=c.TEXT, anchor="lm")
    if team.chips:  # this node's own stars / cycles / points, under its title
        _chips(card, game, team.chips, x0 + 10, y0 + TAB_H + ROW_GAP + CHIP_H / 2, colour, light)
    members = team.members[:4]
    if team.chips or y1 - y0 > _team_h(game, False):
        top = y0 + _portrait_top(game) if team.chips else round(y0 + (y1 - y0 - _team_h(game, False)) / 2 + _portrait_top(game, False))
    else:
        top = y0 + _portrait_top(game, False)
    row_w = len(members) * PORTRAIT + max(0, len(members) - 1) * PORTRAIT_GAP
    if team.bangboo:
        row_w += PORTRAIT_GAP + BANGBOO
    x = x0 + (x1 - x0 - row_w) // 2
    for m in members:
        _portrait(card, game, m, images.get(m.icon_url or ""), x, top, accent)
        x += PORTRAIT + PORTRAIT_GAP
    if team.bangboo:  # smaller, sitting on the same bottom line
        b = team.bangboo
        _zzz_portrait(card, b, images.get(b.icon_url or ""), x, top + PORTRAIT + 4 - BANGBOO, accent, BANGBOO, copies=False)


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
    height = 120 + sum(_section_height(game, r) + GAP for r in records) + PAD - GAP
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
        h = _section_height(game, record)
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
            team_h = _team_h(game, _has_chips(record))
            for head, row in _rows(record):
                if head:  # a stage of its own: a header line across the section, the team centred under it
                    _stage_head(card, head, by + 18, colour, mode_light)
                    by += STAGE_HEAD
                row_w = len(row) * col_w + (len(row) - 1) * GAP
                bx = PAD + (W - 2 * PAD - row_w) // 2  # a short row sits in the middle
                for team in row:
                    if team.plight:
                        _shimmer(card, (bx, by, bx + col_w, by + team_h))
                    _team(card, game, team, images, (bx, by, bx + col_w, by + team_h), accent, colour, mode_light)
                    edge = bx - 2 * GAP  # the stage's own numbers, as tall tiles beside its box
                    for label, value in reversed(team.left):
                        edge -= _side_w(game, label, value)
                        _side_tile(card, game, record, label, value, (edge, by, edge + _side_w(game, label, value), by + team_h), colour, images)
                        edge -= 12
                    edge = bx + col_w + 2 * GAP
                    for label, value in team.right:
                        _side_tile(card, game, record, label, value, (edge, by, edge + _side_w(game, label, value), by + team_h), colour, images)
                        edge += _side_w(game, label, value) + 12
                    bx += col_w + GAP
                by += team_h + GAP
        y += h + GAP

    out = io.BytesIO()
    card.convert("RGB").save(out, "PNG", compress_level=3)  # quick to pack; optimize=True took longer than the drawing
    return out.getvalue()
