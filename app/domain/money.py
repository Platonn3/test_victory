from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")
ZERO = Decimal("0.00")


def as_money(value: Decimal) -> Decimal:
    """Normalize a Decimal monetary value to kopecks."""
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def require_non_negative(value: Decimal, field: str) -> Decimal:
    normalized = as_money(value)
    if normalized < ZERO:
        raise ValueError(f"{field} must be non-negative")
    return normalized
