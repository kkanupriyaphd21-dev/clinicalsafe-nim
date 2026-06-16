"""
src/generation/nim_generator.py
NVIDIA NIM table summarization wrapper with numeric verification.
"""
import json
import logging
import re
import time
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from src.generation.provenance import extract_facts
from src.services.nim_client import NIMClient

logger = logging.getLogger(__name__)


# Population qualifier injected automatically by table type.
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

# Base system prompt shared across all table types.
_BASE_SYSTEM_PROMPT = (
    "You are a senior medical writer preparing text for an ICH E3 clinical study report. "
    "Write in plain regulatory prose. Do not use bullet points, numbered lists, or dashes. "
    "Do not bold or emphasise inline numbers. Do not state what the table is or is not. "
    "Only describe rows, values, and categories that are explicitly present in the table. "
    "Never infer or comment on the absence of categories that are not listed in the table.\n\n"
    "NUMERIC ACCURACY RULES (strictly enforce):\n"
    "1. Copy EVERY number from the table exactly as shown, including decimals and percentages.\n"
    "2. NEVER round, approximate, or paraphrase numbers (e.g., write '33.3%' not '33%').\n"
    "3. NEVER add numbers that are not in the source table.\n"
    "4. Report counts and percentages in 'n (X.X%)' format when the table uses it.\n"
    "5. For confidence intervals use the format: OR/HR X.XX (95% CI: X.XX–X.XX).\n"
    "6. For p-values use lowercase p (e.g., p < 0.001) and keep the comparison concise: 'versus placebo (p < 0.001)'.\n"
    "7. Order treatment arms: Placebo first, then active doses ascending.\n"
    "8. State the analysis population explicitly as the first clause of the narrative.\n"
    "9. End with one concise interpretive sentence that characterises the finding.\n"
    "10. Do NOT use the phrase 'clinically significant' or 'clinically meaningful improvement' unless an MCID is provided in the context.\n"
    "11. For continuous variables, label the dispersion measure explicitly, e.g., 'mean (SD)' or '45.2 years (SD 11.3)'.\n"
)

# Table-type specific prompt additions.
_TABLE_TYPE_PROMPTS = {
    "demographics": (
        "Summarise demographic and baseline characteristics for the {population}. "
        "Provide one or two prose paragraphs. Report the size of each treatment group, mean/median age, sex, race, "
        "and relevant baseline measures exactly as shown. "
        "When reporting continuous variables such as age or BMI, label the dispersion measure explicitly, "
        "e.g., 'mean (SD)' or '45.2 years (SD 11.3)'. "
        "Conclude with a sentence stating that baseline characteristics were generally balanced across treatment groups."
    ),
    "disposition": (
        "Summarise subject disposition for the {population}. Report screened, randomised, completed, and withdrawn counts "
        "for each treatment arm. Conclude with a brief statement on overall retention."
    ),
    "efficacy": (
        "Summarise efficacy endpoint results for the {population}. "
        "Report response rates, odds ratios/hazard ratios with 95% confidence intervals, median times, and p-values exactly as shown. "
        "{statistical_method_clause}"
        "Use concise comparison language: 'versus placebo (p < 0.001)' rather than 'when comparing the active treatment groups to placebo'. "
        "Do not describe the finding as 'clinically significant' or 'clinically meaningful' unless an MCID is provided. "
        "Conclude with an interpretive sentence on the magnitude of the efficacy finding."
    ),
    "adverse_event": (
        "Summarise treatment-emergent adverse events (TEAEs), serious adverse events (SAEs), and "
        "discontinuations due to AEs for the {population}. Report the incidence for each treatment arm in prose. "
        "Do not mention deaths, fatal events, or categories not present as explicit rows. "
        "Conclude with a sentence on the overall safety profile relative to placebo."
    ),
    "laboratory": (
        "Summarise clinical laboratory safety findings for the {population}. Report abnormalities, shift tables, or "
        "clinically significant values as shown. Conclude with a brief safety interpretation."
    ),
    "vital_signs": (
        "Summarise vital signs, physical findings, or ECG results for the {population}. Report values and notable changes "
        "as shown. Conclude with a brief interpretive sentence."
    ),
    "exposure": (
        "Summarise extent of exposure for the {population} including duration, dose intensity, and compliance. "
        "Conclude with a brief interpretive sentence."
    ),
    "concomitant": (
        "Summarise concomitant or prior medications for the {population}. Report the most common categories or agents "
        "as shown. Conclude with a brief interpretive sentence."
    ),
    "pharmacokinetics": (
        "Summarise pharmacokinetic parameters for the {population}. Report Cmax, Tmax, AUC, half-life, and other PK "
        "values exactly as shown. Conclude with a brief interpretive sentence."
    ),
    "other": (
        "Summarise the table contents in one or two prose paragraphs for the {population}. Report all numbers exactly "
        "as shown. Conclude with a brief interpretive sentence."
    ),
}

_CLINICAL_USER_PROMPT = (
    "Table type: {table_type}\n"
    "Analysis population: {population}\n"
    "{statistical_method_text}"
    "Table data:\n{table_text}\n\n"
    "Write a concise clinical narrative paragraph (or two) in plain prose. "
    "Start by naming the analysis population. "
    "Copy all numbers exactly — no rounding, no approximations. "
    "Do not use bullet points, bold, or dashes."
)


class NIMGenerator:
    def __init__(self, db: Session, model: Optional[str] = None):
        self.db = db
        self.client = NIMClient(db)
        self.model = model

    @staticmethod
    def _clean_summary(summary: str) -> str:
        """
        Post-process NIM output to remove markdown formatting, internal annotations,
        and fabricated absence claims.
        """
        if not summary:
            return summary

        # Strip markdown bold/italic.
        text = re.sub(r"\*\*", "", summary)
        text = re.sub(r"__", "", text)

        # Remove common internal classifier leaks.
        leaks = [
            r"This table does not contain clinical safety data\.\s*",
            r"This table contains (?:no|only) clinical safety data\.\s*",
            r"(?:The )?table (?:does not contain|contains no) clinical safety data\.\s*",
            r"(?:The )?following data (?:is|are) presented:\s*",
            r"(?:The )?table includes the following data:\s*",
        ]
        for leak in leaks:
            text = re.sub(leak, "", text, flags=re.IGNORECASE)

        # Convert bullet-like list items to prose if needed.
        text = re.sub(r"^\s*[-•]\s+", "", text, flags=re.MULTILINE)

        # Normalise whitespace.
        text = re.sub(r"\s+", " ", text).strip()
        return text

    @staticmethod
    def _sanitize_regulatory_language(summary: str) -> str:
        """
        Replace unsupported regulatory phrases and tighten statistical attribution.
        """
        if not summary:
            return summary

        # Replace unsupported clinical-significance claims with safer alternatives.
        replacements = [
            (r"\bclinically meaningful improvement\b", "improvement"),
            (r"\bclinically significant(?:ly)?\b", "statistically significant"),
            (r"\bno clinically meaningful difference\b", "no statistically significant difference"),
            (r"\bno clinically significant difference\b", "no statistically significant difference"),
            # Tighten verbose p-value attribution.
            (r"\bwhen comparing the active treatment groups? to(?: the)? placebo\b", "versus placebo"),
            (r"\bwhen comparing the active groups? to(?: the)? placebo\b", "versus placebo"),
            (r"\bwhen comparing to(?: the)? placebo\b", "versus placebo"),
            # Prefer "compared with" over "compared to" (ICH convention).
            (r"\bcompared to\b", "compared with"),
        ]
        for pattern, repl in replacements:
            summary = re.sub(pattern, repl, summary, flags=re.IGNORECASE)

        # Clean up double spaces introduced by replacements.
        summary = re.sub(r"\s+", " ", summary).strip()
        return summary

    @staticmethod
    def _filter_absence_claims(summary: str, source_table: str) -> Tuple[str, List[str]]:
        """
        Remove or flag sentences that assert absence of categories not present in the table.
        e.g., 'There were no fatal events' when the table has no Fatal/Death row.
        """
        warnings: List[str] = []
        source_lower = source_table.lower()

        # Patterns that claim absence of a category.
        absence_patterns = [
            (r"(?i)(?:there were|there was)\s+no\s+([a-z\s]+?)(?:\s+reported)?", "no {group}"),
            (r"(?i)no\s+([a-z\s]+?)\s+(?:were|was)\s+reported", "no {group} reported"),
            (r"(?i)no\s+fatal(?:ities| events)?\s+(?:were|was)\s+reported", "fatal"),
            (r"(?i)(?:there were|there was)\s+no\s+fatal(?:ities| events)?", "fatal"),
            (r"(?i)no\s+deaths\s+(?:were|was)\s+reported", "death"),
            (r"(?i)(?:there were|there was)\s+no\s+death", "death"),
        ]

        sentences = re.split(r"(?<=[.!?])\s+", summary)
        kept = []
        for sent in sentences:
            drop = False
            for pattern, concept in absence_patterns:
                m = re.search(pattern, sent)
                if not m:
                    continue
                # Determine concept to check in source table.
                check = concept
                if "{group}" in check:
                    check = m.group(1).strip().lower()
                # If the concept is not explicitly present in the source table, drop the sentence.
                if check and check not in source_lower:
                    drop = True
                    warnings.append(f"Removed absence claim not supported by table: {sent.strip()}")
                    break
            if not drop:
                kept.append(sent)

        return " ".join(kept), warnings

    def generate(
        self,
        table_text: str,
        table_type: str = "other",
        max_tokens: int = 1024,
        temperature: float = 0.0,
        timeout_sec: int = 60,
        statistical_method: Optional[str] = None,
    ) -> Dict:
        start = time.time()
        warnings: List[str] = []

        population = POPULATION_BY_TABLE_TYPE.get(table_type, "study population")
        type_instruction = _TABLE_TYPE_PROMPTS.get(table_type, _TABLE_TYPE_PROMPTS["other"]).format(
            population=population,
            statistical_method_clause=(
                f"The primary comparison method is: {statistical_method}. "
                if statistical_method
                else ""
            ),
        )
        system_prompt = _BASE_SYSTEM_PROMPT + "\n" + type_instruction

        statistical_method_text = (
            f"Statistical method: {statistical_method}\n" if statistical_method else ""
        )
        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": _CLINICAL_USER_PROMPT.format(
                    table_text=table_text,
                    table_type=table_type,
                    population=population,
                    statistical_method_text=statistical_method_text,
                ),
            },
        ]

        try:
            data, key_id = self.client.chat_completion(
                messages=messages,
                model=self.model,
                max_tokens=max_tokens,
                temperature=temperature,
                endpoint_label="single_table_summarize",
            )
            summary = data["choices"][0]["message"]["content"].strip()
            model_used = data.get("model", self.model or "unknown")
            tokens_generated = data.get("usage", {}).get("completion_tokens")
        except (KeyError, IndexError, json.JSONDecodeError) as e:
            raise RuntimeError(f"NVIDIA NIM: Unexpected response format: {e}")

        summary = self._clean_summary(summary)
        summary = self._sanitize_regulatory_language(summary)
        summary, absence_warnings = self._filter_absence_claims(summary, table_text)
        warnings.extend(absence_warnings)

        verified, accuracy, vwarn = self._verify_output(summary, table_text)
        warnings.extend(vwarn)

        elapsed_ms = round((time.time() - start) * 1000, 2)

        return {
            "summary": summary,
            "model_used": f"nim/{model_used}",
            "verified": verified,
            "numeric_accuracy": accuracy,
            "inference_time_ms": elapsed_ms,
            "warnings": warnings,
            "tokens_generated": tokens_generated,
            "extracted_facts": extract_facts(summary, table_text),
            "key_id": key_id,
        }

    @staticmethod
    def _extract_numbers(text: str) -> set:
        nums = set()
        for m in re.finditer(r"\b\d+(?:\.\d+)?", text):
            nums.add(float(m.group()))
        for m in re.finditer(r"\b\d{1,3}(?:,\d{3})+(?:\.\d+)?", text):
            nums.add(float(m.group().replace(",", "")))
        for m in re.finditer(r"\b(\d+(?:\.\d+)?)%", text):
            nums.add(float(m.group(1)))
        for m in re.finditer(r"\b(19|20)\d{2}\b", text):
            nums.add(float(m.group()))
        return nums

    @staticmethod
    def _is_date_number(n_str: str) -> bool:
        val = float(n_str)
        if 1 <= val <= 31 and "." not in n_str:
            return True
        if 1900 <= val <= 2099 and "." not in n_str:
            return True
        return False

    def _verify_output(self, narrative: str, source_table: str) -> Tuple[bool, float, List[str]]:
        source_nums = self._extract_numbers(source_table)
        output_strs = re.findall(r"\b\d+(?:\.\d+)?", narrative)

        if not output_strs:
            return True, 1.0, []

        bad = []
        for n_str in output_strs:
            try:
                n_val = float(n_str)
            except ValueError:
                bad.append(n_str)
                continue
            if self._is_date_number(n_str):
                if not any(abs(n_val - s) <= 1.0 for s in source_nums):
                    continue
            if not any(abs(n_val - s) <= max(n_val * 0.02, 1.0) for s in source_nums):
                bad.append(n_str)

        accuracy = 1.0 - (len(bad) / len(output_strs)) if output_strs else 1.0
        warnings = []
        if bad:
            warnings.append(f"Numbers not in source table: {bad}")

        verified = accuracy >= 0.95
        return verified, round(accuracy, 4), warnings
