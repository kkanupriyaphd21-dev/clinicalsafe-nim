"""
src/data_processing/pdf_extractor.py

Minimal PDF table extraction for uploaded documents.
"""
import logging
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Dict

logger = logging.getLogger(__name__)


@dataclass
class TablePair:
    pair_id: str
    table_text: str
    html: Optional[str] = None
    json_data: Optional[List[Dict]] = None
    headers: Optional[List[str]] = None
    page: int = 0


@dataclass
class PDFExtractionResult:
    pairs: List[TablePair] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


class ClinicalPDFExtractor:
    def __init__(self, pdf_path: str, use_gpu_ocr: bool = False):
        self.pdf_path = Path(pdf_path)
        self.use_gpu_ocr = use_gpu_ocr

    def extract_all(self) -> PDFExtractionResult:
        result = PDFExtractionResult()
        try:
            import pdfplumber
            pair_idx = 0
            with pdfplumber.open(str(self.pdf_path)) as pdf:
                for page_num, page in enumerate(pdf.pages, start=1):
                    tables = page.extract_tables() or []
                    for raw in tables:
                        if not raw or len(raw) < 2:
                            continue
                        pair_idx += 1
                        headers = [str(c or "").strip() for c in raw[0]]
                        parts = ["start_table", f"[HEADERS: | {' | '.join(headers)}]"]
                        for row in raw[1:]:
                            if not any(c for c in row):
                                continue
                            cells = [str(c or "").strip() for c in row]
                            parts.append(f"[ROW] {' | '.join(cells)}")
                        parts.append("end_table")
                        result.pairs.append(TablePair(
                            pair_id=f"p{page_num}_t{pair_idx}",
                            table_text=" ".join(parts),
                            headers=headers,
                            page=page_num,
                        ))
        except Exception as e:
            logger.exception("PDF extraction failed")
            result.errors.append(str(e))
        return result
