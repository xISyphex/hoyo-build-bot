"""Small line icons for the stat panel, drawn with Pillow so every game gets the same set."""

from __future__ import annotations

import math

from PIL import Image, ImageDraw

SS = 4  # drawn this many times bigger, then shrunk for smooth edges

# Stat name keywords -> icon, checked in order (so "CRIT DMG" wins over "DMG").
KINDS = [
    ("CRIT Rate", "crosshair"), ("CRIT DMG", "burst"), ("HP", "heart"), ("ATK", "sword"),
    ("DEF", "shield"), ("SPD", "speed"), ("Energy", "bolt"), ("Break", "crack"), ("Impact", "crack"),
    ("EHR", "target"), ("Effect Hit", "target"), ("RES", "shield_dot"), ("Healing", "plus"),
    ("PEN", "pierce"), ("EM", "gem"), ("Elemental Mastery", "gem"), ("AP", "gem"), ("AM", "gem"),
    ("Anomaly", "gem"), ("DMG", "orb"),
]


def kind_of(name: str) -> str:
    for key, kind in KINDS:
        if key in name:
            return kind
    return "diamond"


def icon(name: str, size: int, color, orb_color=None) -> Image.Image:
    """The icon for a stat name, size x size pixels, in color (orb_color tints elemental DMG)."""
    s = size * SS
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    c = s / 2
    w = max(2, round(s * 0.09))  # line width
    col = tuple(color[:3]) + (255,)
    kind = kind_of(name)
    if kind == "heart":
        r = s * 0.2
        d.ellipse((c - 2 * r, s * 0.2, c, s * 0.2 + 2 * r), fill=col)
        d.ellipse((c, s * 0.2, c + 2 * r, s * 0.2 + 2 * r), fill=col)
        d.polygon([(c - 2 * r + s * 0.01, s * 0.2 + r * 1.3), (c + 2 * r - s * 0.01, s * 0.2 + r * 1.3), (c, s * 0.86)], fill=col)
    elif kind == "sword":
        blade = [(s * 0.78, s * 0.12), (s * 0.88, s * 0.22), (s * 0.42, s * 0.68), (s * 0.32, s * 0.58)]
        d.polygon(blade, fill=col)
        d.line((s * 0.2, s * 0.52, s * 0.48, s * 0.8), fill=col, width=w)  # guard
        d.line((s * 0.34, s * 0.66, s * 0.14, s * 0.86), fill=col, width=w)  # grip
    elif kind in ("shield", "shield_dot"):
        pts = [(c, s * 0.1), (s * 0.84, s * 0.24), (s * 0.8, s * 0.56), (c, s * 0.9), (s * 0.2, s * 0.56), (s * 0.16, s * 0.24)]
        d.polygon(pts, outline=col, width=w)
        if kind == "shield_dot":
            d.ellipse((c - s * 0.1, c - s * 0.08, c + s * 0.1, c + s * 0.12), fill=col)
        else:
            d.polygon([(c, s * 0.24), (s * 0.7, s * 0.32), (s * 0.67, s * 0.54), (c, s * 0.76)], fill=col)
    elif kind == "speed":
        for dx in (0, s * 0.28):
            d.line((s * 0.18 + dx, s * 0.2, s * 0.46 + dx, c, s * 0.18 + dx, s * 0.8), fill=col, width=w, joint="curve")
    elif kind == "crosshair":
        r = s * 0.3
        d.ellipse((c - r, c - r, c + r, c + r), outline=col, width=w)
        for a in range(4):
            dx, dy = math.cos(a * math.pi / 2), math.sin(a * math.pi / 2)
            d.line((c + dx * s * 0.18, c + dy * s * 0.18, c + dx * s * 0.46, c + dy * s * 0.46), fill=col, width=w)
        d.ellipse((c - w, c - w, c + w, c + w), fill=col)
    elif kind == "burst":
        pts = []
        for i in range(16):
            a = -math.pi / 2 + i * math.pi / 8
            rad = s * (0.44 if i % 2 == 0 else 0.2)
            pts.append((c + rad * math.cos(a), c + rad * math.sin(a)))
        d.polygon(pts, fill=col)
    elif kind == "bolt":
        d.polygon([(s * 0.58, s * 0.08), (s * 0.22, s * 0.56), (s * 0.48, s * 0.56), (s * 0.4, s * 0.92),
                   (s * 0.78, s * 0.42), (s * 0.52, s * 0.42)], fill=col)
    elif kind == "crack":
        d.polygon([(s * 0.16, s * 0.16), (s * 0.84, s * 0.16), (s * 0.84, s * 0.84), (s * 0.16, s * 0.84)], outline=col, width=w)
        d.line((s * 0.5, s * 0.16, s * 0.4, s * 0.42, s * 0.6, s * 0.56, s * 0.48, s * 0.84), fill=col, width=w, joint="curve")
    elif kind == "target":
        for r in (0.4, 0.24):
            d.ellipse((c - s * r, c - s * r, c + s * r, c + s * r), outline=col, width=w)
        d.ellipse((c - w * 1.2, c - w * 1.2, c + w * 1.2, c + w * 1.2), fill=col)
    elif kind == "plus":
        d.rounded_rectangle((c - s * 0.12, s * 0.14, c + s * 0.12, s * 0.86), w, fill=col)
        d.rounded_rectangle((s * 0.14, c - s * 0.12, s * 0.86, c + s * 0.12), w, fill=col)
    elif kind == "pierce":
        d.line((s * 0.12, c, s * 0.7, c), fill=col, width=w)
        d.polygon([(s * 0.9, c), (s * 0.62, c - s * 0.18), (s * 0.62, c + s * 0.18)], fill=col)
        d.line((s * 0.42, s * 0.14, s * 0.42, s * 0.36), fill=col, width=w)
        d.line((s * 0.42, s * 0.64, s * 0.42, s * 0.86), fill=col, width=w)
    elif kind == "gem":
        pts = [(c + s * 0.4 * math.cos(math.pi / 6 + i * math.pi / 3), c + s * 0.4 * math.sin(math.pi / 6 + i * math.pi / 3)) for i in range(6)]
        d.polygon(pts, outline=col, width=w)
        d.polygon([(c, s * 0.3), (s * 0.68, c), (c, s * 0.7), (s * 0.32, c)], fill=col)
    elif kind == "orb":
        oc = tuple((orb_color or color)[:3]) + (255,)
        d.ellipse((s * 0.14, s * 0.14, s * 0.86, s * 0.86), outline=oc, width=w)
        d.ellipse((s * 0.3, s * 0.3, s * 0.7, s * 0.7), fill=oc)
    else:
        d.polygon([(c, s * 0.18), (s * 0.82, c), (c, s * 0.82), (s * 0.18, c)], fill=col)
    return img.resize((size, size), Image.LANCZOS)
