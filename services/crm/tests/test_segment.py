"""Tests for the segment DSL: the in-memory evaluator (used by preview) and the
SQL compiler (used by approve). These mirror each other and both sit on the
trust boundary between the AI co-pilot and the database."""

from datetime import datetime, timedelta, timezone

import pytest

from app.domain.segment import (
    SegmentError,
    compile_segment,
    evaluate_segment,
    parse_segment,
)

NOW = datetime(2026, 6, 1, tzinfo=timezone.utc)


def _cust(**kw):
    base = {
        "total_orders": 0,
        "total_spend": 0.0,
        "avg_order_value": 0.0,
        "lifecycle_stage": "active",
        "channel_optin": "email",
        "city": "Mumbai",
        "last_order_at": NOW - timedelta(days=10),
        "signup_at": NOW - timedelta(days=100),
    }
    base.update(kw)
    return base


def _seg(rules, match="all"):
    return parse_segment({"match": match, "rules": rules})


def test_numeric_ops_do_not_trigger_membership_check():
    # Regression: a dict-dispatch comparator evaluated `left in right` for every
    # op, so a numeric `gt` against an int blew up with `3 in 0`. Explicit
    # branching must keep numeric ops away from the `in` path.
    seg = _seg([{"field": "total_orders", "op": "gt", "value": 0}])
    customers = [_cust(total_orders=3), _cust(total_orders=0)]
    matched = evaluate_segment(seg, customers, now=NOW)
    assert len(matched) == 1
    assert matched[0]["total_orders"] == 3


@pytest.mark.parametrize(
    "op,value,field_val,expected",
    [
        ("gte", 5, 5, True),
        ("gte", 5, 4, False),
        ("lt", 100.0, 99.0, True),
        ("lte", 2, 3, False),
        ("neq", 1, 2, True),
        ("eq", 7, 7, True),
    ],
)
def test_scalar_comparisons(op, value, field_val, expected):
    seg = _seg([{"field": "total_orders", "op": op, "value": value}])
    matched = evaluate_segment(seg, [_cust(total_orders=field_val)], now=NOW)
    assert bool(matched) is expected


def test_in_operator_on_enum():
    seg = _seg(
        [{"field": "lifecycle_stage", "op": "in", "value": ["lapsed", "at_risk"]}]
    )
    customers = [
        _cust(lifecycle_stage="lapsed"),
        _cust(lifecycle_stage="vip"),
        _cust(lifecycle_stage="at_risk"),
    ]
    assert len(evaluate_segment(seg, customers, now=NOW)) == 2


def test_match_any_vs_all():
    rules = [
        {"field": "lifecycle_stage", "op": "eq", "value": "vip"},
        {"field": "total_spend", "op": "gt", "value": 10000.0},
    ]
    cust = [_cust(lifecycle_stage="vip", total_spend=0.0)]
    assert len(evaluate_segment(_seg(rules, "all"), cust, now=NOW)) == 0
    assert len(evaluate_segment(_seg(rules, "any"), cust, now=NOW)) == 1


def test_derived_days_since_last_order():
    seg = _seg([{"field": "days_since_last_order", "op": "gte", "value": 30}])
    recent = _cust(last_order_at=NOW - timedelta(days=5))
    stale = _cust(last_order_at=NOW - timedelta(days=60))
    matched = evaluate_segment(seg, [recent, stale], now=NOW)
    assert len(matched) == 1
    assert matched[0]["last_order_at"] == stale["last_order_at"]


def test_unknown_field_is_rejected_at_parse():
    with pytest.raises(SegmentError):
        parse_segment({"match": "all", "rules": [
            {"field": "ssn", "op": "eq", "value": "x"}]})


def test_bad_operator_for_type_is_rejected():
    # `in` is not valid for a numeric field.
    with pytest.raises(SegmentError):
        parse_segment({"match": "all", "rules": [
            {"field": "total_orders", "op": "in", "value": [1, 2]}]})


def test_compiler_parameterizes_values():
    # The injection defense: values become bound parameters, never inlined into
    # the SQL string. A hostile string can't escape the parameter slot.
    seg = _seg([{"field": "city", "op": "eq", "value": "'); DROP TABLE customers;--"}])
    sql, params = compile_segment(seg, now=NOW)
    assert "DROP TABLE" not in sql
    assert any("DROP TABLE" in str(v) for v in params.values())
    assert ":" in sql  # uses a named bind parameter
