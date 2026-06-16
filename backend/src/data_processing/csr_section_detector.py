"""
src/data_processing/csr_section_detector.py

Detects ICH E3 section headers and boundaries in Clinical Study Report PDFs.
Uses pdfplumber text extraction and regex patterns to identify section
start pages and titles. Falls back to TOC page detection if available.
"""

import re
import logging
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# ICH E3 top-level section numbers and canonical titles
ICH_E3_SECTIONS: Dict[str, str] = {
    "1": "Synopsis",
    "2": "Introduction",
    "3": "Investigational Plan / Study Objectives",
    "4": "Study Patients / Patient Disposition",
    "5": "Efficacy Evaluation",
    "6": "Safety Evaluation",
    "7": "Discussion and Overall Conclusions",
    "8": "Tables, Figures, and Graphs",
    "9": "Appendices",
}

ICH_E3_SUBSECTIONS: Dict[str, str] = {
    "3.1": "Overall Study Design",
    "3.2": "Discussion of Study Design",
    "3.3": "Selection of Study Population",
    "3.4": "Treatments",
    "3.5": "Efficacy and Safety Variables",
    "3.6": "Data Quality Assurance",
    "3.7": "Statistical Methods",
    "3.8": "Changes in the Conduct of the Study",
    "4.1": "Disposition of Patients",
    "4.2": "Protocol Deviations",
    "4.3": "Demographic and Other Baseline Characteristics",
    "4.4": "Treatment Compliance",
    "5.1": "Data Sets Analyzed",
    "5.2": "Demographic and Baseline Characteristics",
    "5.3": "Measurements of Treatment Compliance",
    "5.4": "Efficacy Results and Tabulations",
    "6.1": "Extent of Exposure",
    "6.2": "Adverse Events",
    "6.3": "Deaths, Other SAEs, and Other Significant AEs",
    "6.4": "Clinical Laboratory Evaluation",
    "6.5": "Vital Signs, Physical Findings",
    "6.6": "ECG",
    "6.7": "Safety Conclusions",
}


@dataclass
class SectionBoundary:
    section_number: str
    title: str
    start_page: int
    end_page: Optional[int] = None
    subsection_of: Optional[str] = None
    toc_entry: Optional[str] = None

    @property
    def canonical_title(self) -> str:
        return ICH_E3_SECTIONS.get(self.section_number,
               ICH_E3_SUBSECTIONS.get(self.section_number,
               self.title))

    @property
    def level(self) -> int:
        dots = self.section_number.count(".")
        return 1 if dots == 0 else 2


class CSRSectionDetector:
    SECTION_HEADER_PATTERN = re.compile(
        r'^\s*(\d+(?:\.\d+)*)\s+[\.\s]*([A-Z][A-Za-z0-9\s\-,/()]+?)(?=\s*\.{2,}\s*\d+\s*$|\s*$|\.{2,}\s)',
        re.MULTILINE,
    )

    TOC_LINE_PATTERN = re.compile(
        r'^\s*(\d+(?:\.\d+)*)\s+(.+?)\.{2,}\s*(\d+)\s*$',
        re.MULTILINE,
    )

    BODY_SECTION_HEADER = re.compile(
        r'^\s*(\d+(?:\.\d+)*)\.?\s+([A-Z][A-Za-z0-9\s\-,/()]{3,80})\s*$',
        re.MULTILINE,
    )

    PAGE_NUMBER_PATTERN = re.compile(r'^\s*Page\s+(\d+)\s*$', re.IGNORECASE | re.MULTILINE)

    SCATTERED_CHAR_LINE = re.compile(r'^[a-zA-Z]{1,3}\n', re.MULTILINE)
    TRAILING_ARTIFACT = re.compile(r' [a-z]{1,2}$', re.MULTILINE)
    EMBEDDED_ARTIFACT = re.compile(r'[a-z]{1,3}\n', re.MULTILINE)

    def __init__(self):
        self.sections: List[SectionBoundary] = []

    @staticmethod
    def _clean_page_text(text: str) -> str:
        """Remove scattered single-char artifacts from PDF text extraction."""
        text = CSRSectionDetector.SCATTERED_CHAR_LINE.sub('', text)
        text = CSRSectionDetector.TRAILING_ARTIFACT.sub('', text)
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()

    def detect(self, pdf_path: str) -> List[SectionBoundary]:
        try:
            import pdfplumber
            with pdfplumber.open(pdf_path) as pdf:
                total_pages = len(pdf.pages)
                sections = self._try_toc_detection(pdf)
                if not sections:
                    sections = self._try_body_header_detection(pdf)
                if not sections:
                    sections = self._create_default_section(total_pages)
                self._resolve_end_pages(sections, total_pages)
                self.sections = sections
                logger.info(f"Detected {len(sections)} sections in {pdf_path}")
                for s in sections:
                    logger.debug(f"  Section {s.section_number}: {s.title} (pp. {s.start_page}-{s.end_page})")
                return sections
        except Exception as e:
            logger.error(f"Section detection failed: {e}")
            return self._create_default_section(self._guess_page_count(pdf_path))

    def _try_toc_detection(self, pdf) -> List[SectionBoundary]:
        toc_text = ""
        for i in range(min(5, len(pdf.pages))):
            page = pdf.pages[i]
            text = page.extract_text(x_tolerance=3, y_tolerance=3) or ""
            text = self._clean_page_text(text)
            toc_text += text + "\n---PAGE BREAK---\n"

        sections = []
        seen_numbers = set()
        for m in self.TOC_LINE_PATTERN.finditer(toc_text):
            sec_num = m.group(1).strip()
            title = self._clean_title(m.group(2).strip())
            page = int(m.group(3))
            if sec_num not in seen_numbers and len(title) >= 3:
                seen_numbers.add(sec_num)
                sections.append(SectionBoundary(
                    section_number=sec_num,
                    title=title,
                    start_page=page,
                    toc_entry=m.group(0).strip(),
                    subsection_of=sec_num.rsplit(".", 1)[0] if "." in sec_num else None,
                ))

        return sections

    def _try_body_header_detection(self, pdf) -> List[SectionBoundary]:
        sections = []
        seen_numbers = set()
        for i, page in enumerate(pdf.pages):
            text = page.extract_text(x_tolerance=3, y_tolerance=3) or ""
            text = self._clean_page_text(text)
            for m in self.BODY_SECTION_HEADER.finditer(text):
                sec_num = m.group(1)
                title = m.group(2).strip()
                title = self._clean_title(title)
                title = re.sub(r'\s+', ' ', title).strip()
                if sec_num not in seen_numbers and len(title) >= 3:
                    seen_numbers.add(sec_num)
                    sections.append(SectionBoundary(
                        section_number=sec_num,
                        title=title,
                        start_page=i + 1,
                        subsection_of=sec_num.rsplit(".", 1)[0] if "." in sec_num else None,
                    ))
        return sections

    @staticmethod
    def _clean_title(title: str) -> str:
        title = title.strip()
        title = re.sub(r'\s+', ' ', title)
        title = re.sub(r'\s+[a-z]\s+', ' ', title)
        title = re.sub(r'\s+[a-zA-Z]{1,3}$', '', title)
        title = re.sub(r'\s{2,}', ' ', title)
        if title.rstrip('.').strip() in ('', 'Table'):
            return title
        return title.strip()

    def _create_default_section(self, total_pages: int) -> List[SectionBoundary]:
        return [
            SectionBoundary(
                section_number=str(i),
                title=ICH_E3_SECTIONS.get(str(i), f"Section {i}"),
                start_page=1,
            )
            for i in range(1, 8)
        ]

    def _guess_page_count(self, pdf_path: str) -> int:
        try:
            import fitz
            doc = fitz.open(pdf_path)
            count = len(doc)
            doc.close()
            return count
        except Exception:
            return 0

    def _resolve_end_pages(self, sections: List[SectionBoundary], total_pages: int):
        sorted_secs = sorted(sections, key=lambda s: (s.start_page, s.section_number))
        for i in range(len(sorted_secs)):
            if i + 1 < len(sorted_secs):
                sorted_secs[i].end_page = sorted_secs[i + 1].start_page - 1
            else:
                sorted_secs[i].end_page = total_pages

    def get_top_level_sections(self) -> List[SectionBoundary]:
        return [s for s in self.sections if s.level == 1]

    def get_subsections(self, parent_number: str) -> List[SectionBoundary]:
        prefix = f"{parent_number}."
        return [s for s in self.sections if s.section_number.startswith(prefix)]

    def get_section_content_range(self, section: SectionBoundary) -> Tuple[int, int]:
        return section.start_page, section.end_page or section.start_page
