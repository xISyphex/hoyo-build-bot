"""The build card: one image with the character art, stats, gear and weapon.

Pictures are downloaded once, shrunk, and kept on disk, so a card only needs
network access the first time a character or item shows up. Drawing runs in a
worker thread and takes a fraction of a second, even on a small VM.
"""

from __future__ import annotations

import asyncio
import hashlib
import io
import logging
import math
import os
from pathlib import Path

import aiohttp
from PIL import Image, ImageChops, ImageDraw, ImageFont

from .embeds import ELEMENT_COLORS, GAME_LABELS, ZZZ_RARITY, _is_zero, _name
from .models import CharacterBuild, Gear, PlayerProfile

log = logging.getLogger("hoyo-bot")

W, H = 1200, 720
ART_W = 400  # left column: character art, name and weapon
STATS_X, STATS_W = 420, 284
GEAR_X = 722
PAD = 24
FONT_DIR = Path(__file__).parent / "fonts"
TEXT = (238, 236, 246)
DIM = (176, 172, 196)
GOLD = (255, 209, 102)
PANEL = (255, 255, 255, 14)
LINE = (255, 255, 255, 22)
ART_MAX = 1100  # art is kept at most this tall
ICON_MAX = 192


def _font(weight: str, size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(str(FONT_DIR / f"Inter-{weight}.otf"), size)
    except OSError:
        return ImageFont.load_default(size)


class Fonts:
    def __init__(self) -> None:
        self.name = {s: _font("Bold", s) for s in (56, 50, 44, 38, 32)}
        self.meta = _font("SemiBold", 22)
        self.stat = _font("Regular", 24)
        self.stat_b = _font("Bold", 24)
        self.stat_s = _font("Regular", 20)
        self.small = _font("Regular", 18)
        self.small_b = _font("Bold", 18)
        self.slot = _font("Regular", 17)
        self.slot_b = _font("Bold", 14)
        self.main = _font("Bold", 24)
        self.sub = _font("Regular", 18)
        self.sub_b = _font("SemiBold", 18)
        self.wname = _font("Bold", 21)


FONTS: Fonts | None = None


def _accent(build: CharacterBuild) -> tuple[int, int, int]:
    color = ELEMENT_COLORS.get(build.element, GAME_LABELS[build.game]["color"])
    return (color >> 16 & 255, color >> 8 & 255, color & 255)


def _mix(a, b, t: float) -> tuple[int, int, int]:
    return tuple(round(x + (y - x) * t) for x, y in zip(a, b))


def _background(accent) -> Image.Image:
    """Dark backdrop with a soft glow of the element color behind the art."""
    small = Image.new("RGB", (W // 8, H // 8))
    px = small.load()
    dark, deep = (14, 12, 24), _mix((14, 12, 24), accent, 0.38)
    cx, cy = small.width * 0.16, small.height * 0.42
    for y in range(small.height):
        for x in range(small.width):
            d = math.hypot((x - cx) / small.width, (y - cy) / small.height)
            px[x, y] = _mix(deep, dark, min(d / 0.75, 1))
    return small.resize((W, H), Image.BILINEAR).convert("RGBA")


def _fit_text(draw: ImageDraw.ImageDraw, text: str, font, width: int) -> str:
    if draw.textlength(text, font=font) <= width:
        return text
    while text and draw.textlength(text + "…", font=font) > width:
        text = text[:-1]
    return text.rstrip() + "…"


def _wrap(draw: ImageDraw.ImageDraw, text: str, font, width: int, lines: int, sep: str = " ") -> list[str]:
    out, current = [], ""
    for word in text.split(sep):
        trial = f"{current}{sep}{word}" if current else word
        if draw.textlength(trial, font=font) <= width or not current:
            current = trial
        else:
            out.append(current)
            current = word
    out.append(current)
    if len(out) > lines:
        out = out[: lines - 1] + [_fit_text(draw, sep.join(out[lines - 1 :]), font, width)]
    return out


def _star(draw: ImageDraw.ImageDraw, cx: float, cy: float, r: float, fill) -> None:
    points = []
    for i in range(10):
        angle = -math.pi / 2 + i * math.pi / 5
        rad = r if i % 2 == 0 else r * 0.45
        points.append((cx + rad * math.cos(angle), cy + rad * math.sin(angle)))
    draw.polygon(points, fill=fill)


def _paste_art(card: Image.Image, art: Image.Image | None) -> None:
    """Character art across the left column, fading out to the right."""
    if art is None:
        return
    art = art.convert("RGBA")
    scale = (H + 60) / art.height
    if art.width * scale < ART_W + 140:
        scale = (ART_W + 140) / art.width
    art = art.resize((round(art.width * scale), round(art.height * scale)), Image.LANCZOS)
    width = ART_W + 140
    left = max((art.width - width) // 2, 0)
    top = max((art.height - H) // 3, 0)
    art = art.crop((left, top, left + width, top + H))
    fade = Image.new("L", (width, 1))
    for x in range(width):
        fade.putpixel((x, 0), 255 if x < width * 0.55 else round(255 * max(0, 1 - (x - width * 0.55) / (width * 0.45))))
    art.putalpha(ImageChops.multiply(art.getchannel("A"), fade.resize(art.size)))
    card.alpha_composite(art, (0, 0))


def _shade(card: Image.Image, box, top_alpha: int, bottom_alpha: int) -> None:
    x0, y0, x1, y1 = box
    grad = Image.new("L", (1, y1 - y0))
    for y in range(y1 - y0):
        grad.putpixel((0, y), round(top_alpha + (bottom_alpha - top_alpha) * y / max(y1 - y0 - 1, 1)))
    layer = Image.new("RGBA", (x1 - x0, y1 - y0), (10, 8, 18, 255))
    layer.putalpha(grad.resize(layer.size))
    card.alpha_composite(layer, (x0, y0))


def _panel(card: Image.Image, box, radius: int = 16, fill=PANEL) -> None:
    layer = Image.new("RGBA", card.size, (0, 0, 0, 0))
    ImageDraw.Draw(layer).rounded_rectangle(box, radius, fill=fill, outline=(255, 255, 255, 20))
    card.alpha_composite(layer)


def _icon(card: Image.Image, img: Image.Image | None, box) -> None:
    if img is None:
        return
    x0, y0, x1, y1 = box
    img = img.convert("RGBA")
    img.thumbnail((x1 - x0, y1 - y0), Image.LANCZOS)
    card.alpha_composite(img, (x0 + (x1 - x0 - img.width) // 2, y0 + (y1 - y0 - img.height) // 2))


def crit_value(build: CharacterBuild) -> float | None:
    """CRIT Rate × 2 + CRIT DMG from gear substats, a common way to rate a build's rolls."""
    total, seen = 0.0, False
    for piece in build.gear:
        for s in piece.subs:
            if s.name in ("CRIT Rate", "CRIT DMG"):
                seen = True
                value = float(s.value.rstrip("%").replace(",", ""))
                total += 2 * value if s.name == "CRIT Rate" else value
    return total if seen else None


def draw_card(build: CharacterBuild, images: dict[str, Image.Image]) -> bytes:
    global FONTS
    FONTS = FONTS or Fonts()
    f = FONTS
    accent = _accent(build)
    light = _mix(accent, (255, 255, 255), 0.45)
    labels = GAME_LABELS[build.game]

    card = _background(accent)
    _paste_art(card, images.get(build.art_url or "") or images.get(build.icon_url or ""))
    _shade(card, (0, 0, W, 210), 215, 0)
    _shade(card, (0, H - 280, W, H), 0, 225)
    draw = ImageDraw.Draw(card)

    # Name, then element · level · constellation and the rarity.
    for size, font in f.name.items():
        if draw.textlength(build.name, font=font) <= ART_W - PAD or size == 32:
            break
    name = _fit_text(draw, build.name, font, ART_W - PAD)
    draw.text((PAD + 4, 28), name, font=font, fill=TEXT)
    y = 28 + font.size + 16
    pill = build.element
    pw = draw.textlength(pill, font=f.meta) + 24
    draw.rounded_rectangle((PAD + 4, y, PAD + 4 + pw, y + 34), 17, fill=accent + (255,))
    draw.text((PAD + 16, y + 4), pill, font=f.meta, fill=(16, 14, 26) if sum(accent) > 450 else TEXT)
    meta = f"Lv. {build.level} · {labels['cons']}{build.constellation}"
    draw.text((PAD + 16 + pw, y + 4), meta, font=f.meta, fill=TEXT)
    x = PAD + 28 + pw + draw.textlength(meta, font=f.meta)
    if build.game == "zzz":
        draw.text((x, y + 4), f"{ZZZ_RARITY.get(build.rarity, '?')}-Rank", font=f.meta, fill=GOLD)
    else:
        for i in range(build.rarity):
            _star(draw, x + 10 + i * 22, y + 17, 10, GOLD)

    # Weapon, bottom left.
    if build.weapon:
        w = build.weapon
        stat_lines = _wrap(ImageDraw.Draw(card), " · ".join(f"{_name(s)} {s.value}" for s in w.stats), f.small_b, ART_W - 6 - PAD - 120, 2, " · ")
        name_lines = _wrap(ImageDraw.Draw(card), w.name, f.wname, ART_W - 6 - PAD - 120, 2)
        box_h = 34 + 26 * len(name_lines) + 24 + 22 * len(stat_lines)
        box = (PAD, H - PAD - max(box_h, 112), ART_W - 6, H - PAD)
        _panel(card, box, 14, (8, 6, 16, 190))
        _icon(card, images.get(w.icon_url or ""), (box[0] + 10, box[1] + 10, box[0] + 96, box[3] - 10))
        tx = box[0] + 108
        tw = box[2] - tx - 12
        draw = ImageDraw.Draw(card)
        ty = box[1] + (box[3] - box[1] - box_h) // 2 + 14
        for line in name_lines:
            draw.text((tx, ty), line, font=f.wname, fill=TEXT)
            ty += 26
        draw.text((tx, ty + 2), f"{labels['refine']}{w.refinement} · Lv. {w.level}", font=f.small, fill=DIM)
        ty += 28
        for line in stat_lines:
            draw.text((tx, ty), _fit_text(draw, line, f.small_b, tw), font=f.small_b, fill=TEXT)
            ty += 22

    # Stats column.
    stats = [s for s in build.stats if not _is_zero(s.value)]
    sets = build.set_bonuses[:3]
    cv = crit_value(build)
    set_lines = [(c, _wrap(ImageDraw.Draw(card), n, f.small, STATS_W - 40 - 36, 2)) for c, _, n in (b.partition(" ") for b in sets)]
    footer_h = sum(8 + 22 * len(lines) for _, lines in set_lines) + (44 if cv is not None else 0)
    box = (STATS_X, PAD, STATS_X + STATS_W, H - PAD)
    _panel(card, box)
    draw = ImageDraw.Draw(card)
    row_h = min(44, (box[3] - box[1] - 24 - footer_h - (16 if footer_h else 0)) / max(len(stats), 1))
    y = box[1] + 14
    for i, s in enumerate(stats):
        room = STATS_W - 40 - draw.textlength(s.value, font=f.stat_b)
        font = f.stat if draw.textlength(_name(s), font=f.stat) <= room else f.stat_s  # long names step down a size
        label = _fit_text(draw, _name(s), font, room)
        mid = y + row_h / 2
        draw.text((box[0] + 18, mid), label, font=font, fill=TEXT, anchor="lm")
        draw.text((box[2] - 18, mid), s.value, font=f.stat_b, fill=TEXT, anchor="rm")
        if i < len(stats) - 1:
            draw.line((box[0] + 18, y + row_h, box[2] - 18, y + row_h), fill=LINE, width=1)
        y += row_h
    y = box[3] - 14 - footer_h
    if cv is not None:
        draw.text((box[0] + 18, y + 18), "Crit Value", font=f.small, fill=DIM, anchor="lm")
        draw.text((box[2] - 18, y + 18), f"{cv:.1f}", font=f.stat_b, fill=GOLD, anchor="rm")
        y += 44
    for count, lines in set_lines:
        draw.text((box[0] + 18, y + 11), count, font=f.small_b, fill=light, anchor="lm")
        for line in lines:
            draw.text((box[0] + 58, y + 11), line, font=f.small, fill=TEXT, anchor="lm")
            y += 22
        y += 8

    # Gear, two per row.
    gear = build.gear[:6]
    if gear:
        cols, rows = 2, max(3, math.ceil(len(gear) / 2))
        gw = (W - PAD - GEAR_X - 12 * (cols - 1)) / cols
        gh = (H - 2 * PAD - 12 * (rows - 1)) / rows
        for i, piece in enumerate(gear):
            x0 = GEAR_X + (i % cols) * (gw + 12)
            y0 = PAD + (i // cols) * (gh + 12)
            badge = piece.slot.rsplit(" ", 1)[-1] if build.game == "zzz" else None
            box = (round(x0), round(y0), round(x0 + gw), round(y0 + gh))
            _gear(card, piece, images.get(piece.piece_icon or ""), box, light, labels["max_level"], badge)
    else:
        draw.text((GEAR_X + 20, PAD + 20), f"No {labels['gear'].lower()} equipped.", font=f.stat, fill=DIM)

    out = io.BytesIO()
    card.convert("RGB").save(out, "PNG", optimize=True)
    return out.getvalue()


def _gear(card: Image.Image, piece: Gear, icon: Image.Image | None, box, light, max_level: int, badge: str | None) -> None:
    """One piece: its picture, main stat and value, then the substats with a dot per roll."""
    f = FONTS
    _panel(card, box, 14, (0, 0, 0, 70))
    x0, y0, x1, y1 = box
    _icon(card, icon, (x0 + 10, y0 + 10, x0 + 66, y0 + 66))
    draw = ImageDraw.Draw(card)
    if badge:
        draw.ellipse((x0 + 48, y0 + 48, x0 + 72, y0 + 72), fill=(20, 18, 30), outline=light, width=2)
        draw.text((x0 + 60, y0 + 60), badge, font=f.slot_b, fill=TEXT, anchor="mm")
    tx = x0 + (80 if icon or badge else 14)
    draw.text((tx, y0 + 14), _fit_text(draw, _name(piece.main), f.slot, x1 - tx - 10), font=f.slot, fill=DIM)
    draw.text((tx, y0 + 34), piece.main.value, font=f.main, fill=light)
    if piece.level < max_level:
        lx = tx + draw.textlength(piece.main.value, font=f.main) + 10
        draw.text((lx, y0 + 40), f"+{piece.level}", font=f.slot, fill=DIM)
    y = y0 + 76
    step = min(27, (y1 - 10 - y) / max(len(piece.subs), 1))
    for s in piece.subs:
        mid = y + step / 2
        value_w = draw.textlength(s.value, font=f.sub_b)
        dots_w = 8 * s.rolls
        label = _fit_text(draw, _name(s), f.sub, x1 - x0 - 34 - value_w - dots_w)
        draw.text((x0 + 14, mid), label, font=f.sub, fill=TEXT, anchor="lm")
        draw.text((x1 - 12, mid), s.value, font=f.sub_b, fill=TEXT, anchor="rm")
        dx = x1 - 20 - value_w
        for _ in range(s.rolls):
            draw.ellipse((dx - 6, mid - 3, dx, mid + 3), fill=light)
            dx -= 8
        y += step


class CardMaker:
    """Downloads (once) the pictures a card needs and draws it off the event loop."""

    def __init__(self, session: aiohttp.ClientSession, cache_dir: str):
        self.session = session
        self.dir = Path(cache_dir) / "images"
        self.failed: set[str] = set()
        self.cards: dict[str, bytes] = {}  # recent cards, so flipping back and forth is instant

    async def render(self, profile: PlayerProfile, build: CharacterBuild) -> bytes:
        key = hashlib.sha1(repr((profile.uid, build)).encode()).hexdigest()
        if key in self.cards:
            return self.cards[key]
        urls = {build.art_url, build.icon_url, build.weapon.icon_url if build.weapon else None}
        urls |= {p.piece_icon for p in build.gear}
        urls.discard(None)
        loaded = await asyncio.gather(*(self._image(u, big=u == build.art_url) for u in urls))
        images = {u: img for u, img in zip(urls, loaded) if img is not None}
        png = await asyncio.to_thread(draw_card, build, images)
        if len(self.cards) >= 40:
            self.cards.pop(next(iter(self.cards)))
        self.cards[key] = png
        return png

    async def _image(self, url: str, big: bool) -> Image.Image | None:
        path = self.dir / (hashlib.sha1(url.encode()).hexdigest() + ".png")
        if path.exists():
            return await asyncio.to_thread(_open, path)
        if url in self.failed:
            return None
        try:
            async with self.session.get(url, timeout=aiohttp.ClientTimeout(total=20)) as resp:
                resp.raise_for_status()
                data = await resp.read()
            return await asyncio.to_thread(_shrink_and_save, data, path, ART_MAX if big else ICON_MAX)
        except Exception as exc:
            log.warning("Could not load card image %s: %s", url, exc)
            self.failed.add(url)
            return None


def _open(path: Path) -> Image.Image:
    with Image.open(path) as img:
        return img.convert("RGBA")


def _shrink_and_save(data: bytes, path: Path, limit: int) -> Image.Image:
    with Image.open(io.BytesIO(data)) as img:
        img = img.convert("RGBA")
    if max(img.size) > limit:
        img.thumbnail((limit, limit), Image.LANCZOS)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    img.save(tmp, "PNG")
    os.replace(tmp, path)
    return img
