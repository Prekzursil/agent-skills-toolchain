"""Generic stopping-condition evaluator.

Walks predicate specs. Does not branch on a condition id. An encoding may
carry an amendment slot keyed by a ruling id; any condition can use that
slot. Aggregation never folds NOT-CHECKED into a pass.
"""
from __future__ import annotations

from typing import Any

VERDICTS = frozenset({"TRUE", "FALSE", "NOT-CHECKED"})
CONFIDENCE = frozenset({"QUOTED", "RECONSTRUCTED", "ABSENT-VERBATIM"})


def blank_state() -> dict:
    return {
        "selected_option_ids": None,
        "dispositions": None,
        "required_tests": None,
        "suites": None,
        "compatibility_cells": None,
        "benchmark": None,
        "vuln_scan_fresh": None,
        "license_scan_fresh": None,
        "docs_code_agree": None,
        "canary_succeeded": None,
        "marketplace_release_succeeded": None,
        "merged_pr": None,
        "receipts": None,
        "rollback_tested": None,
        "unknowns": None,
        "counts": {},
        "protocol_ids": None,
        "preset_ids": None,
        "rulings": {},
        "release_mode": None,
        "canary_channel_present": None,
        "verbatim_spec_present": False,
    }


def dig(state: dict, key: Any) -> Any:
    if key is None:
        return None
    if isinstance(key, (list, tuple)):
        cur: Any = state
        for k in key:
            if not isinstance(cur, dict):
                return None
            cur = cur.get(k)
        return cur
    if isinstance(key, str) and "." in key:
        return dig(state, key.split("."))
    if isinstance(state, dict):
        return state.get(key)
    return None


def ruling_recorded(state: dict, ruling_id: str) -> bool:
    rec = (state.get("rulings") or {}).get(ruling_id)
    if not isinstance(rec, dict):
        return False
    return rec.get("recorded") is True


def active_spec(encoding: dict, state: dict) -> tuple[dict, bool, str]:
    """Return (spec, amendment_applied, live_text). Generic amendment slot."""
    amendment = encoding.get("amendment")
    as_written = encoding["as_written"]
    text = encoding.get("text") or ""
    if not isinstance(amendment, dict):
        return as_written, False, text
    rid = str(amendment.get("ruling_id") or "")
    if rid and ruling_recorded(state, rid):
        amended = amendment.get("amended")
        if not isinstance(amended, dict):
            raise RuntimeError("amendment.amended missing")
        live_text = str(amendment.get("text") or text)
        return amended, True, live_text
    return as_written, False, text


def _combine_all(parts: list[str]) -> str:
    if any(p == "FALSE" for p in parts):
        return "FALSE"
    if any(p == "NOT-CHECKED" for p in parts):
        return "NOT-CHECKED"
    return "TRUE"


def _combine_any(parts: list[str]) -> str:
    if any(p == "TRUE" for p in parts):
        return "TRUE"
    if any(p == "NOT-CHECKED" for p in parts):
        return "NOT-CHECKED"
    return "FALSE"


def eval_spec(spec: dict, state: dict) -> tuple[str, str]:
    """Return (verdict, evidence). Verdict is one of VERDICTS."""
    kind = spec.get("kind")
    if kind == "absent_verbatim":
        line = spec.get("spec_line")
        return (
            "NOT-CHECKED",
            f"verbatim _USER-PROMPTS.md:{line} absent; predicate not guessed",
        )
    if kind == "all_of":
        parts = []
        notes = []
        for p in spec.get("parts") or []:
            v, e = eval_spec(p, state)
            parts.append(v)
            notes.append(e)
        return _combine_all(parts), " | ".join(notes)
    if kind == "any_of":
        parts = []
        notes = []
        for p in spec.get("parts") or []:
            v, e = eval_spec(p, state)
            parts.append(v)
            notes.append(e)
        return _combine_any(parts), " | ".join(notes)
    if kind == "bool":
        val = dig(state, spec.get("key"))
        key = spec.get("key")
        if val is True:
            return "TRUE", f"{key}=true"
        if val is False:
            return "FALSE", f"{key}=false"
        return "NOT-CHECKED", f"{key} missing"
    if kind == "receipts_green":
        recs = state.get("receipts")
        ids = list(spec.get("ids") or [])
        if not isinstance(recs, dict):
            return "NOT-CHECKED", "receipts map missing: " + ",".join(ids)
        missing = []
        bad = []
        ok = []
        for uid in ids:
            row = recs.get(uid)
            if not isinstance(row, dict):
                missing.append(uid)
                continue
            st = str(row.get("state") or "").upper()
            if st == "SUCCESS":
                ok.append(uid)
            else:
                bad.append(f"{uid}:{st or 'empty'}")
        if bad:
            return "FALSE", "receipts not green: " + ",".join(bad)
        if missing:
            return "NOT-CHECKED", "receipts missing: " + ",".join(missing)
        return "TRUE", "receipts green: " + ",".join(ok)
    if kind == "closed_set":
        ids = dig(state, spec.get("ids_key"))
        mapping = dig(state, spec.get("map_key"))
        if not isinstance(ids, list) or not isinstance(mapping, dict):
            return (
                "NOT-CHECKED",
                f"{spec.get('ids_key')}/{spec.get('map_key')} missing",
            )
        if spec.get("required_nonempty") and len(ids) == 0:
            return "NOT-CHECKED", "selected option id list empty"
        allowed = set(spec.get("allowed") or [])
        bad = []
        missing = []
        for oid in ids:
            disp = mapping.get(oid)
            if disp is None:
                missing.append(str(oid))
            elif disp not in allowed:
                bad.append(f"{oid}:{disp}")
        if bad:
            return "FALSE", "non-terminal dispositions: " + ",".join(bad[:12])
        if missing:
            return "NOT-CHECKED", "unmapped option ids: " + ",".join(missing[:12])
        return "TRUE", f"all {len(ids)} selected ids in {sorted(allowed)}"
    if kind == "none_red":
        tests = dig(state, spec.get("key"))
        if not isinstance(tests, list):
            return "NOT-CHECKED", f"{spec.get('key')} missing"
        if spec.get("required_nonempty") and len(tests) == 0:
            return "NOT-CHECKED", "required-test list empty"
        red = []
        unknown = []
        for t in tests:
            if not isinstance(t, dict):
                unknown.append("non-object")
                continue
            if t.get("red") is True or str(t.get("status") or "").lower() == "red":
                red.append(str(t.get("id") or "?"))
            elif t.get("red") is None and not t.get("status"):
                unknown.append(str(t.get("id") or "?"))
        if red:
            return "FALSE", "red required tests: " + ",".join(red[:12])
        if unknown:
            return "NOT-CHECKED", "required tests without status: " + ",".join(
                unknown[:12]
            )
        return "TRUE", f"no red among {len(tests)} required tests"
    if kind == "all_have":
        items = dig(state, spec.get("key"))
        field = spec.get("field")
        if not isinstance(items, list):
            return "NOT-CHECKED", f"{spec.get('key')} missing"
        if spec.get("required_nonempty") and len(items) == 0:
            return "NOT-CHECKED", f"{spec.get('key')} empty"
        missing = []
        failed = []
        for it in items:
            if not isinstance(it, dict):
                missing.append("non-object")
                continue
            val = it.get(field)
            if val is True:
                continue
            if val is False:
                failed.append(str(it.get("id") or "?"))
            else:
                missing.append(str(it.get("id") or "?"))
        if failed:
            return "FALSE", f"{field}=false: " + ",".join(failed[:12])
        if missing:
            return "NOT-CHECKED", f"{field} unset: " + ",".join(missing[:12])
        return "TRUE", f"all {len(items)} items have {field}=true"
    if kind == "cells_supported_only_with_run":
        cells = dig(state, spec.get("key"))
        if not isinstance(cells, list):
            return "NOT-CHECKED", f"{spec.get('key')} missing"
        if spec.get("required_nonempty") and len(cells) == 0:
            return "NOT-CHECKED", "compatibility cell list empty"
        bogus = []
        for c in cells:
            if not isinstance(c, dict):
                continue
            mark = str(c.get("mark") or "")
            if mark == "SUPPORTED" and not c.get("test_run"):
                bogus.append(str(c.get("id") or "?"))
        if bogus:
            return (
                "FALSE",
                "SUPPORTED without test_run: " + ",".join(bogus[:12]),
            )
        return "TRUE", f"{len(cells)} cells; no untested SUPPORTED mark"
    if kind == "benchmark":
        b = dig(state, spec.get("key"))
        if not isinstance(b, dict):
            return "NOT-CHECKED", "benchmark ledger missing"
        verdict = str(b.get("verdict") or "")
        run_ids = b.get("run_ids")
        if not isinstance(run_ids, list) or not run_ids:
            return "NOT-CHECKED", "benchmark run_ids missing"
        if verdict in {"", "UNMEASURED"}:
            return "NOT-CHECKED", "benchmark UNMEASURED"
        if verdict == "REGRESSED":
            return "FALSE", "benchmark REGRESSED run_ids=" + ",".join(
                str(x) for x in run_ids[:8]
            )
        if verdict == "IMPROVED":
            return "TRUE", "benchmark IMPROVED run_ids=" + ",".join(
                str(x) for x in run_ids[:8]
            )
        if verdict == "NEUTRAL":
            return "FALSE", "benchmark NEUTRAL (no intended improvement)"
        return "NOT-CHECKED", f"benchmark verdict={verdict}"
    if kind == "unknowns_two_part":
        unk = dig(state, spec.get("key"))
        if not isinstance(unk, list):
            return "NOT-CHECKED", "unknowns register missing"
        bad = []
        for u in unk:
            if not isinstance(u, dict):
                bad.append("non-object")
                continue
            if not u.get("settling_experiment") or not u.get("impact"):
                bad.append(str(u.get("id") or "?"))
        if bad:
            return "FALSE", "unknowns failing two-part test: " + ",".join(bad[:12])
        return "TRUE", f"{len(unk)} open unknowns pass two-part test"
    if kind == "count_ge":
        val = dig(state, spec.get("key"))
        floor = spec.get("floor")
        if not isinstance(val, int) or not isinstance(floor, int):
            return "NOT-CHECKED", f"{spec.get('key')} missing (floor={floor})"
        if val >= floor:
            return "TRUE", f"{spec.get('key')}={val} >= {floor}"
        return "FALSE", f"{spec.get('key')}={val} < {floor}"
    if kind == "disjoint_ids":
        a = dig(state, spec.get("key_a"))
        b = dig(state, spec.get("key_b"))
        if not isinstance(a, list) or not isinstance(b, list):
            return (
                "NOT-CHECKED",
                f"{spec.get('key_a')}/{spec.get('key_b')} missing",
            )
        overlap = sorted(set(a) & set(b))
        if overlap:
            return "FALSE", "id overlap: " + ",".join(str(x) for x in overlap[:12])
        return "TRUE", "disjoint id sets"
    raise RuntimeError(f"unknown predicate kind {kind!r}")


def aggregate(rows: list[dict]) -> dict:
    counts = {"TRUE": 0, "FALSE": 0, "NOT-CHECKED": 0}
    if len(rows) != 21:
        return {
            "counts": dict(counts),
            "program_complete": False,
            "program_verdict": "PROGRAM-INCOMPLETE",
            "not_checked_folded_into_pass": False,
            "reason": f"expected 21 rows, got {len(rows)}",
        }
    for row in rows:
        v = row.get("verdict")
        if v not in VERDICTS:
            raise ValueError(
                f"condition {row.get('id')} empty or absent verdict: {v!r}"
            )
        counts[v] += 1
    complete = counts["TRUE"] == 21
    blocking = []
    for row in rows:
        if row["verdict"] != "TRUE":
            blocking.append(
                {
                    "id": row.get("id"),
                    "verdict": row["verdict"],
                    "settling_probe": row.get("settling_probe"),
                }
            )
    return {
        "counts": counts,
        "program_complete": complete,
        "program_verdict": (
            "PROGRAM-COMPLETE" if complete else "PROGRAM-INCOMPLETE"
        ),
        "not_checked_folded_into_pass": False,
        "blocking": blocking,
        "true_plus_not_checked": counts["TRUE"] + counts["NOT-CHECKED"],
    }


def evaluate_encoding(encoding: dict, state: dict) -> dict:
    if encoding.get("text_confidence") not in CONFIDENCE:
        raise RuntimeError(f"bad confidence {encoding.get('id')}")
    spec, applied, live_text = active_spec(encoding, state)
    verdict, evidence = eval_spec(spec, state)
    if verdict not in VERDICTS:
        raise RuntimeError(f"non-tri-state {encoding.get('id')}: {verdict!r}")
    unsat = (
        encoding.get("as_written_satisfiability") == "UNSATISFIABLE-AS-WRITTEN"
        and not applied
    )
    row = {
        "id": encoding["id"],
        "spec_line": encoding["spec_line"],
        "text": live_text,
        "text_confidence": encoding["text_confidence"],
        "catalog_anchor": encoding.get("catalog_anchor"),
        "verdict": verdict,
        "evidence_pointer": evidence,
        "settling_probe": encoding["settling_probe"],
        "probe_cost": encoding["probe_cost"],
        "amendment_applied": applied,
        "unsatisfiable_as_written": unsat,
        "kind": spec.get("kind"),
    }
    if encoding.get("as_written_text"):
        row["as_written_text"] = encoding["as_written_text"]
    if encoding.get("as_written_satisfiability"):
        row["as_written_satisfiability"] = encoding["as_written_satisfiability"]
    return row


def run(state: dict, encodings: list[dict]) -> dict:
    rows = [evaluate_encoding(e, state) for e in encodings]
    agg = aggregate(rows)
    return {
        "conditions": rows,
        "aggregation": agg,
        "inherited_from_phase_graph": False,
    }
