from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

from app.domain.entities import Allocation, Invoice, MatchReason, MatchResult, Payment
from app.domain.matching.references import extract_invoice_numbers
from app.domain.money import ZERO

_PAYER_INN_MISMATCH_WARNING = "ИНН плательщика отличается от ИНН покупателя"


@dataclass(slots=True)
class MatchingContext:
    invoices: dict[str, Invoice]
    outstanding: dict[str, Decimal]


class MatchingRule(Protocol):
    def match(
        self,
        payment: Payment,
        invoices: Sequence[Invoice],
        context: MatchingContext,
    ) -> MatchResult | None: ...


def _payer_warning(payment: Payment, invoice: Invoice) -> tuple[str, ...]:
    if payment.payer_inn and payment.payer_inn != invoice.customer_inn:
        return (_PAYER_INN_MISMATCH_WARNING,)
    return ()


def _payer_warning_for_invoices(
    payment: Payment, invoices: Sequence[Invoice]
) -> tuple[str, ...]:
    if payment.payer_inn and any(
        payment.payer_inn != invoice.customer_inn for invoice in invoices
    ):
        return (_PAYER_INN_MISMATCH_WARNING,)
    return ()


class ExplicitInvoiceRule:
    def match(
        self,
        payment: Payment,
        invoices: Sequence[Invoice],
        context: MatchingContext,
    ) -> MatchResult | None:
        del invoices
        references = extract_invoice_numbers(payment.purpose)
        if len(references) != 1:
            return None
        number = references[0]
        invoice = context.invoices.get(number)
        if invoice is None:
            return MatchResult(
                payment.id, (), payment.amount, MatchReason.INVOICE_NOT_FOUND, references
            )
        outstanding = context.outstanding[number]
        warnings = _payer_warning(payment, invoice)
        if outstanding == ZERO:
            return MatchResult(
                payment.id,
                (),
                payment.amount,
                MatchReason.INVOICE_ALREADY_PAID,
                references,
                warnings,
            )
        allocated = min(payment.amount, outstanding)
        reason = (
            MatchReason.THIRD_PARTY_WITH_INVOICE_REFERENCE
            if warnings
            else MatchReason.INVOICE_NUMBER
        )
        allocation = Allocation(payment.id, number, allocated, reason)
        remainder = payment.amount - allocated
        result_reason = MatchReason.OVERPAYMENT if remainder else reason
        return MatchResult(
            payment.id, (allocation,), remainder, result_reason, references, warnings
        )


class MultipleInvoicesRule:
    def match(
        self,
        payment: Payment,
        invoices: Sequence[Invoice],
        context: MatchingContext,
    ) -> MatchResult | None:
        del invoices
        references = extract_invoice_numbers(payment.purpose)
        if len(references) < 2:
            return None
        if any(number not in context.invoices for number in references):
            return MatchResult(
                payment.id, (), payment.amount, MatchReason.INVOICE_NOT_FOUND, references
            )
        referenced_invoices = tuple(context.invoices[number] for number in references)
        warnings = _payer_warning_for_invoices(payment, referenced_invoices)
        required = sum((context.outstanding[number] for number in references), ZERO)
        if payment.amount < required:
            return MatchResult(
                payment.id,
                (),
                payment.amount,
                MatchReason.MULTIPLE_INVOICE_AMOUNT_MISMATCH,
                references,
                warnings,
            )
        allocations = tuple(
            Allocation(
                payment.id,
                number,
                context.outstanding[number],
                MatchReason.MULTIPLE_INVOICE_NUMBERS,
            )
            for number in references
            if context.outstanding[number] > ZERO
        )
        remainder = payment.amount - required
        reason = MatchReason.OVERPAYMENT if remainder else MatchReason.MULTIPLE_INVOICE_NUMBERS
        return MatchResult(payment.id, allocations, remainder, reason, references, warnings)


class InnAmountRule:
    def match(
        self,
        payment: Payment,
        invoices: Sequence[Invoice],
        context: MatchingContext,
    ) -> MatchResult | None:
        if extract_invoice_numbers(payment.purpose):
            return None
        candidates = tuple(
            invoice
            for invoice in invoices
            if payment.payer_inn
            and invoice.customer_inn == payment.payer_inn
            and context.outstanding[invoice.number] == invoice.amount
            and invoice.amount == payment.amount
        )
        if len(candidates) == 1:
            invoice = candidates[0]
            allocation = Allocation(
                payment.id, invoice.number, payment.amount, MatchReason.INN_AMOUNT
            )
            return MatchResult(
                payment.id,
                (allocation,),
                ZERO,
                MatchReason.INN_AMOUNT,
                (invoice.number,),
            )
        if len(candidates) > 1:
            numbers = tuple(invoice.number for invoice in candidates)
            return MatchResult(
                payment.id, (), payment.amount, MatchReason.AMBIGUOUS, numbers
            )
        return None
