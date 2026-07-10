"""Tests for the deterministic engine (no network / no LLM needed)."""
import pandas as pd

from src.rules import Rule, run_rule


def _df():
    return pd.DataFrame({
        "id": ["1", "2", "2", "4"],
        "email": ["a@b.com", "bad", "c@d.com", ""],
        "age": ["30", "-5", "200", "40"],
        "country": ["US", "US", "USA", "UK"],
    })


def test_not_null():
    r = Rule(id="e_nn", check="not_null", column="email")
    assert run_rule(r, _df()).failed_count == 1


def test_unique():
    r = Rule(id="id_u", check="unique", column="id")
    assert run_rule(r, _df()).failed_count == 1


def test_range():
    r = Rule(id="age_r", check="range", column="age", params={"min": 0, "max": 120})
    assert run_rule(r, _df()).failed_count == 2  # -5 and 200


def test_allowed_values():
    r = Rule(id="c_av", check="allowed_values", column="country",
             params={"values": ["US", "UK"]})
    assert run_rule(r, _df()).failed_count == 1  # "USA"


def test_regex_email():
    r = Rule(id="e_re", check="regex", column="email",
             params={"pattern": r"[^@\s]+@[^@\s]+\.[^@\s]+"})
    assert run_rule(r, _df()).failed_count == 1  # "bad"


def test_row_count_min():
    r = Rule(id="rc", check="row_count_min", params={"min": 10})
    assert run_rule(r, _df()).passed is False
