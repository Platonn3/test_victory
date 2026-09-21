from typing import BinaryIO, Protocol

from app.domain.entities import InvoiceBatch, PaymentBatch


class PaymentSource(Protocol):
    def load(self, source: BinaryIO) -> PaymentBatch: ...


class InvoiceSource(Protocol):
    def load(self, source: BinaryIO) -> InvoiceBatch: ...
