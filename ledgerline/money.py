from decimal import ROUND_HALF_EVEN, Decimal, InvalidOperation

CENT = Decimal("0.01")
ZERO = Decimal("0.00")


class MoneyError(ValueError):
    pass


def parse(value: str) -> Decimal:
    try:
        amount = Decimal(value)
    except (InvalidOperation, TypeError) as exc:
        raise MoneyError(f"invalid amount: {value!r}") from exc
    if not amount.is_finite():
        raise MoneyError(f"invalid amount: {value!r}")
    if amount != amount.quantize(CENT):
        raise MoneyError("amount has more than two fraction digits")
    return amount.quantize(CENT)


def quantize(amount: Decimal) -> Decimal:
    return amount.quantize(CENT, rounding=ROUND_HALF_EVEN)


def fmt(amount: Decimal) -> str:
    return str(quantize(amount))


def total(amounts) -> Decimal:
    return sum((parse(a) if isinstance(a, str) else a for a in amounts), ZERO)
