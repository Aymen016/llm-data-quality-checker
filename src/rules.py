"""Data-quality rules: the schema, plus the engine that actually runs them.

A Rule is a small declarative object. The engine knows how to evaluate each
`check` type against a DataFrame and count violations. The LLM only produces
these Rule objects — it never touches the data itself.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

import pandas as pd

CHECKS = {"not_null", "unique", "range", "allowed_values", "regex", "row_count_min"}


@dataclass
class Rule:
    id: str
    check: str                      # one of CHECKS
    column: str | None = None       # None for table-level checks (row_count_min)
    params: dict = field(default_factory=dict)
    severity: str = "error"         # error | warn
    rationale: str = ""

    def validate(self, columns: list[str]) -> None:
        if self.check not in CHECKS:
            raise ValueError(f"unknown check: {self.check}")
        if self.check != "row_count_min" and self.column not in columns:
            raise ValueError(f"rule {self.id}: column '{self.column}' not in data")


@dataclass
class RuleResult:
    rule: Rule
    passed: bool
    failed_count: int
    total: int
    detail: str = ""
    violations: list[dict] = field(default_factory=list)  # sample offending rows


MAX_VIOLATION_SAMPLES = 5


def _non_blank_mask(s: pd.Series) -> pd.Series:
    return s.str.strip() != ""


def _sample_violations(col: pd.Series, bad_mask: pd.Series) -> list[dict]:
    """Sample offending rows for display: CSV line number (1-based, header = line 1)
    plus the value that violated the rule."""
    idx = bad_mask[bad_mask].index[:MAX_VIOLATION_SAMPLES]
    return [{"row": int(i) + 2, "value": col.loc[i]} for i in idx]


def run_rule(rule: Rule, df: pd.DataFrame) -> RuleResult:
    total = len(df)

    if rule.check == "row_count_min":
        need = int(rule.params["min"])
        ok = total >= need
        return RuleResult(rule, ok, 0 if ok else 1, total,
                          f"rows={total}, required>={need}")

    col = df[rule.column]

    if rule.check == "not_null":
        bad_mask = col.str.strip() == ""
        bad = int(bad_mask.sum())
        violations = _sample_violations(col, bad_mask)

    elif rule.check == "unique":
        nb = col[_non_blank_mask(col)]
        bad_mask = nb.duplicated()
        bad = int(bad_mask.sum())
        violations = _sample_violations(nb, bad_mask)

    elif rule.check == "range":
        nb = col[_non_blank_mask(col)]
        nums = pd.to_numeric(nb, errors="coerce")
        lo = rule.params.get("min")
        hi = rule.params.get("max")
        bad_mask = nums.isna()  # unparseable numbers count as violations
        if lo is not None:
            bad_mask |= nums < lo
        if hi is not None:
            bad_mask |= nums > hi
        bad = int(bad_mask.sum())
        violations = _sample_violations(nb, bad_mask)

    elif rule.check == "allowed_values":
        allowed = set(rule.params["values"])
        nb = col[_non_blank_mask(col)]
        bad_mask = ~nb.isin(allowed)
        bad = int(bad_mask.sum())
        violations = _sample_violations(nb, bad_mask)

    elif rule.check == "regex":
        pattern = re.compile(rule.params["pattern"])
        nb = col[_non_blank_mask(col)]
        bad_mask = ~nb.map(lambda v: bool(pattern.fullmatch(v)))
        bad = int(bad_mask.sum())
        violations = _sample_violations(nb, bad_mask)

    else:  # pragma: no cover
        raise ValueError(rule.check)

    return RuleResult(rule, bad == 0, int(bad), total,
                      f"{bad} violating rows", violations)
