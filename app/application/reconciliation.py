import logging
from collections import defaultdict
from collections.abc import Sequence
from decimal import Decimal

from app.application.errors import ReconciliationError
from app.domain.entities import (
    DuplicateRecord,
    Expense,
    Invoice,
    InvoiceBatch,
    InvoiceResult,
    InvoiceStatus,
    MatchResult,
    Payment,
    PaymentAudit,
    PaymentBatch,
    ReconciliationResult,
    UnallocatedPaymentPart,
)
from app.domain.matching.engine import MatchingEngine
from app.domain.money import ZERO
from app.domain.validator import ReconciliationValidator

logger = logging.getLogger(__name__)


class ReconciliationService:
    def __init__(self, matcher: MatchingEngine, validator: ReconciliationValidator) -> None:
        self._matcher = matcher
        self._validator = validator

    def execute(
        self, payments: PaymentBatch, invoices: InvoiceBatch
    ) -> ReconciliationResult:
        logger.info("reconciliation started")
        unique_payments, payment_duplicates = self._deduplicate_payments(payments.payments)
        unique_expenses, expense_duplicates = self._deduplicate_expenses(payments.expenses)
        duplicates = payment_duplicates + expense_duplicates
        logger.info("duplicates found: %d", len(duplicates))
        total_income = sum((payment.amount for payment in unique_payments), ZERO)
        total_expenses = sum((expense.amount for expense in unique_expenses), ZERO)
        self._validate_bank_controls(payments, total_income, total_expenses)
        matches = self._matcher.match_all(unique_payments, invoices.invoices)
        self._validator.validate(unique_payments, invoices.invoices, matches)
        logger.info("validation result: ok")
        result = self._build_result(
            unique_payments,
            invoices.invoices,
            matches,
            duplicates,
            total_income,
            total_expenses,
            payments,
        )
        logger.info(
            "reconciliation completed: payments=%d invoices=%d duplicates=%d allocated=%s "
            "unallocated=%s",
            len(unique_payments),
            len(invoices.invoices),
            len(duplicates),
            result.total_allocated,
            result.total_unallocated,
        )
        return result

    @staticmethod
    def _deduplicate_payments(
        payments: Sequence[Payment],
    ) -> tuple[tuple[Payment, ...], tuple[DuplicateRecord, ...]]:
        seen: set[str] = set()
        unique: list[Payment] = []
        duplicates: list[DuplicateRecord] = []
        for payment in payments:
            if payment.fingerprint in seen:
                duplicates.append(
                    DuplicateRecord(
                        "income",
                        payment.document_number,
                        payment.amount,
                        payment.fingerprint,
                    )
                )
            else:
                seen.add(payment.fingerprint)
                unique.append(payment)
        return tuple(unique), tuple(duplicates)

    @staticmethod
    def _deduplicate_expenses(
        expenses: Sequence[Expense],
    ) -> tuple[tuple[Expense, ...], tuple[DuplicateRecord, ...]]:
        seen: set[str] = set()
        unique: list[Expense] = []
        duplicates: list[DuplicateRecord] = []
        for expense in expenses:
            if expense.fingerprint in seen:
                duplicates.append(
                    DuplicateRecord(
                        "expense",
                        expense.document_number,
                        expense.amount,
                        expense.fingerprint,
                    )
                )
            else:
                seen.add(expense.fingerprint)
                unique.append(expense)
        return tuple(unique), tuple(duplicates)

    @staticmethod
    def _validate_bank_controls(
        batch: PaymentBatch, total_income: Decimal, total_expenses: Decimal
    ) -> None:
        controls = batch.controls
        if controls.income is not None and controls.income != total_income:
            raise ReconciliationError(
                "Сумма поступлений после удаления дублей не совпадает с итогом банка"
            )
        if controls.expenses is not None and controls.expenses != total_expenses:
            raise ReconciliationError(
                "Сумма списаний после удаления дублей не совпадает с итогом банка"
            )
        values = (
            controls.opening_balance,
            controls.income,
            controls.expenses,
            controls.closing_balance,
        )
        if all(value is not None for value in values):
            assert controls.opening_balance is not None
            assert controls.income is not None
            assert controls.expenses is not None
            assert controls.closing_balance is not None
            expected = controls.opening_balance + controls.income - controls.expenses
            if expected != controls.closing_balance:
                raise ReconciliationError("Не сходится контрольный баланс банковской выписки")

    @staticmethod
    def _build_result(
        payments: Sequence[Payment],
        invoices: Sequence[Invoice],
        matches: Sequence[MatchResult],
        duplicates: tuple[DuplicateRecord, ...],
        total_income: Decimal,
        total_expenses: Decimal,
        batch: PaymentBatch,
    ) -> ReconciliationResult:
        payment_by_id = {payment.id: payment for payment in payments}
        allocations = tuple(item for match in matches for item in match.allocations)
        allocated_by_invoice: dict[str, Decimal] = defaultdict(lambda: ZERO)
        for allocation in allocations:
            allocated_by_invoice[allocation.invoice_number] += allocation.amount
        invoice_results = tuple(
            ReconciliationService._invoice_result(invoice, allocated_by_invoice[invoice.number])
            for invoice in invoices
        )
        unallocated = tuple(
            UnallocatedPaymentPart(
                payment_by_id[match.payment_id],
                match.unallocated_amount,
                match.reason,
                match.candidate_invoices,
            )
            for match in matches
            if match.unallocated_amount > ZERO
        )
        audits = tuple(
            PaymentAudit(
                payment_by_id[match.payment_id],
                match.allocations,
                match.unallocated_amount,
                match.reason,
                match.candidate_invoices,
                match.warnings,
            )
            for match in matches
        )
        warnings = tuple(
            [
                f"Обнаружен дубль документа {item.document_number} на сумму "
                f"{ReconciliationService._format_money(item.amount)}"
                for item in duplicates
            ]
            + [warning for match in matches for warning in match.warnings]
        )
        total_allocated = sum((item.amount for item in allocations), ZERO)
        total_unallocated = sum((item.amount for item in unallocated), ZERO)
        total_invoice_amount = sum((invoice.amount for invoice in invoices), ZERO)
        total_outstanding = sum((item.outstanding_amount for item in invoice_results), ZERO)
        controls = batch.controls
        complete_controls = all(
            value is not None
            for value in (
                controls.opening_balance,
                controls.income,
                controls.expenses,
                controls.closing_balance,
            )
        )
        return ReconciliationResult(
            invoice_results,
            audits,
            allocations,
            unallocated,
            duplicates,
            warnings,
            total_invoice_amount,
            total_income,
            total_expenses,
            total_allocated,
            total_unallocated,
            total_outstanding,
            controls.opening_balance,
            controls.closing_balance,
            "ok" if complete_controls else "not_available",
        )

    @staticmethod
    def _invoice_result(invoice: Invoice, allocated: Decimal) -> InvoiceResult:
        outstanding = invoice.amount - allocated
        if allocated == invoice.amount:
            status = InvoiceStatus.FULLY_PAID
        elif allocated == ZERO:
            status = InvoiceStatus.UNPAID
        else:
            status = InvoiceStatus.PARTIALLY_PAID
        return InvoiceResult(invoice, allocated, outstanding, status)

    @staticmethod
    def _format_money(value: Decimal) -> str:
        return f"{value:,.2f}".replace(",", " ").replace(".", ",")
