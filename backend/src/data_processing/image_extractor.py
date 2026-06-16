"""
src/data_processing/image_extractor.py

Minimal image table extraction stub.
For full OCR support, install easyocr and img2table and replace this stub.
"""
from dataclasses import dataclass, field
from typing import List, Optional, Dict


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

    def extract(self, image_path: str) -> ImageExtractionResult:
        return ImageExtractionResult(
            success=False,
            error="Image OCR table extraction is not enabled in this build. "
                  "Install easyocr + img2table for full support.",
            tables=[],
        )

    def extract_from_bytes(self, image_bytes: bytes) -> ImageExtractionResult:
        return ImageExtractionResult(
            success=False,
            error="Image OCR table extraction is not enabled in this build.",
            tables=[],
        )
