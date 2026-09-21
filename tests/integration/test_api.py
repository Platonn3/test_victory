from pathlib import Path

from fastapi.testclient import TestClient

from app.adapters.reports.memory_store import InMemoryReportStore
from app.bootstrap.dependencies import get_report_store
from app.main import app


def test_health() -> None:
    with TestClient(app) as client:
        assert client.get("/health").json() == {"status": "ok"}


def test_index_contains_upload_form() -> None:
    with TestClient(app) as client:
        response = client.get("/")
    assert response.status_code == 200
    assert "statement_file" in response.text
    assert "invoices_file" in response.text


def test_full_upload_and_report_download(data_dir: Path) -> None:
    store = InMemoryReportStore()
    app.dependency_overrides[get_report_store] = lambda: store
    try:
        with (
            TestClient(app) as client,
            (data_dir / "statement_2026_08.csv").open("rb") as statement,
            (data_dir / "invoices_2026_08.xlsx").open("rb") as invoices,
        ):
            response = client.post(
                "/reconcile",
                files={
                    "statement_file": ("statement.csv", statement, "text/csv"),
                    "invoices_file": (
                        "invoices.xlsx",
                        invoices,
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    ),
                },
            )
            assert response.status_code == 200
            assert "6 346 449,00" in response.text
            marker = '/reports/'
            report_id = response.text.split(marker, 1)[1].split('"', 1)[0]
            download = client.get(f"/reports/{report_id}")
            assert download.status_code == 200
            assert download.content.startswith(b"PK")
    finally:
        app.dependency_overrides.clear()


def test_upload_validation_and_missing_report() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/reconcile",
            files={
                "statement_file": ("statement.txt", b"x", "text/plain"),
                "invoices_file": ("invoices.xlsx", b"x", "application/octet-stream"),
            },
        )
        assert response.status_code == 400
        assert client.get("/reports/missing").status_code == 404
