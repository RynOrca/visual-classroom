"""Tests for V3 virtual-classroom UnlimitedOCR integration."""

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

from api.routers.virtual_classroom_ocr import router as ocr_router
from open_notebook.graphs.source import content_process
from open_notebook.virtual_classroom.ocr import pdf_has_text_layer


def _make_scanned_pdf(path: Path) -> None:
    """Create a tiny image-only PDF (no selectable text layer)."""
    image = Image.new("RGB", (600, 200), "white")
    draw = ImageDraw.Draw(image)
    draw.text((20, 60), "Hello OCR", fill="black")
    image.save(path, "PDF", resolution=100.0)


def test_pdf_has_text_layer_detects_scanned_pdf(tmp_path):
    pdf_path = tmp_path / "scanned.pdf"
    _make_scanned_pdf(pdf_path)

    assert pdf_has_text_layer(str(pdf_path)) is False


def test_pdf_has_text_layer_returns_true_for_unreadable_pdf(tmp_path):
    pdf_path = tmp_path / "invalid.pdf"
    pdf_path.write_text("this is not a real pdf")

    # If we cannot inspect the file, assume it is not a scanned PDF so the
    # normal content-core pipeline still gets a chance to handle it.
    assert pdf_has_text_layer(str(pdf_path)) is True


@pytest.mark.asyncio
async def test_content_process_uses_unlimited_ocr_for_scanned_pdf(tmp_path):
    pdf_path = tmp_path / "scanned.pdf"
    _make_scanned_pdf(pdf_path)

    with (
        patch(
            "open_notebook.graphs.source.is_unlimited_ocr_available",
            return_value=True,
        ),
        patch("open_notebook.graphs.source.pdf_has_text_layer", return_value=False),
        patch(
            "open_notebook.graphs.source.run_unlimited_ocr",
            return_value="OCR extracted text",
        ),
        patch(
            "open_notebook.graphs.source.extract_content",
            new_callable=AsyncMock,
        ) as mock_extract,
    ):
        result = await content_process(
            {
                "source_id": "source:test",
                "content_state": {
                    "file_path": str(pdf_path),
                    "delete_source": False,
                },
                "embed": False,
                "apply_transformations": [],
            }
        )

    assert result["extraction"].content == "OCR extracted text"
    mock_extract.assert_not_called()


def test_ocr_endpoint_updates_source():
    app = FastAPI()
    app.include_router(ocr_router, prefix="/api")

    class FakeAsset:
        file_path = "scanned.pdf"

    class FakeSource:
        id = "source:abc"
        asset = FakeAsset()
        full_text = None

        async def save(self):
            return None

    with (
        patch(
            "api.routers.virtual_classroom_ocr.Source.get",
            new=AsyncMock(return_value=FakeSource()),
        ),
        patch(
            "api.routers.virtual_classroom_ocr.is_unlimited_ocr_available",
            return_value=True,
        ),
        patch(
            "api.routers.virtual_classroom_ocr.run_unlimited_ocr",
            return_value="OCR text from test",
        ),
    ):
        client = TestClient(app)
        response = client.post(
            "/api/virtual-classroom/ocr", json={"source_id": "source:abc"}
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["source_id"] == "source:abc"
    assert payload["ocr_engine"] == "unlimited_ocr"
    assert payload["text_length"] == len("OCR text from test")
    assert payload["updated"] is True
