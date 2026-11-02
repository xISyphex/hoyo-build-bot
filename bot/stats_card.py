"""The /<game>-stats image: each game in its own design (Star Rail's hologram, ZZZ's retro dashboard, Genshin's
panels)."""

from __future__ import annotations

from PIL import Image

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
    return list(dict.fromkeys([u.icon for u in p.units if u.icon] + [r.icon for r in p.regions if r.icon]))
