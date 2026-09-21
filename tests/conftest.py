from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from app.domain.entities import Invoice, Payment


@pytest.fixture
def data_dir() -> Path:
    return Path(__file__).parents[1] / "data"


def make_invoice(
    number: str = "100",
    amount: str = "100.00",
    inn: str = "7700000001",
) -> Invoice:
    return Invoice(number, date(2026, 8, 1), "Покупатель", inn, Decimal(amount))


def make_payment(
    document: str = "1",
    amount: str = "100.00",
    purpose: str = "Оплата по счету №100",
    inn: str | None = "7700000001",
) -> Payment:
    return Payment(
        id=f"payment-{document}",
        document_number=document,
        date=date(2026, 8, 2),
        payer_name="Плательщик",
        payer_inn=inn,
        amount=Decimal(amount),
        purpose=purpose,
        fingerprint=f"fingerprint-{document}",
    )
