"""
src/data_processing/image_extractor.py

Image table extraction using easyocr and img2table.
"""
from dataclasses import dataclass, field
from typing import List, Optional, Dict
import logging

logger = logging.getLogger(__name__)


@dataclass
class ExtractedTable:
    table_id: str
    linearized: str
    html: Optional[str] = None
    json_data: Optional[List[Dict]] = None
    headers: Optional[List[str]] = None
    n_rows: int = 0
    n_cols: int = 0


@dataclass
class ImageExtractionResult:
    success: bool = True
    error: Optional[str] = None
    tables: List[ExtractedTable] = field(default_factory=list)


class ClinicalImageExtractor:
    def __init__(self, use_gpu: bool = False):
        self.use_gpu = use_gpu
        self.enabled = False
        try:
            from img2table.ocr import EasyOCR
            self.ocr = EasyOCR(lang=["en"], gpu=use_gpu)
            self.enabled = True
        except ImportError:
            logger.warning("easyocr and/or img2table not installed. Scanned PDF/OCR table extraction is disabled.")

    def extract(self, image_path: str) -> ImageExtractionResult:
        if not self.enabled:
            return ImageExtractionResult(
                success=False,
                error="Image OCR table extraction is not enabled in this build. "
                      "Install easyocr + img2table for full support.",
                tables=[],
            )
        try:
            from img2table.document import Image
            doc = Image(src=image_path)
            extracted_tables = doc.extract_tables(ocr=self.ocr, implicit_rows=True, borderless_tables=True)
            tables = []
            for i, tbl in enumerate(extracted_tables):
                headers = []
                rows = []
                json_data = []
                
                content = tbl.content
                if content:
                    row_keys = sorted(content.keys())
                    for r_idx in row_keys:
                        row_cells = [content[r_idx][c_idx].value or "" for c_idx in sorted(content[r_idx].keys())]
                        rows.append(row_cells)
                    
                    if rows:
                        headers = rows[0]
                        rows_body = rows[1:] if len(rows) > 1 else []
                        for row_body in rows_body:
                            row_dict = {}
                            for col_idx, cell_val in enumerate(row_body):
                                header_name = headers[col_idx] if col_idx < len(headers) else f"col_{col_idx}"
                                row_dict[header_name] = cell_val
                            json_data.append(row_dict)
                
                parts = ["start_table"]
                if headers:
                    parts.append(f"[HEADERS: | {' | '.join(headers)}]")
                for row in rows[1:] if len(rows) > 1 else rows:
                    parts.append(f"[ROW] {' | '.join(row)}")
                parts.append("end_table")
                
                tables.append(ExtractedTable(
                    table_id=f"ocr_t{i+1}",
                    linearized=" ".join(parts),
                    json_data=json_data,
                    headers=headers,
                    n_rows=len(rows),
                    n_cols=len(headers) if headers else 0,
                ))
            return ImageExtractionResult(
                success=True,
                tables=tables,
            )
        except Exception as e:
            logger.exception("OCR table extraction failed")
            return ImageExtractionResult(
                success=False,
                error=str(e),
                tables=[],
            )

    def extract_from_bytes(self, image_bytes: bytes) -> ImageExtractionResult:
        if not self.enabled:
            return ImageExtractionResult(
                success=False,
                error="Image OCR table extraction is not enabled in this build. "
                      "Install easyocr + img2table for full support.",
                tables=[],
            )
        try:
            from img2table.document import Image
            doc = Image(src=image_bytes)
            extracted_tables = doc.extract_tables(ocr=self.ocr, implicit_rows=True, borderless_tables=True)
            tables = []
            for i, tbl in enumerate(extracted_tables):
                headers = []
                rows = []
                json_data = []
                content = tbl.content
                if content:
                    row_keys = sorted(content.keys())
                    for r_idx in row_keys:
                        row_cells = [content[r_idx][c_idx].value or "" for c_idx in sorted(content[r_idx].keys())]
                        rows.append(row_cells)
                    
                    if rows:
                        headers = rows[0]
                        rows_body = rows[1:] if len(rows) > 1 else []
                        for row_body in rows_body:
                            row_dict = {}
                            for col_idx, cell_val in enumerate(row_body):
                                header_name = headers[col_idx] if col_idx < len(headers) else f"col_{col_idx}"
                                row_dict[header_name] = cell_val
                            json_data.append(row_dict)
                
                parts = ["start_table"]
                if headers:
                    parts.append(f"[HEADERS: | {' | '.join(headers)}]")
                for row in rows[1:] if len(rows) > 1 else rows:
                    parts.append(f"[ROW] {' | '.join(row)}")
                parts.append("end_table")
                
                tables.append(ExtractedTable(
                    table_id=f"ocr_t{i+1}",
                    linearized=" ".join(parts),
                    json_data=json_data,
                    headers=headers,
                    n_rows=len(rows),
                    n_cols=len(headers) if headers else 0,
                ))
            return ImageExtractionResult(
                success=True,
                tables=tables,
            )
        except Exception as e:
            logger.exception("OCR table extraction from bytes failed")
            return ImageExtractionResult(
                success=False,
                error=str(e),
                tables=[],
            )
