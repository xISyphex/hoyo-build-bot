"""The /genshin-patch, /hsr-patch and /zzz-patch image: the version, a bar of how far through it we are with the time
left, and the banners running now (featured art large, the 4-star / A-rank items small), then the ones coming next.

Times on the card are in the player's server's own clock (the reply's text carries Discord timestamps for everyone's
own time zone)."""

from __future__ import annotations

import datetime as dt
import io

import dataclasses

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

from . import card as c
from . import record_icons as icons
from . import timezones
from .patch import KINDS, SERVER_UTC, TITLES, Banner, Patch, version_start
from .records_card import GAME_ACCENT, _cover, _rarity_tile
from .unit_traits import CRYO

W = 1200
PAD = 36
GAP = 18
COLS = 2
CARD_W = (W - 2 * PAD - (COLS - 1) * GAP) // COLS
CARD_H = 206
ART_W, ART_H = 144, 180  # the featured item's picture
SMALL = 58  # the 4-star / A-rank items
HEAD = 196  # title, countdown and the version bar
SECTION_HEAD = 46
WEAPON_KINDS = {"Weapon event wish", "Light cone warps", "W-Engine channels", "W-Engine reverberation"}
TOP_RARITY = {True: 5, False: 4}


def _short(delta: dt.timedelta) -> str:
    """'19d 13h', or under a day '5h 12m'."""
    total = max(0, int(delta.total_seconds()))
    days, rest = divmod(total, 86400)
    hours, rest = divmod(rest, 3600)
    return f"{days}d {hours}h" if days else f"{hours}h {rest // 60}m"


def _local(when: dt.datetime, clock: str | None) -> dt.datetime:
    """The time on a server's clock, or in a person's own time zone (see Patch.clock)."""
    if clock in SERVER_UTC or not clock:
        return when.astimezone(dt.timezone(dt.timedelta(hours=SERVER_UTC.get(clock or "", 0))))
    return when.astimezone(timezones.zone(clock) or dt.timezone.utc)


def _day(when: dt.datetime, clock: str | None) -> str:
    t = _local(when, clock)
    return f"{t.day} {t:%b}"


def _stamp(when: dt.datetime, clock: str | None) -> str:
    t = _local(when, clock)
    return f"{t:%a} {t.day} {t:%b} · {t:%H:%M}"


def _zone_label(patch: Patch) -> str:
    """Which clock the card's times are in, for its header: 'Times in New York · UTC-5 (EST)', or the server's."""
    clock = patch.clock
    if not clock:
        return ""
    t = _local(patch.end or patch.now, clock)  # the zone as at the end time printed under the countdown
    minutes = round(t.utcoffset().total_seconds() / 60)
    sign, minutes = "-" if minutes < 0 else "+", abs(minutes)
    offset = f"UTC{sign}{minutes // 60}" + (f":{minutes % 60:02d}" if minutes % 60 else "")
    if clock in SERVER_UTC:
        return f"Times in {clock} server time · {offset}"
    if clock.startswith("UTC"):
        return f"Times in {offset}"
    place = clock.rsplit("/", 1)[-1].replace("_", " ")
    abbr = t.tzname() or ""
    return f"Times in {place} · {offset}" + (f" ({abbr})" if abbr and abbr[0].isalpha() and abbr != "UTC" else "")


def _fit(icon: Image.Image, w: int, h: int, weapon: bool) -> Image.Image:
    """Characters fill the tile (faces sit high); weapons and light cones are shown whole, centred."""
    if not weapon:
        return _cover(icon, w, h)
    pic = icon.convert("RGBA")
    scale = min(w / pic.width, h / pic.height) * 0.92
    pic = pic.resize((max(1, round(pic.width * scale)), max(1, round(pic.height * scale))), Image.LANCZOS)
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    out.alpha_composite(pic, ((w - pic.width) // 2, (h - pic.height) // 2))
    return out


def _tile(card: Image.Image, icon: Image.Image | None, box, top: bool, weapon: bool, radius: int) -> None:
    """An item on its rarity colour (gold 5-star / S, purple 4-star / A), rounded."""
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    tile = _rarity_tile(w, h, TOP_RARITY[top])
    if icon is not None:
        tile.alpha_composite(_fit(icon, w, h, weapon))
    mask = Image.new("L", (w * 4, h * 4), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, w * 4 - 1, h * 4 - 1), radius * 4, fill=255)
    tile.putalpha(mask.resize((w, h), Image.LANCZOS))
    card.alpha_composite(tile, (x0, y0))
    ImageDraw.Draw(card).rounded_rectangle(box, radius, outline=(255, 255, 255, 50), width=1)


def _symbol(url: str, images: dict, game: str) -> Image.Image | None:
    if url == CRYO:
        return c._tinted(c._snowflake(), (170, 225, 245))
    icon = images.get(url)
    if icon is None:
        return None
    icon = icon.convert("RGBA")
    if game == "genshin" and "GachaTypeIcon" in url:  # the grey weapon type icons, a little brighter
        icon = Image.merge("RGBA", (*ImageEnhance.Brightness(icon.convert("RGB")).enhance(1.5).split(), icon.getchannel("A")))
    return icon.crop(icon.getchannel("A").getbbox() or (0, 0, icon.width, icon.height))


def _marks(card: Image.Image, urls: list[str], images: dict, game: str, x: float, cy: float, size: int) -> float:
    """A unit's element and path / specialty / weapon type, each on a small dark disc, from x; returns the width."""
    start = x
    for url in urls:
        icon = _symbol(url, images, game)
        if icon is None:
            continue
        disc = Image.new("RGBA", card.size, (0, 0, 0, 0))
        ImageDraw.Draw(disc).ellipse((x, cy - size / 2, x + size, cy + size / 2), fill=(10, 10, 16, 210),
                                     outline=(255, 255, 255, 70), width=1)
        c._layer_onto(card, disc)
        inner = size * 0.72
        scale = inner / max(icon.size)
        icon = icon.resize((max(1, round(icon.width * scale)), max(1, round(icon.height * scale))), Image.LANCZOS)
        card.alpha_composite(icon, (round(x + (size - icon.width) / 2), round(cy - icon.height / 2)))
        x += size + 4
    return x - start - 4 if x > start else 0


def _pill(card: Image.Image, right: float, y: float, text: str, accent, font, icon: Image.Image | None = None) -> float:
    """A dark pill ending at right, centred on y; returns its left edge."""
    draw = ImageDraw.Draw(card)
    w = draw.textlength(text, font=font) + 28 + (icon.width + 6 if icon else 0)
    box = (right - w, y - 16, right, y + 16)
    layer = Image.new("RGBA", card.size, (0, 0, 0, 0))
    ImageDraw.Draw(layer).rounded_rectangle(box, 16, fill=(10, 10, 16, 200), outline=accent + (170,), width=1)
    c._layer_onto(card, layer)
    x = box[0] + 14
    if icon:
        card.alpha_composite(icon, (round(x), round(y - icon.height / 2)))
        x += icon.width + 6
    draw.text((x, y), text, font=font, fill=c.TEXT, anchor="lm")
    return box[0]


def _bar(card: Image.Image, patch: Patch, now: dt.datetime, y: int, accent, light) -> None:
    """How far through the version we are: a track from its start to its end, filled up to now, with a tick where
    the second half's banners start."""
    f = c.FONTS
    draw = ImageDraw.Draw(card)
    start, end = version_start(patch), patch.end
    x0, x1, h = PAD, W - PAD, 12
    layer = Image.new("RGBA", card.size, (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    ld.rounded_rectangle((x0, y, x1, y + h), h // 2, fill=(255, 255, 255, 22))
    if not (start and end and end > start):
        c._layer_onto(card, layer)
        return
    done = min(1.0, max(0.0, (now - start) / (end - start)))
    fx = x0 + round((x1 - x0) * done)
    if fx > x0 + h:
        fill = Image.linear_gradient("L").rotate(90, expand=True).resize((fx - x0, h))
        grad = Image.composite(Image.new("RGBA", (fx - x0, h), light + (255,)), Image.new("RGBA", (fx - x0, h), accent + (255,)), fill)
        mask = Image.new("L", (fx - x0, h), 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, fx - x0 - 1, h - 1), h // 2, fill=255)
        layer.paste(grad, (x0, y), mask)
    # The second half: the latest start among this version's banners, when it isn't the version's own start
    halves = sorted({b.start for b in patch.banners if b.version == patch.version and b.start > start + dt.timedelta(days=3)})
    for when in halves[:1]:
        tx = x0 + round((x1 - x0) * (when - start) / (end - start))
        ld.rounded_rectangle((tx - 1, y - 5, tx + 1, y + h + 5), 1, fill=(255, 255, 255, 150))
        draw.text((tx, y + h + 16), f"Phase 2 · {_day(when, patch.clock)}", font=f.stamp, fill=c.DIM, anchor="mm")
    glow = Image.new("RGBA", card.size, (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse((fx - 13, y + h / 2 - 13, fx + 13, y + h / 2 + 13), fill=light + (150,))
    c._layer_onto(card, glow.filter(ImageFilter.GaussianBlur(6)))
    ld.ellipse((fx - 8, y + h / 2 - 8, fx + 8, y + h / 2 + 8), fill=(255, 255, 255, 255), outline=accent + (255,), width=3)
    c._layer_onto(card, layer)
    draw.text((x0, y + h + 16), _day(start, patch.clock), font=f.stamp, fill=c.DIM, anchor="lm")
    draw.text((x1, y + h + 16), _day(end, patch.clock), font=f.stamp, fill=c.DIM, anchor="rm")


def _banner(card: Image.Image, game: str, b: Banner, images: dict, box, accent, now: dt.datetime) -> None:
    f = c.FONTS
    x0, y0, x1, y1 = box
    c._panel(card, box, 18, (255, 255, 255, 12))
    weapon = b.kind in WEAPON_KINDS
    tops = [i for i in b.items if i[1]] or [(n, True, None) for n in b.featured]
    rest = [i for i in b.items if not i[1]]
    # The featured item(s), large
    n = max(1, min(2, len(tops)))
    aw = ART_W if n == 1 else 104
    ax = x0 + 14
    for name, _, icon in tops[:2]:
        _tile(card, images.get(icon or ""), (ax, y0 + 13, ax + aw, y0 + 13 + ART_H), True, weapon, 14)
        _marks(card, b.traits.get(name, []), images, game, ax + 6, y0 + 13 + 6 + 16, 32)
        ax += aw + 8
    tx = ax + 8
    width = x1 - tx - 16
    draw = ImageDraw.Draw(card)
    names = " & ".join(t[0] for t in tops) or "?"
    draw.text((tx, y0 + 30), c._fit_text(draw, names, f.main, width), font=f.main, fill=c.TEXT, anchor="lm")
    # The 4-star / A-rank items, small, with their names under them
    sx = tx
    for name, _, icon in rest[:5]:
        if sx + SMALL > x1 - 14:
            break
        _tile(card, images.get(icon or ""), (sx, y0 + 56, sx + SMALL, y0 + 56 + SMALL), False, weapon, 10)
        sx += SMALL + 8
    if rest:
        line = ", ".join(r[0] for r in rest)
        draw.text((tx, y0 + 56 + SMALL + 18), c._fit_text(draw, line, f.small, width), font=f.small, fill=c.DIM, anchor="lm")
    # Its time left, in the bottom-right corner
    _pill(card, x1 - 18, y1 - 34, f"ends in {_short(b.end - now)}", accent, f.small_b, icons.clock(18, (230, 230, 240)))


def _split(b: Banner) -> list[Banner]:
    """One card per featured item: a banner with two (ZZZ's channels, Genshin's weapon wish) becomes two cards
    sharing the 4-star / A-rank items."""
    tops = [i for i in b.items if i[1]]
    if len(tops) < 2:
        return [b]
    rest = [i for i in b.items if not i[1]]
    return [dataclasses.replace(b, featured=[t[0]], icon=t[2], items=[t] + rest) for t in tops]


def _rows(n: int) -> int:
    return (n + COLS - 1) // COLS


def draw_patch(patch: Patch, images: dict[str, Image.Image], now: dt.datetime | None = None) -> bytes:
    if patch.game == "zzz":  # ZZZ's own retro dashboard, like its build card and records
        from . import patch_zzz
        return patch_zzz.draw_patch(patch, images, now)
    if patch.game == "hsr":  # Star Rail's navigation hologram, like its build card and records
        from . import patch_hsr
        return patch_hsr.draw_patch(patch, images, now)
    c.FONTS = c.FONTS or c.Fonts()
    f = c.FONTS
    now = now or dt.datetime.now(dt.timezone.utc)
    game, server = patch.game, patch.clock
    accent = GAME_ACCENT[game]
    light = c._mix(accent, (255, 255, 255), 0.45)
    running = [one for b in patch.banners if b.start <= now < b.end for one in _split(b)]
    sections = [(k, [b for b in running if b.kind == k]) for k in KINDS[game]]
    sections = [(k, bs) for k, bs in sections if bs]
    upcoming = sorted((one for b in patch.banners if b.start > now and b.featured for one in _split(b)),
                      key=lambda b: b.start)[:6]
    height = HEAD + sum(SECTION_HEAD + _rows(len(bs)) * (CARD_H + GAP) for _, bs in sections) + PAD
    if not sections:
        height += 60
    if upcoming:
        height += SECTION_HEAD + 84 + GAP

    card = Image.new("RGBA", (W, height), (14, 12, 24, 255))
    glow = Image.new("RGBA", (W, height), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse((-300, -260, 700, 300), fill=c._mix((14, 12, 24), accent, 0.45) + (255,))
    ImageDraw.Draw(glow).ellipse((W - 420, -200, W + 300, 220), fill=c._mix((14, 12, 24), accent, 0.25) + (255,))
    card.alpha_composite(glow.filter(ImageFilter.GaussianBlur(120)))
    draw = ImageDraw.Draw(card)

    # Title on the left, time left on the right
    c._spaced(draw, (PAD + 2, 42), TITLES[game].upper(), f.label, light, 2.4)
    draw.text((PAD, 92), f"Version {patch.version}", font=f.name[56], fill=c.TEXT, anchor="lm")
    if patch.end:
        c._spaced(draw, (W - PAD - 160, 42), "ENDS IN", f.label, c.DIM, 2.4)
        left = _short(patch.end - now)
        draw.text((W - PAD, 92), left, font=f.name[50], fill=c.TEXT, anchor="rm")
        lw = draw.textlength(left, font=f.name[50])
        clock = icons.clock(34, light)
        card.alpha_composite(clock, (round(W - PAD - lw - 14 - clock.width), 92 - clock.height // 2))
        draw.text((W - PAD, 134), _stamp(patch.end, server), font=f.small, fill=c.DIM, anchor="rm")
    else:
        draw.text((W - PAD, 92), "End not announced", font=f.meta, fill=c.DIM, anchor="rm")
    draw.text((PAD + 2, 134), _zone_label(patch), font=f.small, fill=c.DIM, anchor="lm")
    _bar(card, patch, now, 152, accent, light)

    y = HEAD
    for kind, banners in sections:
        draw = ImageDraw.Draw(card)
        draw.rounded_rectangle((PAD, y + 12, PAD + 4, y + 34), 2, fill=accent + (255,))
        draw.text((PAD + 16, y + 23), kind, font=f.stat_b, fill=c.TEXT, anchor="lm")
        y += SECTION_HEAD
        for i, b in enumerate(banners):
            bx = PAD + (i % COLS) * (CARD_W + GAP)
            by = y + (i // COLS) * (CARD_H + GAP)
            _banner(card, game, b, images, (bx, by, bx + CARD_W, by + CARD_H), accent, now)
        y += _rows(len(banners)) * (CARD_H + GAP)
    if not sections:
        ImageDraw.Draw(card).text((PAD, y + 30), "No banners are running right now.", font=f.stat, fill=c.DIM, anchor="lm")
        y += 60

    if upcoming:  # what's next, small: featured item, name and start
        draw = ImageDraw.Draw(card)
        draw.rounded_rectangle((PAD, y + 12, PAD + 4, y + 34), 2, fill=c.DIM + (255,))
        draw.text((PAD + 16, y + 23), "Coming next", font=f.stat_b, fill=c.TEXT, anchor="lm")
        y += SECTION_HEAD
        x = PAD
        for b in upcoming:
            top = next((i for i in b.items if i[1]), (b.featured[0], True, b.icon))
            name = c._fit_text(draw, top[0], f.small_b, 150)
            marks = [u for u in b.traits.get(top[0], []) if u == CRYO or u in images]
            day = _day(b.start, server)
            line = draw.textlength(day, font=f.small) + (8 + len(marks) * 28 - 4 if marks else 0)
            w = round(64 + 12 + max(draw.textlength(name, font=f.small_b), line) + 18)
            if x + w > W - PAD:
                break
            c._panel(card, (x, y, x + w, y + 84), 14, (255, 255, 255, 12))
            _tile(card, images.get(top[2] or ""), (x + 10, y + 10, x + 74, y + 74), True, b.kind in WEAPON_KINDS, 10)
            draw = ImageDraw.Draw(card)
            draw.text((x + 86, y + 30), name, font=f.small_b, fill=c.TEXT, anchor="lm")
            draw.text((x + 86, y + 56), day, font=f.small, fill=c.DIM, anchor="lm")
            _marks(card, marks, images, game, x + 86 + draw.textlength(day, font=f.small) + 8, y + 56, 24)
            x += w + 12

    out = io.BytesIO()
    card.convert("RGB").save(out, "PNG", compress_level=3)
    return out.getvalue()


def image_urls(patch: Patch, now: dt.datetime) -> list[str]:
    """The pictures draw_patch can use."""
    marks = {u for b in patch.banners if b.end > now for urls in b.traits.values() for u in urls if u != CRYO}
    return list({i[2] for b in patch.banners if b.end > now for i in b.items if i[2]} | {b.icon for b in patch.banners if b.icon} | marks)
