import logging
from dataclasses import replace
from datetime import date
from decimal import Decimal

import pytest

from app.application.errors import ReconciliationError
from app.application.reconciliation import ReconciliationService
from app.domain.entities import BankControlTotals, Expense, InvoiceBatch, PaymentBatch
from app.domain.matching.engine import MatchingEngine
from app.domain.matching.rules import ExplicitInvoiceRule, InnAmountRule, MultipleInvoicesRule
from app.domain.validator import ReconciliationValidator
from tests.conftest import make_invoice, make_payment


def service() -> ReconciliationService:
    return ReconciliationService(
        MatchingEngine((ExplicitInvoiceRule(), MultipleInvoicesRule(), InnAmountRule())),
        ReconciliationValidator(),
    )


def test_service_deduplicates_exact_payment_but_not_different_document() -> None:
    first = make_payment("1", "100")
    duplicate = replace(first)
    second = make_payment("2", "100")
    result = service().execute(
        PaymentBatch((first, duplicate, second), ()),
        InvoiceBatch((make_invoice(),)),
    )
    assert result.total_income == Decimal("200.00")
    assert len(result.duplicates) == 1
    assert result.total_unallocated == Decimal("100.00")


def test_service_deduplicates_expenses() -> None:
    expense = Expense("1", date(2026, 8, 1), Decimal("10"), "same")
    result = service().execute(
        PaymentBatch(
            (make_payment(),),
            (expense, expense),
            BankControlTotals(expenses=Decimal("10"), income=Decimal("100")),
        ),
        InvoiceBatch((make_invoice(),)),
    )
    assert result.total_expenses == Decimal("10.00")
    assert len(result.duplicates) == 1


@pytest.mark.parametrize(
    "controls",
    [
        BankControlTotals(income=Decimal("99")),
        BankControlTotals(expenses=Decimal("1")),
        BankControlTotals(
            opening_balance=Decimal("10"),
            income=Decimal("100"),
            expenses=Decimal("0"),
            closing_balance=Decimal("109"),
        ),
    ],
)
def test_service_rejects_invalid_bank_controls(controls: BankControlTotals) -> None:
    with pytest.raises(ReconciliationError):
        service().execute(
            PaymentBatch((make_payment(),), (), controls), InvoiceBatch((make_invoice(),))
        )


def test_service_reports_partial_invoice_and_missing_controls() -> None:
    result = service().execute(
        PaymentBatch((make_payment(amount="40"),), ()),
        InvoiceBatch((make_invoice(),)),
    )
    assert result.partially_paid_count == 1
    assert result.balance_check == "not_available"


def test_service_logs_duplicates_and_successful_validation(
    caplog: pytest.LogCaptureFixture,
) -> None:
    payment = make_payment()
    with caplog.at_level(logging.INFO, logger="app.application.reconciliation"):
        service().execute(
            PaymentBatch((payment, replace(payment)), ()),
            InvoiceBatch((make_invoice(),)),
        )
    assert "duplicates found: 1" in caplog.messages
    assert "validation result: ok" in caplog.messages
