"""The minigame's pictures: the /<game>-pull results (like the game's own results screen: 5-stars first, glowing) and
the /<game>-box inventory (one page of characters or weapons, with copies)."""

from __future__ import annotations

import io
import math

from PIL import Image, ImageDraw, ImageFilter

from . import card as c
from . import record_icons as icons
from .gacha import RULES, THREE_STAR, BannerChoice, Pull
from .patch_card import _fit
from .records_card import GAME_ACCENT, GAME_TITLE

W = 1200
PAD = 36
GAP = 16
STRIP = 74  # under each item: its stars and name
BG = (14, 12, 24)
RARITY = {5: ((214, 150, 64), (110, 64, 30)), 4: ((140, 98, 214), (64, 42, 116)), 3: ((70, 120, 190), (34, 58, 104))}
GLOW = {5: (255, 196, 90), 4: (176, 128, 255), 3: (90, 150, 230)}
PULL_WORD = {"genshin": "Wish", "hsr": "Warp", "zzz": "Signal Search"}
PAGES = {"genshin": ("Characters", "Weapons"), "hsr": ("Characters", "Light Cones"), "zzz": ("Agents", "W-Engines")}
RANK_LETTER = {5: "S", 4: "A", 3: "B"}


def _rarity_bg(w: int, h: int, r: int) -> Image.Image:
    top, bottom = RARITY[r]
    grad = Image.linear_gradient("L").resize((w, h))
    return Image.composite(Image.new("RGBA", (w, h), bottom + (255,)), Image.new("RGBA", (w, h), top + (255,)), grad)


def _background(height: int, accent) -> Image.Image:
    card = Image.new("RGBA", (W, height), BG + (255,))
    glow = Image.new("RGBA", (W, height), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse((-300, -260, 700, 300), fill=c._mix(BG, accent, 0.45) + (255,))
    ImageDraw.Draw(glow).ellipse((W - 420, -200, W + 300, 220), fill=c._mix(BG, accent, 0.25) + (255,))
    card.alpha_composite(glow.filter(ImageFilter.GaussianBlur(120)))
    return card


def _stars(card: Image.Image, game: str, r: int, cx: float, cy: float, size: int) -> None:
    """The item's rarity: the game's own stars, or ZZZ's rank letter."""
    if game == "zzz":
        mark = icons.rating(RANK_LETTER[r], size + 8, c.FONTS.name[32])
        card.alpha_composite(mark, (round(cx - mark.width / 2), round(cy - mark.height / 2)))
        return
    star = icons.star(game, size)
    step = size - 2
    x = cx - (r * step) / 2
    for _ in range(r):
        card.alpha_composite(star, (round(x), round(cy - star.height / 2)))
        x += step


def _blank(w: int, h: int, r: int, game: str) -> Image.Image:
    """No picture (3-stars, or one that didn't load): a big faint star / rank letter."""
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    if game == "zzz":
        mark = icons.rating(RANK_LETTER[r], h // 2, c.FONTS.name[56])
    else:
        mark = icons.star(game, h // 2)
    mark = mark.copy()  # the icons are cached
    mark.putalpha(mark.getchannel("A").point(lambda a: a * 0.35))
    out.alpha_composite(mark, ((w - mark.width) // 2, (h - mark.height) // 2))
    return out


def _item(card: Image.Image, game: str, name: str, r: int, weapon: bool, pic: Image.Image | None, box,
          glow: bool, tags: tuple[str, ...] = (), copies: int | None = None) -> None:
    """One item: its picture on its rarity colour, then a dark strip with its stars and name."""
    f = c.FONTS
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    art_h = h - STRIP
    if glow:  # the 5-star / 4-star shine around the item
        halo = Image.new("RGBA", card.size, (0, 0, 0, 0))
        ImageDraw.Draw(halo).rounded_rectangle((x0 - 6, y0 - 6, x1 + 6, y1 + 6), 22, fill=GLOW[r] + (150 if r == 5 else 90,))
        c._layer_onto(card, halo.filter(ImageFilter.GaussianBlur(14)))
    tile = Image.new("RGBA", (w, h), (18, 16, 28, 255))
    tile.alpha_composite(_rarity_bg(w, art_h, r))
    if r == 5:  # light rays behind the art
        rays = Image.new("RGBA", (w, art_h), (0, 0, 0, 0))
        rd = ImageDraw.Draw(rays)
        cx, cy, reach = w / 2, art_h * 0.5, w
        for k in range(12):
            a, b = math.radians(k * 30), math.radians(k * 30 + 10)
            rd.polygon([(cx, cy), (cx + math.cos(a) * reach, cy + math.sin(a) * reach),
                        (cx + math.cos(b) * reach, cy + math.sin(b) * reach)], fill=(255, 240, 200, 34))
        tile.alpha_composite(rays)
    tile.alpha_composite(_fit(pic, w, art_h, weapon) if pic is not None else _blank(w, art_h, r, game))
    # the strip, with a line of the rarity colour on top
    d = ImageDraw.Draw(tile)
    d.rectangle((0, art_h, w, h), fill=(20, 18, 32, 255))
    d.rectangle((0, art_h, w, art_h + 3), fill=GLOW[r] + (255,))
    mask = Image.new("L", (w * 4, h * 4), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, w * 4 - 1, h * 4 - 1), 64, fill=255)
    tile.putalpha(mask.resize((w, h), Image.LANCZOS))
    card.alpha_composite(tile, (x0, y0))
    edge = Image.new("RGBA", card.size, (0, 0, 0, 0))
    ImageDraw.Draw(edge).rounded_rectangle(box, 16, outline=GLOW[r] + (150,) if r >= 4 else (255, 255, 255, 40),
                                           width=2 if r == 5 else 1)
    c._layer_onto(card, edge)
    _stars(card, game, r, x0 + w / 2, y0 + art_h + 22, 22)
    draw = ImageDraw.Draw(card)
    draw.text((x0 + w / 2, y0 + art_h + 52), c._fit_text(draw, name, f.small_b, w - 16), font=f.small_b,
              fill=c.TEXT, anchor="mm")
    ty = y0 + 8
    for tag in tags:  # NEW / 50/50 LOST, top left
        tw = draw.textlength(tag, font=f.label) + 16
        fill = (226, 64, 84, 255) if tag == "NEW" else (24, 22, 36, 255)
        draw.rounded_rectangle((x0 + 8, ty, x0 + 8 + tw, ty + 22), 11, fill=fill, outline=GLOW[r] + (255,) if tag != "NEW" else None)
        draw.text((x0 + 8 + tw / 2, ty + 11), tag, font=f.label, fill=c.TEXT, anchor="mm")
        ty += 28
    if copies is not None:  # x5, top right
        text = f"x{copies}"
        tw = draw.textlength(text, font=f.small_b) + 20
        draw.rounded_rectangle((x1 - 8 - tw, y0 + 8, x1 - 8, y0 + 36), 14, fill=(10, 10, 16, 210),
                               outline=GLOW[r] + (200,), width=1)
        draw.text((x1 - 8 - tw / 2, y0 + 22), text, font=f.small_b, fill=c.TEXT, anchor="mm")


def _head(card: Image.Image, game: str, title: str, sub: str) -> None:
    f = c.FONTS
    accent = GAME_ACCENT[game]
    light = c._mix(accent, (255, 255, 255), 0.45)
    draw = ImageDraw.Draw(card)
    c._spaced(draw, (PAD + 2, 42), GAME_TITLE[game].upper(), f.label, light, 2.4)
    draw.text((PAD, 88), title, font=f.name[50], fill=c.TEXT, anchor="lm")
    draw.text((PAD + 2, 132), sub, font=f.stat, fill=c.DIM, anchor="lm")


def _grid(n: int, cols: int, tile_w: int) -> list[tuple[int, int]]:
    """Top-left corners of n tiles, cols to a row, each row centred."""
    out = []
    for i in range(n):
        row, col = divmod(i, cols)
        in_row = min(cols, n - row * cols)
        left = (W - in_row * tile_w - (in_row - 1) * GAP) // 2
        out.append((left + col * (tile_w + GAP), row))
    return out


def draw_pulls(game: str, banner: BannerChoice, results: list[Pull], pity: dict, left: int,
               box: dict, fairy: str, images: dict[str, Image.Image]) -> bytes:
    """The pull results, best first, 5 to a row."""
    c.FONTS = c.FONTS or c.Fonts()
    f = c.FONTS
    accent = GAME_ACCENT[game]
    order = sorted(range(len(results)), key=lambda i: (-results[i].rarity, i))
    cols = 5
    tile_w = (W - 2 * PAD - (cols - 1) * GAP) // cols
    tile_h = tile_w + STRIP
    rows = (len(results) + cols - 1) // cols
    top = 186
    height = top + rows * (tile_h + GAP + 8) + 96
    card = _background(height, accent)
    n = len(results)
    _head(card, game, f"{n}× {PULL_WORD[game]}", f"on {banner.title}")
    # Pity on the right: how far to a guaranteed 5-star
    rule = RULES[(game, banner.kind)]
    draw = ImageDraw.Draw(card)
    five = rarity_word(game, 5)
    c._spaced(draw, (W - PAD - 150, 42), f"{five} PITY", f.label, c.DIM, 2.4)
    of = f" / {rule.hard}"
    draw.text((W - PAD, 96), of, font=f.name[32], fill=c.DIM, anchor="rm")
    draw.text((W - PAD - draw.textlength(of, font=f.name[32]), 88), f"{pity.get('five', 0)}", font=f.name[50],
              fill=c.TEXT, anchor="rm")
    bar_x0, bar_x1, bar_y = W - PAD - 260, W - PAD, 124
    layer = Image.new("RGBA", card.size, (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    ld.rounded_rectangle((bar_x0, bar_y, bar_x1, bar_y + 8), 4, fill=(255, 255, 255, 26))
    done = min(1.0, pity.get("five", 0) / rule.hard)
    if done > 0:
        ld.rounded_rectangle((bar_x0, bar_y, bar_x0 + max(8, round((bar_x1 - bar_x0) * done)), bar_y + 8), 4,
                             fill=GLOW[5] + (255,))
    c._layer_onto(card, layer)
    draw = ImageDraw.Draw(card)
    if pity.get("guarantee"):
        draw.text((W - PAD, 150), "Next is guaranteed", font=f.small_b, fill=GLOW[5], anchor="rm")

    seen: dict[str, int] = {}
    owned = {name: n for page in box.values() for name, (_, n) in page.items()}
    got = {}
    for r in results:
        got[r.name] = got.get(r.name, 0) + 1
    for slot, i in zip(_grid(n, cols, tile_w), order):
        r = results[i]
        x, row = slot
        y = top + row * (tile_h + GAP + 8)
        seen[r.name] = seen.get(r.name, 0) + 1
        tags = []
        if r.rarity >= 4 and seen[r.name] == 1 and owned.get(r.name, 0) == got[r.name]:
            tags.append("NEW")
        if r.rarity == 5 and not r.featured:
            tags.append("50/50 LOST" if banner.kind == "character" else "OFF-BANNER")
        pic = images.get(r.name)
        _item(card, game, r.name, r.rarity, r.weapon, pic, (x, y, x + tile_w, y + tile_h), r.rarity >= 4, tuple(tags))

    # Fairy's verdict and what's left
    draw = ImageDraw.Draw(card)
    y = height - 62
    draw.text((PAD, y), f"Fairy: “{fairy}”", font=f.stat, fill=c.TEXT, anchor="lm")
    draw.text((W - PAD, y), f"{left} pull{'' if left == 1 else 's'} left", font=f.stat_b, fill=c.DIM, anchor="rm")
    return _png(card)


def rarity_word(game: str, r: int) -> str:
    return RANK_LETTER[r] + "-RANK" if game == "zzz" else f"{r}-STAR"


def draw_box(game: str, owner: str, box: dict, page: int, pulls: int, images: dict[str, Image.Image]) -> bytes:
    """One page of the box: characters (page 0) or weapons (page 1), best and most copies first."""
    c.FONTS = c.FONTS or c.Fonts()
    f = c.FONTS
    accent = GAME_ACCENT[game]
    key = ("characters", "weapons")[page]
    items = sorted(box.get(key, {}).items(), key=lambda kv: (-kv[1][0], -kv[1][1], kv[0]))
    cols = 6
    tile_w = (W - 2 * PAD - (cols - 1) * GAP) // cols
    tile_h = tile_w + STRIP
    shown = items[:48]
    rows = max(1, (len(shown) + cols - 1) // cols)
    top = 236
    height = top + rows * (tile_h + GAP) + PAD + (30 if len(items) > len(shown) else 0)
    card = _background(height, accent)
    fives = sum(1 for _, (r, _n) in items if r == 5)
    fours = sum(1 for _, (r, _n) in items if r == 4)
    copies = sum(n for _, (_r, n) in items)
    _head(card, game, f"{owner}'s Box",
          f"{len(items)} {PAGES[game][page].lower()} · {copies} copies · {pulls} pull{'' if pulls == 1 else 's'} left")
    # Page tabs
    draw = ImageDraw.Draw(card)
    x = PAD
    for i, label in enumerate(PAGES[game]):
        n = len(box.get(("characters", "weapons")[i], {}))
        text = f"{label}  {n}"
        tw = draw.textlength(text, font=f.stat_b) + 36
        active = i == page
        c._panel(card, (x, 166, x + tw, 206), 20, accent + (255,) if active else (255, 255, 255, 18))
        draw = ImageDraw.Draw(card)
        draw.text((x + tw / 2, 186), text, font=f.stat_b, fill=BG if active else c.DIM, anchor="mm")
        x += tw + 12
    # Rarity counts on the right
    label = f"{rarity_word(game, 5)} {fives}   ·   {rarity_word(game, 4)} {fours}"
    draw.text((W - PAD, 186), label, font=f.stat_b, fill=c.DIM, anchor="rm")

    if not items:
        draw.text((PAD, top + 40), f"Nothing here yet. Pull with /{game}-pull.", font=f.stat, fill=c.DIM, anchor="lm")
    for i, (name, (r, n)) in enumerate(shown):
        row, col = divmod(i, cols)
        x = PAD + col * (tile_w + GAP)
        y = top + row * (tile_h + GAP)
        _item(card, game, name, r, key == "weapons", images.get(name), (x, y, x + tile_w, y + tile_h), False,
              copies=n)
    if len(items) > len(shown):
        ImageDraw.Draw(card).text((W // 2, height - PAD - 6), f"+ {len(items) - len(shown)} more", font=f.stat,
                                  fill=c.DIM, anchor="mm")
    return _png(card)


def _png(card: Image.Image) -> bytes:
    out = io.BytesIO()
    card.convert("RGB").save(out, "PNG", compress_level=3)
    return out.getvalue()
