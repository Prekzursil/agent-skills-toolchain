#!/usr/bin/env python3
"""Gate-decision record, live event harvest, field coverage, and rate-quoting floor.

RES-0099: what must be recorded on every gate decision so false-positive and
false-negative rates can be computed later, where that record lives, and the
minimum sample before a rate may be quoted.

Named probes and the research artifact import this module so they cannot drift.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
EVENTS_REL = "command-center/events/EVENTS.jsonl"
EVENTS_JSONL = REPO / EVENTS_REL
PROBES_ROOT = REPO / "command-center" / "p2-wave" / "probes"
SKIP_UNIT = "RES-0099"

SCHEMA_VERSION = "gate.decision.v1"
EVENT_TYPE = "gate.decision"
RECORD_LIVES_AT = EVENTS_REL

Z95 = 1.959963984540054
# Rule of three: 0 errors in n trials => ~95% upper bound 3/n. n=30 => 10%.
MIN_LABELLED_N = 30
# A gate with no known-bad fixture has an unmeasurable FN (catalog REL-0019).
MIN_PER_CLASS = 5

FIRE_STATES = frozenset(
    {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT", "FAIL", "ERROR", "NO-GO", "RED"}
)
SILENT_STATES = frozenset(
    {"SUCCESS", "PASS", "DELIVERED", "GO", "GREEN", "OK"}
)
HARVEST_NAMES = frozenset(
    {
        "_validate_out.json",
        "_measure_out.json",
        "_strike_out.json",
        "SUBAGENT-RETURN.json",
    }
)

# native = first-class names. proxy = related keys that are NOT the field.
FIELDS: list[dict[str, Any]] = [
    {
        "name": "schema_version",
        "native": ["schema_version"],
        "proxy": [],
        "why": "Pin the record shape so later rate code does not silently misread old lines.",
    },
    {
        "name": "event_type",
        "native": ["event_type"],
        "proxy": [],
        "why": "EVENTS.jsonl is mixed; rates must select gate.decision rows only.",
    },
    {
        "name": "record_id",
        "native": ["record_id"],
        "proxy": ["id", "unit_id"],
        "why": "Stable join key. A unit id is a proxy, not unique per firing.",
    },
    {
        "name": "ts",
        "native": ["ts", "when", "captured_at", "timestamp"],
        "proxy": [],
        "why": "Window the canary; a rate without time cannot be reproduced.",
    },
    {
        "name": "gate_id",
        "native": ["gate_id"],
        "proxy": [],
        "why": "FP/FN are per-gate. A unit id is not a gate id.",
    },
    {
        "name": "command",
        "native": ["command"],
        "proxy": [],
        "why": "The exact invocation the reviewer re-runs on the other shell.",
    },
    {
        "name": "exit_code",
        "native": ["exit_code", "exit"],
        "proxy": [],
        "why": "Observed process result, independent of the prose state field.",
    },
    {
        "name": "predicted_class",
        "native": ["predicted_class"],
        "proxy": ["state", "status"],
        "why": "POSITIVE=gate fired (block/fail). NEGATIVE=gate silent (pass). state is a proxy.",
    },
    {
        "name": "ground_truth_class",
        "native": ["ground_truth_class", "ground_truth", "y_true"],
        "proxy": [],
        "why": "POSITIVE=should-fire, NEGATIVE=should-not, UNLABELLED=must not enter the denominator.",
    },
    {
        "name": "truth_source",
        "native": ["truth_source", "label_source"],
        "proxy": [],
        "why": "fixture | human-adjudication | planted-canary. Unsourced labels cannot audit the rate.",
    },
    {
        "name": "input_fingerprint",
        "native": ["input_fingerprint"],
        "proxy": [],
        "why": "sha256 of the bytes the gate actually saw, not of a later rewritten artifact.",
    },
    {
        "name": "fixture_id",
        "native": ["fixture_id"],
        "proxy": [],
        "why": "Membership in the labelled set published before the measurement.",
    },
    {
        "name": "denominator_eligible",
        "native": ["denominator_eligible"],
        "proxy": [],
        "why": "False when unlabelled. Prevents mixing live traffic into a quoted rate.",
    },
    {
        "name": "confusion",
        "native": ["confusion"],
        "proxy": [],
        "why": "TP|FP|TN|FN|UNLABELLED|ERROR, derived only when both classes are labelled.",
    },
    {
        "name": "shell",
        "native": ["shell"],
        "proxy": [],
        "why": "Reviewer requirement: PowerShell 7 vs Git Bash reproduction.",
    },
    {
        "name": "git_rev",
        "native": ["git_rev"],
        "proxy": ["rev", "commit"],
        "why": "Which tree produced the decision.",
    },
    {
        "name": "worktree_id",
        "native": ["worktree_id"],
        "proxy": [],
        "why": "Isolate sibling-worktree contamination from the rate.",
    },
    {
        "name": "prev_digest",
        "native": ["prev_digest"],
        "proxy": [],
        "why": "CC-0007 hash chain: a silent rewrite of a past decision must break the chain.",
    },
    {
        "name": "digest",
        "native": ["digest", "event_digest"],
        "proxy": [],
        "why": "This record's digest. Artifact sha256 is a different object and must not be reused.",
    },
]


def wilson_interval(k: int, n: int, z: float = Z95) -> tuple[float, float, float]:
    """Return (point, lo, hi) for k successes in n Bernoulli trials."""
    if n <= 0:
        return 0.0, 0.0, 1.0
    p = k / n
    z2 = z * z
    den = 1.0 + z2 / n
    center = (p + z2 / (2.0 * n)) / den
    margin = z * math.sqrt((p * (1.0 - p) + z2 / (4.0 * n)) / n) / den
    return p, max(0.0, center - margin), min(1.0, center + margin)


def rule_of_three_upper(n: int) -> float:
    if n <= 0:
        return 1.0
    return min(1.0, 3.0 / n)


def quote_rate(k: int, n: int, n_complement: int, kind: str) -> dict[str, Any]:
    """Refuse to quote when the sample is below the floor.

    n is this class's labelled count; k is errors in that class.
    n_complement is the other labelled class (known-bad for FP, known-good for FN).
    """
    eligible = n >= MIN_LABELLED_N and n_complement >= MIN_PER_CLASS and n >= MIN_PER_CLASS
    point, lo, hi = wilson_interval(k, n)
    rot3 = rule_of_three_upper(n) if k == 0 else None
    if not eligible:
        return {
            "quoted": False,
            "status": "RATE-NOT-QUOTED",
            "kind": kind,
            "k": k,
            "n": n,
            "complement_n": n_complement,
            "reason": (
                f"RATE-NOT-QUOTED: {kind} needs labelled n>={MIN_LABELLED_N} on this "
                f"class and >={MIN_PER_CLASS} on the complementary class "
                f"(got n={n} complement={n_complement}). "
                f"Rule-of-three 95% upper at this n is {rule_of_three_upper(n):.3f}."
            ),
            "wilson_point_if_forced": round(point, 6),
            "wilson_lo_if_forced": round(lo, 6),
            "wilson_hi_if_forced": round(hi, 6),
            "rule_of_three_upper": rot3,
            "min_labelled_n": MIN_LABELLED_N,
            "min_per_class": MIN_PER_CLASS,
        }
    return {
        "quoted": True,
        "status": "QUOTED",
        "kind": kind,
        "k": k,
        "n": n,
        "complement_n": n_complement,
        "point": round(point, 6),
        "wilson95_lo": round(lo, 6),
        "wilson95_hi": round(hi, 6),
        "wilson95_lo": round(lo, 6),
        "wilson95_hi": round(hi, 6),
        "rule_of_three_upper": rot3,
        "min_labelled_n": MIN_LABELLED_N,
        "min_per_class": MIN_PER_CLASS,
    }


def collect_keys(obj: Any, prefix: str = "", out: set[str] | None = None) -> set[str]:
    if out is None:
        out = set()
    if isinstance(obj, dict):
        for k, v in obj.items():
            key = str(k)
            out.add(key)
            nxt = f"{prefix}.{key}" if prefix else key
            if prefix:
                out.add(nxt)
            collect_keys(v, nxt, out)
    elif isinstance(obj, list):
        for item in obj[:12]:
            collect_keys(item, f"{prefix}[]" if prefix else "[]", out)
    return out


def derive_predicted(obj: dict) -> str | None:
    """Proxy predicted class from existing state/status. Not a label."""
    candidates: list[Any] = [obj.get("state"), obj.get("status")]
    doc = obj.get("doc")
    if isinstance(doc, dict):
        candidates.append(doc.get("state"))
    ru = obj.get("ready_units")
    if isinstance(ru, dict) and "delivered" in ru:
        return "NEGATIVE" if ru.get("delivered") is True else "POSITIVE"
    for raw in candidates:
        if isinstance(raw, str):
            u = raw.upper()
            if u in FIRE_STATES:
                return "POSITIVE"
            if u in SILENT_STATES:
                return "NEGATIVE"
    return None


def load_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    if not path.is_file() or path.stat().st_size <= 0:
        return rows
    text = path.read_text(encoding="utf-8", errors="replace")
    for i, line in enumerate(text.splitlines()):
        s = line.strip()
        if not s:
            continue
        try:
            rec = json.loads(s)
        except json.JSONDecodeError:
            rows.append({"_parse_error": True, "_line": i + 1})
            continue
        if isinstance(rec, dict):
            rows.append(rec)
        else:
            rows.append({"_non_object": True, "_line": i + 1})
    return rows


def record_from_path(rel: str) -> dict[str, Any] | None:
    """Load one on-disk JSON file into a harvest record. None if unreadable."""
    path = REPO / rel
    if not path.is_file():
        return None
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(doc, dict):
        return None
    keys = collect_keys(doc)
    return {
        "path": rel.replace("\\", "/"),
        "kind": path.name,
        "keys": sorted(keys),
        "predicted_derived": derive_predicted(doc),
        "native_predicted": "predicted_class" in keys,
        "native_truth": any(
            k in keys for k in ("ground_truth_class", "ground_truth", "y_true")
        ),
    }


def records_from_paths(rels: list[str]) -> tuple[list[dict[str, Any]], list[str]]:
    """Replay a frozen path list. Returns (records, missing_relpaths)."""
    rows: list[dict[str, Any]] = []
    missing: list[str] = []
    for rel in rels:
        rec = record_from_path(str(rel).replace("\\", "/"))
        if rec is None:
            missing.append(str(rel))
        else:
            rows.append(rec)
    return rows, missing


def harvest_live_gate_json() -> list[dict[str, Any]]:
    """Real on-disk gate-like JSON. Not invented. Excludes this unit's own files."""
    rows: list[dict[str, Any]] = []
    if not PROBES_ROOT.is_dir():
        return rows
    paths = sorted(
        p for p in PROBES_ROOT.rglob("*") if p.is_file() and p.name in HARVEST_NAMES
    )
    for path in paths:
        rel = path.relative_to(REPO).as_posix()
        if SKIP_UNIT in rel.split("/"):
            continue
        rec = record_from_path(rel)
        if rec is not None:
            rows.append(rec)
    return rows


def field_status(field: dict, keyset: set[str]) -> str:
    if any(a in keyset for a in field["native"]):
        return "already-present"
    if any(a in keyset for a in field["proxy"]):
        return "proxy-only-must-add-first-class"
    return "would-have-to-be-added"


def coverage_for_records(records: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(records)
    field_rows = []
    for field in FIELDS:
        already = 0
        proxy = 0
        missing = 0
        for rec in records:
            keys = set(rec.get("keys") or [])
            st = field_status(field, keys)
            if st == "already-present":
                already += 1
            elif st == "proxy-only-must-add-first-class":
                proxy += 1
            else:
                missing += 1
        if n == 0:
            status = "unmeasurable-no-events"
        elif already == n:
            status = "already-present"
        elif missing == n and proxy == 0:
            status = "would-have-to-be-added"
        elif already == 0 and proxy > 0:
            status = "proxy-only-must-add-first-class"
        else:
            status = "partial"
        field_rows.append(
            {
                "name": field["name"],
                "why": field["why"],
                "native_aliases": field["native"],
                "proxy_aliases": field["proxy"],
                "n": n,
                "already_present": already,
                "proxy_only": proxy,
                "would_have_to_be_added": missing,
                "status": status,
            }
        )
    labelled = sum(1 for r in records if r.get("native_truth"))
    derived_pred = sum(1 for r in records if r.get("predicted_derived"))
    native_pred = sum(1 for r in records if r.get("native_predicted"))
    if n == 0:
        block = "Zero events: a rate over an empty set is undefined."
    elif labelled == 0:
        block = (
            "No harvested record carries ground_truth_class, so every row is "
            "UNLABELLED and must not enter a false-positive or false-negative "
            "denominator."
        )
    else:
        block = "insufficient labelled sample"
    return {
        "record_count": n,
        "labelled_ground_truth_count": labelled,
        "native_predicted_class_count": native_pred,
        "derived_predicted_from_state_count": derived_pred,
        "fields": field_rows,
        "rate_may_be_quoted": False,
        "rate_quote_block_reason": block,
    }


def analyze() -> dict[str, Any]:
    jsonl_present = EVENTS_JSONL.is_file() and EVENTS_JSONL.stat().st_size > 0
    jsonl_rows_raw = load_jsonl(EVENTS_JSONL) if jsonl_present else []
    jsonl_mapped = []
    for rec in jsonl_rows_raw:
        keys = collect_keys(rec)
        jsonl_mapped.append(
            {
                "path": EVENTS_REL,
                "kind": "EVENTS.jsonl",
                "keys": sorted(keys),
                "predicted_derived": derive_predicted(rec)
                if not rec.get("_parse_error")
                else None,
                "native_predicted": "predicted_class" in keys,
                "native_truth": any(
                    k in keys for k in ("ground_truth_class", "ground_truth", "y_true")
                ),
            }
        )
    harvested = harvest_live_gate_json()
    # Probe1 freezes harvested_paths and reloads each path as a single JSON
    # object. EVENTS.jsonl is JSONL, so it cannot be that corpus. Primary
    # field_coverage is always the harvest. The catalog-named log is replayed
    # separately as events_jsonl_coverage.
    replay_source = "harvested-live-probe-json"
    replay_records = harvested
    cov = coverage_for_records(replay_records)
    jsonl_cov = coverage_for_records(jsonl_mapped)
    added = [
        f["name"]
        for f in cov["fields"]
        if f["status"]
        in {
            "would-have-to-be-added",
            "proxy-only-must-add-first-class",
            "partial",
            "unmeasurable-no-events",
        }
    ]
    present = [f["name"] for f in cov["fields"] if f["status"] == "already-present"]
    jsonl_added = [
        f["name"]
        for f in jsonl_cov["fields"]
        if f["status"] != "already-present"
    ]
    jsonl_present_fields = [
        f["name"] for f in jsonl_cov["fields"] if f["status"] == "already-present"
    ]
    jsonl_union_keys: set[str] = set()
    jsonl_verbs: list[str] = []
    jsonl_ids: list[str] = []
    jsonl_event_types: list[str] = []
    gate_decision_rows = 0
    for rec in jsonl_rows_raw:
        if not isinstance(rec, dict):
            continue
        jsonl_union_keys.update(str(k) for k in rec.keys())
        if isinstance(rec.get("verb"), str):
            jsonl_verbs.append(rec["verb"])
        if rec.get("id") is not None:
            jsonl_ids.append(str(rec["id"]))
        et = rec.get("event_type")
        if isinstance(et, str):
            jsonl_event_types.append(et)
            if et == EVENT_TYPE:
                gate_decision_rows += 1
    return {
        "events_jsonl": {
            "path": EVENTS_REL,
            "present": jsonl_present,
            "bytes": EVENTS_JSONL.stat().st_size if jsonl_present else 0,
            "line_records": len(jsonl_rows_raw),
            "gate_decision_rows": gate_decision_rows,
            "verbs": jsonl_verbs,
            "ids": jsonl_ids,
            "event_types": jsonl_event_types,
            "union_keys": sorted(jsonl_union_keys),
        },
        "events_jsonl_coverage": {
            "against": EVENTS_REL if jsonl_present else "EVENTS.jsonl-absent",
            "record_count": jsonl_cov["record_count"],
            "labelled_ground_truth_count": jsonl_cov["labelled_ground_truth_count"],
            "native_predicted_class_count": jsonl_cov["native_predicted_class_count"],
            "derived_predicted_from_state_count": jsonl_cov["derived_predicted_from_state_count"],
            "fields_already_present": jsonl_present_fields,
            "fields_that_would_have_to_be_added": jsonl_added,
            "fields": jsonl_cov["fields"],
            "rate_may_be_quoted": jsonl_cov["rate_may_be_quoted"],
            "rate_quote_block_reason": jsonl_cov["rate_quote_block_reason"],
        },
        "replay_source": replay_source,
        "harvested_probe_json_count": len(harvested),
        "harvested_paths": [r["path"] for r in harvested],
        "coverage": cov,
        "fields_already_present": present,
        "fields_that_would_have_to_be_added": added,
        "min_sample": {
            "min_labelled_n": MIN_LABELLED_N,
            "min_per_class": MIN_PER_CLASS,
            "why": (
                "A binomial rate with 0 observed errors has a 95% rule-of-three "
                f"upper bound of 3/n. At n={MIN_LABELLED_N} that bound is "
                f"{rule_of_three_upper(MIN_LABELLED_N):.1%}. Quoting 0% FP or FN "
                "below that n is an overclaim. The complementary-class floor of "
                f"{MIN_PER_CLASS} is the REL-0019 rule: a gate with no known-bad "
                "fixture has an unmeasurable false-negative rate and must be "
                "published NOT-CHECKED, never given a passing threshold."
            ),
            "wilson_z95": Z95,
            "rule_of_three_upper_at_min_n": round(rule_of_three_upper(MIN_LABELLED_N), 6),
        },
        "record_lives_at": RECORD_LIVES_AT,
        "schema_version": SCHEMA_VERSION,
        "event_type": EVENT_TYPE,
        "field_names": [f["name"] for f in FIELDS],
    }


def confusion(predicted: str, truth: str) -> str:
    if predicted == "ERROR":
        return "ERROR"
    if truth == "UNLABELLED" or predicted in {None, "UNKNOWN"}:
        return "UNLABELLED"
    if predicted == "POSITIVE" and truth == "POSITIVE":
        return "TP"
    if predicted == "POSITIVE" and truth == "NEGATIVE":
        return "FP"
    if predicted == "NEGATIVE" and truth == "NEGATIVE":
        return "TN"
    if predicted == "NEGATIVE" and truth == "POSITIVE":
        return "FN"
    return "ERROR"


def empty_record_template() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "event_type": EVENT_TYPE,
        "record_id": None,
        "ts": None,
        "gate_id": None,
        "command": None,
        "exit_code": None,
        "predicted_class": None,
        "ground_truth_class": "UNLABELLED",
        "truth_source": None,
        "input_fingerprint": None,
        "fixture_id": None,
        "denominator_eligible": False,
        "confusion": "UNLABELLED",
        "shell": None,
        "git_rev": None,
        "worktree_id": None,
        "prev_digest": None,
        "digest": None,
    }


coverage_for_records = coverage_for_records


if __name__ == "__main__":
    print(json.dumps(analyze(), indent=2, sort_keys=True))
