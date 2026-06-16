"""
src/data_processing/csr_parser.py

Parses a full Clinical Study Report (CSR) PDF into structured sections,
each containing extracted tables and associated narrative text.
"""

import hashlib
import re
import logging
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Any, Set
from dataclasses import dataclass, field, asdict

from src.data_processing.csr_section_detector import CSRSectionDetector

logger = logging.getLogger(__name__)


@dataclass
class CSRTable:
    table_id: str
    linearized: str
    html: Optional[str] = None
    json_data: Optional[List[Dict]] = None
    headers: Optional[List[str]] = None
    page: int = 0
    table_type: str = "unknown"
    title: str = ""
    source_page_start: int = 0
    source_page_end: int = 0
    surrounding_text: str = ""


@dataclass
class CSRSection:
    section_number: str
    title: str
    canonical_title: str
    start_page: int
    end_page: int
    level: int
    narrative_text: str
    tables: List[CSRTable] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "section_number": self.section_number,
            "title": self.title,
            "canonical_title": self.canonical_title,
            "start_page": self.start_page,
            "end_page": self.end_page,
            "level": self.level,
            "narrative_text": self.narrative_text[:2000] if self.narrative_text else "",
            "table_count": len(self.tables),
            "tables": [asdict(t) for t in self.tables],
        }


@dataclass
class CSRDocument:
    filename: str
    total_pages: int
    sections: List[CSRSection] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "filename": self.filename,
            "total_pages": self.total_pages,
            "section_count": len(self.sections),
            "total_tables": sum(len(s.tables) for s in self.sections),
            "sections": [s.to_dict() for s in self.sections],
            "errors": self.errors,
        }


class CSRParser:
    WRITEUP_PATTERNS = [
        r'Table\s+\d+[\.:]\s*(?:presents|shows|displays|summarizes|provides|lists)',
        r'(?:Overall|The following|The table\s+\d+)',
        r'(?:Treatment-emergent|Treatment emergent|TEAE)',
        r'(?:Adverse events?|AEs?|SAEs?)\s+(?:were|are|occurred)',
        r'(?:All|Most|Nearly all)\s+subjects',
        r'(?:A total of|Of the|Among)',
        r'(?:No|There were no)',
    ]
    _WRITEUP_RE = re.compile(
        '(' + '|'.join(WRITEUP_PATTERNS) + ')',
        re.IGNORECASE
    )

    TABLE_TITLE_PATTERN = re.compile(
        r'(?:Table|Figure)\s+(\d+(?:\.\d+)*)[\.:]\s*([^\n]{5,120})',
        re.IGNORECASE
    )

    SECTION_INTRO_PATTERN = re.compile(
        r'^\s*(?:Introduction|Overview|Summary|Analysis|Results|Evaluation)\s',
        re.IGNORECASE
    )

    def __init__(self, pdf_path: str, use_gpu_ocr: bool = False):
        self.pdf_path = Path(pdf_path)
        self.use_gpu_ocr = use_gpu_ocr
        self.document = CSRDocument(
            filename=self.pdf_path.name,
            total_pages=0,
        )
        self._all_narratives: Dict[int, str] = {}
        self._table_references: Dict[str, int] = {}
        self._seen_table_hashes: Set[str] = set()

    def parse(self) -> CSRDocument:
        detector = CSRSectionDetector()
        boundaries = detector.detect(str(self.pdf_path))
        try:
            import pdfplumber
            with pdfplumber.open(str(self.pdf_path)) as pdf:
                self.document.total_pages = len(pdf.pages)
                self._build_narrative_index(pdf)
                for boundary in boundaries:
                    section = self._extract_section(pdf, boundary)
                    if section.tables or section.narrative_text:
                        self.document.sections.append(section)
        except Exception as e:
            logger.warning(f"pdfplumber failed, trying scanned fallback: {e}")
            self._fallback_scanned(boundaries)
        logger.info(
            f"CSR parse complete: {len(self.document.sections)} sections, "
            f"{sum(len(s.tables) for s in self.document.sections)} tables"
        )
        return self.document

    def _build_narrative_index(self, pdf):
        for i, page in enumerate(pdf.pages):
            text = page.extract_text(x_tolerance=3, y_tolerance=3) or ""
            self._all_narratives[i + 1] = text

    def _extract_section(self, pdf, boundary) -> CSRSection:
        start = boundary.start_page
        end = min(boundary.end_page or start, len(pdf.pages))
        section_pages = list(range(start, end + 1))
        section_narrative_parts = []
        tables: List[CSRTable] = []
        table_idx = 0
        for page_num in section_pages:
            if page_num <= 0 or page_num > len(pdf.pages):
                continue
            page = pdf.pages[page_num - 1]
            page_text = page.extract_text(x_tolerance=3, y_tolerance=3) or ""
            section_narrative_parts.append(page_text)
            raw_tables = page.extract_tables() or []
            for t_idx, raw_table in enumerate(raw_tables):
                if not raw_table or len(raw_table) < 2:
                    continue
                table_hash = self._hash_table(raw_table)
                if not table_hash or table_hash in self._seen_table_hashes:
                    logger.debug(f"Skipping duplicate table on page {page_num}")
                    continue
                self._seen_table_hashes.add(table_hash)
                table_idx += 1
                title = self._find_table_title(page_text, t_idx)
                linearized = self._linearize_table(raw_table, title)
                table_type = self._classify_table(linearized)
                surrounding = self._find_writeup_for_table(
                    page_text, linearized, page_num
                )
                tables.append(CSRTable(
                    table_id=f"t{table_idx}_p{page_num}",
                    linearized=linearized,
                    page=page_num,
                    table_type=table_type,
                    title=title,
                    source_page_start=page_num,
                    source_page_end=page_num,
                    surrounding_text=surrounding,
                ))
        narrative_text = " ".join(
            t for t in section_narrative_parts if t.strip()
        )
        return CSRSection(
            section_number=boundary.section_number,
            title=boundary.title,
            canonical_title=boundary.canonical_title,
            start_page=start,
            end_page=end,
            level=boundary.level,
            narrative_text=self._clean_narrative(narrative_text),
            tables=tables,
        )

    @staticmethod
    def _hash_table(raw_table) -> str:
        """Create a deterministic content hash for a raw table to deduplicate repeats."""
        if not raw_table:
            return ""
        normalized = []
        for row in raw_table:
            if not any(c for c in row):
                continue
            cells = [str(c or "").strip().lower() for c in row]
            normalized.append("|".join(cells))
        return hashlib.sha256("\n".join(normalized).encode("utf-8")).hexdigest()[:32]

    def _find_table_title(self, page_text: str, table_idx: int) -> str:
        matches = self.TABLE_TITLE_PATTERN.findall(page_text)
        if matches and table_idx < len(matches):
            num, title = matches[table_idx]
            return f"Table {num}: {title.strip()}"
        return ""

    def _linearize_table(self, raw_table, title: str = "") -> str:
        if not raw_table:
            return ""
        title_str = title or "Clinical Safety Table"
        parts = [f"start_table [TABLE_TITLE: {title_str}]"]
        headers = [str(c or "").strip() for c in raw_table[0]]
        parts.append(f"[HEADERS: | {' | '.join(headers)}]")
        for row in raw_table[1:]:
            if not any(c for c in row):
                continue
            cells = [str(c or "").strip() for c in row]
            parts.append(f"[ROW] {' | '.join(cells)}")
        parts.append("end_table")
        return " ".join(parts)

    def _find_writeup_for_table(
        self, page_text: str, linearized: str, page_num: int
    ) -> str:
        for pattern_str in self.WRITEUP_PATTERNS:
            m = re.search(
                pattern_str + r'.{50,1200}?(?=\n\n|\Z)',
                page_text,
                re.IGNORECASE | re.DOTALL
            )
            if m:
                candidate = m.group(0).strip()
                if re.search(r'\d', candidate):
                    return candidate
        for np in range(page_num + 1, page_num + 4):
            next_text = self._all_narratives.get(np, "")
            if next_text:
                for pattern_str in self.WRITEUP_PATTERNS:
                    m = re.search(
                        pattern_str + r'.{50,800}?(?=\n\n|\Z)',
                        next_text,
                        re.IGNORECASE | re.DOTALL
                    )
                    if m and re.search(r'\d', m.group(0)):
                        return m.group(0).strip()
        return ""

    @staticmethod
    def _remove_scattered_chars(text: str) -> str:
        """Remove scattered single-character artifacts from pdfplumber extraction."""
        text = re.sub(r'^[a-zA-Z]{1,3}\n', '', text, flags=re.MULTILINE)
        text = re.sub(r'\s[a-z]{1,2}\n', '\n', text)
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text

    def _clean_narrative(self, text: str) -> str:
        text = self._remove_scattered_chars(text)
        text = re.sub(r'\s{2,}', ' ', text)
        text = re.sub(r'Page\s+\d+\s+of\s+\d+', '', text, flags=re.IGNORECASE)
        return text.strip()

    TABLE_CLASSIFIERS = {
        "disposition": ["disposition", "withdrawn", "completed", "screened", "enrolled", "randomized"],
        "demographics": ["demographic", "age", "sex", "gender", "race", "ethnicity", "baseline characteristic"],
        "exposure": ["exposure", "duration of exposure", "dose intensity", "cumulative dose"],
        "efficacy": ["efficacy", "response rate", "objective response", "orr", "cr", "pr", "sd", "pd",
                     "progression-free", "pfs", "overall survival", "os", "time to response", "duration of response"],
        "adverse_event": ["teae", "sae", "adverse event", "ae", "treatment emergent", "serious adverse"],
        "laboratory": ["laboratory", "haematology", "hematology", "chemistry", "liver function", "renal function"],
        "vital_signs": ["vital sign", "blood pressure", "heart rate", "temperature", "respiratory rate", "ecg", "electrocardiogram"],
        "concomitant": ["concomitant", "prior medication", "medication history"],
        "pharmacokinetics": ["pharmacokinetic", "pk", "concentration", "auc", "cmax", "tmax", "half-life"],
        "other": [],
    }

    def _classify_table(self, linearized: str) -> str:
        """Classify table by content type using title, headers, and cell text."""
        text = linearized.lower()
        scores = {}
        for table_type, keywords in self.TABLE_CLASSIFIERS.items():
            if table_type == "other":
                continue
            scores[table_type] = sum(1 for kw in keywords if kw in text)
        if scores:
            best = max(scores, key=scores.get)
            if scores[best] > 0:
                return best
        return "other"

    def _fallback_scanned(self, boundaries):
        try:
            import fitz
            doc = fitz.open(str(self.pdf_path))
            self.document.total_pages = len(doc)
            for boundary in boundaries:
                start = boundary.start_page
                end = min(boundary.end_page or start, len(doc))
                section_pages = list(range(start, end + 1))
                section_tables = []
                for page_num in section_pages:
                    if page_num < 1 or page_num > len(doc):
                        continue
                    page = doc[page_num - 1]
                    mat = fitz.Matrix(200 / 72, 200 / 72)
                    pix = page.get_pixmap(matrix=mat, alpha=False)
                    img_bytes = pix.tobytes("png")
                    try:
                        from src.data_processing.image_extractor import ClinicalImageExtractor
                        img_extractor = ClinicalImageExtractor(use_gpu=self.use_gpu_ocr)
                        result = img_extractor.extract_from_bytes(img_bytes)
                        scan_idx = 0
                        for table in result.tables:
                            if table.n_rows >= 2:
                                table_hash = self._hash_table(table.json_data or [])
                                if not table_hash or table_hash in self._seen_table_hashes:
                                    continue
                                self._seen_table_hashes.add(table_hash)
                                scan_idx += 1
                                section_tables.append(CSRTable(
                                    table_id=f"scan_t{scan_idx}_p{page_num}",
                                    linearized=table.linearized,
                                    html=table.html,
                                    json_data=table.json_data,
                                    headers=table.headers,
                                    page=page_num,
                                    table_type=self._classify_table(table.linearized),
                                    source_page_start=page_num,
                                    source_page_end=page_num,
                                    surrounding_text="",
                                ))
                    except Exception as e:
                        logger.warning(f"Image extraction failed for page {page_num}: {e}")
                self.document.sections.append(CSRSection(
                    section_number=boundary.section_number,
                    title=boundary.title,
                    canonical_title=boundary.canonical_title,
                    start_page=start,
                    end_page=end,
                    level=boundary.level,
                    narrative_text="",
                    tables=section_tables,
                ))
            doc.close()
        except ImportError:
            self.document.errors.append("PyMuPDF not available for scanned PDF fallback")
        except Exception as e:
            self.document.errors.append(f"Scanned PDF fallback failed: {e}")
