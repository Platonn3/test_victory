import pytest

from app.domain.matching.references import extract_invoice_numbers


@pytest.mark.parametrize(
    ("purpose", "expected"),
    [
        ("Оплата по счету №142 от 02.08.2026", ("142",)),
        ("Оплата сч. 145. В т.ч. НДС", ("145",)),
        ("Оплата по сч 150 за товар", ("150",)),
        ("ОПЛАТА ПО СЧЕТУ 151 ОТ 06.08.2026", ("151",)),
        ("inv-149 payment", ("149",)),
        ("Оплата по сч. 160, 161, 162 согласно договору", ("160", "161", "162")),
        ("Оплата по договору №12/26. НДС 22%", ()),
        ("Возврат налога по решению №1187", ()),
        ("Оплата по сч. 160, 160", ("160",)),
    ],
)
def test_extract_invoice_numbers(purpose: str, expected: tuple[str, ...]) -> None:
    assert extract_invoice_numbers(purpose) == expected
