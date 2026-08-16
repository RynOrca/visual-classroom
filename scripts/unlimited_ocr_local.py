#!/usr/bin/env python3
"""Local Unlimited-OCR helper for V3 virtual classroom.

This script renders a PDF (or image) to page images and sends them to a local
OpenAI-compatible OCR server (llama.cpp / SGLang / LM Studio).

Example usage:

    python scripts/unlimited_ocr_local.py --input_path lecture.pdf --server http://127.0.0.1:10000/v1

The extracted text is printed to stdout. Set `UNLIMITED_OCR_COMMAND` in .env to:

    UNLIMITED_OCR_COMMAND="python D:/Code/Working-on-it/v3-visualclassroom/scripts/unlimited_ocr_local.py --input_path {input_path}"
"""

import argparse
import base64
import io
import os
import sys
from pathlib import Path

import httpx
from PIL import Image


def _render_pdf_pages(pdf_path: str, scale: float, max_pages: int):
    """Yield PIL images for each page of a PDF."""
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(pdf_path)
    total = min(len(pdf), max_pages) if max_pages > 0 else len(pdf)
    for i in range(total):
        page = pdf[i]
        bitmap = page.render(scale=scale)
        pil = bitmap.to_pil()
        yield i + 1, pil.convert("RGB")
    pdf.close()


def _image_to_data_url(image: Image.Image) -> str:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def _ocr_image(server: str, model: str, image: Image.Image) -> str:
    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Convert the document to markdown. Preserve the original text and structure."},
                    {"type": "image_url", "image_url": {"url": _image_to_data_url(image)}},
                ],
            }
        ],
        "max_tokens": 8192,
        "temperature": 0,
    }
    url = server.rstrip("/") + "/chat/completions"
    with httpx.Client(timeout=600) as client:
        response = client.post(url, json=payload)
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]


def _process_image_file(image_path: str, server: str, model: str) -> str:
    with Image.open(image_path) as img:
        return _ocr_image(server, model, img.convert("RGB"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Local Unlimited-OCR helper")
    parser.add_argument("--input_path", required=True, help="Path to PDF or image file")
    parser.add_argument("--server", default=os.environ.get("UNLIMITED_OCR_SERVER", "http://127.0.0.1:10000/v1"), help="OpenAI-compatible OCR server base URL")
    parser.add_argument("--model", default=os.environ.get("UNLIMITED_OCR_MODEL", "unlimited-ocr"), help="Model name on the server")
    parser.add_argument("--scale", type=float, default=2.0, help="PDF render scale")
    parser.add_argument("--max-pages", type=int, default=100, help="Maximum pages to process")
    args = parser.parse_args()

    input_path = Path(args.input_path)
    if not input_path.exists():
        print(f"File not found: {input_path}", file=sys.stderr)
        return 1

    suffix = input_path.suffix.lower()
    try:
        if suffix == ".pdf":
            pages_text = []
            for page_no, image in _render_pdf_pages(str(input_path), args.scale, args.max_pages):
                try:
                    text = _ocr_image(args.server, args.model, image)
                    pages_text.append(f"\n\n===== Page {page_no} =====\n{text.strip()}")
                except Exception as e:
                    pages_text.append(f"\n\n===== Page {page_no} =====\n[OCR failed: {e}]")
            print("\n".join(pages_text))
        elif suffix in {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".webp"}:
            text = _process_image_file(str(input_path), args.server, args.model)
            print(text)
        else:
            print(f"Unsupported file type: {suffix}", file=sys.stderr)
            return 1
    except Exception as e:
        print(f"UnlimitedOCR local helper error: {e}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
