"""The Genshin build card as a page of the Adventurer's Handbook: cream paper with a gold double border, the
character's art on a framed night-blue plate, attributes and artifacts on paper cards ruled in gold and written in
the game's slate ink. Headings in Cinzel (OFL), a serif close to Genshin's title lettering."""

from __future__ import annotations

import io
import random

from PIL import Image, ImageDraw, ImageFilter

from . import card as base
from . import stat_icons
from .effective import piece_count
from .embeds import ELEMENT_COLORS, _is_zero, _name
from .models import CharacterBuild, Gear

W, H = base.W, base.H
PAD = 24
ART_X0, ART_X1 = PAD, 400  # the art plate
STATS_X, STATS_W = 418, 284
GEAR_X = 718
SS = 4

PAPER = (236, 229, 216)  # Genshin's menu cream
CARD = (244, 239, 229)  # a paper card on the page
INK = (73, 83, 102)  # the game's slate text
INK_DIM = (132, 124, 110)
GOLD = (211, 188, 142)  # Genshin's trim gold
GOLD_DEEP = (168, 132, 74)
NAVY = (26, 30, 48)  # the art plate
GOOD = (194, 110, 24)  # effective substats: amber ink
CV = (38, 128, 122)  # Crit Value: teal ink
RARITY_BG = {5: ((148, 92, 48), (204, 146, 76)), 4: ((96, 76, 146), (150, 116, 200)), 3: ((72, 104, 140), (100, 146, 186))}


def cinzel(size: int, weight: int = 700):
    try:
        font = base.ImageFont.truetype(str(base.FONT_DIR / "Cinzel-Variable.ttf"), size)
        font.set_variation_by_axes([weight])
        return font
    except OSError:
        return base.ImageFont.load_default(size)


def accent_of(element: str) -> tuple[int, int, int]:
    color = ELEMENT_COLORS.get(element, 0xD3BC8E)
    return (color >> 16 & 255, color >> 8 & 255, color & 255)


def paper(w: int, h: int, seed: str = "") -> Image.Image:
    """Cream paper with a faint grain and darker, warmer edges."""
    rnd = random.Random(seed)
    page = Image.new("RGB", (w, h), PAPER)
    grain = Image.effect_noise((w // 2, h // 2), 18).resize((w, h), Image.BILINEAR)
    page = Image.composite(page, Image.new("RGB", (w, h), (214, 202, 180)), grain.point(lambda v: 200 + (v - 128) // 6))
    edge = Image.new("L", (w, h), 0)
    ImageDraw.Draw(edge).rectangle((0, 0, w, h), outline=255, width=60)
    edge = edge.filter(ImageFilter.GaussianBlur(50))
    page = Image.composite(Image.new("RGB", (w, h), (205, 190, 162)), page, edge.point(lambda v: v * 3 // 4))
    rnd.random()
    return page.convert("RGBA")


def frame(card: Image.Image, box, r: int = 0, inset: int = 5, color=GOLD_DEEP) -> None:
    """A gold double rule with small diamonds at the corners, like the Handbook's page borders."""
    x0, y0, x1, y1 = box
    layer = Image.new("RGBA", ((x1 - x0 + 1) * SS, (y1 - y0 + 1) * SS), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    k = SS
    d.rounded_rectangle((0, 0, layer.width - 1, layer.height - 1), r * k, outline=color + (255,), width=2 * k)
    d.rounded_rectangle((inset * k, inset * k, layer.width - 1 - inset * k, layer.height - 1 - inset * k), max(0, r - inset) * k,
                        outline=color + (150,), width=k)
    s = 7 * k
    for cx, cy in ((0, 0), (layer.width - 1, 0), (0, layer.height - 1), (layer.width - 1, layer.height - 1)):
        cx = min(max(cx, s), layer.width - 1 - s)
        cy = min(max(cy, s), layer.height - 1 - s)
        cx += (-1 if cx < layer.width / 2 else 1) * (s - inset * k // 2) * 0
        d.polygon([(cx, cy - s), (cx + s, cy), (cx, cy + s), (cx - s, cy)], fill=color + (255,))
        d.polygon([(cx, cy - s // 2), (cx + s // 2, cy), (cx, cy + s // 2), (cx - s // 2, cy)], fill=CARD + (255,))
    card.alpha_composite(layer.resize((x1 - x0 + 1, y1 - y0 + 1), Image.LANCZOS), (x0, y0))


def sheet(card: Image.Image, box, fill=CARD, r: int = 10, border=GOLD, alpha: int = 255) -> None:
    """A paper card on the page: a soft shadow, the card, a thin gold rule."""
    x0, y0, x1, y1 = box
    shadow = Image.new("RGBA", card.size, (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle((x0 + 1, y0 + 3, x1 + 1, y1 + 3), r, fill=(90, 70, 40, 50))
    base._layer_onto(card, shadow.filter(ImageFilter.GaussianBlur(4)))
    layer = Image.new("RGBA", card.size, (0, 0, 0, 0))
    ImageDraw.Draw(layer).rounded_rectangle(box, r, fill=fill + (alpha,), outline=border + (255,), width=1)
    base._layer_onto(card, layer)


def ornament(draw: ImageDraw.ImageDraw, x0: float, x1: float, y: float, color=GOLD_DEEP) -> None:
    """A ruled line with a diamond in the middle, under a heading."""
    mid = (x0 + x1) / 2
    draw.line((x0, y, mid - 9, y), fill=color, width=1)
    draw.line((mid + 9, y, x1, y), fill=color, width=1)
    draw.polygon([(mid, y - 5), (mid + 5, y), (mid, y + 5), (mid - 5, y)], fill=color)


def heading(draw: ImageDraw.ImageDraw, x: float, y: float, text: str, size: int = 17, color=INK, spacing: float = 2.0) -> float:
    font = cinzel(size, 700)
    for ch in text:
        draw.text((x, y), ch, font=font, fill=color, anchor="lm")
        x += draw.textlength(ch, font=font) + spacing
    return x


def rarity_square(icon: Image.Image | None, rarity: int, size: int, r: int = 8) -> Image.Image:
    """An item on its rarity's gradient, like the game's inventory squares."""
    top, bottom = RARITY_BG.get(rarity, RARITY_BG[3])
    tile = Image.composite(Image.new("RGBA", (size, size), bottom + (255,)), Image.new("RGBA", (size, size), top + (255,)),
                           Image.linear_gradient("L").resize((size, size)))
    if icon is not None:
        pic = icon.convert("RGBA")
        pic.thumbnail((size - 6, size - 6), Image.LANCZOS)
        tile.alpha_composite(pic, ((size - pic.width) // 2, (size - pic.height) // 2))
    mask = Image.new("L", (size * SS, size * SS), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, size * SS - 1, size * SS - 1), r * SS, fill=255)
    tile.putalpha(mask.resize((size, size), Image.LANCZOS))
    return tile


def _art_plate(card: Image.Image, build: CharacterBuild, images, accent) -> None:
    box = (ART_X0, PAD, ART_X1, H - PAD)
    w, h = box[2] - box[0], box[3] - box[1]
    plate = Image.new("RGBA", (w, h), NAVY + (255,))
    glow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse((-w * 0.3, h * 0.15, w * 1.3, h * 1.1), fill=base._mix(NAVY, accent, 0.55) + (255,))
    plate.alpha_composite(glow.filter(ImageFilter.GaussianBlur(70)))
    art = images.get(build.art_url or "") or images.get(build.icon_url or "")
    if art is not None:
        pic = art.convert("RGBA")
        scale = h * 1.04 / pic.height
        pic = pic.resize((round(pic.width * scale), round(pic.height * scale)), Image.LANCZOS)
        plate.alpha_composite(pic, ((w - pic.width) // 2 + 18, h - pic.height + 10))
    shade = Image.linear_gradient("L").resize((w, 200)).transpose(Image.FLIP_TOP_BOTTOM)
    top = Image.new("RGBA", (w, 200), NAVY + (255,))
    top.putalpha(shade.point(lambda v: v * 230 // 255))
    plate.alpha_composite(top, (0, 0))
    mask = Image.new("L", (w * SS, h * SS), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, w * SS - 1, h * SS - 1), 12 * SS, fill=255)
    plate.putalpha(mask.resize((w, h), Image.LANCZOS))
    card.alpha_composite(plate, box[:2])
    frame(card, box, 12, 5, GOLD)


def _title(card: Image.Image, build: CharacterBuild, images, accent, light) -> None:
    draw = ImageDraw.Draw(card)
    x = ART_X0 + 22
    for size in (46, 40, 34, 30, 26):
        font = cinzel(size, 800)
        if draw.textlength(build.name, font=font) <= ART_X1 - x - 18:
            break
    draw.text((x, PAD + 52), base._fit_text(draw, build.name, font, ART_X1 - x - 18), font=font, fill=(250, 244, 230), anchor="ls")
    # element and weapon type symbols, the level and the stars, on one line under the name
    y = PAD + 80
    sx = x
    for url, bright in ((build.element_icon, False), (build.path_icon, True)):
        icon = images.get(url or "")
        if icon is None and url == build.element_icon and build.element == "Cryo":
            icon = base._tinted(base._snowflake(), light)
        if icon is None:
            continue
        icon = icon.convert("RGBA")
        icon = icon.crop(icon.getchannel("A").getbbox() or (0, 0, icon.width, icon.height))
        icon.thumbnail((26, 26), Image.LANCZOS)
        card.alpha_composite(icon, (round(sx), round(y - icon.height / 2)))
        sx += icon.width + 8
    draw = ImageDraw.Draw(card)
    sx += 4
    draw.text((sx, y), f"Lv. {build.level}", font=base.FONTS.meta, fill=(236, 229, 216), anchor="lm")
    sx += draw.textlength(f"Lv. {build.level}", font=base.FONTS.meta) + 14
    for i in range(build.rarity):
        base._star(draw, sx + 8 + i * 18, y, 8, (255, 204, 80))
    draw.line((x, y + 20, ART_X1 - 22, y + 20), fill=GOLD, width=1)


def _weapon(card: Image.Image, build: CharacterBuild, images) -> None:
    w = build.weapon
    if not w:
        return
    f = base.FONTS
    x0, x1 = ART_X0 + 14, ART_X1 - 14
    draw = ImageDraw.Draw(card)
    stat_lines = base._wrap(draw, " · ".join(f"{_name(s)} {s.value}" for s in w.stats), f.small_b, x1 - x0 - 112, 2, " · ")
    name_lines = base._wrap(draw, w.name, cinzel(19, 700), x1 - x0 - 112, 2)
    box_h = max(112, 30 + 24 * len(name_lines) + 24 + 22 * len(stat_lines))
    box = (x0, H - PAD - 14 - box_h, x1, H - PAD - 14)
    sheet(card, box, CARD, 8, GOLD, 240)
    card.alpha_composite(rarity_square(images.get(w.icon_url or ""), w.rarity, 84), (box[0] + 10, round((box[1] + box[3]) / 2 - 42)))
    draw = ImageDraw.Draw(card)
    tx = box[0] + 106
    ty = box[1] + (box_h - (24 * len(name_lines) + 26 + 22 * len(stat_lines))) / 2 + 10
    for line in name_lines:
        draw.text((tx, ty), line, font=cinzel(19, 700), fill=INK, anchor="lm")
        ty += 24
    draw.text((tx, ty + 2), f"Refinement {w.refinement} · Lv. {w.level}", font=f.small, fill=INK_DIM, anchor="lm")
    ty += 26
    for line in stat_lines:
        draw.text((tx, ty), base._fit_text(draw, line, f.small_b, box[2] - tx - 10), font=f.small_b, fill=INK, anchor="lm")
        ty += 22


def _stats(card: Image.Image, build: CharacterBuild, accent, wanted) -> None:
    f = base.FONTS
    box = (STATS_X, PAD, STATS_X + STATS_W, H - PAD)
    sheet(card, box, CARD, 10)
    draw = ImageDraw.Draw(card)
    end = heading(draw, box[0] + 18, box[1] + 26, "ATTRIBUTES", 16)
    ornament(draw, end + 8, box[2] - 18, box[1] + 26)
    stats = [s for s in build.stats if not _is_zero(s.value)]
    value = base.gear_value(build, wanted)
    effective = sum(piece_count(p, wanted) for p in build.gear) if wanted and build.gear else None
    badges = [b for b in ((*value, CV) if value else None, ("EFFECTIVE SUBS", str(effective), GOOD) if effective is not None else None) if b]
    footer = 56 * len(badges)
    wanted_totals = {base.TOTAL_NAMES.get(n, n.rstrip("%")) for n in wanted or ()}
    top = box[1] + 46
    row_h = min(50, (box[3] - top - 12 - footer) / max(len(stats), 1))
    bands = Image.new("RGBA", card.size, (0, 0, 0, 0))
    bd = ImageDraw.Draw(bands)
    for i in range(len(stats)):
        if i % 2 == 0:
            bd.rectangle((box[0] + 10, top + i * row_h + 1, box[2] - 10, top + (i + 1) * row_h - 1), fill=(150, 120, 70, 22))
    base._layer_onto(card, bands)
    draw = ImageDraw.Draw(card)
    y = top
    for s in stats:
        mid = y + row_h / 2
        name = _name(s)
        dmg = ELEMENT_COLORS.get(name.split(" ")[0])
        orb = (dmg >> 16 & 255, dmg >> 8 & 255, dmg & 255) if dmg else GOLD_DEEP
        card.alpha_composite(stat_icons.icon(name, 20, GOLD_DEEP, orb), (box[0] + 18, round(mid - 10)))
        room = box[2] - 18 - (box[0] + 48) - 10 - draw.textlength(s.value, font=f.stat_b)
        font = f.stat if draw.textlength(name, font=f.stat) <= room else f.stat_s
        color = GOOD if s.name in wanted_totals else INK
        draw.text((box[0] + 48, mid), base._fit_text(draw, name, font, room), font=font, fill=color, anchor="lm")
        draw.text((box[2] - 18, mid), s.value, font=f.stat_b, fill=color, anchor="rm")
        y += row_h
    by = box[3] - 12 - footer + 10
    for label, value, color in badges:
        b = (box[0] + 12, by, box[2] - 12, by + 44)
        layer = Image.new("RGBA", card.size, (0, 0, 0, 0))
        ImageDraw.Draw(layer).rounded_rectangle(b, 6, fill=color + (26,), outline=color + (160,), width=1)
        base._layer_onto(card, layer)
        draw = ImageDraw.Draw(card)
        heading(draw, b[0] + 14, by + 22, label, 12, color, 1.6)
        draw.text((b[2] - 14, by + 22), value, font=f.stat_b, fill=color, anchor="rm")
        by += 56


def _gear(card: Image.Image, piece: Gear, icon, box, wanted) -> None:
    f = base.FONTS
    x0, y0, x1, y1 = box
    sheet(card, box, CARD, 10)
    card.alpha_composite(rarity_square(icon, piece.rarity, 56, 7), (x0 + 10, y0 + 10))
    draw = ImageDraw.Draw(card)
    tx = x0 + 78
    draw.text((tx, y0 + 22), base._fit_text(draw, _name(piece.main), f.slot, x1 - tx - 10), font=f.slot, fill=INK_DIM, anchor="lm")
    draw.text((tx, y0 + 48), piece.main.value, font=f.main, fill=INK, anchor="lm")
    if piece.level < 20:
        draw.text((tx + draw.textlength(piece.main.value, font=f.main) + 10, y0 + 50), f"+{piece.level}", font=f.slot,
                  fill=INK_DIM, anchor="lm")
    draw.line((x0 + 12, y0 + 74, x1 - 12, y0 + 74), fill=GOLD, width=1)
    y = y0 + 80
    count_h = 22 if wanted else 0
    step = min(27, (y1 - 10 - count_h - y) / max(len(piece.subs), 1))
    for s in piece.subs:
        mid = y + step / 2
        good = bool(wanted) and s.name in wanted
        color = GOOD if good else INK
        value_x = x1 - 12 - base.DOTS * 7 - 4
        vw = draw.textlength(s.value, font=f.sub_b)
        draw.text((x0 + 14, mid), base._fit_text(draw, _name(s), f.sub, value_x - x0 - 22 - vw), font=f.sub_b if good else f.sub,
                  fill=color, anchor="lm")
        draw.text((value_x, mid), s.value, font=f.sub_b, fill=color, anchor="rm")
        dx = value_x + 6
        for _ in range(min(max(s.rolls - 1, 0), base.DOTS)):
            draw.ellipse((dx, mid - 3, dx + 6, mid + 3), fill=GOOD if good else GOLD_DEEP)
            dx += 7
        y += step
    if wanted and piece.subs:
        base._slanted(card, ((x0 + x1) / 2, y1 - 8), str(piece_count(piece, wanted)), f.count, GOOD)


def draw_card(build: CharacterBuild, images: dict[str, Image.Image], uid: str | None = None,
              wanted: set[str] | None = None, face=None) -> bytes:
    base.FONTS = base.FONTS or base.Fonts()
    f = base.FONTS
    accent = accent_of(build.element)
    light = base._mix(accent, (255, 255, 255), 0.45)
    card = paper(W, H, build.name)
    frame(card, (8, 8, W - 9, H - 9), 0, 5)
    _art_plate(card, build, images, accent)
    _title(card, build, images, accent, light)
    n = max(0, min(build.constellation, 6))
    base._cons_column(card, build, n, accent, light, images, ART_X0 + 38, 150)
    _weapon(card, build, images)
    _stats(card, build, accent, wanted)
    gear = build.gear[:6]
    cols, gap = 2, 12
    gw = (W - PAD - GEAR_X - gap) / cols
    if gear:
        rows = 3
        gh = (H - 2 * PAD - gap * (rows - 1)) / rows
        for i, piece in enumerate(gear):
            gx = GEAR_X + (i % cols) * (gw + gap)
            gy = PAD + (i // cols) * (gh + gap)
            _gear(card, piece, images.get(piece.piece_icon or ""), (round(gx), round(gy), round(gx + gw), round(gy + gh)), wanted)
    else:
        ImageDraw.Draw(card).text((GEAR_X + 20, PAD + 20), "No artifacts equipped.", font=f.stat, fill=INK_DIM)
    if uid:
        server = base.server_name(build.game, uid)
        foot = f"{server} · UID {uid}" if server else f"UID {uid}"
        if build.source == "hoyolab":
            foot = f"via HoYoLAB · {foot}"
        ImageDraw.Draw(card).text((W - 18, H - 13), foot, font=f.stamp, fill=INK_DIM, anchor="rd")
    out = io.BytesIO()
    card.convert("RGB").save(out, "PNG", compress_level=3)
    return out.getvalue()
