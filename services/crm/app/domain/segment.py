"""The Segment DSL — a small, closed grammar for describing an audience.

Why a DSL instead of letting the model write SQL? Two reasons, both defensible
on camera:

  1. Safety. The AI co-pilot turns natural language into a *segment*, and that
     segment is untrusted model output derived from untrusted marketer/customer
     text. If we let it emit SQL we'd be one prompt-injection away from
     `DROP TABLE`. Instead the model may only emit this JSON grammar; we validate
     every field against a fixed schema, then *we* compile it to parameterized
     SQL. The model never touches the database.

  2. Inspectability. The grammar is human-readable, so the marketer sees the rule
     ("ordered ≥ 1 time AND last_order_at before 60 days ago") and can edit it.
     Never send to a black-box audience.

The grammar (intentionally tiny):

    Segment    := { "match": "all" | "any", "rules": [Rule, ...] }
    Rule       := { "field": Field, "op": Op, "value": <json> }
    Field      := one of FIELDS below (closed set, bound to the real schema)
    Op         := one of OPS below
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal


class SegmentError(ValueError):
    """Raised when a segment fails validation. Surfaced to the user, never the DB."""


# The closed set of queryable fields. Adding a field here is the *only* way to
# make it reachable by a generated segment — the model cannot invent columns.
# Each maps to a (sql_expression, type) the compiler knows how to parameterize.
FIELDS: dict[str, str] = {
    "total_orders": "int",        # lifetime order count
    "total_spend": "money",       # lifetime spend, minor units
    "days_since_last_order": "int_derived",
    "days_since_signup": "int_derived",
    "lifecycle_stage": "enum",    # new | active | at_risk | lapsed | vip
    "channel_optin": "enum",      # whatsapp | sms | email | rcs
    "city": "string",
    "avg_order_value": "money",
}

LIFECYCLE_STAGES = {"new", "active", "at_risk", "lapsed", "vip"}
CHANNELS = {"whatsapp", "sms", "email", "rcs"}

OPS: dict[str, set[str]] = {
    "int": {"eq", "neq", "gt", "gte", "lt", "lte"},
    "int_derived": {"eq", "neq", "gt", "gte", "lt", "lte"},
    "money": {"eq", "neq", "gt", "gte", "lt", "lte"},
    "enum": {"eq", "neq", "in"},
    "string": {"eq", "neq", "in"},
}


@dataclass(frozen=True, slots=True)
class Rule:
    field: str
    op: str
    value: Any


@dataclass(frozen=True, slots=True)
class Segment:
    match: Literal["all", "any"]
    rules: tuple[Rule, ...]

    def describe(self) -> str:
        """Human sentence shown in the HITL review panel."""
        joiner = " AND " if self.match == "all" else " OR "
        return joiner.join(f"{r.field} {r.op} {r.value!r}" for r in self.rules)


def _validate_value(field: str, op: str, value: Any) -> Any:
    ftype = FIELDS[field]
    if field == "lifecycle_stage":
        vals = value if isinstance(value, list) else [value]
        if not all(v in LIFECYCLE_STAGES for v in vals):
            raise SegmentError(f"invalid lifecycle_stage in {value!r}")
    if field == "channel_optin":
        vals = value if isinstance(value, list) else [value]
        if not all(v in CHANNELS for v in vals):
            raise SegmentError(f"invalid channel in {value!r}")
    if op == "in" and not isinstance(value, list):
        raise SegmentError("op 'in' requires a list value")
    if ftype in {"int", "int_derived", "money"} and not isinstance(value, (int, float)):
        raise SegmentError(f"field {field} expects a number, got {type(value).__name__}")
    return value


def parse_segment(raw: dict) -> Segment:
    """Validate untrusted JSON into a Segment, or raise SegmentError.

    This is the trust boundary: nothing past this point is model-controlled
    except validated, typed values that the compiler will parameterize.
    """
    if not isinstance(raw, dict):
        raise SegmentError("segment must be an object")
    match = raw.get("match", "all")
    if match not in ("all", "any"):
        raise SegmentError("match must be 'all' or 'any'")
    rules_raw = raw.get("rules")
    if not isinstance(rules_raw, list) or not rules_raw:
        raise SegmentError("segment must have at least one rule")
    if len(rules_raw) > 12:
        raise SegmentError("too many rules (max 12)")

    rules: list[Rule] = []
    for r in rules_raw:
        if not isinstance(r, dict):
            raise SegmentError("each rule must be an object")
        field = r.get("field")
        op = r.get("op")
        if field not in FIELDS:
            raise SegmentError(f"unknown field {field!r}")
        if op not in OPS[FIELDS[field]]:
            raise SegmentError(f"op {op!r} not allowed for field {field!r}")
        value = _validate_value(field, op, r.get("value"))
        rules.append(Rule(field=field, op=op, value=value))

    return Segment(match=match, rules=tuple(rules))


# --- Compilation to parameterized SQL ---------------------------------------
# The compiler is the only place a segment becomes SQL, and it always uses bound
# parameters (:p0, :p1, ...) — values are data, never string-concatenated.

_SQL_OPS = {"eq": "=", "neq": "<>", "gt": ">", "gte": ">=", "lt": "<", "lte": "<="}

# Maps a DSL field to a SQL expression over the customer projection view. Derived
# fields are computed against `now` which the compiler binds as a parameter.
_FIELD_SQL = {
    "total_orders": "c.total_orders",
    "total_spend": "c.total_spend",
    "avg_order_value": "c.avg_order_value",
    "lifecycle_stage": "c.lifecycle_stage",
    "channel_optin": "c.channel_optin",
    "city": "c.city",
    "days_since_last_order": "EXTRACT(DAY FROM (:now - c.last_order_at))",
    "days_since_signup": "EXTRACT(DAY FROM (:now - c.signup_at))",
}


def compile_segment(seg: Segment, now: datetime | None = None) -> tuple[str, dict]:
    """Compile a validated Segment into a (where_clause, params) pair using only
    bound parameters. Returns SQL safe to drop into a parameterized query."""
    now = now or datetime.now(timezone.utc)
    params: dict[str, Any] = {"now": now}
    clauses: list[str] = []
    for i, rule in enumerate(seg.rules):
        col = _FIELD_SQL[rule.field]
        if rule.op == "in":
            keys = []
            for j, v in enumerate(rule.value):
                k = f"p{i}_{j}"
                params[k] = v
                keys.append(f":{k}")
            clauses.append(f"{col} IN ({', '.join(keys)})")
        else:
            k = f"p{i}"
            params[k] = rule.value
            clauses.append(f"{col} {_SQL_OPS[rule.op]} :{k}")
    glue = " AND " if seg.match == "all" else " OR "
    return f"({glue.join(clauses)})", params


# --- In-memory evaluation ----------------------------------------------------
# Used by the SQLite dev path and by tests: evaluate a validated Segment against
# a customer record (a plain dict with the FIELDS keys + last_order_at/signup_at).
# Same Segment, same semantics as the SQL compiler — just no database.

def _cmp(op: str, left: Any, right: Any) -> bool:
    if left is None:
        # A missing value only satisfies "not equal"; every other comparison is
        # false rather than raising.
        return op == "neq"
    # Explicit branching (not a dict) so we never evaluate the wrong operator —
    # e.g. `left in right` must not run when the op is a numeric comparison.
    if op == "eq":
        return left == right
    if op == "neq":
        return left != right
    if op == "gt":
        return left > right
    if op == "gte":
        return left >= right
    if op == "lt":
        return left < right
    if op == "lte":
        return left <= right
    if op == "in":
        return left in right
    raise SegmentError(f"unknown op {op!r}")


def evaluate_rule(rule: Rule, customer: dict, now: datetime) -> bool:
    if rule.field == "days_since_last_order":
        ts = customer.get("last_order_at")
        left = (now - ts).days if ts else None
    elif rule.field == "days_since_signup":
        ts = customer.get("signup_at")
        left = (now - ts).days if ts else None
    else:
        left = customer.get(rule.field)
    return _cmp(rule.op, left, rule.value)


def evaluate_segment(seg: Segment, customers: list[dict], now: datetime | None = None) -> list[dict]:
    """Return the customers matching the segment. Mirrors compile_segment."""
    now = now or datetime.now(timezone.utc)
    out = []
    for c in customers:
        results = [evaluate_rule(r, c, now) for r in seg.rules]
        if (all(results) if seg.match == "all" else any(results)):
            out.append(c)
    return out
