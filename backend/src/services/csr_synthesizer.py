"""
src/services/csr_synthesizer.py

Parallel NIM-based CSR summarization.
Processes all tables in a CSR document concurrently through NVIDIA NIM,
then groups them by ICH E3 section and synthesises regulatory-grade prose.
"""
import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional, Any, Tuple

from sqlalchemy.orm import Session

from src.data_processing.csr_parser import CSRTable, CSRSection, CSRDocument
from src.generation.nim_generator import NIMGenerator
from src.services.csr_consistency import CSRConsistencyGuardian
from src.services.csr_ich_e3_mapper import get_ich_section_for_table_type, get_all_ich_section_numbers

logger = logging.getLogger(__name__)


class TableSummaryResult:
    __slots__ = (
        "table_id", "table_text", "summary", "verified",
        "numeric_accuracy", "table_type", "page", "title",
        "inference_time_ms", "warnings", "extracted_facts", "error",
        "ich_section_number", "ich_section_title",
    )

    def __init__(
        self,
        table_id: str = "",
        table_text: str = "",
        summary: str = "",
        verified: bool = False,
        numeric_accuracy: float = 0.0,
        table_type: str = "unknown",
        page: int = 0,
        title: str = "",
        inference_time_ms: float = 0.0,
        warnings: Optional[List[str]] = None,
        extracted_facts: Optional[List[Dict]] = None,
        error: Optional[str] = None,
        ich_section_number: str = "",
        ich_section_title: str = "",
    ):
        self.table_id = table_id
        self.table_text = table_text
        self.summary = summary
        self.verified = verified
        self.numeric_accuracy = numeric_accuracy
        self.table_type = table_type
        self.page = page
        self.title = title
        self.inference_time_ms = inference_time_ms
        self.warnings = warnings or []
        self.extracted_facts = extracted_facts or []
        self.error = error
        self.ich_section_number = ich_section_number
        self.ich_section_title = ich_section_title

    def to_dict(self) -> Dict:
        return {
            "table_id": self.table_id,
            "table_text": self.table_text,
            "summary": self.summary,
            "verified": self.verified,
            "numeric_accuracy": self.numeric_accuracy,
            "table_type": self.table_type,
            "page": self.page,
            "title": self.title,
            "inference_time_ms": self.inference_time_ms,
            "warnings": self.warnings,
            "extracted_facts": self._deduplicated_facts(),
            "error": self.error,
            "ich_section_number": self.ich_section_number,
            "ich_section_title": self.ich_section_title,
        }

    def _deduplicated_facts(self) -> List[Dict]:
        """Deduplicate extracted facts by (value, row, source cell) composite key."""
        seen = set()
        out = []
        for f in self.extracted_facts:
            key = (
                str(f.get("value", "")),
                str(f.get("source_row_idx", "")),
                str(f.get("source_col", "")),
                str(f.get("source_value_repr", "")),
            )
            if key in seen:
                continue
            seen.add(key)
            out.append(f)
        return out


class SectionSummaryResult:
    __slots__ = (
        "section_number", "title", "canonical_title",
        "start_page", "end_page", "level",
        "table_summaries", "section_synthesis", "key_findings", "tables_found",
        "verified_count", "accuracy",
    )

    def __init__(
        self,
        section_number: str = "",
        title: str = "",
        canonical_title: str = "",
        start_page: int = 0,
        end_page: int = 0,
        level: int = 1,
        table_summaries: Optional[List[TableSummaryResult]] = None,
        section_synthesis: str = "",
        key_findings: Optional[List[str]] = None,
        tables_found: int = 0,
        verified_count: int = 0,
        accuracy: float = 0.0,
    ):
        self.section_number = section_number
        self.title = title
        self.canonical_title = canonical_title
        self.start_page = start_page
        self.end_page = end_page
        self.level = level
        self.table_summaries = table_summaries or []
        self.section_synthesis = section_synthesis
        self.key_findings = key_findings or []
        self.tables_found = tables_found
        self.verified_count = verified_count
        self.accuracy = accuracy

    def to_dict(self) -> Dict:
        return {
            "section_number": self.section_number,
            "title": self.title,
            "canonical_title": self.canonical_title,
            "start_page": self.start_page,
            "end_page": self.end_page,
            "level": self.level,
            "table_summaries": [t.to_dict() for t in self.table_summaries],
            "section_synthesis": self.section_synthesis,
            "key_findings": self.key_findings,
            "tables_found": self.tables_found,
            "verified_count": self.verified_count,
            "accuracy": round(self.accuracy, 4),
        }


class CSRSummaryResult:
    def __init__(
        self,
        filename: str = "",
        total_pages: int = 0,
        sections: Optional[List[SectionSummaryResult]] = None,
        document_synthesis: str = "",
        total_tables: int = 0,
        verified_tables: int = 0,
        overall_numeric_accuracy: float = 0.0,
        total_inference_time_ms: float = 0.0,
        consistency_warnings: Optional[List[Dict]] = None,
        errors: Optional[List[str]] = None,
    ):
        self.filename = filename
        self.total_pages = total_pages
        self.sections = sections or []
        self.document_synthesis = document_synthesis
        self.total_tables = total_tables
        self.verified_tables = verified_tables
        self.overall_numeric_accuracy = overall_numeric_accuracy
        self.total_inference_time_ms = total_inference_time_ms
        self.consistency_warnings = consistency_warnings or []
        self.errors = errors or []

    def to_dict(self) -> Dict:
        return {
            "filename": self.filename,
            "total_pages": self.total_pages,
            "sections": [s.to_dict() for s in self.sections],
            "document_synthesis": self.document_synthesis,
            "total_tables": self.total_tables,
            "verified_tables": self.verified_tables,
            "overall_numeric_accuracy": self.overall_numeric_accuracy,
            "total_inference_time_ms": self.total_inference_time_ms,
            "consistency_warnings": self.consistency_warnings,
            "errors": self.errors,
        }


class CSRNIMSynthesizer:
    def __init__(
        self,
        db: Optional[Session] = None,
        session_factory = None,
        model: Optional[str] = None,
        max_workers: int = 5,
        max_tokens: int = 1024,
        temperature: float = 0.0,
        study_metadata: Optional[Dict[str, Any]] = None,
    ):
        self.db = db
        self.model = model
        self.max_workers = max_workers
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.study_metadata = study_metadata or {}
        self._guardian = CSRConsistencyGuardian()
        
        # Setup session_factory for thread safety
        if session_factory is None:
            from src.models.database import SessionLocal
            self.session_factory = SessionLocal
        else:
            self.session_factory = session_factory

    def summarize_table(self, table: CSRTable) -> TableSummaryResult:
        start = time.time()
        if not table.linearized:
            return TableSummaryResult(
                table_id=table.table_id,
                table_type=table.table_type,
                page=table.page,
                title=table.title,
                warnings=["Empty table text"],
            )

        ich = get_ich_section_for_table_type(table.table_type)
        statistical_method = self._statistical_method_for_table(table)
        last_exc = None
        for attempt in range(3):
            db = None
            try:
                # Thread-safe session creation
                if self.session_factory:
                    db = self.session_factory()
                else:
                    db = self.db

                gen = NIMGenerator(db, model=self.model)
                result = gen.generate(
                    table_text=table.linearized,
                    table_type=table.table_type,
                    max_tokens=self.max_tokens,
                    temperature=self.temperature,
                    timeout_sec=300,
                    statistical_method=statistical_method,
                )
                facts = result.get("extracted_facts", [])
                facts_dicts = [f if isinstance(f, dict) else {} for f in facts]
                elapsed = round((time.time() - start) * 1000, 2)
                return TableSummaryResult(
                    table_id=table.table_id,
                    table_text=table.linearized,
                    summary=result.get("summary", ""),
                    verified=result.get("verified", False),
                    numeric_accuracy=result.get("numeric_accuracy", 0.0),
                    table_type=table.table_type,
                    page=table.page,
                    title=table.title,
                    inference_time_ms=elapsed,
                    warnings=result.get("warnings", []),
                    extracted_facts=facts_dicts,
                    ich_section_number=ich.section_number,
                    ich_section_title=ich.title,
                )
            except Exception as e:
                last_exc = e
                logger.warning(f"NIM summarization attempt {attempt+1}/3 failed for {table.table_id}: {e}")
                if attempt < 2:
                    time.sleep(5)
            finally:
                if self.session_factory and db:
                    db.close()
        elapsed = round((time.time() - start) * 1000, 2)
        logger.error(f"NIM summarization failed after 3 attempts for {table.table_id}: {last_exc}")
        return TableSummaryResult(
            table_id=table.table_id,
            table_text=table.linearized,
            table_type=table.table_type,
            page=table.page,
            title=table.title,
            inference_time_ms=elapsed,
            warnings=[f"NIM generation failed: {last_exc}"],
            error=str(last_exc),
            ich_section_number=ich.section_number,
            ich_section_title=ich.title,
        )

    def _process_tables_parallel(
        self,
        tables: List[CSRTable],
        completed_offset: int = 0,
        total_all: int = 0,
        progress_callback = None,
    ) -> List[TableSummaryResult]:
        if not tables:
            return []
        results: List[Optional[TableSummaryResult]] = [None] * len(tables)
        with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            future_map = {
                pool.submit(self.summarize_table, t): i
                for i, t in enumerate(tables)
            }
            for future in as_completed(future_map):
                idx = future_map[future]
                try:
                    results[idx] = future.result()
                except Exception as e:
                    results[idx] = TableSummaryResult(
                        table_id=tables[idx].table_id,
                        error=str(e),
                    )
                if progress_callback:
                    done = completed_offset + sum(1 for r in results if r is not None and (r.summary or r.error))
                    tbl = tables[idx]
                    label = tbl.title or tbl.table_type or f"page {tbl.page}"
                    progress_callback("summarizing", done, total_all, f"Table {done}/{total_all}: {label}")
        return [r for r in results if r is not None]

    def _statistical_method_for_table(self, table: CSRTable) -> Optional[str]:
        """Return the statistical method for this table type from study metadata."""
        methods = self.study_metadata.get("statistical_methods", {})
        if table.table_type == "efficacy":
            return methods.get("primary_efficacy") or methods.get("efficacy")
        if table.table_type in ("adverse_event", "laboratory", "vital_signs"):
            return methods.get("safety")
        return methods.get(table.table_type)

    def _deduplicate_sentences(self, sentences: List[str]) -> List[str]:
        """Remove near-duplicate sentences ignoring whitespace/case."""
        seen = set()
        out = []
        for s in sentences:
            key = re.sub(r"\s+", " ", s.lower().strip()).strip(".!")
            if not key or key in seen:
                continue
            seen.add(key)
            out.append(s)
        return out

    def _synthesise_section_prose(
        self,
        section_number: str,
        section_title: str,
        table_results: List[TableSummaryResult],
    ) -> str:
        """Create a cross-table synthesis as a single prose paragraph.

        The synthesis must add framing context and interpretation that is NOT
        already present in the per-table summaries, especially for single-table
        sections. Production latency is kept low by using deterministic rules.
        """
        if not table_results:
            return ""

        summaries = [tr.summary for tr in table_results if tr.summary]
        if not summaries:
            return ""

        # Build a population framing clause from the first table's type.
        populations = [tr.table_type for tr in table_results]
        from src.generation.nim_generator import POPULATION_BY_TABLE_TYPE
        population = POPULATION_BY_TABLE_TYPE.get(populations[0], "study population")
        if len(set(populations)) == 1:
            framing = f"In the {population}, {section_title.lower()} are summarised as follows. "
        else:
            framing = f"This section presents {section_title.lower()} findings across the relevant analysis populations. "

        if len(summaries) == 1:
            # For a single table, extract key quantitative claims and add interpretation.
            summary = summaries[0]
            key_facts = self._extract_key_quantitative_facts(summary)
            if key_facts:
                interpretation = (
                    f"The most salient finding is {key_facts[0]}. "
                    f"Overall, these data support the {section_title.lower()} profile of the investigational product."
                )
            else:
                interpretation = f"Overall, these data characterise the {section_title.lower()} profile observed in this study."
            return framing + summary + " " + interpretation

        # Multi-table: integrate unique sentences then add a closing interpretation.
        all_sentences: List[str] = []
        for s in summaries:
            all_sentences.extend(re.split(r"(?<=[.!?])\s+", s.strip()))
        unique = self._deduplicate_sentences(all_sentences)
        if not unique:
            body = " ".join(summaries)
        else:
            body = " ".join(unique)

        closing = (
            f"Taken together, the {len(summaries)} source tables describe a coherent "
            f"{section_title.lower()} profile for the {population}."
        )
        return framing + body + " " + closing

    def _extract_key_quantitative_facts(self, summary: str) -> List[str]:
        """Pull out the sentence containing the strongest quantitative claim."""
        if not summary:
            return []
        candidates = []
        for sent in re.split(r"(?<=[.!?])\s+", summary):
            score = 0
            if re.search(r"p\s*[<]\s*0\.\d+", sent, re.IGNORECASE):
                score += 3
            if re.search(r"\bor\s*=\s*\d+\.\d+", sent, re.IGNORECASE):
                score += 2
            if re.search(r"\d+\.\d+%", sent):
                score += 1
            if score:
                candidates.append((score, sent.strip()))
        candidates.sort(key=lambda x: x[0], reverse=True)
        return [sent for _, sent in candidates[:2]]

    def synthesize_section(
        self,
        section_number: str,
        section_title: str,
        table_results: List[TableSummaryResult],
    ) -> SectionSummaryResult:
        if not table_results:
            return SectionSummaryResult(
                section_number=section_number,
                title=section_title,
                canonical_title=section_title,
            )

        verified_count = sum(1 for tr in table_results if tr.verified)
        total_accuracy = sum(tr.numeric_accuracy for tr in table_results if tr.verified)
        accuracy = total_accuracy / max(verified_count, 1)

        synthesis = self._synthesise_section_prose(section_number, section_title, table_results)
        key_findings = self._extract_key_findings(table_results)

        return SectionSummaryResult(
            section_number=section_number,
            title=section_title,
            canonical_title=section_title,
            table_summaries=table_results,
            section_synthesis=synthesis,
            key_findings=key_findings,
            tables_found=len(table_results),
            verified_count=verified_count,
            accuracy=accuracy,
        )

    def _extract_key_findings(
        self, table_results: List[TableSummaryResult]
    ) -> List[str]:
        findings = []
        for tr in table_results:
            if not tr.summary:
                continue
            key_signals = (
                r"(?:statistically significant|p\s*[<>=]\s*0\.05|p\s*<\s*0\.001|"
                r"high|elevated|notable|significant|clinically meaningful|"
                r"increased|decreased|worse|improved|difference)"
            )
            if re.search(key_signals, tr.summary, re.IGNORECASE):
                for sent in re.split(r"(?<=[.!])\s+", tr.summary):
                    if re.search(key_signals, sent, re.IGNORECASE):
                        findings.append(sent.strip())
                        if len(findings) >= 5:
                            break
            if len(findings) >= 5:
                break
        return findings

    def summarize_document(
        self,
        csr_document: CSRDocument,
        progress_callback = None,
    ) -> CSRSummaryResult:
        start_total = time.time()
        total_tables = 0
        verified_count = 0
        total_accuracy = 0.0

        total_tables_all = sum(len(s.tables) for s in csr_document.sections)
        completed_tables = 0

        if progress_callback:
            progress_callback("parsing", 0, total_tables_all, "Parsing PDF and detecting sections…")

        # Flatten all tables, deduplicate by ID, and process in parallel.
        all_tables: List[CSRTable] = []
        seen_ids = set()
        for section in csr_document.sections:
            for t in section.tables:
                if t.table_id not in seen_ids:
                    all_tables.append(t)
                    seen_ids.add(t.table_id)

        table_results = self._process_tables_parallel(
            all_tables,
            completed_tables,
            len(all_tables),
            progress_callback,
        )

        # Group results by ICH E3 section.
        ich_groups: Dict[str, List[TableSummaryResult]] = {sn: [] for sn in get_all_ich_section_numbers()}
        for tr in table_results:
            sn = tr.ich_section_number
            if sn not in ich_groups:
                sn = "14.0"
            ich_groups[sn].append(tr)

        sections: List[SectionSummaryResult] = []
        for sn in get_all_ich_section_numbers():
            group = ich_groups[sn]
            if not group:
                continue
            ich = get_ich_section_for_table_type(group[0].table_type)
            section_result = self.synthesize_section(sn, ich.title, group)
            sections.append(section_result)
            for tr in group:
                total_tables += 1
                if tr.verified:
                    verified_count += 1
                total_accuracy += tr.numeric_accuracy

        overall_accuracy = round(total_accuracy / max(total_tables, 1), 4)
        total_time = round((time.time() - start_total) * 1000, 2)

        if progress_callback:
            progress_callback("verifying", total_tables_all, total_tables_all, "Verifying numeric accuracy and cross-table consistency…")

        consistency_warnings = self._guardian.check_all(table_results)

        if progress_callback:
            progress_callback("synthesizing", 0, 0, "Generating document synthesis…")

        document_synthesis = self._generate_document_synthesis(
            sections, csr_document, consistency_warnings
        )

        if progress_callback:
            progress_callback("complete", total_tables_all, total_tables_all, "Done")

        return CSRSummaryResult(
            filename=csr_document.filename,
            total_pages=csr_document.total_pages,
            sections=sections,
            document_synthesis=document_synthesis,
            total_tables=total_tables,
            verified_tables=verified_count,
            overall_numeric_accuracy=overall_accuracy,
            total_inference_time_ms=total_time,
            consistency_warnings=consistency_warnings,
            errors=csr_document.errors,
        )

    def _generate_document_synthesis(
        self,
        sections: List[SectionSummaryResult],
        csr_document: CSRDocument,
        consistency_warnings: List[Dict],
    ) -> str:
        total_tables = sum(s.tables_found for s in sections)
        total_verified = sum(s.verified_count for s in sections)
        vpct = round(total_verified / max(total_tables, 1) * 100)

        parts = [
            f"This Clinical Study Report ({csr_document.filename}, {csr_document.total_pages} pages) "
            f"summarises {total_tables} table(s) across {len(sections)} ICH E3 section(s). "
            f"Per-table numeric verification was performed using the configured inference engine; "
            f"{total_verified}/{total_tables} table(s) ({vpct}%) met the ≥95% accuracy threshold."
        ]

        for s in sections:
            if s.section_synthesis:
                parts.append(f"\nSection {s.section_number} ({s.canonical_title}): {s.section_synthesis}")

        if consistency_warnings:
            parts.append(
                f"\nCross-table consistency review identified {len(consistency_warnings)} item(s) for medical writer review."
            )
        else:
            parts.append("\nCross-table consistency review identified no discrepancies.")

        return "\n".join(parts)
