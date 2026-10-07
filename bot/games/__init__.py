"""One adapter per game: turn a raw Enka.Network response into a PlayerProfile."""


def fmt_int(value: float) -> str:
    return f"{int(value):,}"


def fmt_pct(value: float, digits: int = 1) -> str:
    """value is a fraction: 0.623 -> '62.3%'."""
    return f"{value * 100:.{digits}f}%"
