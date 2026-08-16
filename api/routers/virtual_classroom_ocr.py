"""V3 virtual classroom OCR API."""

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from open_notebook.domain.notebook import Source
from open_notebook.virtual_classroom.ocr import (
    is_unlimited_ocr_available,
    run_unlimited_ocr,
)

router = APIRouter()


class OcrRequest(BaseModel):
    source_id: str
    force: bool = False


class OcrResponse(BaseModel):
    source_id: str
    ocr_engine: str
    text_length: int
    updated: bool


@router.post("/virtual-classroom/ocr", response_model=OcrResponse)
async def ocr_source(data: OcrRequest):
    """Run UnlimitedOCR on a source file and update its full_text."""
    source = await Source.get(data.source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    file_path = source.asset.file_path if source.asset else None
    if not file_path:
        raise HTTPException(status_code=400, detail="Source has no local file path")

    if not is_unlimited_ocr_available():
        raise HTTPException(
            status_code=400,
            detail="UNLIMITED_OCR_COMMAND is not configured. Set it in .env first.",
        )

    text = run_unlimited_ocr(file_path)
    if not text:
        raise HTTPException(status_code=500, detail="UnlimitedOCR returned no text")

    source.full_text = text
    await source.save()
    return OcrResponse(
        source_id=source_id,
        ocr_engine="unlimited_ocr",
        text_length=len(text),
        updated=True,
    )
