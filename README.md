# LLM-Powered Data Quality Checker

Point it at a CSV and it profiles the data, asks an LLM to propose data-quality
rules, runs those rules, and prints a pass/fail report.

The design principle: **the LLM proposes checks, plain code enforces them.** The
model never inspects raw rows (it hallucinates and can't scale) — it only reasons
over a small statistical *profile* and returns declarative rules. A deterministic
engine then runs each rule against the full dataset. You get an LLM's judgment
about what *should* be true with the reliability of ordinary code doing the
counting.

## Example

```
$ python cli.py check data/customers.csv

Data Quality Report
============================================================
8 rules | 2 passed | 5 errors | 1 warnings
[PASS] customer_id_not_null   (not_null on customer_id)      -> 0 violating rows
[FAIL] customer_id_unique     (unique on customer_id)        -> 1 violating rows
[FAIL] email_format           (regex on email)               -> 1 violating rows
[FAIL] age_range              (range on age)                 -> 2 violating rows
[FAIL] country_allowed        (allowed_values on country)    -> 3 violating rows
[FAIL] amount_non_negative    (range on amount_spent)        -> 2 violating rows
...
```

The sample data is deliberately messy (duplicate id, bad email, age of -5 and 999,
`US`/`USA`/`United States` mix, negative spend) so you can see the checks bite.

## How it works

```
 CSV ─► profile.py ─► {per-column stats}
                            │
                            ▼
                     llm_rules.py ─► LLM ─► [rules as JSON] ─► validate
                            │
 CSV ──────────────► rules.py (engine) ◄────┘
                            │
                            ▼
                       report.py ─► pass/fail report + summary
```

- **profile.py** — per-column stats: type, blank/distinct counts, min/max, sample values.
- **llm_rules.py** — sends the profile to the LLM; parses + validates the returned rules; drops any that reference missing columns. Also has `baseline_rules()` for a no-LLM heuristic.
- **rules.py** — the `Rule` schema and the engine. Supported checks: `not_null`, `unique`, `range`, `allowed_values`, `regex`, `row_count_min`.
- **report.py** — runs rules, formats the report, returns a summary.
- **runner.py** — ties the steps together (plain functions; drop into cron/Airflow later).

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env      # add an API key for LLM-proposed rules (optional)
```

## Usage

```bash
python cli.py check data/customers.csv          # LLM proposes the rules
python cli.py check data/customers.csv --no-llm # heuristic rules, no key needed
```

Exit code is nonzero when any `error`-severity rule fails, so it drops straight
into CI or a pipeline gate.

## Extending

Add a new check by adding a branch in `rules.run_rule` and listing it in `CHECKS`
and the LLM system prompt. That's the only place check logic lives.

## Stack

Python · pandas · Anthropic/OpenAI SDK
