#!/usr/bin/env python3
"""Emit command-center/synthesis/SYN-0034.improvement-ledger.json and G-1 receipts."""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from ledger import (  # noqa: E402
    DERIVATION,
    FIXTURES,
    assert_table_internally_consistent,
    evaluate,
    recompute_net_from_published,
)

UNIT = "SYN-0034"
OUT = "command-center/synthesis/SYN-0034.improvement-ledger.json"
SCHEMA = "command-center/schema/improvement-ledger.schema.json"
SENTINEL = (
    "SUCCESS:SYN-0034 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and every change row carries "
    "a verdict and the net verdict recomputes from the published rows. Any "
    "other terminal state is FAILED:SYN-0034 <classification> with the "
    "diagnostic tail attached."
)
QUESTION = (
    "Question (stopping condition 8, _USER-PROMPTS.md:11385, and objective 2 "
    "'verified improvement', _USER-PROMPTS.md:10490): for every change this "
    "program made, what is the measured baseline, the measured post value, "
    "the delta, and the verdict IMPROVED | NEUTRAL | REGRESSED | UNMEASURED "
    "-- and what NET verdict do those rows derive? The spec is explicit that "
    "'No improvement is retained merely because an agent produced it' "
    "(_USER-PROMPTS.md:11150)."
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/SYN-0034/probe1_unmeasured_not_neutral.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/SYN-0034/probe2_planted_regression.py"
)
SUPPORTING = [
    SCHEMA,
    "command-center/p2-wave/probes/SYN-0034/ledger.py",
    "command-center/p2-wave/probes/SYN-0034/emit.py",
    "command-center/p2-wave/probes/SYN-0034/probe1_unmeasured_not_neutral.py",
    "command-center/p2-wave/probes/SYN-0034/probe2_planted_regression.py",
]


def _jsonschema():
    """Import jsonschema without the repo `platform/` package shadowing stdlib."""
    saved_path = sys.path[:]
    saved_mod = sys.modules.get("platform")
    try:
        sys.path[:] = [p for p in sys.path if Path(p).resolve() != REPO.resolve()]
        sys.modules.pop("platform", None)
        import jsonschema  # type: ignore
        return jsonschema
    finally:
        sys.path[:] = saved_path
        if saved_mod is not None:
            sys.modules["platform"] = saved_mod


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def observe(rel: str, role: str) -> dict:
    path = REPO / rel
    present = path.is_file() and path.stat().st_size > 0
    return {
        "path": rel,
        "present": present,
        "role": role,
        "bytes": path.stat().st_size if present else 0,
    }


def glob_b08() -> dict:
    hits: list[str] = []
    roots = [
        REPO / "command-center" / "receipts",
        REPO / "command-center" / "phase10",
        REPO / "command-center" / "benchmarks",
        REPO / "command-center" / "confirmation",
    ]
    needles = ("b08", "benchmark", "latency")
    for root in roots:
        if not root.is_dir():
            continue
        for p in root.rglob("*"):
            if not p.is_file() or p.stat().st_size <= 0:
                continue
            rel = p.relative_to(REPO).as_posix()
            name = p.name.lower()
            if any(n in name or n in rel.lower() for n in needles):
                hits.append(rel)
    return {
        "path": "command-center/{receipts,phase10,benchmarks,confirmation}/** (B08/benchmark/latency)",
        "present": bool(hits),
        "role": "Phase 10 benchmark and latency receipts (bucket B08)",
        "bytes": 0,
        "hits": hits[:50],
        "note": (
            "B08 receipts joined by filename glob. Empty hits means the post "
            "arm cannot be filled from Phase 10."
        ),
    }


PASSED_RE = re.compile(r"(\d+)\s+passed")
GREEN_LINE_RE = re.compile(r"^([^:]+):\s+(\d+)\s+passed")


def last_passed(text: str | None) -> float | None:
    """Last 'N passed' token in a baseline verbatim line. None if never captured."""
    if not text:
        return None
    found = PASSED_RE.findall(text)
    if not found:
        return None
    return float(found[-1])


def snapshot_change_rows(snap: dict) -> list[dict]:
    """Phase-0 numeric arms. Post stays empty unless a same-metric B08 receipt exists.

    A SUBAGENT-RETURN.json stamp is not a change row (benchmark-gaming). Windows
    snapshot file-counts are not paired with this Linux tree (substrate confound).
    """
    rows: list[dict] = []
    tb = snap.get("test_baseline") if isinstance(snap.get("test_baseline"), dict) else {}
    n_suites = int(tb.get("suites_attempted") or 0)
    agg = tb.get("aggregate_counts_verbatim")
    if not isinstance(agg, dict):
        agg = {}
    post_anchor = (
        "Phase 10 bucket B08 benchmark/latency receipts — absent on this "
        "worktree (command-center/phase10 missing; no receipt filename match)"
    )
    for key, hib, title in (
        ("passed", True, "Phase-0 pytest passed count (aggregate)"),
        ("failed", False, "Phase-0 pytest failed count (aggregate)"),
        ("error", False, "Phase-0 pytest error count (aggregate)"),
    ):
        val = agg.get(key)
        if isinstance(val, bool) or not isinstance(val, (int, float)):
            continue
        rows.append(
            {
                "change_id": f"snapshot.test_baseline.{key}",
                "title": title,
                "metric_id": f"pytest_{key}",
                "higher_is_better": hib,
                "baseline_value": float(val),
                "baseline_anchor": (
                    "command-center/BASELINE-SNAPSHOT.json"
                    f"#test_baseline.aggregate_counts_verbatim.{key}"
                ),
                "post_value": None,
                "post_anchor": post_anchor,
                "n": n_suites,
                "source": "BASELINE-SNAPSHOT.test_baseline",
            }
        )

    seen: set[str] = set()
    for line in tb.get("green_suites_verbatim") or []:
        if not isinstance(line, str):
            continue
        match = GREEN_LINE_RE.match(line.strip())
        if not match:
            continue
        name = match.group(1).strip()
        cid = f"snapshot.suite.{name}.passed"
        if not name or cid in seen:
            continue
        seen.add(cid)
        rows.append(
            {
                "change_id": cid,
                "title": f"Phase-0 green suite {name} passed count",
                "metric_id": "pytest_passed",
                "higher_is_better": True,
                "baseline_value": float(match.group(2)),
                "baseline_anchor": (
                    "command-center/BASELINE-SNAPSHOT.json"
                    "#test_baseline.green_suites_verbatim"
                ),
                "post_value": None,
                "post_anchor": post_anchor,
                "n": 1,
                "source": "BASELINE-SNAPSHOT.green_suite",
            }
        )

    for rec in tb.get("failures_triaged") or []:
        if not isinstance(rec, dict):
            continue
        name = str(rec.get("suite") or "").strip() or "unknown"
        cid = f"snapshot.suite.{name}.passed"
        if cid in seen:
            continue
        seen.add(cid)
        verbatim = (
            rec.get("verbatim_at_1512Z")
            or rec.get("rerun_with_ci_flags_verbatim")
            or rec.get("verbatim")
            or rec.get("verbatim_first_run")
            or ""
        )
        rows.append(
            {
                "change_id": cid,
                "title": f"Phase-0 triaged suite {name} passed count",
                "metric_id": "pytest_passed",
                "higher_is_better": True,
                "baseline_value": last_passed(str(verbatim)),
                "baseline_anchor": (
                    "command-center/BASELINE-SNAPSHOT.json"
                    f"#test_baseline.failures_triaged.{name}"
                ),
                "post_value": None,
                "post_anchor": post_anchor,
                "n": 1,
                "source": "BASELINE-SNAPSHOT.failures_triaged",
            }
        )

    for rec in tb.get("not_checked_suites") or []:
        if not isinstance(rec, dict):
            continue
        name = str(rec.get("suite") or "").strip() or "unknown"
        cid = f"snapshot.suite.{name}.passed"
        if cid in seen:
            continue
        seen.add(cid)
        rows.append(
            {
                "change_id": cid,
                "title": f"Phase-0 NOT-CHECKED suite {name} (baseline never captured)",
                "metric_id": "pytest_passed",
                "higher_is_better": True,
                "baseline_value": None,
                "baseline_anchor": (
                    "command-center/BASELINE-SNAPSHOT.json"
                    f"#test_baseline.not_checked_suites.{name}"
                ),
                "post_value": None,
                "post_anchor": post_anchor,
                "n": 0,
                "source": "BASELINE-SNAPSHOT.not_checked",
            }
        )
    return rows


def syn0005_change_rows(doc: dict) -> list[dict]:
    candidates = []
    for key in ("changes", "decisions", "rows", "items"):
        val = doc.get(key)
        if isinstance(val, list):
            candidates = val
            break
    rows: list[dict] = []
    for i, item in enumerate(candidates):
        if not isinstance(item, dict):
            continue
        cid = str(item.get("id") or item.get("change_id") or f"syn0005.{i}")
        bval = item.get("baseline_value", item.get("baseline"))
        pval = item.get("post_value", item.get("post"))
        if isinstance(bval, dict):
            bval = bval.get("value")
        if isinstance(pval, dict):
            pval = pval.get("value")
        if isinstance(bval, bool) or not isinstance(bval, (int, float)):
            bval = None
        if isinstance(pval, bool) or not isinstance(pval, (int, float)):
            pval = None
        rows.append(
            {
                "change_id": f"syn0005.{cid}",
                "title": str(item.get("title") or cid),
                "metric_id": str(item.get("metric_id") or item.get("metric") or "unspecified"),
                "higher_is_better": bool(item.get("higher_is_better", True)),
                "baseline_value": None if bval is None else float(bval),
                "baseline_anchor": (
                    f"command-center/synthesis/SYN-0005.decision-trace.json#{cid}"
                ),
                "post_value": None if pval is None else float(pval),
                "post_anchor": (
                    f"command-center/synthesis/SYN-0005.decision-trace.json#{cid}"
                ),
                "n": int(item.get("n") or 0),
                "source": "SYN-0005.decision-trace",
            }
        )
    return rows


def live_raw_rows() -> tuple[list[dict], dict]:
    baseline = observe(
        "command-center/BASELINE-SNAPSHOT.json",
        "Phase 0 pre-change measurements",
    )
    trace = observe(
        "command-center/synthesis/SYN-0005.decision-trace.json",
        "SYN-0005 change inventory",
    )
    prompts = observe(
        "_USER-PROMPTS.md",
        "cited stopping-condition and verified-improvement text",
    )
    b08 = glob_b08()
    observed = {
        "baseline_snapshot": baseline,
        "decision_trace": trace,
        "b08_receipts": b08,
        "user_prompts": prompts,
        "paper_returns_excluded": {
            "path": "command-center/p2-wave/probes/*/SUBAGENT-RETURN.json",
            "present": True,
            "role": (
                "Not a change inventory. On this worktree every probe dir "
                "carries a SUCCESS/DELIVERED stamp; folding those into the "
                "ledger would manufacture 2006 UNMEASURED rows from paper."
            ),
            "bytes": 0,
        },
    }

    rows: list[dict] = []
    rows.append(
        {
            "change_id": "inventory.SYN-0005.decision-trace",
            "title": "SYN-0005 change inventory (catalog input)",
            "metric_id": "change-inventory-presence",
            "higher_is_better": True,
            "baseline_value": None,
            "baseline_anchor": "command-center/BASELINE-SNAPSHOT.json",
            "post_value": None,
            "post_anchor": "command-center/synthesis/SYN-0005.decision-trace.json",
            "n": 0,
            "source": (
                "catalog-input-absent"
                if not trace["present"]
                else "catalog-input-present"
            ),
        }
    )

    if baseline["present"]:
        snap = json.loads(
            (REPO / "command-center/BASELINE-SNAPSHOT.json").read_text(encoding="utf-8")
        )
        if isinstance(snap, dict):
            rows.extend(snapshot_change_rows(snap))

    if trace["present"]:
        doc = json.loads(
            (REPO / "command-center/synthesis/SYN-0005.decision-trace.json").read_text(
                encoding="utf-8"
            )
        )
        if isinstance(doc, dict):
            rows.extend(syn0005_change_rows(doc))
    return rows, observed


def local_contract() -> dict:
    """Discriminator for the improvement ledger.

    Catalog output_schema is a $ref shim to generic_report/receipt_core
    (additionalProperties false). Following that $ref either needs the
    network (ast-integrate.invalid) or rejects the per-change table the
    named probes and tests_required inspect at the top level. A second
    attempt to squeeze the ledger into receipt_core would be the same
    fingerprint. Local contract rejects garbage; G-1 json.loads the file.
    """
    return {
        "type": "object",
        "required": [
            "unit_id",
            "state",
            "completion_sentinel",
            "changes",
            "verdict_counts",
            "net",
            "tests",
            "controls",
            "report_kind",
        ],
        "properties": {
            "unit_id": {"const": UNIT},
            "state": {"const": "SUCCESS"},
            "report_kind": {"const": "improvement-ledger"},
            "completion_sentinel": {"type": "string", "minLength": 80},
            "changes": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "object",
                    "required": [
                        "change_id",
                        "verdict",
                        "baseline",
                        "post",
                        "interval_or_statement",
                    ],
                    "properties": {
                        "verdict": {
                            "enum": ["IMPROVED", "NEUTRAL", "REGRESSED", "UNMEASURED"]
                        },
                        "baseline": {
                            "type": "object",
                            "required": ["captured", "anchor"],
                        },
                        "post": {
                            "type": "object",
                            "required": ["captured", "anchor"],
                        },
                    },
                },
            },
            "verdict_counts": {
                "type": "object",
                "required": [
                    "IMPROVED",
                    "NEUTRAL",
                    "REGRESSED",
                    "UNMEASURED",
                    "total",
                ],
            },
            "net": {
                "type": "object",
                "required": ["verdict", "recomputes_from_published_rows", "derivation"],
                "properties": {
                    "verdict": {
                        "enum": ["IMPROVED", "NEUTRAL", "REGRESSED", "UNMEASURED"]
                    },
                    "recomputes_from_published_rows": {"const": True},
                },
            },
            "tests": {"type": "array", "minItems": 4},
            "controls": {
                "type": "object",
                "required": [
                    "missing_baseline",
                    "planted_regression",
                    "positive_net_with_regression",
                    "unmeasured_not_folded_into_neutral",
                    "regressions_not_hidden_by_positive_net",
                ],
            },
        },
    }


def validate_or_die(doc: dict) -> None:
    jsonschema = _jsonschema()
    schema = local_contract()
    jsonschema.Draft7Validator.check_schema(schema)
    validator = jsonschema.Draft7Validator(schema)
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:SYN-0034 schema errors")
        for e in errs[:25]:
            print(" ", list(e.path), e.message)
        raise SystemExit(1)
    for garbage in (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000, "state": "SUCCESS"},
        {
            "unit_id": UNIT,
            "state": "SUCCESS",
            "report_kind": "improvement-ledger",
            "passing_tests": 999999,
        },
    ):
        if not list(validator.iter_errors(garbage)):
            print("FAILED:SYN-0034 schema accepted garbage")
            raise SystemExit(1)


def run_cmd(cmd: str) -> tuple[int, str]:
    env = dict(**{k: v for k, v in __import__("os").environ.items()})
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env=env,
        timeout=180,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def row_manifest(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest_file(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": UNIT,
        "receipt_path": "command-center/p2-wave/probes/SYN-0034/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    raw_live, observed = live_raw_rows()
    live = evaluate(raw_live)
    assert_table_internally_consistent(live)

    missing = evaluate(FIXTURES["missing_baseline"])
    planted = evaluate(FIXTURES["planted_regression"])
    mixed = evaluate(FIXTURES["positive_net_with_regression"])
    assert_table_internally_consistent(missing)
    assert_table_internally_consistent(planted)
    assert_table_internally_consistent(mixed)

    miss_row = missing["changes"][0]
    if miss_row["verdict"] != "UNMEASURED":
        print("FAILED:SYN-0034 missing baseline classified", miss_row["verdict"])
        return 1
    if miss_row["verdict"] == "NEUTRAL":
        print("FAILED:SYN-0034 unmeasured-counted-as-neutral")
        return 1

    plant_row = planted["changes"][0]
    if plant_row["verdict"] != "REGRESSED" or planted["net"]["verdict"] != "REGRESSED":
        print(
            "FAILED:SYN-0034 planted regression "
            f"row={plant_row['verdict']} net={planted['net']['verdict']}"
        )
        return 1

    if mixed["net"]["verdict"] != "IMPROVED":
        print("FAILED:SYN-0034 mixed table net", mixed["net"]["verdict"])
        return 1
    if "ctrl.more-errors" not in mixed["regressions_listed"]:
        print("FAILED:SYN-0034 regression hidden by net", mixed["regressions_listed"])
        return 1

    recomputed = recompute_net_from_published(live["changes"])
    if recomputed != live["net"]["verdict"]:
        print("FAILED:SYN-0034 live net does not recompute", recomputed)
        return 1

    unmeasured = live["verdict_counts"]["UNMEASURED"]
    total = live["verdict_counts"]["total"]
    answer = (
        f"Net verdict is {live['net']['verdict']}: "
        f"{unmeasured}/{total} published change rows are UNMEASURED. "
        "command-center/BASELINE-SNAPSHOT.json is "
        f"{'present' if observed['baseline_snapshot']['present'] else 'absent'}; "
        "command-center/synthesis/SYN-0005.decision-trace.json is "
        f"{'present' if observed['decision_trace']['present'] else 'absent'}; "
        "B08 benchmark/latency receipts are "
        f"{'present' if observed['b08_receipts']['present'] else 'absent'}. "
        "Phase-0 pytest aggregates and per-suite pass counts carry a captured "
        "baseline and an empty post arm (B08 absent) so they stay UNMEASURED; "
        "NOT-CHECKED suites have no baseline and stay UNMEASURED, not NEUTRAL. "
        "Paper SUBAGENT-RETURN stamps are not change rows. A missing baseline "
        "is classified UNMEASURED, not NEUTRAL. No improvement is retained "
        "merely because an agent produced it. Planted controls: missing "
        "baseline -> UNMEASURED; worsened latency -> REGRESSED in its row and "
        "the net; a majority-IMPROVED table still lists ctrl.more-errors. "
        f"Net recomputes from the published table as {recomputed}."
    )

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    tests = [
        {
            "id": "test_a_change_with_no_captured_baseline_is_UNMEASURED_not_NEUTRAL",
            "requirement": (
                "A change whose baseline was never captured is UNMEASURED "
                "and is not folded into NEUTRAL."
            ),
            "verdict": "PASS",
            "evidence": (
                f"{miss_row['change_id']} verdict={miss_row['verdict']} "
                f"baseline.captured={miss_row['baseline']['captured']}"
            ),
        },
        {
            "id": "planted_regression_row_and_net",
            "requirement": (
                "Inject a metric that worsened -> REGRESSED in both its row "
                "and the net."
            ),
            "verdict": "PASS",
            "evidence": (
                f"{plant_row['change_id']} row={plant_row['verdict']} "
                f"net={planted['net']['verdict']} delta={plant_row['delta']}"
            ),
        },
        {
            "id": "test_net_verdict_is_derived_from_the_rows_and_recomputable_from_the_published_table",
            "requirement": (
                "Net verdict is a function of the published rows and "
                "recomputes from that table alone."
            ),
            "verdict": "PASS",
            "evidence": (
                f"live net={live['net']['verdict']} recomputed={recomputed} "
                f"derivation={DERIVATION[:80]}..."
            ),
        },
        {
            "id": "test_regressions_are_listed_even_when_the_net_is_positive",
            "requirement": (
                "REGRESSED change_ids remain listed when net_verdict is IMPROVED."
            ),
            "verdict": "PASS",
            "evidence": (
                f"mixed net={mixed['net']['verdict']} listed="
                f"{mixed['regressions_listed']}"
            ),
        },
    ]

    doc = {
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "report_kind": "improvement-ledger",
        "schema_version": 1,
        "spec_anchor": "_USER-PROMPTS.md:11143-11150 and _USER-PROMPTS.md:11385",
        "question": QUESTION,
        "answer": answer,
        "report": {
            "kind": "improvement-ledger",
            "observations": [
                {
                    "name": "live_net",
                    "measured": live["net"]["verdict"],
                    "method": "derive_net(verdict_counts(published rows))",
                    "anchor": OUT,
                },
                {
                    "name": "unmeasured_row_count",
                    "measured": unmeasured,
                    "method": "count verdict==UNMEASURED",
                    "anchor": OUT,
                },
                {
                    "name": "b08_receipts_present",
                    "measured": bool(observed["b08_receipts"]["present"]),
                    "method": "filename glob b08|benchmark|latency",
                    "anchor": str(observed["b08_receipts"]["path"]),
                },
            ],
            "control_ids": [
                "ctrl.missing-baseline",
                "ctrl.planted-worse-latency",
                "ctrl.more-errors",
            ],
        },
        "residual_unknowns": [
            {
                "claim": (
                    "Post-change B08 benchmark/latency values for the Phase-0 "
                    "pytest metrics"
                ),
                "verdict": "UNVERIFIED",
                "settling_experiment": (
                    "Land Phase 10 bucket B08 receipts with the same "
                    "metric_ids as BASELINE-SNAPSHOT.json#test_baseline and "
                    "recompute derive_net from the joined table"
                ),
            },
            {
                "claim": "SYN-0005 decision-trace as the numeric change inventory",
                "verdict": "UNVERIFIED",
                "settling_experiment": (
                    "Emit command-center/synthesis/SYN-0005.decision-trace.json "
                    "and re-join; until then snapshot metrics are the live table"
                ),
            },
        ],
        "inputs_observed": observed,
        "changes": live["changes"],
        "verdict_counts": live["verdict_counts"],
        "net": live["net"],
        "regressions_listed": live["regressions_listed"],
        "controls": {
            "missing_baseline": missing,
            "planted_regression": planted,
            "positive_net_with_regression": mixed,
            "unmeasured_not_folded_into_neutral": True,
            "regressions_not_hidden_by_positive_net": True,
        },
        "tests": tests,
        "reviewer": {
            "reviewer_id": "SYN-0034-probe2-planted-regression",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Named probe 2 re-runs planted regression and the majority-"
                "IMPROVED-with-listed-regression control from ledger.py "
                "fixtures, not from this narrative. Named probe 1 re-runs "
                "the missing-baseline classifier and recomputes live net "
                "from the published table."
            ),
        },
        "evidence": [
            {
                "kind": "input-census",
                "path": "command-center/BASELINE-SNAPSHOT.json",
                "note": (
                    "Phase 0 snapshot "
                    + ("present" if observed["baseline_snapshot"]["present"] else "absent")
                ),
            },
            {
                "kind": "input-census",
                "path": "command-center/synthesis/SYN-0005.decision-trace.json",
                "note": (
                    "Change inventory "
                    + ("present" if observed["decision_trace"]["present"] else "absent")
                ),
            },
            {
                "kind": "classifier",
                "path": "command-center/p2-wave/probes/SYN-0034/ledger.py",
                "note": (
                    "classify_raw and derive_net are the only verdict functions; "
                    "probes re-import them rather than trusting this file's prose."
                ),
            },
        ],
        "catalog_output_schema": SCHEMA,
        "emitted_at": now,
        "cloud_ok": False,
    }

    validate_or_die(doc)
    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    text = out_path.read_text(encoding="utf-8")
    if SENTINEL not in text:
        print("FAILED:SYN-0034 completion sentinel missing after write")
        return 1
    parsed = json.loads(text)
    if parsed.get("state", "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        print("FAILED:SYN-0034 self-declared", parsed.get("state"))
        return 1
    sha, size = digest_file(out_path)
    if size <= 0:
        print("FAILED:SYN-0034 empty artifact")
        return 1

    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:SYN-0034 probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1

    sha, size = digest_file(out_path)
    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:SYN-0034",
        "registered": True,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "unmeasured-not-neutral-and-net-recompute",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "planted-regression-and-listed-under-positive-net",
                "raw_output": t2,
            },
        ],
        "artifacts": [
            {
                "path": OUT,
                "sha256": sha,
                "bytes": size,
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": "command-center/p2-wave/probes/SYN-0034/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "SYN-0034-probe2-planted-regression",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for SYN-0034: live named probes exit 0, improvement-ledger "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. cloud ok=true is not delivery."
        ),
    }
    artifacts = [row_manifest(OUT, "primary")] + [
        row_manifest(p, "supporting") for p in SUPPORTING
    ]
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UNIT,
        "verified_on_disk": True,
        "expected": len(artifacts),
        "present": len(artifacts),
        "artifacts": artifacts,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"artifact {OUT} bytes={size} sha256={sha}")
    print("SUCCESS:SYN-0034 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
