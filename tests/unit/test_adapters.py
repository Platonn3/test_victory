import io
from decimal import Decimal

import pytest
from openpyxl import Workbook

from app.adapters.invoice_sources.excel import ExcelInvoiceSource
from app.adapters.payment_sources.bank_csv import BankCsvPaymentSource
from app.application.errors import ReconciliationError


def workbook_bytes(rows: list[list[object]]) -> io.BytesIO:
    workbook = Workbook()
    sheet = workbook.active
    for row in rows:
        sheet.append(row)
    output = io.BytesIO()
    workbook.save(output)
    output.seek(0)
    return output


def test_excel_adapter_finds_shifted_header_and_mixed_types() -> None:
    source = workbook_bytes(
        [
            ["Реестр"],
            [],
            ["№ счета", "Дата счета", "Покупатель", "ИНН", "Сумма"],
            [142.0, "02.08.2026", "Покупатель", 7700000001, "66 909,55"],
            ["Итого", None, None, None, 66909.55],
        ]
    )
    batch = ExcelInvoiceSource().load(source)
    assert batch.invoices[0].number == "142"
    assert batch.invoices[0].customer_inn == "7700000001"
    assert batch.invoices[0].amount == Decimal("66909.55")


def test_excel_adapter_rejects_duplicate_invoice_number() -> None:
    source = workbook_bytes(
        [
            ["№ счета", "Дата счета", "Покупатель", "ИНН", "Сумма"],
            ["1", "01.08.2026", "A", "1", 10],
            ["1", "02.08.2026", "B", "2", 20],
        ]
    )
    with pytest.raises(ReconciliationError, match="более одного раза"):
        ExcelInvoiceSource().load(source)


@pytest.mark.parametrize("content", [b"not xlsx", workbook_bytes([["nothing"]]).getvalue()])
def test_excel_adapter_rejects_broken_or_missing_table(content: bytes) -> None:
    with pytest.raises(ReconciliationError):
        ExcelInvoiceSource().load(io.BytesIO(content))


def statement_bytes(operation: str, encoding: str = "cp1251") -> io.BytesIO:
    content = (
        "Выписка по счету;1\r\n"
        "Входящий остаток;100,00\r\n\r\n"
        "Дата;Номер документа;Списание;Поступление;Контрагент;ИНН контрагента;"
        "Назначение платежа\r\n"
        f"{operation}\r\n"
        "Обороты за период;;0,00;10,00;;;\r\n"
        "Исходящий остаток;;;110,00;;;\r\n"
    )
    return io.BytesIO(content.encode(encoding))


def test_csv_adapter_reads_controls_and_utf8() -> None:
    source = statement_bytes(
        "01.08.2026;1;;10,00;Плательщик;7700000001;Оплата", "utf-8"
    )
    batch = BankCsvPaymentSource().load(source)
    assert batch.payments[0].amount == Decimal("10.00")
    assert batch.controls.opening_balance == Decimal("100.00")
    assert batch.controls.closing_balance == Decimal("110.00")


def test_csv_adapter_reads_expense() -> None:
    content = (
        "Дата;Номер документа;Списание;Поступление;Контрагент;ИНН контрагента;"
        "Назначение платежа\n"
        "01.08.2026;1;10,00;;Получатель;1;Комиссия\n"
    ).encode("cp1251")
    batch = BankCsvPaymentSource().load(io.BytesIO(content))
    assert batch.expenses[0].amount == Decimal("10.00")


@pytest.mark.parametrize(
    "content",
    [
        b"unknown",
        (
            "Дата;Номер документа;Списание;Поступление;Контрагент;ИНН контрагента;"
            "Назначение платежа\n01.08.2026;1;10,00;10,00;A;1;X\n"
        ).encode("cp1251"),
        (
            "Дата;Номер документа;Списание;Поступление;Контрагент;ИНН контрагента;"
            "Назначение платежа\n01.08.2026;;;10,00;A;1;X\n"
        ).encode("cp1251"),
    ],
)
def test_csv_adapter_rejects_malformed_content(content: bytes) -> None:
    with pytest.raises(ReconciliationError):
        BankCsvPaymentSource().load(io.BytesIO(content))
