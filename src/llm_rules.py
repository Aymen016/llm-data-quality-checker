"""Ask an LLM to propose data-quality rules from a column profile.

The model returns JSON matching the Rule schema. We parse + validate it, so a
malformed or hallucinated rule (e.g. referencing a missing column) is rejected
rather than trusted blindly.
"""
from __future__ import annotations

import json
import os

from .config import ANTHROPIC_MODEL, LLM_PROVIDER, OPENAI_MODEL
from .rules import Rule

SYSTEM = """You are a data quality analyst. Given a JSON profile of a dataset's
columns (types, blank counts, distinct counts, sample/distinct values, numeric
min/max), propose a set of data-quality rules.

Return ONLY a JSON array. Each rule is an object with:
  id            short slug, e.g. "age_range"
  check         one of: not_null | unique | range | allowed_values | regex | row_count_min
  column        the column name (omit for row_count_min)
  params        check-specific:
                  range          -> {"min": <num>, "max": <num>}
                  allowed_values -> {"values": [...]}
                  regex          -> {"pattern": "<full-match regex>"}
                  row_count_min  -> {"min": <int>}
                  not_null/unique-> {}
  severity      "error" or "warn"
  rationale     one short sentence on why

Only reference columns that exist in the profile. Infer sensible bounds from the
data (e.g. human age 0-120). For inconsistent categories, propose allowed_values
using the cleaned set you'd expect. No prose, no markdown — JSON array only."""


def _call_llm(profile_json: str) -> str:
    if LLM_PROVIDER == "anthropic" and os.getenv("ANTHROPIC_API_KEY"):
        import anthropic
        client = anthropic.Anthropic()
        msg = client.messages.create(
            model=ANTHROPIC_MODEL, max_tokens=1500, system=SYSTEM,
            messages=[{"role": "user", "content": profile_json}],
        )
        return "".join(b.text for b in msg.content if b.type == "text")

    if LLM_PROVIDER == "openai" and os.getenv("OPENAI_API_KEY"):
        from openai import OpenAI
        client = OpenAI()
        resp = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[{"role": "system", "content": SYSTEM},
                      {"role": "user", "content": profile_json}],
        )
        return resp.choices[0].message.content

    raise RuntimeError(
        "No LLM configured. Set LLM_PROVIDER + API key in .env, or use "
        "baseline_rules() for a no-LLM heuristic ruleset."
    )


def _parse(raw: str, columns: list[str]) -> list[Rule]:
    raw = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```")
    data = json.loads(raw)
    rules: list[Rule] = []
    for obj in data:
        rule = Rule(
            id=obj["id"], check=obj["check"], column=obj.get("column"),
            params=obj.get("params", {}), severity=obj.get("severity", "error"),
            rationale=obj.get("rationale", ""),
        )
        try:
            rule.validate(columns)
        except ValueError:
            continue  # drop invalid / hallucinated rules
        rules.append(rule)
    return rules


def propose_rules(profile: dict) -> list[Rule]:
    columns = list(profile["columns"].keys())
    raw = _call_llm(json.dumps(profile, indent=2))
    return _parse(raw, columns)


def baseline_rules(profile: dict) -> list[Rule]:
    """Heuristic ruleset with no LLM — useful as a fallback and for testing.
    Deliberately simpler than what the LLM produces."""
    rules: list[Rule] = []
    for name, col in profile["columns"].items():
        # anything never blank in the sample is probably required
        if col["blank_count"] == 0:
            rules.append(Rule(id=f"{name}_not_null", check="not_null", column=name,
                              rationale="No blanks observed; likely required."))
        # fully-distinct string columns look like keys
        if col["distinct_count"] == col["total"] - col["blank_count"]:
            rules.append(Rule(id=f"{name}_unique", check="unique", column=name,
                              rationale="All values distinct; likely a key."))
        # low-cardinality strings -> categorical
        if col["inferred_type"] == "string" and "distinct_values" in col:
            rules.append(Rule(id=f"{name}_allowed", check="allowed_values", column=name,
                              params={"values": col["distinct_values"]},
                              severity="warn",
                              rationale="Low cardinality; treat as category set."))
        # numeric -> range from observed min/max, widened slightly
        if col["inferred_type"] == "numeric":
            rules.append(Rule(id=f"{name}_range", check="range", column=name,
                              params={"min": min(0, col["min"]), "max": col["max"]},
                              severity="warn",
                              rationale="Bound to observed numeric range."))
    return rules
