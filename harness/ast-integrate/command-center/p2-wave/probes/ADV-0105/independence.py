#!/usr/bin/env python3
"""ADV-0105: input-set overlap and outcome-error correlation.

Two mechanically different instruments on the same question: whether agreement
among N agents is independent corroboration or one shared lens.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Iterable

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT_ID = "ADV-0105"
OUTPUT_REL = (
    "command-center/adversarial/"
    "ADV-0105-agent-independence-shared-input-audit.json"
)
SCHEMA_REL = "command-center/schema/refutation-record.schema.json"
CATALOG_REL = "command-center/WORK-UNIT-CATALOG.json"
P1_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0105/probe1_input_overlap.py"
)
P2_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0105/probe2_outcome_correlation.py"
)
LEGAL = frozenset(
    {"CONFIRMED", "REFUTED", "PARTIAL", "NOT-CHECKED", "BLOCKED"}
)
PROBE1_NAME = (
    "Probe 1: compute the input-set overlap between agents for each "
    "corroboration event; identical prefixes or a shared briefing artifact "
    "reduce N to 1."
)
PROBE2_NAME = (
    "Probe 2 (mechanically different): outcome correlation - where the same "
    "agents have judged many items, measure their error correlation; "
    "near-perfect agreement across a diverse item set indicates a shared "
    "lens rather than independent confirmation."
)
JACCARD_COLLAPSE = 0.99
CORR_COLLAPSE = 0.95
JACCARD_DISTINCT_MAX = 0.35
CORR_DISTINCT_MAX = 0.35
SAMPLE_REVIEW_IDS = (
    "IMP-0148",
    "CNF-0091",
    "CNF-0046",
    "ARC-0012",
    "RES-0108",
    "CNL-0121",
    "TST-0262",
    "IMP-0418",
)


def load_catalog_unit() -> dict:
    data = json.loads((REPO / CATALOG_REL).read_text(encoding="utf-8"))
    for u in data.get("work_units") or []:
        if isinstance(u, dict) and u.get("id") == UNIT_ID:
            return u
    raise RuntimeError("ADV-0105 missing from catalog")


def catalog_sentinel() -> str:
    return str(load_catalog_unit()["completion_sentinel"])


def jaccard(a: Iterable[str], b: Iterable[str]) -> float:
    sa, sb = set(a), set(b)
    if not sa and not sb:
        return 1.0
    return len(sa & sb) / len(sa | sb)


def pearson(xs: list[float], ys: list[float]) -> float | None:
    n = len(xs)
    if n != len(ys) or n < 2:
        return None
    mx = sum(xs) / n
    my = sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    dy = math.sqrt(sum((y - my) ** 2 for y in ys))
    if dx == 0.0 and dy == 0.0:
        return 1.0 if xs == ys else 0.0
    if dx == 0.0 or dy == 0.0:
        return 1.0 if xs == ys else 0.0
    return num / (dx * dy)


def pairwise_max_jaccard(agents: list[dict]) -> dict:
    best = {"a": None, "b": None, "jaccard": -1.0, "shared": []}
    for i, left in enumerate(agents):
        for right in agents[i + 1 :]:
            ja = jaccard(left["inputs"], right["inputs"])
            shared = sorted(set(left["inputs"]) & set(right["inputs"]))
            if ja > best["jaccard"]:
                best = {
                    "a": left["id"],
                    "b": right["id"],
                    "jaccard": round(ja, 6),
                    "shared": shared,
                }
    return best


def pairwise_max_corr(agents: list[dict]) -> dict:
    best: dict[str, Any] = {
        "a": None,
        "b": None,
        "correlation": None,
        "n_items": 0,
    }
    best_abs = -1.0
    for i, left in enumerate(agents):
        for right in agents[i + 1 :]:
            ea = left.get("errors") or []
            eb = right.get("errors") or []
            c = pearson([float(x) for x in ea], [float(x) for x in eb])
            if c is None:
                continue
            if abs(c) > best_abs:
                best_abs = abs(c)
                best = {
                    "a": left["id"],
                    "b": right["id"],
                    "correlation": round(c, 6),
                    "n_items": len(ea),
                }
    return best


def collapse_reason(overlap: dict, corr: dict) -> str | None:
    shared = overlap.get("shared") or []
    briefing = any(
        str(s).startswith(("briefing:", "case-packet:", "rubric:"))
        for s in shared
    )
    if float(overlap.get("jaccard") or 0) >= JACCARD_COLLAPSE:
        return "identical-input-set"
    if briefing and float(overlap.get("jaccard") or 0) >= 0.5:
        return "shared-briefing-artifact"
    c = corr.get("correlation")
    n = int(corr.get("n_items") or 0)
    if c is not None and n >= 8 and abs(float(c)) >= CORR_COLLAPSE:
        return "near-perfect-error-correlation"
    return None


def calibration_gate_exit(overlap_j: float, corr: float | None) -> int:
    if overlap_j >= JACCARD_COLLAPSE and corr is not None and abs(corr) >= CORR_COLLAPSE:
        return 1
    return 0


def _item_errors(pattern: str) -> list[int]:
    table = {
        "lens-a": [1, 0, 1, 1, 0, 1, 0, 0, 1, 1, 0, 1, 0, 1, 1, 0],
        "lens-b": [1, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0],
    }
    return list(table[pattern])


def annotate_event(
    event_id: str,
    agents: list[dict],
    kind: str,
    used_as_corroboration: bool,
    note: str = "",
) -> dict:
    overlap = pairwise_max_jaccard(agents)
    corr = pairwise_max_corr(agents)
    reason = collapse_reason(overlap, corr)
    claimed_n = len(agents)
    effective_n = 1 if reason else claimed_n
    gate = calibration_gate_exit(
        float(overlap.get("jaccard") or 0),
        corr.get("correlation"),
    )
    if reason:
        verdict = "CONFIRMED"
    elif overlap.get("jaccard") is not None and corr.get("correlation") is not None:
        verdict = "REFUTED"
    else:
        verdict = "PARTIAL"
    return {
        "event_id": event_id,
        "kind": kind,
        "used_as_corroboration": used_as_corroboration,
        "claimed_n": claimed_n,
        "effective_n": effective_n,
        "collapse_reason": reason,
        "overlap": overlap,
        "correlation": corr,
        "calibration_gate_exit": gate,
        "verdict": verdict,
        "note": note,
        "agents": [
            {
                "id": a["id"],
                "inputs": list(a["inputs"]),
                "n_errors": len(a.get("errors") or []),
                "error_sum": int(sum(a.get("errors") or [])),
            }
            for a in agents
        ],
    }


def synthetic_events() -> list[dict]:
    distinct_a = {
        "id": "agent-distinct-a",
        "inputs": [
            "case-packet:partition-alpha",
            "briefing:role-chair-notes-v1",
            "prefix:alpha/evidence/",
        ],
        "errors": _item_errors("lens-a"),
    }
    distinct_b = {
        "id": "agent-distinct-b",
        "inputs": [
            "case-packet:partition-beta",
            "briefing:role-critic-notes-v7",
            "prefix:beta/counter/",
        ],
        "errors": _item_errors("lens-b"),
    }
    shared_a = {
        "id": "agent-shared-a",
        "inputs": [
            "case-packet:frozen-packet-9",
            "briefing:panel-packet-verbatim",
            "prefix:shared/stale/",
        ],
        "errors": _item_errors("lens-a"),
    }
    shared_b = {
        "id": "agent-shared-b",
        "inputs": list(shared_a["inputs"]),
        "errors": list(shared_a["errors"]),
    }
    return [
        annotate_event(
            "control:distinct-inputs",
            [distinct_a, distinct_b],
            "distinct-control",
            True,
            "Deliberately disjoint briefings and weakly related error vectors.",
        ),
        annotate_event(
            "control:shared-mutant",
            [shared_a, shared_b],
            "shared-mutant",
            True,
            "Mutant copies agent A's inputs and error vector onto agent B.",
        ),
    ]


def _load_mod(name: str, path: Path):
    import importlib.util
    import sys

    parent = str(path.parent)
    if parent not in sys.path:
        sys.path.insert(0, parent)
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def cnf0091_event() -> dict | None:
    council = REPO / "command-center/p2-wave/probes/CNF-0091/council.py"
    gt = REPO / "command-center/p2-wave/probes/CNF-0091/ground_truth.py"
    if not council.is_file() or not gt.is_file():
        return None
    cmod = _load_mod("adv0105_cnf0091_council", council)
    gmod = _load_mod("adv0105_cnf0091_gt", gt)
    both = cmod.run_both()
    payload = "case-packet:cnf0091-payload:" + gmod.PAYLOAD.hex()
    question = "question:cnf0091-int-from-bytes"
    biased = both["biased"]
    chair_assert = biased["chair"]["asserted_position"]
    agents = [
        {
            "id": "chair-biased",
            "inputs": [payload, question, f"briefing:chair-assert:{chair_assert}"],
            "errors": [1],
        }
    ]
    for row in biased["participant_positions"]:
        pid = row["participant_id"]
        inputs = [payload, question]
        if pid == "P-sycophant":
            inputs.append(f"briefing:chair-assert:{chair_assert}")
        err = 0 if row["position"] == gmod.correct_value() else 1
        agents.append({"id": pid, "inputs": inputs, "errors": [err]})
    return annotate_event(
        "session:CNF-0091:biased-chair",
        agents,
        "live-council",
        True,
        "Biased chair injects a shared wrong briefing; the sycophant copies it.",
    )


def cnf0091_neutral() -> dict | None:
    council = REPO / "command-center/p2-wave/probes/CNF-0091/council.py"
    gt = REPO / "command-center/p2-wave/probes/CNF-0091/ground_truth.py"
    if not council.is_file() or not gt.is_file():
        return None
    cmod = _load_mod("adv0105_cnf0091_council_n", council)
    gmod = _load_mod("adv0105_cnf0091_gt_n", gt)
    both = cmod.run_both()
    payload = "case-packet:cnf0091-payload:" + gmod.PAYLOAD.hex()
    question = "question:cnf0091-int-from-bytes"
    agents = [
        {"id": "chair-neutral", "inputs": [payload, question], "errors": [0]}
    ]
    for row in both["neutral"]["participant_positions"]:
        agents.append(
            {
                "id": row["participant_id"],
                "inputs": [payload, question],
                "errors": [0 if row["position"] == gmod.correct_value() else 1],
            }
        )
    return annotate_event(
        "session:CNF-0091:neutral-chair",
        agents,
        "live-council",
        True,
        "Neutral chair: correct positions, but every persona received the same packet.",
    )


def _reviewer_inputs(doc: dict) -> list[str]:
    rev = doc.get("reviewer") if isinstance(doc.get("reviewer"), dict) else {}
    for key in ("input_manifest", "inputs", "input_set"):
        val = rev.get(key)
        if isinstance(val, list) and val:
            return [str(x) for x in val]
        if isinstance(val, str) and val.strip():
            return [val.strip()]
    return []


def _producer_inputs(doc: dict, unit_id: str) -> list[str]:
    for key in ("producer_inputs", "input_manifest", "input_set"):
        val = doc.get(key)
        if isinstance(val, list) and val:
            return [str(x) for x in val]
        if isinstance(val, str) and val.strip():
            return [val.strip()]
    return []


def _not_checked_review(uid: str, note: str) -> dict:
    return {
        "event_id": f"review:{uid}:independent-pass",
        "kind": "claimed-independent-review",
        "used_as_corroboration": True,
        "claimed_n": None,
        "effective_n": None,
        "collapse_reason": None,
        "overlap": {},
        "correlation": {},
        "calibration_gate_exit": None,
        "verdict": "NOT-CHECKED",
        "note": note,
        "agents": [],
        "complete_dual_input_manifest": False,
        "reviewer_id": None,
    }


def scan_independent_reviews() -> dict:
    """Closed SAMPLE_REVIEW_IDS only.

    An open glob of probes/*/SUBAGENT-RETURN.json grows while sibling units
    land receipts. That changes claimed_n / all_event_ids / sample fill-in
    between emit and remesure, which is exactly named-probe1-raw-mismatch.
    """
    probes = REPO / "command-center/p2-wave/probes"
    rows = []
    for uid in SAMPLE_REVIEW_IDS:
        ret_path = probes / uid / "SUBAGENT-RETURN.json"
        if not ret_path.is_file():
            rows.append(_not_checked_review(uid, "SUBAGENT-RETURN.json absent"))
            continue
        try:
            doc = json.loads(ret_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            rows.append(
                _not_checked_review(uid, "SUBAGENT-RETURN.json unparseable")
            )
            continue
        if not isinstance(doc, dict):
            rows.append(
                _not_checked_review(uid, "SUBAGENT-RETURN.json not an object")
            )
            continue
        rev = doc.get("reviewer") if isinstance(doc.get("reviewer"), dict) else {}
        claimed = (
            rev.get("independent") is True
            and str(rev.get("verdict") or "").upper() in {"PASS", "SUCCESS"}
        )
        if not claimed:
            rows.append(
                _not_checked_review(
                    uid, "receipt does not claim independent PASS"
                )
            )
            continue
        prod = _producer_inputs(doc, uid)
        r_in = _reviewer_inputs(doc)
        complete = bool(prod) and bool(r_in) and set(prod) != set(r_in)
        if not complete:
            shared_dir = f"briefing:probe-dir:{uid}"
            prod = [shared_dir, f"catalog:{uid}"]
            r_in = [shared_dir, f"catalog:{uid}"]
        agents = [
            {"id": f"producer:{uid}", "inputs": prod, "errors": []},
            {"id": f"reviewer:{uid}", "inputs": r_in, "errors": []},
        ]
        ev = annotate_event(
            f"review:{uid}:independent-pass",
            agents,
            "claimed-independent-review",
            True,
            "complete_dual_input_manifest=" + ("true" if complete else "false"),
        )
        ev["complete_dual_input_manifest"] = complete
        ev["reviewer_id"] = rev.get("reviewer_id")
        rows.append(ev)
    claimed_rows = [r for r in rows if r["verdict"] != "NOT-CHECKED"]
    n = len(claimed_rows)
    n_complete = sum(1 for r in claimed_rows if r.get("complete_dual_input_manifest"))
    n_collapse = sum(1 for r in claimed_rows if r.get("effective_n") == 1)
    if n and n_complete == 0 and n_collapse == n:
        corpus_verdict = "CONFIRMED"
    elif n:
        corpus_verdict = "PARTIAL"
    else:
        corpus_verdict = "NOT-CHECKED"
    return {
        "n_claimed_independent_pass": n,
        "n_complete_dual_input_manifest": n_complete,
        "n_collapse_to_one_lens": n_collapse,
        "corpus_verdict": corpus_verdict,
        "enumeration": "closed-sample",
        "samples": rows,
        "all_event_ids": [r["event_id"] for r in rows],
    }


def historical_absent() -> list[dict]:
    paths = {
        "historical:ADV-0087-panels": (
            "command-center/adversarial/ADV-0087-judge-same-vendor-bias.json"
        ),
        "historical:ADV-0093-panels": (
            "command-center/adversarial/ADV-0093-chair-and-owner-sycophancy.json"
        ),
        "historical:fan-out-contract-C4": (
            "command-center/p2-wave/cloud-ok-2026-08-17/tree"
        ),
    }
    out = []
    for tid, rel in paths.items():
        exists = (REPO / rel).exists()
        out.append(
            {
                "event_id": tid,
                "kind": "historical",
                "used_as_corroboration": True,
                "claimed_n": None,
                "effective_n": None,
                "collapse_reason": None,
                "overlap": {},
                "correlation": {},
                "calibration_gate_exit": None,
                "verdict": "PARTIAL" if exists else "NOT-CHECKED",
                "note": (
                    f"path {rel} exists={exists}; this Linux worktree does not "
                    "carry the prior Windows/cloud-ok panel artifacts"
                    if not exists
                    else f"path {rel} present; not re-parsed in this pass"
                ),
                "agents": [],
            }
        )
    return out


def measure() -> dict:
    events = synthetic_events()
    live_b = cnf0091_event()
    live_n = cnf0091_neutral()
    if live_b:
        events.append(live_b)
    if live_n:
        events.append(live_n)
    reviews = scan_independent_reviews()
    events.extend(reviews["samples"])
    events.extend(historical_absent())
    distinct = next(e for e in events if e["event_id"] == "control:distinct-inputs")
    mutant = next(e for e in events if e["event_id"] == "control:shared-mutant")
    dj = float(distinct["overlap"]["jaccard"])
    dc = distinct["correlation"]["correlation"]
    mj = float(mutant["overlap"]["jaccard"])
    mc = mutant["correlation"]["correlation"]
    control_ok = (
        dj <= JACCARD_DISTINCT_MAX
        and dc is not None
        and abs(float(dc)) <= CORR_DISTINCT_MAX
        and distinct["calibration_gate_exit"] == 0
        and distinct["verdict"] == "REFUTED"
    )
    mutant_ok = (
        mj >= JACCARD_COLLAPSE
        and mc is not None
        and abs(float(mc)) >= CORR_COLLAPSE
        and mutant["calibration_gate_exit"] == 1
        and mutant["verdict"] == "CONFIRMED"
    )
    corpus = {
        "event_id": "live:independent-reviewer-corpus",
        "kind": "claimed-independent-review-corpus",
        "used_as_corroboration": True,
        "claimed_n": reviews["n_claimed_independent_pass"],
        "effective_n": 1 if reviews["n_complete_dual_input_manifest"] == 0 else None,
        "collapse_reason": (
            "missing-dual-input-manifest"
            if reviews["n_complete_dual_input_manifest"] == 0
            and reviews["n_claimed_independent_pass"]
            else None
        ),
        "overlap": {},
        "correlation": {},
        "calibration_gate_exit": None,
        "verdict": reviews["corpus_verdict"],
        "note": (
            f"enumeration=closed-sample "
            f"claimed_independent_pass={reviews['n_claimed_independent_pass']} "
            f"complete_dual_manifest={reviews['n_complete_dual_input_manifest']} "
            f"collapse_to_one_lens={reviews['n_collapse_to_one_lens']}"
        ),
        "agents": [],
        "all_event_ids": reviews["all_event_ids"],
    }
    events.append(corpus)
    n_conf = sum(1 for e in events if e["verdict"] == "CONFIRMED")
    n_ref = sum(1 for e in events if e["verdict"] == "REFUTED")
    n_nc = sum(1 for e in events if e["verdict"] == "NOT-CHECKED")
    if n_conf and n_ref:
        overall = "PARTIAL"
    elif n_conf and not n_ref and not n_nc:
        overall = "CONFIRMED"
    elif n_ref and not n_conf:
        overall = "REFUTED"
    else:
        overall = "PARTIAL"
    return {
        "events": events,
        "reviews": {
            "n_claimed_independent_pass": reviews["n_claimed_independent_pass"],
            "n_complete_dual_input_manifest": reviews["n_complete_dual_input_manifest"],
            "n_collapse_to_one_lens": reviews["n_collapse_to_one_lens"],
            "corpus_verdict": reviews["corpus_verdict"],
            "enumeration": reviews["enumeration"],
        },
        "controls": {
            "distinct_jaccard": dj,
            "distinct_correlation": dc,
            "distinct_gate": distinct["calibration_gate_exit"],
            "distinct_ok": control_ok,
            "mutant_jaccard": mj,
            "mutant_correlation": mc,
            "mutant_gate": mutant["calibration_gate_exit"],
            "mutant_ok": mutant_ok,
            "both_ok": control_ok and mutant_ok,
        },
        "counts": {
            "events": len(events),
            "CONFIRMED": n_conf,
            "REFUTED": n_ref,
            "PARTIAL": sum(1 for e in events if e["verdict"] == "PARTIAL"),
            "NOT-CHECKED": n_nc,
            "BLOCKED": sum(1 for e in events if e["verdict"] == "BLOCKED"),
        },
        "overall_verdict": overall,
    }


def _event_line(ev: dict) -> str:
    o = ev.get("overlap") or {}
    c = ev.get("correlation") or {}
    return (
        f"{ev['event_id']} verdict={ev['verdict']} "
        f"claimed_n={ev.get('claimed_n')} effective_n={ev.get('effective_n')} "
        f"jaccard={o.get('jaccard')} corr={c.get('correlation')} "
        f"gate={ev.get('calibration_gate_exit')} reason={ev.get('collapse_reason')}"
    )


def overlap_snapshot(m: dict | None = None) -> dict:
    m = m or measure()
    rows = []
    for ev in m["events"]:
        o = ev.get("overlap") or {}
        rows.append(
            {
                "event_id": ev["event_id"],
                "verdict": ev["verdict"],
                "jaccard": o.get("jaccard"),
                "pair": [o.get("a"), o.get("b")],
                "shared": o.get("shared"),
                "claimed_n": ev.get("claimed_n"),
                "effective_n": ev.get("effective_n"),
                "collapse_reason": ev.get("collapse_reason"),
            }
        )
    return {
        "instrument": "input-set-jaccard",
        "controls": m["controls"],
        "reviews": m["reviews"],
        "rows": rows,
        "overall_verdict": m["overall_verdict"],
    }


def correlation_snapshot(m: dict | None = None) -> dict:
    m = m or measure()
    rows = []
    for ev in m["events"]:
        c = ev.get("correlation") or {}
        rows.append(
            {
                "event_id": ev["event_id"],
                "verdict": ev["verdict"],
                "correlation": c.get("correlation"),
                "n_items": c.get("n_items"),
                "pair": [c.get("a"), c.get("b")],
                "claimed_n": ev.get("claimed_n"),
                "effective_n": ev.get("effective_n"),
                "collapse_reason": ev.get("collapse_reason"),
            }
        )
    return {
        "instrument": "error-vector-pearson",
        "controls": m["controls"],
        "reviews": m["reviews"],
        "rows": rows,
        "overall_verdict": m["overall_verdict"],
    }


def probe1_report(m: dict | None = None) -> str:
    m = m or measure()
    snap = overlap_snapshot(m)
    lines = [PROBE1_NAME, json.dumps(snap, sort_keys=True, default=str)]
    for ev in m["events"]:
        lines.append(_event_line(ev))
    ctrl = m["controls"]
    lines.append(
        "control_distinct "
        f"jaccard={ctrl['distinct_jaccard']} corr={ctrl['distinct_correlation']} "
        f"gate={ctrl['distinct_gate']} ok={ctrl['distinct_ok']}"
    )
    lines.append(
        "control_shared_mutant "
        f"jaccard={ctrl['mutant_jaccard']} corr={ctrl['mutant_correlation']} "
        f"gate={ctrl['mutant_gate']} ok={ctrl['mutant_ok']}"
    )
    lines.append(
        f"overall_verdict={m['overall_verdict']} events={m['counts']['events']}"
    )
    return "\n".join(lines) + "\n"


def probe2_report(m: dict | None = None) -> str:
    m = m or measure()
    snap = correlation_snapshot(m)
    lines = [PROBE2_NAME, json.dumps(snap, sort_keys=True, default=str)]
    for ev in m["events"]:
        c = ev.get("correlation") or {}
        lines.append(
            f"{ev['event_id']} corr={c.get('correlation')} "
            f"n_items={c.get('n_items')} verdict={ev['verdict']} "
            f"reason={ev.get('collapse_reason')}"
        )
    ctrl = m["controls"]
    lines.append(
        "calibration distinct_corr="
        f"{ctrl['distinct_correlation']} mutant_corr={ctrl['mutant_correlation']} "
        f"distinct_below_max={abs(float(ctrl['distinct_correlation'] or 0)) <= CORR_DISTINCT_MAX} "
        f"mutant_above_min={abs(float(ctrl['mutant_correlation'] or 0)) >= CORR_COLLAPSE}"
    )
    lines.append(
        f"overall_verdict={m['overall_verdict']} both_controls_ok={ctrl['both_ok']}"
    )
    return "\n".join(lines) + "\n"


def targets_from(m: dict) -> list[dict]:
    return [
        {
            "target_id": ev["event_id"],
            "verdict": ev["verdict"],
            "claimed_n": ev.get("claimed_n"),
            "effective_n": ev.get("effective_n"),
            "collapse_reason": ev.get("collapse_reason"),
            "jaccard": (ev.get("overlap") or {}).get("jaccard"),
            "correlation": (ev.get("correlation") or {}).get("correlation"),
            "note": ev.get("note") or "",
        }
        for ev in m["events"]
    ]
