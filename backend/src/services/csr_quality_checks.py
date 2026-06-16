"""
src/services/csr_quality_checks.py

Layer 1 automated pre-review checks for CSR narrative output.
Runs after generation and before human review. Produces structured
pass/fail/warning flags that can be embedded in DOCX comments or JSON.
"""
import hashlib
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


POPULATION_BY_TABLE_TYPE = {
    "demographics": "Full Analysis Set (FAS)",
    "disposition": "Full Analysis Set (FAS)",
    "efficacy": "Intent-to-Treat (ITT) population",
    "adverse_event": "Safety population",
    "laboratory": "Safety population",
    "vital_signs": "Safety population",
    "exposure": "Safety population",
    "concomitant": "Full Analysis Set (FAS)",
    "pharmacokinetics": "Pharmacokinetic analysis set",
    "other": "study population",
}

PROHIBITED_UNSUPPORTED_PHRASES = [
    "clinically significant",
    "clinically meaningful improvement",
    "no clinically meaningful difference",
    "no clinically significant difference",
]


@dataclass
class QualityFinding:
    check_id: str
    name: str
    description: str
    type: str  # "blocking" | "warning"
    status: str  # "PASS" | "FAIL" | "WARNING"
    message: str
    suggestion: str = ""
    source_table_id: str = ""
    source_section: str = ""
    flagged_text: str = ""


@dataclass
class QualityReport:
    document_id: str
    document_sha256: str
    findings: List[QualityFinding] = field(default_factory=list)
    passed_blocking: bool = True

    def to_dict(self) -> Dict:
        return {
            "document_id": self.document_id,
            "document_sha256": self.document_sha256,
            "passed_blocking": self.passed_blocking,
            "findings": [
                {
                    "check_id": f.check_id,
                    "name": f.name,
                    "description": f.description,
                    "type": f.type,
                    "status": f.status,
                    "message": f.message,
                    "suggestion": f.suggestion,
                    "source_table_id": f.source_table_id,
                    "source_section": f.source_section,
                    "flagged_text": f.flagged_text,
                }
                for f in self.findings
            ],
        }


def _normalise(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip()


def _extract_numbers(text: str) -> List[str]:
    """Return number strings as they appear."""
    return re.findall(r"\b\d+(?:\.\d+)?(?:\s*%)?", text)


def _expected_population(table_type: str) -> str:
    return POPULATION_BY_TABLE_TYPE.get(table_type, "study population")


def _population_check(table_result) -> Optional[QualityFinding]:
    """POP_001: table narrative must use the correct analysis population."""
    expected = _expected_population(table_result.table_type)
    summary = table_result.summary or ""
    summary_norm = _normalise(summary)

    # Map expected population to canonical lowercase tokens.
    population_tokens = {
        "safety population": ["safety population", "safety set", "safety analysis set"],
        "intent-to-treat (itt) population": ["itt population", "intent-to-treat", "intent to treat", "full analysis set"],
        "full analysis set (fas)": ["full analysis set", "fas", "intent-to-treat", "itt population"],
        "pharmacokinetic analysis set": ["pharmacokinetic analysis set", "pk analysis set", "pk population"],
        "study population": ["study population", "study participants", "subjects"],
    }
    allowed = population_tokens.get(_normalise(expected), [expected.lower()])

    # If summary already contains the expected population phrase, pass.
    if any(token in summary_norm for token in allowed):
        return None

    # If it contains a conflicting population phrase, fail.
    conflicting = {
        "adverse_event": ["itt population", "intent-to-treat", "intent to treat"],
        "efficacy": ["safety population", "safety set"],
    }
    for conflict in conflicting.get(table_result.table_type, []):
        if conflict in summary_norm:
            return QualityFinding(
                check_id="POP_001",
                name="Population name consistency",
                description="Table narrative must use the analysis population defined in the SAP for this table type.",
                type="blocking",
                status="FAIL",
                message=f"{table_result.table_type} table uses wrong population. Expected '{expected}', found conflicting phrase.",
                suggestion=f"Replace with '{expected}' in the narrative.",
                source_table_id=table_result.table_id,
                source_section=table_result.ich_section_number,
                flagged_text=summary[:200],
            )

    # Population not mentioned at all.
    return QualityFinding(
        check_id="POP_001",
        name="Population name consistency",
        description="Table narrative must use the analysis population defined in the SAP for this table type.",
        type="blocking",
        status="FAIL",
        message=f"{table_result.table_type} table narrative is missing the expected population '{expected}'.",
        suggestion=f"Add an explicit population qualifier: '{expected}'.",
        source_table_id=table_result.table_id,
        source_section=table_result.ich_section_number,
        flagged_text=summary[:200],
    )


def _prohibited_phrase_check(table_result) -> List[QualityFinding]:
    """LANG_001: scan for prohibited unsupported clinical phrases."""
    findings = []
    summary = table_result.summary or ""
    summary_norm = _normalise(summary)
    for phrase in PROHIBITED_UNSUPPORTED_PHRASES:
        if phrase in summary_norm:
            findings.append(
                QualityFinding(
                    check_id="LANG_001",
                    name="Prohibited phrase scan",
                    description="Flags clinical phrases that require supporting context (e.g., MCID) not present in the source table.",
                    type="warning",
                    status="WARNING",
                    message=f"Prohibited phrase '{phrase}' used without required supporting context.",
                    suggestion="Replace with 'statistically significant' or provide MCID justification.",
                    source_table_id=table_result.table_id,
                    source_section=table_result.ich_section_number,
                    flagged_text=phrase,
                )
            )
    return findings


def _statistical_language_check(table_result) -> List[QualityFinding]:
    """LANG_002: statistically significant must be accompanied by p-value in the same sentence."""
    findings = []
    summary = table_result.summary or ""
    sentences = re.split(r"(?<=[.!?])\s+", summary)
    for sent in sentences:
        sent_norm = _normalise(sent)
        if "statistically significant" in sent_norm and not re.search(r"p\s*[<>=]\s*0?\.\d+", sent_norm):
            findings.append(
                QualityFinding(
                    check_id="LANG_002",
                    name="Statistical language validator",
                    description="'Statistically significant' should be accompanied by a p-value in the same sentence.",
                    type="warning",
                    status="WARNING",
                    message="'statistically significant' used without a p-value in the same sentence.",
                    suggestion="Add the p-value immediately after the significant finding, e.g., '(p < 0.001)'.",
                    source_table_id=table_result.table_id,
                    source_section=table_result.ich_section_number,
                    flagged_text=sent.strip(),
                )
            )
    return findings


def _sd_labeling_check(table_result) -> List[QualityFinding]:
    """STY_001: continuous variable parentheticals should be labelled SD/SE/CI."""
    findings = []
    if table_result.table_type != "demographics":
        return findings
    summary = table_result.summary or ""
    # Pattern: number (number) without SD/SE/CI label.
    # Avoid matching n (%) counts.
    for match in re.finditer(r"\b(mean|median|age|bmi|weight|height)\s+\d+(?:\.\d+)?\s+\((?!SD\b|SE\b|95% CI|n=)[^)]*\d+(?:\.\d+)?[^)]*\)", summary, re.IGNORECASE):
        text = match.group(0)
        if "n (" in text or "n=" in text:
            continue
        findings.append(
            QualityFinding(
                check_id="STY_001",
                name="SD labeling check",
                description="Continuous variable parentheticals must be labelled (SD), (SE), or (95% CI).",
                type="warning",
                status="WARNING",
                message="Continuous variable reported with unlabelled dispersion measure.",
                suggestion="Label explicitly, e.g., '45.2 years (SD 11.3)' or '45.2 (SD: 11.3) years'.",
                source_table_id=table_result.table_id,
                source_section=table_result.ich_section_number,
                flagged_text=text,
            )
        )
    return findings


def _synthesis_duplication_check(section_result) -> Optional[QualityFinding]:
    """DUP_001: section synthesis must differ from per-table summary by >30% unique content."""
    synthesis = section_result.section_synthesis or ""
    if not synthesis:
        return None

    sentences = set()
    total_synth_sents = 0
    for sent in re.split(r"(?<=[.!?])\s+", synthesis):
        key = _normalise(sent)
        if key:
            sentences.add(key)
            total_synth_sents += 1

    duplicated = 0
    for tr in section_result.table_summaries:
        for sent in re.split(r"(?<=[.!?])\s+", tr.summary or ""):
            key = _normalise(sent)
            if key and key in sentences:
                duplicated += 1

    if total_synth_sents == 0:
        return None
    duplication_ratio = duplicated / total_synth_sents
    if duplication_ratio >= 0.7:
        return QualityFinding(
            check_id="DUP_001",
            name="Synthesis duplication check",
            description="Section synthesis must add framing/interpretation not present in the per-table summary.",
            type="warning",
            status="WARNING",
            message=f"Section synthesis is {int(duplication_ratio * 100)}% duplicated from per-table summary.",
            suggestion="Add population framing and clinical interpretation not in the per-table summary.",
            source_section=section_result.section_number,
            flagged_text=synthesis[:200],
        )
    return None


def _numerical_faithfulness_check(table_result) -> Optional[QualityFinding]:
    """NUM_001: every number in the narrative should match a value in the source table."""
    source = table_result.table_text or ""
    summary = table_result.summary or ""
    if not source or not summary:
        return None

    source_nums = set(_extract_numbers(source))
    summary_nums = _extract_numbers(summary)
    bad = [n for n in summary_nums if n not in source_nums]
    if not bad:
        return None

    return QualityFinding(
        check_id="NUM_001",
        name="Numerical faithfulness",
        description="Every number in the narrative must match a value in the source table.",
        type="blocking",
        status="FAIL",
        message=f"Numbers in narrative not found in source table: {bad[:5]}",
        suggestion="Verify these numbers against the source table and remove or correct them.",
        source_table_id=table_result.table_id,
        source_section=table_result.ich_section_number,
        flagged_text=str(bad[:5]),
    )


def _absence_claim_check(table_result) -> Optional[QualityFinding]:
    """HAL_001: sentences asserting absence of a category not present in the table."""
    source = table_result.table_text or ""
    summary = table_result.summary or ""
    source_lower = source.lower()

    absence_patterns = [
        (r"(?i)(?:there were|there was)\s+no\s+([a-z\s]+?)(?:\s+reported)?", "no {group}"),
        (r"(?i)no\s+([a-z\s]+?)\s+(?:were|was)\s+reported", "no {group} reported"),
        (r"(?i)no\s+fatal(?:ities| events)?\s+(?:were|was)\s+reported", "fatal"),
        (r"(?i)(?:there were|there was)\s+no\s+fatal(?:ities| events)?", "fatal"),
        (r"(?i)no\s+deaths\s+(?:were|was)\s+reported", "death"),
        (r"(?i)(?:there were|there was)\s+no\s+death", "death"),
    ]

    sentences = re.split(r"(?<=[.!?])\s+", summary)
    for sent in sentences:
        for pattern, concept in absence_patterns:
            m = re.search(pattern, sent)
            if not m:
                continue
            check = concept
            if "{group}" in check:
                check = m.group(1).strip().lower()
            if check and check not in source_lower:
                return QualityFinding(
                    check_id="HAL_001",
                    name="Absence claim detection",
                    description="Sentences asserting absence of a category are flagged when that row is absent from the source table.",
                    type="blocking",
                    status="FAIL",
                    message=f"Unsupported absence claim: '{sent.strip()}'",
                    suggestion="Remove the claim or verify the category exists in the source table.",
                    source_table_id=table_result.table_id,
                    source_section=table_result.ich_section_number,
                    flagged_text=sent.strip(),
                )
    return None


def run_quality_checks(summary_result, include_blocking: bool = True) -> QualityReport:
    """Run full Layer 1 pre-review check suite against a CSRSummaryResult."""
    findings: List[QualityFinding] = []
    doc_id = summary_result.filename.rsplit(".", 1)[0] if "." in summary_result.filename else summary_result.filename
    sha = hashlib.sha256(summary_result.document_synthesis.encode("utf-8")).hexdigest()

    for section in summary_result.sections:
        dup = _synthesis_duplication_check(section)
        if dup:
            findings.append(dup)

        for tr in section.table_summaries:
            if include_blocking:
                checks = [
                    _population_check(tr),
                    _numerical_faithfulness_check(tr),
                    _absence_claim_check(tr),
                ]
                for finding in checks:
                    if finding:
                        findings.append(finding)

            findings.extend(_prohibited_phrase_check(tr))
            findings.extend(_statistical_language_check(tr))
            findings.extend(_sd_labeling_check(tr))

    passed_blocking = not any(f.type == "blocking" and f.status == "FAIL" for f in findings)
    return QualityReport(
        document_id=doc_id,
        document_sha256=sha,
        findings=findings,
        passed_blocking=passed_blocking,
    )
