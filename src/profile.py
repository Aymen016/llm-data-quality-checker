"""Profile a dataset: compute per-column stats the LLM will reason about.

We send the LLM this compact profile, NOT the raw rows. That keeps the prompt
small, keeps private data out of the model, and scales to huge tables.
"""
from __future__ import annotations

import pandas as pd

from .config import SAMPLE_VALUES


def load(path: str) -> pd.DataFrame:
    """Read a CSV. Everything as string first so we can see raw messiness
    (e.g. 'None', empty strings) instead of pandas silently coercing them."""
    return pd.read_csv(path, dtype=str, keep_default_na=False)


def _looks_numeric(series: pd.Series) -> bool:
    non_empty = series[series.str.strip() != ""]
    if non_empty.empty:
        return False
    coerced = pd.to_numeric(non_empty, errors="coerce")
    return coerced.notna().mean() > 0.8  # 80%+ parse as numbers


def profile_column(series: pd.Series) -> dict:
    total = len(series)
    blank = (series.str.strip() == "").sum()
    non_blank = series[series.str.strip() != ""]
    distinct = non_blank.nunique()

    col: dict = {
        "total": int(total),
        "blank_count": int(blank),
        "distinct_count": int(distinct),
        "sample_values": non_blank.drop_duplicates().head(SAMPLE_VALUES).tolist(),
    }

    if _looks_numeric(series):
        nums = pd.to_numeric(non_blank, errors="coerce").dropna()
        col["inferred_type"] = "numeric"
        col["min"] = float(nums.min())
        col["max"] = float(nums.max())
        col["mean"] = round(float(nums.mean()), 2)
    else:
        col["inferred_type"] = "string"
        # small cardinality -> likely categorical; expose the full value set
        if distinct <= 15:
            col["distinct_values"] = sorted(non_blank.unique().tolist())

    return col


def profile(df: pd.DataFrame) -> dict:
    return {
        "row_count": int(len(df)),
        "columns": {name: profile_column(df[name]) for name in df.columns},
    }
