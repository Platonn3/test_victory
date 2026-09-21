from decimal import Decimal

import pytest

from app.domain.entities import Allocation, MatchReason, MatchResult
from app.domain.validator import InvariantViolation, ReconciliationValidator
from tests.conftest import make_invoice, make_payment


def test_validator_accepts_conserved_payment() -> None:
    payment = make_payment()
    match = MatchResult(
        payment.id,
        (Allocation(payment.id, "100", Decimal("100"), MatchReason.INVOICE_NUMBER),),
        Decimal("0"),
        MatchReason.INVOICE_NUMBER,
    )
    ReconciliationValidator().validate((payment,), (make_invoice(),), (match,))


def test_validator_rejects_lost_payment_money() -> None:
    payment = make_payment()
    match = MatchResult(payment.id, (), Decimal("10"), MatchReason.NO_MATCH)
    with pytest.raises(InvariantViolation, match="платежа"):
        ReconciliationValidator().validate((payment,), (make_invoice(),), (match,))


def test_validator_rejects_invoice_overallocation() -> None:
    payment = make_payment(amount="101")
    match = MatchResult(
        payment.id,
        (Allocation(payment.id, "100", Decimal("101"), MatchReason.INVOICE_NUMBER),),
        Decimal("0"),
        MatchReason.INVOICE_NUMBER,
    )
    with pytest.raises(InvariantViolation, match="счёту"):
        ReconciliationValidator().validate((payment,), (make_invoice(),), (match,))
