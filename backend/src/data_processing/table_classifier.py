"""
src/data_processing/table_classifier.py

Standalone ICH E3 table classifier.
Auto-classifies linearized tables into clinical section types using
keyword patterns, header analysis, and N-value detection.
"""

import re
from typing import List, Optional

ICH_E3_TABLE_TYPES = {
    "disposition": "Subject Disposition",
    "demographics": "Demographic and Baseline Characteristics",
    "exposure": "Extent of Exposure",
    "concomitant": "Concomitant Medications",
    "adverse_event": "Adverse Events",
    "deaths": "Deaths and Serious Adverse Events",
    "laboratory": "Laboratory Evaluation",
    "vital_signs": "Vital Signs and ECG",
    "efficacy": "Efficacy Evaluation",
    "pharmacokinetics": "Pharmacokinetic Results",
    "pk_parameters": "PK Parameter Summary",
    "immunogenicity": "Immunogenicity",
    "ecg": "ECG Evaluation",
    "study_design": "Study Design Summary",
    "protocol_deviation": "Protocol Deviations",
    "prior_medications": "Prior and Concomitant Medications",
    "dosing": "Dosing Administration",
    "compliance": "Treatment Compliance",
    "subgroup": "Subgroup Analysis",
    "sensitivity": "Sensitivity Analysis",
    "other": "Additional Analyses",
}

CLINICAL_TYPE_PATTERNS: List[tuple] = [
    ("adverse_event", [
        r"teae", r"sae", r"adverse event", r"treatment.emergent",
        r"serious adverse", r"drug.related", r"ae\b(?!\w)",
    ]),
    ("deaths", [
        r"death", r"fatal", r"mortality", r"cause of death",
    ]),
    ("disposition", [
        r"disposition", r"patient disposition", r"subject disposition",
        r"screen failure", r"enrolled", r"randomized", r"completed study",
        r"premature discontinu", r"withdrawn", r"reason for discontinu",
    ]),
    ("demographics", [
        r"demographic", r"baseline characteristic", r"age", r"sex",
        r"gender", r"race", r"ethnicity", r"bmi", r"weight",
        r"height", r"smoking", r"alcohol",
    ]),
    ("efficacy", [
        r"efficacy", r"response", r"survival", r"pfs", r"os",
        r"objective response", r"tumor", r"progression", r"remission",
        r"endpoint", r"overall survival", r"progression.free",
        r"duration of response", r"disease control",
    ]),
    ("exposure", [
        r"exposure", r"treatment exposure", r"duration of exposure",
        r"cumulative dose", r"dose intensity",
    ]),
    ("concomitant", [
        r"concomitant", r"prior medication", r"prior treatment",
        r"previous therapy",
    ]),
    ("laboratory", [
        r"laboratory", r"lab", r"haematology", r"hematology",
        r"clinical chemistry", r"urinalysis", r"liver function",
        r"renal function", r"blood count", r"coagulation",
    ]),
    ("pharmacokinetics", [
        r"pharmacokinetic", r"pk\b(?!\w)", r"concentration",
        r"c.max", r"t.max", r"auc", r"half.life", r"trough",
    ]),
    ("immunogenicity", [
        r"immunogen", r"antibod", r"ada", r"neutralizing antibod",
    ]),
    ("vital_signs", [
        r"vital sign", r"blood pressure", r"heart rate", r"temperature",
        r"respiratory rate", r"pulse",
    ]),
    ("ecg", [
        r"ecg", r"electrocardiogram", r"qtc", r"qt interval",
        r"heart rhythm",
    ]),
    ("protocol_deviation", [
        r"protocol deviat", r"violation", r"non.compliance",
    ]),
    ("subgroup", [
        r"subgroup", r"subset", r"sub.population",
    ]),
    ("sensitivity", [
        r"sensitivity analys", r"supplement", r"additional analys",
    ]),
    ("dosing", [
        r"dosing", r"dose administration", r"intent.to.treat",
    ]),
]

SECTION_MAP = {
    "disposition": {"primary": "disposition", "section": "4"},
    "demographics": {"primary": "demographics", "section": "4.3"},
    "exposure": {"primary": "exposure", "section": "6.1"},
    "concomitant": {"primary": "concomitant", "section": "6.1.1"},
    "adverse_event": {"primary": "adverse_event", "section": "6.2"},
    "deaths": {"primary": "deaths", "section": "6.3"},
    "laboratory": {"primary": "laboratory", "section": "6.4"},
    "vital_signs": {"primary": "vital_signs", "section": "6.5"},
    "ecg": {"primary": "ecg", "section": "6.6"},
    "efficacy": {"primary": "efficacy", "section": "5"},
    "pharmacokinetics": {"primary": "pharmacokinetics", "section": "5.5"},
    "pk_parameters": {"primary": "pharmacokinetics", "section": "5.5.1"},
    "immunogenicity": {"primary": "immunogenicity", "section": "5.6"},
    "study_design": {"primary": "study_design", "section": "3"},
    "protocol_deviation": {"primary": "protocol_deviation", "section": "4.2"},
    "dosing": {"primary": "dosing", "section": "4.4"},
    "compliance": {"primary": "compliance", "section": "4.5"},
    "subgroup": {"primary": "subgroup", "section": "5.4.1"},
    "sensitivity": {"primary": "sensitivity", "section": "5.4.2"},
    "other": {"primary": "other", "section": "8"},
}


class TableClassifier:
    def classify(self, linearized: str, title: str = "") -> str:
        combined = f"{title.lower()} {linearized.lower()}"

        scores: dict = {}
        for type_key, patterns in CLINICAL_TYPE_PATTERNS:
            score = 0
            for pat in patterns:
                matches = re.findall(pat, combined)
                score += len(matches)
            if score > 0:
                scores[type_key] = score

        if not scores:
            return "other"

        best = max(scores, key=scores.get)
        return best

    def get_ich_e3_section(self, table_type: str) -> str:
        info = SECTION_MAP.get(table_type, SECTION_MAP["other"])
        return info["section"]

    def get_section_label(self, table_type: str) -> str:
        return ICH_E3_TABLE_TYPES.get(table_type, "Additional Analyses")

    def classify_with_metadata(self, linearized: str, title: str = "") -> dict:
        table_type = self.classify(linearized, title)
        return {
            "table_type": table_type,
            "label": self.get_section_label(table_type),
            "ich_e3_section": self.get_ich_e3_section(table_type),
            "is_primary_safety": table_type in (
                "adverse_event", "deaths", "laboratory", "vital_signs", "ecg",
            ),
            "is_efficacy": table_type in ("efficacy", "subgroup", "sensitivity"),
            "is_demographics": table_type in ("demographics", "disposition"),
        }

    def batch_classify(self, tables: list) -> list:
        results = []
        for t in tables:
            if isinstance(t, dict):
                lin = t.get("linearized", "")
                tit = t.get("title", "")
            else:
                lin = getattr(t, "linearized", "")
                tit = getattr(t, "title", "")
            results.append(self.classify_with_metadata(lin, tit))
        return results
