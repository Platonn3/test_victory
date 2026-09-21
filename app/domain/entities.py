from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import StrEnum

from app.domain.money import ZERO, require_non_negative


class MatchReason(StrEnum):
    INVOICE_NUMBER = "invoice_number"
    MULTIPLE_INVOICE_NUMBERS = "multiple_invoice_numbers"
    INN_AMOUNT = "inn_amount"
    THIRD_PARTY_WITH_INVOICE_REFERENCE = "third_party_with_invoice_reference"
    AMBIGUOUS = "ambiguous"
    INVOICE_NOT_FOUND = "invoice_not_found"
    MULTIPLE_INVOICE_AMOUNT_MISMATCH = "multiple_invoice_amount_mismatch"
    INVOICE_ALREADY_PAID = "invoice_already_paid"
    NO_MATCH = "no_match"
    OVERPAYMENT = "overpayment"
    DUPLICATE = "duplicate"


class InvoiceStatus(StrEnum):
    FULLY_PAID = "fully_paid"
    PARTIALLY_PAID = "partially_paid"
    UNPAID = "unpaid"


@dataclass(frozen=True, slots=True)
class Invoice:
    number: str
    date: date
    customer_name: str
    customer_inn: str
    amount: Decimal

    def __post_init__(self) -> None:
        object.__setattr__(self, "amount", require_non_negative(self.amount, "invoice amount"))


@dataclass(frozen=True, slots=True)
class Payment:
    id: str
    document_number: str
    date: date
    payer_name: str
    payer_inn: str | None
    amount: Decimal
    purpose: str
    fingerprint: str

    def __post_init__(self) -> None:
        amount = require_non_negative(self.amount, "payment amount")
        if amount == ZERO:
            raise ValueError("payment amount must be positive")
        object.__setattr__(self, "amount", amount)


@dataclass(frozen=True, slots=True)
class Expense:
    document_number: str
    date: date
    amount: Decimal
    fingerprint: str

    def __post_init__(self) -> None:
        amount = require_non_negative(self.amount, "expense amount")
        if amount == ZERO:
            raise ValueError("expense amount must be positive")
        object.__setattr__(self, "amount", amount)


@dataclass(frozen=True, slots=True)
class BankControlTotals:
    opening_balance: Decimal | None = None
    income: Decimal | None = None
    expenses: Decimal | None = None
    closing_balance: Decimal | None = None


@dataclass(frozen=True, slots=True)
class PaymentBatch:
    payments: tuple[Payment, ...]
    expenses: tuple[Expense, ...]
    controls: BankControlTotals = field(default_factory=BankControlTotals)


@dataclass(frozen=True, slots=True)
class InvoiceBatch:
    invoices: tuple[Invoice, ...]


@dataclass(frozen=True, slots=True)
class Allocation:
    payment_id: str
    invoice_number: str
    amount: Decimal
    reason: MatchReason

    def __post_init__(self) -> None:
        object.__setattr__(self, "amount", require_non_negative(self.amount, "allocation"))


@dataclass(frozen=True, slots=True)
class MatchResult:
    payment_id: str
    allocations: tuple[Allocation, ...]
    unallocated_amount: Decimal
    reason: MatchReason
    candidate_invoices: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class InvoiceResult:
    invoice: Invoice
    allocated_amount: Decimal
    outstanding_amount: Decimal
    status: InvoiceStatus


@dataclass(frozen=True, slots=True)
class UnallocatedPaymentPart:
    payment: Payment
    amount: Decimal
    reason: MatchReason
    candidate_invoices: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class DuplicateRecord:
    direction: str
    document_number: str
    amount: Decimal
    fingerprint: str


@dataclass(frozen=True, slots=True)
class PaymentAudit:
    payment: Payment
    allocations: tuple[Allocation, ...]
    unallocated_amount: Decimal
    reason: MatchReason
    candidate_invoices: tuple[str, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ReconciliationResult:
    invoices: tuple[InvoiceResult, ...]
    payments: tuple[PaymentAudit, ...]
    allocations: tuple[Allocation, ...]
    unallocated: tuple[UnallocatedPaymentPart, ...]
    duplicates: tuple[DuplicateRecord, ...]
    warnings: tuple[str, ...]
    total_invoice_amount: Decimal
    total_income: Decimal
    total_expenses: Decimal
    total_allocated: Decimal
    total_unallocated: Decimal
    total_outstanding: Decimal
    opening_balance: Decimal | None
    closing_balance: Decimal | None
    balance_check: str

    @property
    def fully_paid_count(self) -> int:
        return sum(item.status is InvoiceStatus.FULLY_PAID for item in self.invoices)

    @property
    def partially_paid_count(self) -> int:
        return sum(item.status is InvoiceStatus.PARTIALLY_PAID for item in self.invoices)

    @property
    def unpaid_count(self) -> int:
        return sum(item.status is InvoiceStatus.UNPAID for item in self.invoices)
