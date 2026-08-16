"""UnlimitedOCR integration for V3 virtual classroom.

This is a thin adapter around Baidu's Unlimited-OCR. It is intentionally
optional: if `UNLIMITED_OCR_COMMAND` is not configured, OCR calls return None
so callers can fall back to the built-in content-core / Docling pipeline.
"""

import os
import shlex
import subprocess
import sys
from typing import Optional

from loguru import logger


def is_unlimited_ocr_available() -> bool:
    """Return True when the UnlimitedOCR command is configured."""
    return bool(os.environ.get("UNLIMITED_OCR_COMMAND", "").strip())


def run_unlimited_ocr(pdf_path: str, timeout: int = 600) -> Optional[str]:
    """Run UnlimitedOCR on a PDF and return extracted text.

    The command is read from `UNLIMITED_OCR_COMMAND`. Use `{input_path}` as a
    placeholder for the PDF path, e.g.:

      UNLIMITED_OCR_COMMAND="python C:/Unlimited-OCR/infer.py --model_path ./checkpoints/unlimited-ocr --input_path {input_path}"

    Returns None when OCR is not configured or fails, so the caller can fall
    back to another engine.
    """
    command_template = os.environ.get("UNLIMITED_OCR_COMMAND", "").strip()
    if not command_template:
        return None

    try:
        command = command_template.replace("{input_path}", pdf_path)
        parts = shlex.split(command)
        # Ensure the helper runs in the same Python environment as the API.
        # A bare "python" in UNLIMITED_OCR_COMMAND may resolve to a different
        # interpreter that does not have the project dependencies installed.
        if parts and os.path.splitext(os.path.basename(parts[0]))[0].lower() in {
            "python",
            "python3",
        }:
            parts[0] = sys.executable
        logger.info(f"Running UnlimitedOCR: {command}")
        proc = subprocess.run(
            parts,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if proc.returncode != 0:
            logger.error(f"UnlimitedOCR failed: {proc.stderr[:500]}")
            return None
        text = proc.stdout.strip()
        if not text:
            return None
        # If the CLI prints JSON, try to extract the text field.
        if text.startswith("{"):
            import json
            try:
                data = json.loads(text)
                text = data.get("text") or data.get("content") or text
            except Exception:
                pass
        return text
    except Exception as e:
        logger.error(f"UnlimitedOCR error: {e}")
        return None
