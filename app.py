"""Streamlit frontend: upload a CSV, run the data-quality pipeline, see the report.

Thin UI layer only — all logic still lives in src/runner.py etc. This just
calls check() and renders the result.
"""
from __future__ import annotations

import tempfile
from html import escape
from pathlib import Path

import streamlit as st

from src.runner import check

# ---- status palette (fixed — never themed; see dataviz skill / palette.md) ----
GOOD = "#0ca30c"
WARNING = "#eda100"
CRITICAL = "#d03b3b"
ACCENT = "#2a78d6"


def _rgba(hex_color: str, alpha: float) -> str:
    """Convert '#rrggbb' to an 'rgba(...)' string.

    Streamlit's dataframe grid renders Styler backgrounds on a <canvas>, which
    doesn't understand CSS color-mix() — it needs a literal rgba() value.
    """
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"

st.set_page_config(page_title="Data Quality Checker", page_icon="✅", layout="wide")

st.markdown(
    f"""
    <style>
    .block-container {{ padding-top: 2.5rem; padding-bottom: 3rem; max-width: 1200px; }}

    .dq-hero {{ display: flex; align-items: center; gap: 14px; margin-bottom: 2px; }}
    .dq-hero .badge {{
        width: 44px; height: 44px; border-radius: 12px;
        background: linear-gradient(135deg, {ACCENT}, #1baf7a);
        display: flex; align-items: center; justify-content: center;
        font-size: 22px; flex-shrink: 0;
    }}
    .dq-hero h1 {{ font-size: 1.75rem; font-weight: 700; margin: 0; line-height: 1.2; }}
    .dq-subtitle {{ opacity: 0.65; font-size: 0.95rem; margin: 4px 0 1.75rem 0; max-width: 720px; }}

    .dq-card {{
        background: rgba(127,127,127,0.06);
        border: 1px solid rgba(127,127,127,0.16);
        border-radius: 14px;
        padding: 18px 20px;
    }}

    /* KPI tiles */
    .kpi-row {{ display: flex; gap: 14px; margin: 6px 0 22px 0; flex-wrap: wrap; }}
    .kpi-tile {{
        flex: 1 1 180px;
        background: rgba(127,127,127,0.06);
        border: 1px solid rgba(127,127,127,0.16);
        border-left: 3px solid var(--accent);
        border-radius: 12px;
        padding: 14px 18px;
    }}
    .kpi-tile .kpi-icon {{
        display: inline-flex; align-items: center; justify-content: center;
        width: 26px; height: 26px; border-radius: 8px;
        background: color-mix(in srgb, var(--accent) 18%, transparent);
        color: var(--accent); font-size: 14px; font-weight: 700; margin-bottom: 8px;
    }}
    .kpi-tile .kpi-value {{ font-size: 1.9rem; font-weight: 700; line-height: 1; }}
    .kpi-tile .kpi-label {{ opacity: 0.6; font-size: 0.8rem; margin-top: 5px; }}

    /* Quality meter */
    .meter-wrap {{ margin: 4px 0 24px 0; }}
    .meter-head {{ display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 8px; }}
    .meter-head .meter-title {{ font-weight: 600; font-size: 0.95rem; }}
    .meter-head .meter-score {{ font-size: 1.4rem; font-weight: 700; }}
    .meter-track {{
        height: 10px; border-radius: 6px; overflow: hidden;
        background: color-mix(in srgb, var(--meter-color) 15%, transparent);
    }}
    .meter-fill {{ height: 100%; border-radius: 6px; background: var(--meter-color); }}

    /* Part-to-whole breakdown bar */
    .stack-bar {{
        display: flex; height: 18px; border-radius: 5px; overflow: hidden;
        gap: 2px; background: rgba(127,127,127,0.12); margin-bottom: 10px;
    }}
    .stack-seg {{ height: 100%; }}
    .stack-legend {{ display: flex; gap: 22px; flex-wrap: wrap; font-size: 0.85rem; }}
    .stack-legend .item {{ display: flex; align-items: center; gap: 7px; opacity: 0.85; }}
    .stack-legend .dot {{ width: 9px; height: 9px; border-radius: 3px; flex-shrink: 0; }}

    /* status pills in table */
    .pill {{
        display: inline-block; padding: 2px 9px; border-radius: 999px;
        font-size: 0.78rem; font-weight: 600; white-space: nowrap;
    }}
    .pill-pass {{ background: {_rgba(GOOD, 0.15)}; color: {GOOD}; }}
    .pill-fail {{ background: {_rgba(CRITICAL, 0.15)}; color: {CRITICAL}; }}

    /* rule results table (plain HTML — the Streamlit dataframe grid drops
       cell text when row + cell Styler CSS combine, so we render this ourselves) */
    .dq-table-wrap {{
        overflow-x: auto; border: 1px solid rgba(127,127,127,0.16);
        border-radius: 12px; margin-top: 4px;
    }}
    .dq-table {{ width: 100%; border-collapse: collapse; font-size: 0.87rem; }}
    .dq-table thead th {{
        text-align: left; padding: 10px 14px; font-weight: 600;
        opacity: 0.6; font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.02em;
        background: rgba(127,127,127,0.08);
        border-bottom: 1px solid rgba(127,127,127,0.16);
        white-space: nowrap;
    }}
    .dq-table tbody td {{
        padding: 9px 14px; border-bottom: 1px solid rgba(127,127,127,0.08);
        vertical-align: top;
    }}
    .dq-table tbody tr:last-child td {{ border-bottom: none; }}
    .dq-table .muted-cell {{ opacity: 0.75; }}
    .dq-table .sev {{ font-weight: 600; }}

    div[data-testid="stFileUploaderDropzone"] {{ border-radius: 12px; }}
    .stButton > button {{ border-radius: 8px; font-weight: 600; }}
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="dq-hero">
        <div class="badge">✅</div>
        <h1>Data Quality Checker</h1>
    </div>
    <p class="dq-subtitle">
        Upload a CSV. An LLM proposes data-quality rules from a statistical profile
        (never the raw rows) — plain code then enforces those rules against the
        full dataset.
    </p>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.header("Options")
    use_llm = st.toggle(
        "Use LLM to propose rules",
        value=False,
        help="Requires ANTHROPIC_API_KEY or OPENAI_API_KEY in .env. "
             "Off = heuristic rules, no API key or cost.",
    )

uploaded = st.file_uploader("CSV file", type=["csv"])

sample_path = Path(__file__).parent / "data" / "customers.csv"
use_sample = False
if uploaded is None and sample_path.exists():
    use_sample = st.checkbox(f"Use sample data ({sample_path.name})", value=False)

csv_path: str | None = None
tmp_file = None

if uploaded is not None:
    tmp_file = tempfile.NamedTemporaryFile(suffix=".csv", delete=False)
    tmp_file.write(uploaded.getvalue())
    tmp_file.close()
    csv_path = tmp_file.name
elif use_sample:
    csv_path = str(sample_path)

if csv_path is None:
    st.info("Upload a CSV or check the sample-data box to get started.")
    st.stop()

run = st.button("Run check", type="primary")

if run:
    try:
        with st.spinner("Profiling data and running checks..."):
            st.session_state["result"] = check(csv_path, use_llm=use_llm)
    except Exception as e:
        st.error(f"Check failed: {e}")
        st.stop()
    finally:
        if tmp_file is not None:
            Path(tmp_file.name).unlink(missing_ok=True)
elif tmp_file is not None:
    Path(tmp_file.name).unlink(missing_ok=True)

if "result" not in st.session_state:
    st.stop()

result = st.session_state["result"]
summary = result["summary"]
total, passed, errors, warnings = (
    summary["total"], summary["passed"], summary["errors"], summary["warnings"]
)

# ---- KPI row ----
st.markdown(
    f"""
    <div class="kpi-row">
        <div class="kpi-tile" style="--accent:{ACCENT}">
            <div class="kpi-icon">Σ</div>
            <div class="kpi-value">{total}</div>
            <div class="kpi-label">Rules checked</div>
        </div>
        <div class="kpi-tile" style="--accent:{GOOD}">
            <div class="kpi-icon">✓</div>
            <div class="kpi-value">{passed}</div>
            <div class="kpi-label">Passed</div>
        </div>
        <div class="kpi-tile" style="--accent:{CRITICAL}">
            <div class="kpi-icon">✕</div>
            <div class="kpi-value">{errors}</div>
            <div class="kpi-label">Errors</div>
        </div>
        <div class="kpi-tile" style="--accent:{WARNING}">
            <div class="kpi-icon">!</div>
            <div class="kpi-value">{warnings}</div>
            <div class="kpi-label">Warnings</div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ---- quality meter ----
score = round(100 * passed / total) if total else 0
meter_color = CRITICAL if errors else (WARNING if warnings else GOOD)
st.markdown(
    f"""
    <div class="meter-wrap" style="--meter-color:{meter_color}">
        <div class="meter-head">
            <span class="meter-title">Data quality score</span>
            <span class="meter-score" style="color:{meter_color}">{score}%</span>
        </div>
        <div class="meter-track"><div class="meter-fill" style="width:{score}%"></div></div>
    </div>
    """,
    unsafe_allow_html=True,
)

if errors > 0:
    st.error(f"{errors} rule(s) failed with error severity.")
elif warnings > 0:
    st.warning("No errors, but some rules produced warnings.")
else:
    st.success("No error-severity failures.")

# ---- part-to-whole breakdown ----
segments = [
    ("passed", passed, GOOD),
    ("warnings", warnings, WARNING),
    ("errors", errors, CRITICAL),
]
seg_html = "".join(
    f'<div class="stack-seg" style="width:{(n / total * 100) if total else 0}%; background:{c}"></div>'
    for _, n, c in segments if n > 0
)
legend_html = "".join(
    f'<div class="item"><span class="dot" style="background:{c}"></span>{n} {label}</div>'
    for label, n, c in segments if n > 0
)
st.markdown(
    f"""
    <div class="stack-bar">{seg_html}</div>
    <div class="stack-legend">{legend_html}</div>
    """,
    unsafe_allow_html=True,
)

st.write("")

# ---- rule results table ----
table_rows = [
    {
        "Status": "PASS" if rr.passed else "FAIL",
        "Rule": rr.rule.id,
        "Check": rr.rule.check,
        "Column": rr.rule.column or "(table)",
        "Severity": rr.rule.severity,
        "Detail": rr.detail,
        "Rationale": rr.rule.rationale,
        "Examples": "; ".join(f"row {v['row']}: {v['value']!r}" for v in rr.violations),
    }
    for rr in result["results"]
]
tab_results, tab_report, tab_profile = st.tabs(["Rule results", "Raw report", "Column profile"])

with tab_results:
    filter_choice = st.radio(
        "Filter", ["All", "Failed only"], horizontal=True, label_visibility="collapsed",
    )
    view_rows = table_rows if filter_choice == "All" else [r for r in table_rows if r["Status"] == "FAIL"]

    def _table_row_html(r: dict) -> str:
        is_fail = r["Status"] == "FAIL"
        sev_color = CRITICAL if r["Severity"] == "error" else WARNING
        row_tint = f'background:{_rgba(sev_color, 0.10)};' if is_fail else ""
        pill_class = "pill-fail" if is_fail else "pill-pass"
        status_label = "✕ FAIL" if is_fail else "✓ PASS"
        cells = [r["Rule"], r["Check"], r["Column"], r["Detail"], r["Rationale"]]
        rule, chk, column, detail, rationale = (escape(str(c)) for c in cells)
        examples = escape(r["Examples"]) or "—"
        examples_style = f'color:{sev_color};' if is_fail else ""
        return (
            f'<tr style="{row_tint}">'
            f'<td><span class="pill {pill_class}">{status_label}</span></td>'
            f'<td>{rule}</td><td>{chk}</td><td>{column}</td>'
            f'<td class="sev" style="color:{sev_color}">{escape(r["Severity"])}</td>'
            f'<td>{detail}</td>'
            f'<td class="muted-cell" style="{examples_style}">{examples}</td>'
            f'<td class="muted-cell">{rationale}</td>'
            f'</tr>'
        )

    if view_rows:
        rows_html = "".join(_table_row_html(r) for r in view_rows)
        st.markdown(
            f"""
            <div class="dq-table-wrap">
            <table class="dq-table">
                <thead><tr>
                    <th>Status</th><th>Rule</th><th>Check</th><th>Column</th>
                    <th>Severity</th><th>Detail</th><th>Examples</th><th>Rationale</th>
                </tr></thead>
                <tbody>{rows_html}</tbody>
            </table>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.caption("No rows match this filter.")

with tab_report:
    st.code(result["report"], language=None)

with tab_profile:
    st.json(result["profile"])
