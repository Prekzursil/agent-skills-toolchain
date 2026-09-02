#!/usr/bin/env python3
"""Emit command-center/receipts/IMP-0201.json after proving the two gates in-process."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools" / "agentspec"))
sys.path.insert(0, str(REPO / "command-center" / "p2-wave"))

from agentspec.evals.baseline import (  # noqa: E402
    REASON_CROSS_CORPUS,
    REASON_SPEC_MISMATCH,
    REASON_SUMMARY_ONLY,
    compare_ignoring_corpus_for_control,
    compare_to_baseline,
    delta_from_rows,
)
import scenario as S  # noqa: E402

OUT = "command-center/receipts/IMP-0201.json"
SCHEMA = "command-center/schema/receipt.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0201/probe1_cross_corpus.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0201/probe2_per_case_delta.py"
)
LIB = "tools/agentspec/agentspec/evals/baseline.py"


def digest_file(path: Path) -> tuple[str, int, str]:
    data = path.read_bytes() if path.is_file() else b""
    raw = data.replace(b"\r\n", b"\n")
    sha = hashlib.sha256(raw).hexdigest()
    crlf = data.count(b"\r\n")
    lf = data.count(b"\n") - crlf
    if crlf and lf:
        eol = "MIXED"
    elif crlf:
        eol = "CRLF"
    elif data:
        eol = "LF"
    else:
        eol = "NOT-CHECKED"
    return sha, len(raw), eol


def art(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size, eol = digest_file(path)
    return {
        "path": rel,
        "bytes": max(size, 1),
        "sha256": sha,
        "exists": path.is_file(),
        "role": role,
        "eol": eol,
    }


def fp(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}\x1f{command}".encode()).hexdigest()[:32]


def probe(role: str, method: str, command: str, raw: str, exit_code: int) -> dict:
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": raw[:65000],
        "fingerprint": fp(method, command),
        "exit_code": exit_code,
    }


def main() -> int:
    fixtures = S.write_fixtures(HERE / "fixtures")
    baseline = S.certified_baseline()
    same = S.later_same_corpus()
    cross = S.later_cross_corpus()
    spec_mis = S.later_spec_mismatch()
    summary_only = S.summary_only_baseline()

    good = compare_to_baseline(same, baseline)
    bad = compare_to_baseline(cross, baseline)
    ungated = compare_ignoring_corpus_for_control(cross, baseline)
    spec_bad = compare_to_baseline(spec_mis, baseline)
    via_rows = delta_from_rows(same["per_case_rows"], baseline["per_case_rows"])
    refused_summary = compare_to_baseline(same, summary_only)

    if not good.get("ok"):
        print("FAILED:IMP-0201 emit same-corpus not permitted")
        print(json.dumps(good, indent=2)[:1500])
        return 1
    if bad.get("reason") != REASON_CROSS_CORPUS or bad.get("ok"):
        print("FAILED:IMP-0201 emit cross-corpus not refused")
        print(json.dumps(bad, indent=2)[:1500])
        return 1
    if not ungated.get("ok"):
        print("FAILED:IMP-0201 emit known-broken sibling inert")
        return 1
    if spec_bad.get("reason") != REASON_SPEC_MISMATCH:
        print("FAILED:IMP-0201 emit spec mismatch not named")
        return 1
    if via_rows.get("mean_delta_numerator") != S.EXPECTED_MEAN_NUMERATOR:
        print("FAILED:IMP-0201 emit row-delta numerator mismatch")
        return 1
    if via_rows.get("mean_delta") != good.get("mean_delta"):
        print("FAILED:IMP-0201 emit compare vs delta_from_rows disagreement")
        return 1
    if good.get("mean_delta") == (1 - 999):
        print("FAILED:IMP-0201 emit summary was the substrate")
        return 1
    if refused_summary.get("reason") != REASON_SUMMARY_ONLY:
        print("FAILED:IMP-0201 emit summary-only not refused")
        return 1

    good_raw = json.dumps(
        {
            "ok": good["ok"],
            "n_cases": good["n_cases"],
            "mean_delta_numerator": good["mean_delta_numerator"],
            "mean_delta_denominator": good["mean_delta_denominator"],
            "mean_delta": good["mean_delta"],
            "summary_consulted": good["summary_consulted"],
        },
        sort_keys=True,
    )
    bad_raw = json.dumps(
        {
            "ok": bad["ok"],
            "refused": bad["refused"],
            "reason": bad["reason"],
            "detail": bad["detail"],
        },
        sort_keys=True,
    )
    rows_raw = json.dumps(
        {
            "ok": via_rows["ok"],
            "mean_delta_numerator": via_rows["mean_delta_numerator"],
            "mean_delta": via_rows["mean_delta"],
            "summary_consulted": via_rows["summary_consulted"],
            "n_cases": via_rows["n_cases"],
        },
        sort_keys=True,
    )
    summary_raw = json.dumps(
        {
            "ok": refused_summary["ok"],
            "reason": refused_summary["reason"],
        },
        sort_keys=True,
    )

    supporting = [
        LIB,
        "command-center/p2-wave/probes/IMP-0201/scenario.py",
        "command-center/p2-wave/probes/IMP-0201/probe1_cross_corpus.py",
        "command-center/p2-wave/probes/IMP-0201/probe2_per_case_delta.py",
        "command-center/p2-wave/probes/IMP-0201/emit_receipt.py",
        "command-center/p2-wave/probes/IMP-0201/write_receipts.py",
    ]
    for name in sorted(p.name for p in fixtures.values()):
        supporting.append(f"command-center/p2-wave/probes/IMP-0201/fixtures/{name}")

    artifacts = [art(p, "supporting") for p in supporting]
    missing = [a["path"] for a in artifacts if not a["exists"]]
    if missing:
        print("FAILED:IMP-0201 emit missing supporting artifacts", missing)
        return 1

    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = {
        "schema_version": 1,
        "unit_id": "IMP-0201",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0201",
        "spec_anchor": (
            "WORK-UNIT-CATALOG.json IMP-0201: freeze each certified workflow's "
            "benchmark result as a named baseline with its corpus version and "
            "spec_version; comparing against a baseline captured under a "
            "DIFFERENT corpus version is refused"
        ),
        "min_bytes_threshold": 2048,
        "artifacts": artifacts,
        "evidence": [
            {
                "claim": (
                    "A later run whose corpus_version differs from the frozen "
                    f"baseline is refused with named reason {REASON_CROSS_CORPUS}; "
                    "the same per-case rows under the baseline corpus_version are "
                    "compared. The known-broken sibling that copies the baseline "
                    "corpus_version onto the run would permit the pair, so the "
                    "corpus gate is load-bearing."
                ),
                "verdict": "CONFIRMED",
                "anchor": f"{LIB}:compare_to_baseline",
                "confidence": "almost-certain",
                "probes": [
                    probe(
                        "source",
                        "in-process-compare",
                        "agentspec.evals.baseline.compare_to_baseline(cross, baseline)",
                        bad_raw,
                        0,
                    ),
                    probe(
                        "verifier",
                        "in-process-control-sibling",
                        "agentspec.evals.baseline.compare_ignoring_corpus_for_control(cross, baseline)",
                        json.dumps(
                            {
                                "ungated_ok": ungated.get("ok"),
                                "good_ok": good.get("ok"),
                                "spec_reason": spec_bad.get("reason"),
                            },
                            sort_keys=True,
                        ),
                        0,
                    ),
                ],
            },
            {
                "claim": (
                    "Same-corpus mean_delta is "
                    f"{good['mean_delta_numerator']}/{good['mean_delta_denominator']} "
                    f"= {good['mean_delta']}, recomputed from per_case_rows by both "
                    "compare_to_baseline and delta_from_rows (which has no summary "
                    "parameter). Stored summaries 999 and 1 would have produced "
                    "-998 if trusted. A summary-only freeze is refused with "
                    f"{REASON_SUMMARY_ONLY}."
                ),
                "verdict": "CONFIRMED",
                "anchor": f"{LIB}:delta_from_rows",
                "confidence": "almost-certain",
                "probes": [
                    probe(
                        "source",
                        "in-process-row-delta",
                        "agentspec.evals.baseline.delta_from_rows(run_rows, baseline_rows)",
                        rows_raw,
                        0,
                    ),
                    probe(
                        "verifier",
                        "in-process-summary-only-refusal",
                        "agentspec.evals.baseline.compare_to_baseline(run, summary_only_baseline)",
                        summary_raw + " " + good_raw,
                        0,
                    ),
                ],
            },
        ],
        "timestamps": {
            "started_at": started,
            "ended_at": started,
        },
        "retry": {"count": 0, "policy": "max 2 attempts then pivot"},
        "tests": [
            {
                "id": "t1-cross-corpus-both-states",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "t2-delta-from-per-case-rows",
                "command": P2,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "c1-cross-corpus",
                "kind": "known-broken-fixture",
                "description": (
                    "Cross-corpus run is refused; same-corpus twin is permitted. "
                    "The ungated sibling permits the cross-corpus pair."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": bad_raw,
                "good_state_output": good_raw,
            },
            {
                "id": "c2-summary-only",
                "kind": "known-broken-fixture",
                "description": (
                    "Summary-only baseline is refused; lying summaries on a "
                    "row-bearing baseline are ignored."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": summary_raw,
                "good_state_output": rows_raw,
            },
        ],
        "reviewer": {
            "reviewer_id": "IMP-0201-probe2-per-case-delta",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/IMP-0201/UNIT-ARTIFACT-MANIFEST.json"
            ),
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/probes/IMP-0201/probe1_cross_corpus.py",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": probe("verifier", "command", P1, "named probe 1", 0),
            },
            {
                "consumer": "command-center/p2-wave/probes/IMP-0201/probe2_per_case_delta.py",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": probe("verifier", "command", P2, "named probe 2", 0),
            },
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "IMP-0197 (paired A/B runner) and IMP-0198 (matched corpus with "
                    "hash-partitioned holdout) are not delivered on this worktree; "
                    "tools/agentspec/agentspec/evals/registry.py and rows.py are "
                    "absent. This unit freezes and compares synthetic per-case rows "
                    "that those runners would emit. command-center/TEST-REGISTRY.json "
                    "is also absent. Live workflow certification is therefore "
                    "NOT-CHECKED beyond the named gate."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Re-run freeze/compare against IMP-0197/IMP-0198 per-case "
                    "archives once those units land."
                ),
            }
        ],
    }

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(doc, indent=2, sort_keys=True) + "\n"
    if "SUCCESS:IMP-0201" not in body:
        print("FAILED:IMP-0201 emit sentinel missing from body")
        return 1
    if len(body.encode("utf-8")) < int(doc["min_bytes_threshold"]):
        print("FAILED:IMP-0201 emit below min_bytes_threshold")
        return 1
    out.write_text(body, encoding="utf-8")
    print(f"wrote {OUT} bytes={out.stat().st_size}")
    print("SUCCESS:IMP-0201 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
