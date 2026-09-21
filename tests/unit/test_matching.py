from decimal import Decimal

from app.domain.entities import MatchReason
from app.domain.matching.engine import MatchingEngine
from app.domain.matching.rules import ExplicitInvoiceRule, InnAmountRule, MultipleInvoicesRule
from tests.conftest import make_invoice, make_payment


def engine() -> MatchingEngine:
    return MatchingEngine((ExplicitInvoiceRule(), MultipleInvoicesRule(), InnAmountRule()))


def test_explicit_reference_matches_and_caps_overpayment() -> None:
    payment = make_payment(amount="120.00")
    result = engine().match_all((payment,), (make_invoice(),))[0]
    assert result.allocations[0].amount == Decimal("100.00")
    assert result.unallocated_amount == Decimal("20.00")
    assert result.reason is MatchReason.OVERPAYMENT


def test_explicit_reference_has_priority_and_warns_for_third_party() -> None:
    payment = make_payment(inn="9999999999")
    result = engine().match_all((payment,), (make_invoice(),))[0]
    assert result.allocations[0].reason is MatchReason.THIRD_PARTY_WITH_INVOICE_REFERENCE
    assert result.warnings


def test_missing_explicit_invoice_does_not_fall_back_to_inn() -> None:
    result = engine().match_all(
        (make_payment(purpose="Оплата по счету 999"),), (make_invoice(),)
    )[0]
    assert result.reason is MatchReason.INVOICE_NOT_FOUND
    assert not result.allocations


def test_multiple_payments_close_one_invoice_and_extra_is_unallocated() -> None:
    payments = (
        make_payment("1", "60.00"),
        make_payment("2", "40.00"),
        make_payment("3", "10.00"),
    )
    results = engine().match_all(payments, (make_invoice(),))
    assert sum(len(result.allocations) for result in results) == 2
    assert results[2].reason is MatchReason.INVOICE_ALREADY_PAID
    assert results[2].unallocated_amount == Decimal("10.00")


def test_one_payment_allocates_to_multiple_invoices() -> None:
    invoices = (make_invoice("160", "40"), make_invoice("161", "60"))
    payment = make_payment(amount="100", purpose="Оплата по сч. 160, 161")
    result = engine().match_all((payment,), invoices)[0]
    assert [allocation.amount for allocation in result.allocations] == [
        Decimal("40.00"),
        Decimal("60.00"),
    ]
    assert result.reason is MatchReason.MULTIPLE_INVOICE_NUMBERS


def test_multiple_invoice_reference_warns_for_third_party() -> None:
    invoices = (make_invoice("160", "40"), make_invoice("161", "60"))
    payment = make_payment(
        amount="100", purpose="Оплата по сч. 160, 161", inn="9999999999"
    )
    result = engine().match_all((payment,), invoices)[0]
    assert len(result.allocations) == 2
    assert result.warnings == ("ИНН плательщика отличается от ИНН покупателя",)


def test_multiple_invoice_underpayment_is_not_partially_allocated() -> None:
    invoices = (make_invoice("160", "40"), make_invoice("161", "60"))
    payment = make_payment(amount="99", purpose="Оплата по сч. 160, 161")
    result = engine().match_all((payment,), invoices)[0]
    assert result.reason is MatchReason.MULTIPLE_INVOICE_AMOUNT_MISMATCH
    assert result.allocations == ()


def test_multiple_invoice_missing_reference_is_not_partially_allocated() -> None:
    payment = make_payment(amount="100", purpose="Оплата по сч. 100, 999")
    result = engine().match_all((payment,), (make_invoice(),))[0]
    assert result.reason is MatchReason.INVOICE_NOT_FOUND
    assert result.allocations == ()


def test_unique_inn_and_amount_matches_without_reference() -> None:
    payment = make_payment(purpose="Оплата по договору")
    result = engine().match_all((payment,), (make_invoice(),))[0]
    assert result.reason is MatchReason.INN_AMOUNT
    assert result.allocations[0].invoice_number == "100"


def test_ambiguous_inn_and_amount_stays_unallocated() -> None:
    invoices = (make_invoice("100"), make_invoice("101"))
    result = engine().match_all(
        (make_payment(purpose="Оплата по договору"),), invoices
    )[0]
    assert result.reason is MatchReason.AMBIGUOUS
    assert result.candidate_invoices == ("100", "101")


def test_no_match_stays_unallocated() -> None:
    result = engine().match_all(
        (make_payment(purpose="Возврат налога", inn="999"),), (make_invoice(),)
    )[0]
    assert result.reason is MatchReason.NO_MATCH
    assert result.unallocated_amount == Decimal("100.00")
