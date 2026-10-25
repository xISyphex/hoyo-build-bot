"""Star Rail's battle records as the same navigation hologram as its build card: the bridge's star map behind cyan
holo screens with cut corners, each mode a screen with its totals on small readouts, each team a screen holding its
characters on projected tiles, and the stars in gold."""

from __future__ import annotations

import functools
import io
import math
import random

from PIL import Image, ImageChops, ImageDraw, ImageFilter

from . import card as base
from . import card_hsr as h
from . import record_icons as icons
from . import records_card as rc
from .card_zzz import _nine_slice
from .records import Member, Record, Team, copies_label
from .records_zzz import _foil_text

W = rc.W  # as wide as the other games' records
SS = h.SS
HOLO, TEXT, DIM, FAINT, GOLD, DEEP = h.HOLO, h.TEXT, h.DIM, h.FAINT, h.GOLD, h.DEEP
PAD = 24
GAP = 14
INNER = 18  # a mode screen's padding round its teams
HEAD_H = 96  # the header screen at the top
HEAD = 100  # a mode screen's header: title, season line and the readouts
TILE_W, TILE_H = 100, 118  # a character's projected tile
LEVEL_H = 24  # the strip under its portrait that holds the level
TILE_GAP = 10
LABEL_H = 40  # a team's name over its tiles
CHIPS_H = 40  # its results under them
STAGE_H = 46  # the line over a stage of its own (the King)
SIDE_W = 150  # a stage's own numbers, as readouts beside its screen
MODE_LIGHT = {"moc": (255, 112, 146), "pf": (120, 182, 255), "apoc": (255, 196, 92), "aa": (110, 230, 210)}
RARITY_GLOW = {5: ((150, 112, 44), (34, 26, 10)), 4: ((112, 76, 170), (24, 16, 44))}  # 5★ gold, 4★ purple
TEAM_FILL = (4, 38, 52, 205)
MAX_SCORE = {"pf": (40000, 120000), "apoc": (3850, 11550)}  # foil from: a node's score, then the floor's (Syphex's picks)


def _perfect(mode: str, kind: str, value: str, total: bool = False) -> bool:
    """A perfect result, drawn in ZZZ's platinum foil: the mode's top score, or a clear in 0 cycles."""
    try:
        number = int(value.replace(",", "").split("/")[0])
    except ValueError:
        return False
    if kind == "cycles":
        return number == 0
    if kind == "score" and mode in MAX_SCORE:
        return number >= MAX_SCORE[mode][1 if total else 0]
    return False
MODE_FILL = (2, 24, 34, 190)


def _team_h(chips: bool) -> int:
    return LABEL_H + 6 + TILE_H + 14 + (CHIPS_H if chips else 0)


@functools.lru_cache(maxsize=64)
def _box_slice(fill, edge: int, cut: int) -> Image.Image:
    """A small holo screen (cut corners, rim, corner brackets) to be stretched to any size."""
    c = cut + 26
    n = 2 * c + 1
    k = SS
    layer = Image.new("RGBA", (n * k, n * k), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    shape = h._cut((0, 0, n * k - 1, n * k - 1), cut * k)
    d.polygon(shape, fill=fill)
    d.line(shape + shape[:1], fill=HOLO + (edge,), width=k)
    b = min(22, c - 2) * k
    d.line(((0, b), (0, 0), (b, 0)), fill=HOLO + (255,), width=2 * k)
    d.line(((n * k - 1 - b, n * k - 1), (n * k - 1, n * k - 1), (n * k - 1, n * k - 1 - b)), fill=HOLO + (255,), width=2 * k)
    return layer.resize((n, n), Image.LANCZOS)


def _box(card: Image.Image, box, fill=h.PANEL, edge: int = 120, cut: int = h.CUT) -> None:
    """A holo screen like the build card's, drawn as a small one stretched along its straight edges (big screens
    drawn whole at supersampled size were slow)."""
    x0, y0, x1, y1 = (round(v) for v in box)
    c = cut + 26
    if min(x1 - x0, y1 - y0) <= 2 * c + 2:
        h._panel(card, (x0, y0, x1, y1), fill, edge)
        return
    card.alpha_composite(_nine_slice(_box_slice(fill, edge, cut), c, x1 - x0, y1 - y0), (x0, y0))


def _starmap(w: int, hh: int, seed: str) -> Image.Image:
    """The bridge's star map: dark teal glass lit from the top left, a dot grid, scattered stars, faint orbits."""
    small = Image.new("RGB", (w // 8, hh // 8))
    px = small.load()
    for y in range(small.height):
        for x in range(small.width):
            d = math.hypot((x * 8 - 260) / 900, (y * 8 - 80) / 700)
            px[x, y] = base._mix((14, 62, 84), DEEP, min(d, 1))
    card = small.resize((w, hh), Image.BICUBIC).convert("RGBA")
    layer = Image.new("RGBA", (w, hh), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for gx in range(0, w, 22):
        for gy in range(0, hh, 22):
            d.point((gx, gy), fill=HOLO + (30,))
    rng = random.Random(seed)
    for _ in range(w * hh // 9000):
        x, y = rng.random() * w, rng.random() * hh
        r = rng.choice((0.6, 0.8, 1, 1.4))
        d.ellipse((x - r, y - r, x + r, y + r), fill=(220, 252, 255, rng.randint(40, 170)))
    for r in (380, 640, 940):  # orbits around the top left
        d.ellipse((220 - r, 60 - r * 0.5, 220 + r, 60 + r * 0.5), outline=HOLO + (22,), width=1)
    card.alpha_composite(layer)
    return card


def _star_row(card: Image.Image, x: float, cy: float, got: int, of: int, size: int = 20) -> float:
    """Stars, the earned ones gold and the rest outlined. Returns the row's width."""
    step = size + 4
    layer = Image.new("RGBA", ((of * step) * SS, size * SS), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for i in range(of):
        sx = (i * step + size / 2) * SS
        if i < got:
            base._star(d, sx, size / 2 * SS, size / 2 * SS, GOLD + (255,))
        else:
            base._star(d, sx, size / 2 * SS, size / 2 * SS, (40, 70, 84, 255))
    layer = layer.resize((of * step, size), Image.LANCZOS)
    card.alpha_composite(layer, (round(x), round(cy - size / 2)))
    return of * step - 4


def _stars(value: str) -> tuple[int, int] | None:
    try:
        got, of = value.replace(" ", "").split("/")
        return int(got), int(of)
    except ValueError:
        return None


def _readout_w(draw, label: str, value: str) -> int:
    key = label.lower()
    shown = value.split("/")[0].strip()
    w = draw.textlength(shown, font=h._raj("Bold", 28))
    if key in ("stars", "starward"):
        w += 30
    if "/" in value:
        w += draw.textlength("/" + value.split("/")[1].strip(), font=h._raj("SemiBold", 16)) + 2
    lw = sum(draw.textlength(ch, font=h._raj("Bold", 11)) + 2.4 for ch in label.upper())
    return round(max(w, lw) + 36)


def _readout(card: Image.Image, box, label: str, value: str, mode: str = "") -> None:
    """A small screen with a spaced label over the value, both centred: stars and Starward stars with their icons,
    in gold."""
    _box(card, box, h.PANEL, 120, 10)
    x0, y0, x1, y1 = box
    draw = ImageDraw.Draw(card)
    key = label.lower()
    mid = (x0 + x1) / 2
    lf = h._raj("Bold", 11)
    text = label.upper()
    lw = sum(draw.textlength(ch, font=lf) + 2.4 for ch in text) - 2.4
    h._spaced(draw, (mid - lw / 2, y0 + 16), text, lf, DIM, 2.4)
    cy = (y0 + 22 + y1) / 2
    shown, _, rest = value.partition("/")
    shown, rest = shown.strip(), ("/" + rest.strip()) if rest else ""
    big, small = h._raj("Bold", 28), h._raj("SemiBold", 16)
    icon = None
    if key in ("stars", "starward"):
        icon = icons.star("hsr", 24) if key == "stars" else icons.starward(24)
    total = (icon.width + 6 if icon else 0) + draw.textlength(shown, font=big) + (draw.textlength(rest, font=small) + 2 if rest else 0)
    x = mid - total / 2
    if icon:
        card.alpha_composite(icon, (round(x), round(cy - icon.height / 2)))
        x += icon.width + 6
    color = GOLD if key == "stars" else HOLO if key in ("score", "starward") else TEXT
    if _perfect(mode, key, value, total=True):
        _foil_text(card, (x, cy), shown, big, "lm")
    else:
        draw.text((x, cy), shown, font=big, fill=color, anchor="lm")
    if rest:
        draw.text((x + draw.textlength(shown, font=big) + 2, cy + 4), rest, font=small, fill=FAINT, anchor="lm")


def _tile(card: Image.Image, member: Member, icon: Image.Image | None, x: int, y: int) -> None:
    """A character projected on a tile with a cut corner: lit gold or purple by rarity, the level in a strip under it and the eidolon / superimposition on a plate at its top left."""
    w, hh = TILE_W, TILE_H
    top, bottom = RARITY_GLOW.get(member.rarity, ((40, 70, 84), (6, 20, 28)))
    grad = Image.linear_gradient("L").resize((w, hh))
    glass = Image.composite(Image.new("RGBA", (w, hh), bottom + (255,)), Image.new("RGBA", (w, hh), top + (255,)), grad)
    if icon is not None:
        glass.alpha_composite(rc._cover(icon, w, hh - LEVEL_H, top=True), (0, 0))
    glass.alpha_composite(Image.new("RGBA", (w, LEVEL_H), DEEP + (255,)), (0, hh - LEVEL_H))  # the level's own strip
    ImageDraw.Draw(glass).line(((0, hh - LEVEL_H), (w, hh - LEVEL_H)), fill=HOLO + (150,), width=1)
    mask = Image.new("L", (w * SS, hh * SS), 0)
    shape = h._cut((0, 0, w * SS - 1, hh * SS - 1), 12 * SS)
    ImageDraw.Draw(mask).polygon(shape, fill=255)
    mask = mask.resize((w, hh), Image.LANCZOS)
    glass.putalpha(mask)
    card.alpha_composite(glass, (x, y))
    rim = Image.new("RGBA", (w * SS, hh * SS), (0, 0, 0, 0))
    ImageDraw.Draw(rim).line(shape + shape[:1], fill=HOLO + (150,), width=SS)
    card.alpha_composite(rim.resize((w, hh), Image.LANCZOS), (x, y))
    draw = ImageDraw.Draw(card)
    if member.level:  # "LV 80" centred in the strip under the portrait
        small, big = h._raj("Bold", 11), h._raj("Bold", 16)
        lw = sum(draw.textlength(ch, font=small) + 1.4 for ch in "LV")
        tw = lw + 4 + draw.textlength(str(member.level), font=big)
        lx, ly = x + (w - tw) / 2, y + hh - LEVEL_H / 2
        h._spaced(draw, (lx, ly), "LV", small, DIM, 1.4)
        draw.text((lx + lw + 4, ly), str(member.level), font=big, fill=TEXT, anchor="lm")
    label = copies_label("hsr", member)
    if label:
        eid, _, sup = label.partition("S")
        f = h._raj("Bold", 14)
        sup = f"S{sup}" if sup else ""
        pw = draw.textlength(eid, font=f) + (draw.textlength(sup, font=f) + 4 if sup else 0) + 12
        plate = (x + 4, y + 4, x + 4 + pw, y + 24)
        layer = Image.new("RGBA", card.size, (0, 0, 0, 0))
        ImageDraw.Draw(layer).rectangle(plate, fill=(2, 16, 26, 215), outline=HOLO + (120,))
        base._layer_onto(card, layer)
        draw = ImageDraw.Draw(card)
        draw.text((plate[0] + 6, plate[1] + 10), eid, font=f, fill=GOLD if member.copies else TEXT, anchor="lm")
        if sup:
            draw.text((plate[0] + 10 + draw.textlength(eid, font=f), plate[1] + 10), sup, font=f, fill=HOLO, anchor="lm")


def _chips(card: Image.Image, chips: list[tuple[str, str]], cx: float, cy: float, mode: str = "") -> None:
    """A team's results in a row centred on cx, each on a small dark tag: stars in gold, cycles, score in cyan."""
    draw = ImageDraw.Draw(card)
    f = h._raj("Bold", 17)
    parts = []
    for kind, value in chips:
        stars = _stars(value) if kind == "stars" else None
        text = ""
        if stars:
            w = stars[1] * 22 - 4
        elif kind == "cycles":
            text = f"{value} CYCLE{'S' if value != '1' else ''}"
            w = draw.textlength(text, font=f)
        else:
            text = value.upper() if kind == "text" else value
            w = draw.textlength(text, font=f) + (18 if kind == "score" else 0)
        parts.append((kind, stars, text, w))
    x = cx - (sum(w + 22 for *_, w in parts) + 8 * (len(parts) - 1)) / 2
    for kind, stars, text, w in parts:
        box = (round(x), round(cy - 14), round(x + w + 22), round(cy + 14))
        layer = Image.new("RGBA", card.size, (0, 0, 0, 0))
        ImageDraw.Draw(layer).polygon(h._cut(box, 7), fill=(2, 16, 26, 200), outline=HOLO + (90,))
        base._layer_onto(card, layer)
        draw = ImageDraw.Draw(card)
        if stars:
            _star_row(card, x + 11, cy, *stars, 18)
        else:
            tx = x + 11
            if kind == "score":
                d = 6  # a small diamond, like the map's waypoints
                draw.polygon([(tx + d, cy - d), (tx + 2 * d, cy), (tx + d, cy + d), (tx, cy)], fill=HOLO)
                tx += 18
            color = {"score": HOLO, "cycles": TEXT}.get(kind, DIM)
            if _perfect(mode, kind, value):
                _foil_text(card, (tx, cy + 1), text, f, "lm")
            else:
                draw.text((tx, cy + 1), text, font=f, fill=color, anchor="lm")
        x += w + 22 + 8


def _boss(card: Image.Image, pic: Image.Image, box) -> None:
    """The node's boss projected behind its team: the figure's upper part filling the box's height on the right,
    fading out towards the left and the cut corners."""
    x0, y0, x1, y1 = (round(v) for v in box)
    w, hh = x1 - x0, y1 - y0
    pic = pic.convert("RGBA")
    if bbox := pic.getchannel("A").getbbox():  # the figure without its empty margins
        pic = pic.crop(bbox)
    scale = hh * 1.5 / pic.height  # the head and body; the legs run off the bottom
    pic = pic.resize((max(1, round(pic.width * scale)), max(1, round(pic.height * scale))), Image.LANCZOS)
    layer = Image.new("RGBA", (w, hh), (0, 0, 0, 0))
    layer.alpha_composite(pic, (max(0, round(w * 0.74 - pic.width / 2)), 0) if pic.width < w else ((w - pic.width) // 2, 0))
    fade = Image.linear_gradient("L").rotate(90, expand=True).transpose(Image.FLIP_LEFT_RIGHT).resize((w, hh))
    fade = fade.point(lambda v: round(min(255, v * 1.6) * 0.8))
    shape = Image.new("L", (w * SS, hh * SS), 0)
    ImageDraw.Draw(shape).polygon(h._cut((0, 0, w * SS - 1, hh * SS - 1), 12 * SS), fill=255)
    alpha = ImageChops.multiply(layer.getchannel("A"), ImageChops.multiply(fade, shape.resize((w, hh), Image.LANCZOS)))
    layer.putalpha(alpha)
    card.alpha_composite(layer, (x0, y0))


def _team(card: Image.Image, team: Team, images: dict, box, chips: bool, mode: str = "") -> None:
    """A team on its own screen: a waypoint and its name, its characters on tiles, its results under them."""
    x0, y0, x1, y1 = box
    _box(card, box, TEAM_FILL, 100, 12)
    art = images.get(team.art or "")
    if art is not None:
        _boss(card, art, (x0 + 2, y0 + 2, x1 - 2, y1 - 2))
    draw = ImageDraw.Draw(card)
    cy = y0 + LABEL_H / 2 + 4
    d = 5
    draw.polygon([(x0 + 18, cy - d), (x0 + 18 + d, cy), (x0 + 18, cy + d), (x0 + 18 - d, cy)], fill=HOLO)
    room = x1 - x0 - 48
    label = team.label.upper()
    fits = lambda text, font: draw.textlength(text, font=font) + 1.6 * len(text) <= room
    for size in (19, 17, 15):  # a long boss name gets smaller letters before it gets cut short
        font = h._raj("Bold", size)
        if fits(label, font):
            break
    else:  # still too long: "Ichor Memosprite: Judge of Oblivion" keeps just its own name
        node, _, boss = label.partition(" · ")
        if ": " in boss and fits(short := f"{node} · {boss.split(': ', 1)[1]}", font):
            label = short
            font = next(f for f in (h._raj("Bold", n) for n in (19, 17, 15)) if fits(label, f))
    h._spaced(draw, (x0 + 32, cy), base._fit_text(draw, label, font, room - 1.6 * len(label)), font, TEXT, 1.6)
    members = team.members[:4]
    row = len(members) * TILE_W + max(0, len(members) - 1) * TILE_GAP
    x = round((x0 + x1 - row) / 2)
    top = y0 + LABEL_H + 6
    for m in members:
        _tile(card, m, images.get(m.icon_url or ""), x, top)
        x += TILE_W + TILE_GAP
    if team.chips:
        _chips(card, team.chips, (x0 + x1) / 2, y1 - CHIPS_H / 2 - 6, mode)


def _side(card: Image.Image, record: Record, label: str, value: str, box, images: dict) -> None:
    """A stage's own number beside its screen: the label over a big value, or the rank's chess piece."""
    _box(card, box, h.PANEL, 120, 12)
    x0, y0, x1, y1 = box
    draw = ImageDraw.Draw(card)
    mid = (x0 + x1) / 2
    if label.lower() in ("rank", "medal"):  # the piece speaks for itself, unlabelled (Syphex's pick)
        piece = rc._rank_piece(record, value, 96, images)
        card.alpha_composite(piece, (round(mid - piece.width / 2), round((y0 + y1) / 2 - piece.height / 2)))
        return
    f = h._raj("Bold", 12)
    text = label.upper()
    tw = sum(draw.textlength(ch, font=f) + 2.6 for ch in text) - 2.6
    h._spaced(draw, (mid - tw / 2, y0 + 22), text, f, DIM, 2.6)
    big = h._raj("Bold", 60)
    if _perfect(record.mode, label.lower(), value):
        _foil_text(card, (mid, (y0 + 30 + y1) / 2), value, big, "mm")
        return
    h._top_text(card, (mid - draw.textlength(value, font=big) / 2, (y0 + 30 + y1) / 2 - 34), value, big, TEXT, 0)


def _stage_line(card: Image.Image, text: str, y: float, x0: float, x1: float) -> None:
    """The line over a stage of its own: its name spaced between two light traces, the King's between crowns."""
    draw = ImageDraw.Draw(card)
    f = h._raj("Bold", 22)
    tw = sum(draw.textlength(ch, font=f) + 5 for ch in text) - 5
    side = 40 if text == "KING" else 0
    mid = (x0 + x1) / 2
    half = tw / 2 + side
    for a, b in ((x0, mid - half - 16), (mid + half + 16, x1)):
        draw.line((a, y, b, y), fill=HOLO + (120,), width=1)
    h._top_text(card, (mid - tw / 2, y - f.size / 2 - 2), text, f, HOLO, 5)
    if side:
        crown = icons.crown(28)
        card.alpha_composite(crown, (round(mid - half), round(y - 16)))
        card.alpha_composite(crown, (round(mid + tw / 2 + 12), round(y - 16)))


def _section_h(record: Record) -> int:
    if record.empty or not record.teams:
        return HEAD + 50
    chips = any(t.chips for t in record.teams)
    rows = rc._rows(record)
    return HEAD + sum(_team_h(chips) + GAP + (STAGE_H if head else 0) for head, _ in rows) - GAP + INNER


def draw_records(uid: str, records: list[Record], images: dict[str, Image.Image], nickname: str | None = None) -> bytes:
    base.FONTS = base.FONTS or base.Fonts()
    top = PAD + HEAD_H + GAP
    height = top + sum(_section_h(r) + GAP for r in records) - GAP + PAD
    card = _starmap(W, height, uid)

    # the header: one screen across the top
    _box(card, (PAD, PAD, W - PAD, PAD + HEAD_H))
    h._top_text(card, (PAD + 24, PAD + 14), "BATTLE RECORDS", h._raj("Bold", 40), (255, 255, 255), 6)
    draw = ImageDraw.Draw(card)
    sub = "HONKAI: STAR RAIL" + (f"  ·  {nickname.upper()}" if nickname else "")
    h._spaced(draw, (PAD + 26, PAD + 72), sub, h._raj("SemiBold", 17), DIM, 1.8)
    server = base.server_name("hsr", uid)
    draw.text((W - PAD - 22, PAD + 72), f"{server + ' · ' if server else ''}UID {uid}".upper(), font=h._raj("SemiBold", 15),
              fill=FAINT, anchor="rm")

    y = top
    for record in records:
        sh = _section_h(record)
        light = MODE_LIGHT.get(record.mode, HOLO)
        _box(card, (PAD, y, W - PAD, y + sh), MODE_FILL, 130)
        draw = ImageDraw.Draw(card)
        draw.rectangle((PAD + INNER, y + 22, PAD + INNER + 3, y + 76), fill=light)  # the mode's status light
        glow = Image.new("RGBA", (40, 90), (0, 0, 0, 0))
        ImageDraw.Draw(glow).rectangle((18, 18, 21, 72), fill=light + (200,))
        card.alpha_composite(glow.filter(ImageFilter.GaussianBlur(5)), (PAD + INNER - 18, y + 4))
        tx = PAD + INNER + 18
        h._top_text(card, (tx, y + 18), record.title.upper(), h._raj("Bold", 32), (255, 255, 255), 4)
        draw = ImageDraw.Draw(card)
        if record.season:
            h._spaced(draw, (tx + 2, y + 70), base._fit_text(draw, record.season.upper(), h._raj("SemiBold", 16), 560),
                      h._raj("SemiBold", 16), DIM, 1.4)
        right = W - PAD - INNER
        for label, value in reversed(record.headline):
            w = _readout_w(draw, label, value)
            _readout(card, (right - w, y + 18, right, y + 82), label, value, record.mode)
            right -= w + 10
        if record.empty or not record.teams:
            draw = ImageDraw.Draw(card)
            draw.text((PAD + INNER + 4, y + HEAD + 16), record.empty or "Nothing to show.", font=h._raj("SemiBold", 18),
                      fill=DIM, anchor="lm")
            y += sh + GAP
            continue
        chips = any(t.chips for t in record.teams)
        th = _team_h(chips)
        by = y + HEAD
        col_w = (W - 2 * PAD - 2 * INNER - 2 * GAP) // 3
        for head, row in rc._rows(record):
            if head:
                _stage_line(card, head.upper(), by + STAGE_H / 2 - 4, PAD + INNER, W - PAD - INNER)
                by += STAGE_H
            row_w = len(row) * col_w + (len(row) - 1) * GAP
            bx = (W - row_w) // 2
            for team in row:
                if team.plight:
                    rc._shimmer(card, (bx, by, bx + col_w, by + th))
                _team(card, team, images, (bx, by, bx + col_w, by + th), chips, record.mode)
                edge = bx - 2 * GAP
                for label, value in reversed(team.left):
                    _side(card, record, label, value, (edge - SIDE_W, by + 16, edge, by + th - 16), images)
                    edge -= SIDE_W + 12
                edge = bx + col_w + 2 * GAP
                for label, value in team.right:
                    _side(card, record, label, value, (edge, by + 16, edge + SIDE_W, by + th - 16), images)
                    edge += SIDE_W + 12
                bx += col_w + GAP
            by += th + GAP
        y += sh + GAP

    out = io.BytesIO()
    card.convert("RGB").save(out, "PNG", compress_level=3)
    return out.getvalue()
