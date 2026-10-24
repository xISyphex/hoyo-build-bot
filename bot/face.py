"""Where a ZZZ agent's face is in their full-body picture, so the card can show the same head close-up for everyone.

Every agent also has a round face icon cut from the same drawing; finding that icon inside the full picture
(template matching at a range of sizes) gives the face's centre and size. When OpenCV or the icon is missing,
the face is estimated from the figure's outline instead."""

from __future__ import annotations

import logging

from PIL import Image

log = logging.getLogger("hoyo-bot")

try:
    import cv2
    import numpy as np
except ImportError:  # the card still works, with the outline estimate
    cv2 = None

WORK_H = 600  # the full picture is searched at this height
SIZES = range(40, 260, 6)  # face icon sizes tried, in pixels at WORK_H
SEARCH_H = 0.45  # the face is searched for in this top share of the figure
# Pictures whose face icon is a different drawing, so the search can't find it: picture name -> face centre x, y and
# size as shares of the picture's width / height
KNOWN = {"IconRole38": (0.5, 0.27, 0.09), "IconRole45_01": (0.435, 0.15, 0.14),
         # Star Rail portraits (by character id)
         "1407": (0.468, 0.358, 0.086), "1409": (0.555, 0.427, 0.08)}
MIN_SCORE = 0.6  # a weaker match over a whole Star Rail portrait is usually scenery, not the face
# The outline estimate, from the matches of every agent: the face is this far down the figure and this big
EST_Y, EST_D = 0.148, 0.087


def _grey(img: Image.Image):
    flat = Image.new("RGBA", img.size, (128, 128, 128, 255))
    flat.alpha_composite(img)
    return np.asarray(flat.convert("L"), dtype=np.float32)


def _match(art: Image.Image, icon: Image.Image, bottom: int) -> tuple[float, tuple[float, float, float]] | None:
    """The best match in the picture above y=bottom, with its score."""
    k = WORK_H / art.height
    hay = _grey(art.resize((max(round(art.width * k), 1), WORK_H)))[:max(round(bottom * k), max(SIZES))]
    best, found = -1.0, None
    for d in SIZES:
        if d > min(hay.shape):
            break
        tmpl = icon.resize((d, d))
        mask = np.asarray(tmpl.getchannel("A"), dtype=np.float32) / 255
        scores = np.nan_to_num(cv2.matchTemplate(hay, _grey(tmpl), cv2.TM_CCOEFF_NORMED, mask=mask), nan=-1, posinf=-1, neginf=-1)
        _, score, _, (x, y) = cv2.minMaxLoc(scores)
        if score > best:
            best, found = score, ((x + d / 2) / k, (y + d / 2) / k, d / k)
    return (best, found) if found else None


def find_face(art: Image.Image, icon: Image.Image | None, url: str = "") -> tuple[float, float, float]:
    """(centre x, centre y, size) of the face, in the picture's pixels."""
    if known := KNOWN.get(url.rsplit("/", 1)[-1].rsplit(".", 1)[0]):
        return known[0] * art.width, known[1] * art.height, known[2] * art.height
    art = art.convert("RGBA")
    solid = art.getchannel("A").point(lambda a: 255 if a > 100 else 0)
    top, height = 0, art.height
    if box := solid.getbbox():
        top, height = box[1], box[3] - box[1]
    if cv2 is not None and icon is not None:
        try:
            # the face is in the figure's top part; searching only there keeps hands, tails and weapons out
            if match := _match(art, icon.convert("RGBA"), round(top + SEARCH_H * height)):
                return match[1]
        except Exception:
            log.exception("Face search failed")
    band = solid.crop((0, top, art.width, top + max(round(height * 0.12), 1)))
    weights = list(band.resize((art.width, 1), Image.BOX).getdata())
    total = sum(weights)
    x = sum(i * w for i, w in enumerate(weights)) / total if total else art.width / 2
    return x, top + EST_Y * height, EST_D * height


def find_portrait_face(art: Image.Image, icon: Image.Image | None, url: str = "") -> tuple[float, float, float]:
    """The same for a Star Rail portrait: the figure fills the whole scene, so the whole picture is searched, and
    a weak match falls back to the picture's middle."""
    if known := KNOWN.get(url.rsplit("/", 1)[-1].rsplit(".", 1)[0]):
        return known[0] * art.width, known[1] * art.height, known[2] * art.height
    if cv2 is not None and icon is not None:
        try:
            match = _match(art.convert("RGBA"), icon.convert("RGBA"), art.height)
            if match and match[0] >= MIN_SCORE:
                return match[1]
        except Exception:
            log.exception("Face search failed")
    return art.width / 2, art.height * 0.35, art.height * 0.09
