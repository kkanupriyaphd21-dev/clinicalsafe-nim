"""
src/generation/provenance.py
Per-fact provenance: trace every numeric fact in the generated narrative
back to the source table cell it came from.
"""
import re
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional, Tuple


HEADER_N_PATTERN = re.compile(r'N\s*=\s*(\d+)', re.IGNORECASE)
CELL_N_PCT = re.compile(r'^\s*(\d+)\s*\(\s*(\d+\.?\d*)\s*%?\s*\)')
CELL_N_PCT_ALT = re.compile(r'^\s*(\d+)\s+(\d+\.?\d*)\s*%')
CELL_PCT = re.compile(r'^\s*(\d+\.?\d*)\s*%')
CELL_BARE = re.compile(r'^\s*(\d+)\s*$')
CELL_DECIMAL = re.compile(r'^\s*(\d+\.?\d*)\s*$')
NUM_REGEX = re.compile(r'\b(\d+\.?\d*)\b')


@dataclass
class FactTrace:
    value: str
    value_type: str
    char_offset_start: int
    char_offset_end: int
    source_row_idx: Optional[int]
    source_col: Optional[str]
    source_label: Optional[str]
    source_value_repr: Optional[str]
    status: str
    confidence: float

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class _SourceCell:
    row_idx: int
    col: str
    label: str
    raw: str
    n_value: Optional[int] = None
    pct_value: Optional[float] = None


class ProvenanceExtractor:
    def __init__(self, tolerance: float = 0.5):
        self.tolerance = tolerance

    def extract(self, narrative: str, source_table_text: str) -> List[FactTrace]:
        if not narrative or not source_table_text:
            return []

        source_cells = self._parse_source(source_table_text)
        facts: List[FactTrace] = []
        seen_offsets = set()

        for m in NUM_REGEX.finditer(narrative):
            num_str = m.group(1)
            if (m.start(), m.end()) in seen_offsets:
                continue
            seen_offsets.add((m.start(), m.end()))
            try:
                num = float(num_str)
            except ValueError:
                continue

            trace = self._trace_number(num, num_str, m.start(), m.end(), source_cells)
            facts.append(trace)

        return facts

    def _trace_number(
        self,
        num: float,
        num_str: str,
        start: int,
        end: int,
        source_cells: List[_SourceCell],
    ) -> FactTrace:
        value_type = "integer" if num == int(num) else "decimal"

        best: Optional[Tuple[float, _SourceCell]] = None
        for cell in source_cells:
            if cell.n_value is not None and abs(num - cell.n_value) < self.tolerance:
                conf = 1.0 if num == cell.n_value else 0.9
                if best is None or conf > best[0]:
                    best = (conf, cell)
            elif cell.pct_value is not None and abs(num - cell.pct_value) < self.tolerance:
                conf = 1.0 if num == cell.pct_value else 0.9
                if best is None or conf > best[0]:
                    best = (conf, cell)

        if best is not None:
            confidence, cell = best
            return FactTrace(
                value=num_str,
                value_type=value_type,
                char_offset_start=start,
                char_offset_end=end,
                source_row_idx=cell.row_idx,
                source_col=cell.col,
                source_label=cell.label,
                source_value_repr=cell.raw,
                status="verified",
                confidence=confidence,
            )

        return FactTrace(
            value=num_str,
            value_type=value_type,
            char_offset_start=start,
            char_offset_end=end,
            source_row_idx=None,
            source_col=None,
            source_label=None,
            source_value_repr=None,
            status="unverified",
            confidence=0.0,
        )

    def _parse_source(self, text: str) -> List[_SourceCell]:
        cells: List[_SourceCell] = []

        header_match = re.search(r'\[HEADERS:(.*?)\]', text, re.DOTALL)
        if header_match:
            header_parts = [p.strip() for p in header_match.group(1).split('|') if p.strip()]
            n_a = n_b = None
            for part in header_parts:
                m = HEADER_N_PATTERN.search(part)
                if not m:
                    continue
                n = int(m.group(1))
                if n_a is None:
                    n_a = n
                else:
                    n_b = n
            if n_a is not None:
                cells.append(_SourceCell(
                    row_idx=-1, col="header_n_a", label="Arm A N",
                    raw=f"N={n_a}", n_value=n_a, pct_value=None,
                ))
            if n_b is not None:
                cells.append(_SourceCell(
                    row_idx=-1, col="header_n_b", label="Arm B N",
                    raw=f"N={n_b}", n_value=n_b, pct_value=None,
                ))

        raw_rows = re.findall(r'\[ROW\](.*?)(?=\[ROW\]|end_table)', text, re.DOTALL)
        for i, raw in enumerate(raw_rows):
            parts = [p.strip() for p in raw.split('|')]
            if len(parts) < 2:
                continue
            label = parts[0]
            values = parts[1:]

            for col_idx, value_text in enumerate(values[:2]):
                col_name = "arm_a" if col_idx == 0 else "arm_b"
                n_val, pct_val = self._parse_cell(value_text)
                cells.append(_SourceCell(
                    row_idx=i, col=col_name, label=label,
                    raw=value_text, n_value=n_val, pct_value=pct_val,
                ))

        return cells

    @staticmethod
    def _parse_cell(text: str) -> Tuple[Optional[int], Optional[float]]:
        text = text.replace('|', ' ').strip()
        m = CELL_N_PCT.match(text)
        if m:
            return int(m.group(1)), float(m.group(2))
        m = CELL_N_PCT_ALT.match(text)
        if m:
            return int(m.group(1)), float(m.group(2))
        m = CELL_PCT.match(text)
        if m:
            return None, float(m.group(1))
        m = CELL_BARE.match(text)
        if m:
            return int(m.group(1)), None
        m = CELL_DECIMAL.match(text)
        if m:
            return None, float(m.group(1))
        return None, None


def extract_facts(narrative: str, source_table_text: str) -> List[Dict]:
    extractor = ProvenanceExtractor()
    return [t.to_dict() for t in extractor.extract(narrative, source_table_text)]
