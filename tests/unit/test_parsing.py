from datetime import date, datetime
from decimal import Decimal

import pytest

from app.adapters.parsing import normalize_identifier, parse_date, parse_money
from app.application.errors import ReconciliationError


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("66 909,55", Decimal("66909.55")),
        ("1\u00a0234,50", Decimal("1234.50")),
        (123.4, Decimal("123.40")),
        (Decimal("1.005"), Decimal("1.01")),
    ],
)
def test_parse_money(value: object, expected: Decimal) -> None:
    assert parse_money(value) == expected


@pytest.mark.parametrize("value", [None, "", "broken", True])
def test_parse_money_rejects_invalid_values(value: object) -> None:
    with pytest.raises(ReconciliationError):
        parse_money(value)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("16.08.2026", date(2026, 8, 16)),
        ("2026-08-16", date(2026, 8, 16)),
        (date(2026, 8, 16), date(2026, 8, 16)),
        (datetime(2026, 8, 16, 12), date(2026, 8, 16)),
    ],
)
def test_parse_date(value: object, expected: date) -> None:
    assert parse_date(value) == expected


def test_parse_date_rejects_unknown_format() -> None:
    with pytest.raises(ReconciliationError):
        parse_date("16/08/2026")


def test_normalize_identifier_handles_numeric_excel_values() -> None:
    assert normalize_identifier(142.0, "number") == "142"
    assert normalize_identifier("00142", "number") == "00142"


@pytest.mark.parametrize("value", [None, " ", True])
def test_normalize_identifier_rejects_invalid_values(value: object) -> None:
    with pytest.raises(ReconciliationError):
        normalize_identifier(value, "number")
