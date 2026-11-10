"""One adapter per game: turn a raw Enka.Network response into a PlayerProfile."""


def fmt_int(value: float) -> str:
    return f"{int(value):,}"


def fmt_pct(value: float, digits: int = 1) -> str:
    """value is a fraction: 0.623 -> '62.3%'."""
    return f"{value * 100:.{digits}f}%"


def _with_raw(build, info: dict):
    """The build, keeping the showcase entry it was read from (for /<game> ... gear_from, see bot/borrow.py)."""
    build.raw = info
    return build
