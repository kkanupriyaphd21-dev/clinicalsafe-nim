"""
src/services/csr_ich_e3_mapper.py

ICH E3 section mapping for CSR tables.
Maps extracted table types to the correct ICH E3 section numbers and titles
per the guideline for Structure and Content of Clinical Study Reports.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class ICHSectionDefinition:
    section_number: str
    title: str
    description: str
    table_types: List[str] = field(default_factory=list)


# Mapping requested in production guidelines.
# Table type -> ICH E3 section.
ICH_E3_TABLE_TYPE_MAP: Dict[str, str] = {
    "disposition": "11.1",
    "demographics": "11.1",
    "exposure": "12.1",
    "efficacy": "11.4",
    "adverse_event": "12.2",
    "laboratory": "12.3",
    "vital_signs": "12.4",
    "concomitant": "12.1",
    "pharmacokinetics": "11.4",
    "other": "14.0",
}

ICH_E3_SECTIONS: Dict[str, ICHSectionDefinition] = {
    "11.1": ICHSectionDefinition(
        section_number="11.1",
        title="Study Patients",
        description="Disposition, demographics, and baseline characteristics.",
        table_types=["disposition", "demographics"],
    ),
    "11.4": ICHSectionDefinition(
        section_number="11.4",
        title="Efficacy Results",
        description="Primary and secondary efficacy endpoint results.",
        table_types=["efficacy", "pharmacokinetics"],
    ),
    "12.1": ICHSectionDefinition(
        section_number="12.1",
        title="Extent of Exposure",
        description="Treatment duration, dose intensity, and compliance.",
        table_types=["exposure", "concomitant"],
    ),
    "12.2": ICHSectionDefinition(
        section_number="12.2",
        title="Deaths, Other SAEs, and Other Significant Adverse Events",
        description="Treatment-emergent adverse events and serious adverse events.",
        table_types=["adverse_event"],
    ),
    "12.3": ICHSectionDefinition(
        section_number="12.3",
        title="Clinical Laboratory Evaluation",
        description="Laboratory safety parameters.",
        table_types=["laboratory"],
    ),
    "12.4": ICHSectionDefinition(
        section_number="12.4",
        title="Vital Signs, Physical Findings and Other Observations Related to Safety",
        description="Vital signs, ECG, and physical findings.",
        table_types=["vital_signs"],
    ),
    "14.0": ICHSectionDefinition(
        section_number="14.0",
        title="Additional Analyses",
        description="Tables not otherwise classified.",
        table_types=["other"],
    ),
}


def get_ich_section_for_table_type(table_type: str) -> ICHSectionDefinition:
    """Return the ICH E3 section definition for a given table type."""
    sec_num = ICH_E3_TABLE_TYPE_MAP.get(table_type, "14.0")
    return ICH_E3_SECTIONS.get(sec_num, ICH_E3_SECTIONS["14.0"])


def get_all_ich_section_numbers() -> List[str]:
    """Return canonical ICH section numbers in order."""
    return ["11.1", "11.4", "12.1", "12.2", "12.3", "12.4", "14.0"]
