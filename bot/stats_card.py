"""The /<game>-stats image: each game in its own design (Star Rail's hologram, ZZZ's retro dashboard, Genshin's
panels)."""

from __future__ import annotations

from PIL import Image, ImageDraw

from .stats import Profile


def draw_stats(p: Profile, images: dict[str, Image.Image]) -> bytes:
    if p.game == "hsr":
        from . import stats_hsr
        return stats_hsr.draw_stats(p, images)
    if p.game == "zzz":
        from . import stats_zzz
        return stats_zzz.draw_stats(p, images)
    from . import stats_genshin
    return stats_genshin.draw_stats(p, images)


def image_urls(p: Profile) -> list[str]:
    """The pictures draw_stats can use."""
    urls = [p.avatar, p.banner, *p.namecards, *(r.icon for r in p.regions), *(m.icon for m in p.medals)]
    return list(dict.fromkeys(u for u in urls if u))


def cover(pic: Image.Image, w: int, h: int, focus_y: float = 0.5) -> Image.Image:
    """The picture scaled to fill w x h, cropped around focus_y (0 top, 1 bottom)."""
    pic = pic.convert("RGBA")
    scale = max(w / pic.width, h / pic.height)
    pic = pic.resize((max(w, round(pic.width * scale)), max(h, round(pic.height * scale))), Image.LANCZOS)
    left = (pic.width - w) // 2
    upper = round((pic.height - h) * focus_y)
    return pic.crop((left, upper, left + w, upper + h))


def banner(card: Image.Image, pic: Image.Image | None, box, mask: Image.Image, shade=(10, 8, 18), strength: float = 1.0,
           tint=None, right: float = 0.35) -> None:
    """The name card behind a header: filling the box inside mask, darkened most on the left where the name sits."""
    if pic is None:
        return
    x0, y0, x1, y1 = (round(v) for v in box)
    w, h = x1 - x0, y1 - y0
    art = cover(pic, w, h, 0.4)
    if tint is not None:  # pulled toward the card's own colour so it reads as part of the screen
        art = Image.blend(art.convert("RGB"), Image.new("RGB", art.size, tint), 0.35).convert("RGBA")
    dark = Image.new("L", (w, 1))
    for x in range(w):  # 92% dark behind the name, lighter (right) toward the right edge
        t = x / max(w - 1, 1)
        dark.putpixel((x, 0), round(255 * strength * (0.92 - (0.92 - right) * min(1, t * 1.25))))
    art.alpha_composite(Image.merge("RGBA", (*Image.new("RGB", (w, h), shade).split(), dark.resize((w, h)))))
    alpha = mask.resize((w, h)) if mask.size != (w, h) else mask
    art.putalpha(alpha)
    card.alpha_composite(art, (x0, y0))


def round_avatar(card: Image.Image, pic: Image.Image | None, cx: float, cy: float, r: int, ring, back=(30, 26, 44)) -> None:
    """The profile picture in a circle with a coloured ring (a plain disc when there is none)."""
    scale = 4
    size = 2 * r
    disc = Image.new("L", (size * scale, size * scale), 0)
    ImageDraw.Draw(disc).ellipse((0, 0, size * scale - 1, size * scale - 1), fill=255)
    disc = disc.resize((size, size), Image.LANCZOS)
    face = Image.new("RGBA", (size, size), back + (255,))
    if pic is not None:
        face.alpha_composite(cover(pic, size, size, 0.5))
    face.putalpha(disc)
    ringed = Image.new("RGBA", ((size + 12) * scale,) * 2, (0, 0, 0, 0))
    ImageDraw.Draw(ringed).ellipse((0, 0, ringed.width - 1, ringed.height - 1), fill=tuple(ring)[:3] + (255,))
    ImageDraw.Draw(ringed).ellipse((4 * scale, 4 * scale, ringed.width - 1 - 4 * scale, ringed.height - 1 - 4 * scale),
                                   fill=(0, 0, 0, 0))
    ringed = ringed.resize((size + 12,) * 2, Image.LANCZOS)
    card.alpha_composite(face, (round(cx - r), round(cy - r)))
    card.alpha_composite(ringed, (round(cx - r - 6), round(cy - r - 6)))
