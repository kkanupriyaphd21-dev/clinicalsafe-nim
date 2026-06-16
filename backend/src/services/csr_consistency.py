"""
src/services/csr_consistency.py

Lightweight cross-table consistency checks for CSR summaries.
"""
import re
from typing import Dict, List, Any


class CSRConsistencyGuardian:
    def check_all(self, table_results: List[Any]) -> List[Dict[str, Any]]:
        warnings = []
        warnings.extend(self._check_n_value_agreement(table_results))
        warnings.extend(self._check_arm_names(table_results))
        return warnings

    def _extract_n_values(self, text: str) -> Dict[str, int]:
        values = {}
        for m in re.finditer(r'(?:Arm\s+([A-Z])|Treatment\s+([A-Za-z0-9\-]+))\s+N\s*=\s*(\d+)', text, re.IGNORECASE):
            arm = m.group(1) or m.group(2)
            n = int(m.group(3))
            if arm:
                values[arm.upper() if len(arm) == 1 else arm] = n
        return values

    def _check_n_value_agreement(self, table_results: List[Any]) -> List[Dict[str, Any]]:
        warnings = []
        n_by_arm: Dict[str, List[int]] = {}
        for tr in table_results:
            if not tr.summary:
                continue
            n_values = self._extract_n_values(tr.summary)
            for arm, n in n_values.items():
                n_by_arm.setdefault(arm, []).append(n)

        for arm, values in n_by_arm.items():
            if len(set(values)) > 1:
                warnings.append({
                    "category": "n_value_mismatch",
                    "severity": "warning",
                    "message": f"Arm '{arm}' has inconsistent N values across tables: {sorted(set(values))}",
                    "source_tables": [tr.table_id for tr in table_results if arm in self._extract_n_values(tr.summary)],
                })
        return warnings

    def _check_arm_names(self, table_results: List[Any]) -> List[Dict[str, Any]]:
        warnings = []
        arm_sets: List[set] = []
        for tr in table_results:
            if not tr.summary:
                continue
            arms = set(self._extract_n_values(tr.summary).keys())
            if arms:
                arm_sets.append(arms)

        if len(arm_sets) >= 2:
            common = set.intersection(*arm_sets)
            for i, arms in enumerate(arm_sets):
                diff = arms - common
                if diff and len(diff) >= len(arms):
                    warnings.append({
                        "category": "arm_name_inconsistency",
                        "severity": "info",
                        "message": f"Table uses different arm identifiers than others: {diff}",
                        "source_tables": [table_results[i].table_id],
                    })
        return warnings
