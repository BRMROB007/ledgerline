from decimal import Decimal

import pytest

from ledgerline import money


def test_parse_two_digits():
    assert money.parse("12.50") == Decimal("12.50")


def test_parse_pads_fraction():
    assert money.fmt(money.parse("12.5")) == "12.50"


@pytest.mark.parametrize("bad", ["12.505", "abc", "", "NaN", "Infinity", None])
def test_parse_rejects(bad):
    with pytest.raises(money.MoneyError):
        money.parse(bad)


def test_quantize_half_even():
    assert money.quantize(Decimal("0.125")) == Decimal("0.12")
    assert money.quantize(Decimal("0.135")) == Decimal("0.14")


def test_total_is_exact():
    assert money.total(["0.10", "0.20"]) == Decimal("0.30")


def test_total_empty():
    assert money.total([]) == Decimal("0.00")
