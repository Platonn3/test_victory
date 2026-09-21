import io
import logging
from decimal import Decimal
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, Request, UploadFile
from fastapi.responses import HTMLResponse, Response
from fastapi.templating import Jinja2Templates

from app.application.errors import ReconciliationError
from app.application.reconciliation import ReconciliationService
from app.bootstrap.dependencies import (
    get_invoice_source,
    get_payment_source,
    get_reconciliation_service,
    get_report_exporter,
    get_report_store,
)
from app.domain.validator import InvariantViolation
from app.ports.reports import ReportExporter, ReportStore
from app.ports.sources import InvoiceSource, PaymentSource

logger = logging.getLogger(__name__)
router = APIRouter()
templates = Jinja2Templates(directory=Path(__file__).parents[2] / "templates")
MAX_UPLOAD_BYTES = 20 * 1024 * 1024


def format_money(value: Decimal) -> str:
    return f"{value:,.2f}".replace(",", " ").replace(".", ",")


templates.env.filters["money"] = format_money


@router.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request=request, name="index.html", context={})


@router.post("/reconcile", response_class=HTMLResponse)
async def reconcile(
    request: Request,
    statement_file: Annotated[UploadFile, File()],
    invoices_file: Annotated[UploadFile, File()],
    payment_source: Annotated[PaymentSource, Depends(get_payment_source)],
    invoice_source: Annotated[InvoiceSource, Depends(get_invoice_source)],
    service: Annotated[ReconciliationService, Depends(get_reconciliation_service)],
    exporter: Annotated[ReportExporter, Depends(get_report_exporter)],
    store: Annotated[ReportStore, Depends(get_report_store)],
) -> HTMLResponse:
    try:
        _validate_extension(statement_file.filename, ".csv", "банковской выписки")
        _validate_extension(invoices_file.filename, ".xlsx", "реестра счетов")
        statement_bytes = await _read_upload(statement_file)
        invoice_bytes = await _read_upload(invoices_file)
        payment_batch = payment_source.load(io.BytesIO(statement_bytes))
        invoice_batch = invoice_source.load(io.BytesIO(invoice_bytes))
        logger.info(
            "files parsed: payments=%d invoices=%d",
            len(payment_batch.payments),
            len(invoice_batch.invoices),
        )
        result = service.execute(payment_batch, invoice_batch)
        report_id = store.put(exporter.export(result))
        logger.info("report generated")
        return templates.TemplateResponse(
            request=request,
            name="result.html",
            context={"result": result, "report_id": report_id},
        )
    except ReconciliationError as exc:
        logger.warning("reconciliation rejected: %s", exc)
        return templates.TemplateResponse(
            request=request,
            name="index.html",
            context={"error": str(exc)},
            status_code=400,
        )
    except InvariantViolation as exc:
        logger.exception("reconciliation invariant violation")
        return templates.TemplateResponse(
            request=request,
            name="index.html",
            context={"error": f"Нарушена целостность результата сверки: {exc}"},
            status_code=500,
        )
    except Exception:
        logger.exception("unexpected reconciliation error")
        return templates.TemplateResponse(
            request=request,
            name="index.html",
            context={"error": "Не удалось выполнить сверку. Проверьте файлы и повторите."},
            status_code=500,
        )


@router.get("/reports/{report_id}")
def download_report(
    report_id: str,
    store: Annotated[ReportStore, Depends(get_report_store)],
) -> Response:
    report = store.get(report_id)
    if report is None:
        return Response("Отчёт не найден или срок хранения истёк", status_code=404)
    return Response(
        report,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="reconciliation.xlsx"'},
    )


async def _read_upload(upload: UploadFile) -> bytes:
    content = await upload.read(MAX_UPLOAD_BYTES + 1)
    if not content:
        raise ReconciliationError("Загружен пустой файл")
    if len(content) > MAX_UPLOAD_BYTES:
        raise ReconciliationError("Размер файла превышает 20 МБ")
    return content


def _validate_extension(filename: str | None, suffix: str, label: str) -> None:
    if filename is None or not filename.casefold().endswith(suffix):
        raise ReconciliationError(f"Неверный формат файла {label}: ожидается {suffix}")
