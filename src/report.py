"""Run a list of rules against a DataFrame and format a report."""
from __future__ import annotations

import pandas as pd

from .rules import Rule, RuleResult, run_rule


def run_rules(rules: list[Rule], df: pd.DataFrame) -> list[RuleResult]:
    return [run_rule(r, df) for r in rules]


def format_report(results: list[RuleResult]) -> str:
    lines: list[str] = []
    errors = warns = passed = 0

    for r in results:
        if r.passed:
            passed += 1
            mark = "PASS"
        else:
            mark = "FAIL"
            if r.rule.severity == "error":
                errors += 1
            else:
                warns += 1
        col = r.rule.column or "(table)"
        lines.append(
            f"[{mark}] {r.rule.id}  ({r.rule.check} on {col})  "
            f"-> {r.detail}"
        )
        if not r.passed and r.rule.rationale:
            lines.append(f"        why: {r.rule.rationale}")
        if not r.passed and r.violations:
            examples = ", ".join(f"row {v['row']}={v['value']!r}" for v in r.violations)
            lines.append(f"        e.g. {examples}")

    header = (
        f"Data Quality Report\n"
        f"{'=' * 60}\n"
        f"{len(results)} rules | {passed} passed | "
        f"{errors} errors | {warns} warnings\n"
    )
    return header + "\n".join(lines)


def summary(results: list[RuleResult]) -> dict:
    return {
        "total": len(results),
        "passed": int(sum(r.passed for r in results)),
        "errors": int(sum(not r.passed and r.rule.severity == "error" for r in results)),
        "warnings": int(sum(not r.passed and r.rule.severity == "warn" for r in results)),
    }
