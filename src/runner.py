"""Orchestrates the full pipeline: load -> profile -> propose rules -> run -> report.

Plain functions, no orchestration framework. Swap `check()` into Airflow/cron/
whatever later; the logic doesn't care.
"""
from __future__ import annotations

import pandas as pd

from .llm_rules import baseline_rules, propose_rules
from .profile import load, profile
from .report import format_report, run_rules, summary
from .rules import Rule


def check(path: str, use_llm: bool = True) -> dict:
    """Run the full quality check on a CSV. Returns a dict with the report,
    the rules used, and a pass/fail summary."""
    df: pd.DataFrame = load(path)
    prof = profile(df)

    rules: list[Rule] = propose_rules(prof) if use_llm else baseline_rules(prof)
    results = run_rules(rules, df)

    return {
        "profile": prof,
        "rules": rules,
        "results": results,
        "report": format_report(results),
        "summary": summary(results),
    }
