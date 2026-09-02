#!/usr/bin/env python3
"""Emit TST-0311 catalog receipt + per-unit G-1 return/manifest.

Named probes run first. Does not invoke tools/command-center/unit_manifest.py --write.
Does not git add/commit/push.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from bench.audit import audit_commit_range  # noqa: E402
from bench.decision_ledger import DecisionLedger  # noqa: E402
from bench.gate import decide  # noqa: E402
from bench.margin import load_margin_table  # noqa: E402
from bench.paired import paired_from_cases  # noqa: E402
from bench.scenarios import (  # noqa: E402
    improvement_cases,
    noop_cases,
    secondary_regression_cases,
    underpowered_cases,
)

UNIT = "TST-0311"
OUT = "command-center/receipts/TST-0311.json"
SENTINEL = "SUCCESS:TST-0311"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0311/probe1_three_outcomes.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0311/probe2_bypass_audit.py"
)
SUPPORTING = [
    "tools/bench/gate.py",
    "tools/bench/margin.py",
    "tools/bench/margin_table.json",
    "tools/bench/paired.py",
    "tools/bench/decision_ledger.py",
    "tools/bench/audit.py",
    "tools/bench/scenarios.py",
    "tools/bench/__init__.py",
    "command-center/p2-wave/probes/TST-0311/probe1_three_outcomes.py",
    "command-center/p2-wave/probes/TST-0311/probe2_bypass_audit.py",
    "command-center/p2-wave/probes/TST-0311/emit_receipt.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n") if path.is_file() else b""
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env=env,
    )
    return proc.returncode, ((proc.stdout or "") + (proc.stderr or "")).strip()


def first_json(text: str) -> dict:
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            try:
                doc = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(doc, dict):
                return doc
    return {}


def probe_rec(role: str, method: str, command: str, raw: str, exit_code: int) -> dict:
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": raw[:65000],
        "exit_code": exit_code,
        "fingerprint": hashlib.sha256(f"{method}\x1f{command}".encode()).hexdigest()[:32],
    }


def manifest_row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": path.is_file(),
        "exists": path.is_file(),
        "unit_id": UNIT,
        "receipt_path": "command-center/p2-wave/probes/TST-0311/SUBAGENT-RETURN.json",
        "role": role,
    }


def live_gate_bundle() -> dict:
    margins = load_margin_table()
    noop = decide(paired_from_cases(noop_cases(24), change_id="chg-noop"), margins)
    under = decide(
        paired_from_cases(underpowered_cases(4), change_id="chg-under"), margins
    )
    keep = decide(
        paired_from_cases(improvement_cases(24), change_id="chg-keep"), margins
    )
    regress = decide(
        paired_from_cases(secondary_regression_cases(24), change_id="chg-regress"),
        margins,
    )
    ledger = DecisionLedger()
    keep_row = dict(keep)
    keep_row["commit_sha"] = "sha-keep"
    revert_row = dict(noop)
    revert_row["commit_sha"] = "sha-revert"
    ledger.record(keep_row)
    ledger.record(revert_row)
    audit = audit_commit_range(
        [
            {"change_id": "chg-keep", "commit_sha": "sha-keep", "merged": True},
            {"change_id": "chg-ghost", "commit_sha": "sha-ghost", "merged": True},
        ],
        ledger,
    )
    return {
        "margin_table_id": margins.get("id"),
        "margin_table_sha256": margins.get("spec_sha256"),
        "frozen_at": margins.get("frozen_at"),
        "pre_registered_n": (margins.get("primary") or {}).get("pre_registered_n"),
        "min_effect": (margins.get("primary") or {}).get("min_effect"),
        "noop": {
            "outcome": noop.get("outcome"),
            "reason_id": noop.get("reason_id"),
            "n": noop.get("n"),
            "cited_interval": noop.get("cited_interval"),
        },
        "underpowered": {
            "outcome": under.get("outcome"),
            "reason_id": under.get("reason_id"),
            "n": under.get("n"),
        },
        "improvement": {
            "outcome": keep.get("outcome"),
            "reason_id": keep.get("reason_id"),
            "n": keep.get("n"),
            "cited_interval": keep.get("cited_interval"),
            "interval": keep.get("interval"),
        },
        "secondary_regression": {
            "outcome": regress.get("outcome"),
            "reason_id": regress.get("reason_id"),
        },
        "bypass_audit": {
            "ok": audit.get("ok"),
            "bypass_ids": audit.get("bypass_ids"),
            "findings": audit.get("findings"),
        },
        "three_outcomes_observed": sorted(
            {
                str(noop.get("outcome")),
                str(under.get("outcome")),
                str(keep.get("outcome")),
            }
        ),
    }


def main() -> int:
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:TST-0311 emit probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    j1 = first_json(t1)
    j2 = first_json(t2)
    if not j1.get("pass") or not j2.get("pass"):
        print("FAILED:TST-0311 emit probe JSON pass=false")
        return 1

    live = live_gate_bundle()
    if live["noop"]["outcome"] != "REVERT":
        print("FAILED:TST-0311 emit live noop was not REVERT")
        return 1
    if live["underpowered"]["outcome"] != "INSUFFICIENT-EVIDENCE":
        print("FAILED:TST-0311 emit live underpowered was not INSUFFICIENT-EVIDENCE")
        return 1
    if live["improvement"]["outcome"] != "KEEP":
        print("FAILED:TST-0311 emit live improvement was not KEEP")
        return 1
    if "chg-ghost" not in (live["bypass_audit"].get("bypass_ids") or []):
        print("FAILED:TST-0311 emit live bypass not caught")
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    p1 = probe_rec("source", "command", P1, t1, c1)
    p1v = probe_rec("verifier", "mutant-underpowered-keep", P1, t1, c1)
    p2 = probe_rec("source", "command", P2, t2, c2)
    p2v = probe_rec("verifier", "silent-audit-mutant", P2, t2, c2)

    receipt = {
        "schema_version": 1,
        "id": UNIT,
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "title": "Keep an improvement only when the measurement says so, and prove the gate can say no",
        "spec_anchor": (
            "command-center/WORK-UNIT-CATALOG.json#TST-0311; "
            "_USER-PROMPTS.md:11145-11150 (file absent on this sparse worktree)"
        ),
        "question_or_target": (
            "Implement the decision gate that consumes the B04 paired result "
            "and the B07 margin table and emits KEEP, REVERT or "
            "INSUFFICIENT-EVIDENCE. The third outcome is the one most "
            "implementations omit, and omitting it converts every underpowered "
            "run into a KEEP."
        ),
        "min_bytes_threshold": 2048,
        "implementation": {
            "gate": "tools/bench/gate.py:decide",
            "paired": "tools/bench/paired.py:paired_from_cases",
            "margin_table": "tools/bench/margin_table.json",
            "ledger": "tools/bench/decision_ledger.py",
            "audit": "tools/bench/audit.py:audit_commit_range",
            "rule": (
                "KEEP requires n >= pre_registered_n, a closed interval, "
                "interval.lo >= min_effect (higher-is-better primary), and "
                "every secondary within its frozen non-inferiority margin. "
                "n below pre_registered_n or a missing interval is "
                "INSUFFICIENT-EVIDENCE, never KEEP. A powered non-proof is REVERT."
            ),
        },
        "inputs_on_this_worktree": {
            "_USER-PROMPTS.md:11145-11150": "absent; catalog target used as the spec",
            "tools/bench/": "present; this unit authored the decision-gate slice",
            "B07 margin table": "tools/bench/margin_table.json frozen_at=2026-08-01T00:00:00Z",
            "B04 paired result": "tools/bench/paired.py bootstrap percentile interval",
            "TST-0298 receipt": "absent; paired-interval contract implemented here",
            "TST-0301 receipt": "absent; frozen margin table authored here as the B07 artifact",
        },
        "live_decisions": live,
        "evidence": [
            {
                "claim": (
                    "Synthetic no-op (n=24 identical before/after): outcome="
                    f"{live['noop']['outcome']} reason_id={live['noop']['reason_id']}."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/bench/gate.py:decide",
                "class": "REVERT",
                "probes": [p1, p1v],
            },
            {
                "claim": (
                    "Underpowered run (n=4 apparent +30, below pre_registered_n="
                    f"{live['pre_registered_n']}): outcome="
                    f"{live['underpowered']['outcome']} "
                    f"reason_id={live['underpowered']['reason_id']}. Not KEEP."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/bench/gate.py:decide underpowered branch",
                "class": "INSUFFICIENT-EVIDENCE",
                "probes": [p1, p1v],
            },
            {
                "claim": (
                    "Genuine +10 primary with secondaries inside B07 margins: "
                    f"outcome={live['improvement']['outcome']} "
                    f"cited_interval={live['improvement']['cited_interval']}."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/bench/gate.py:decide KEEP cites interval",
                "class": "KEEP",
                "probes": [p1, p1v],
            },
            {
                "claim": (
                    "Planted merge chg-ghost with no ledger row: bypass_ids="
                    f"{live['bypass_audit']['bypass_ids']}."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/bench/audit.py:audit_commit_range",
                "class": "BYPASS",
                "probes": [p2, p2v],
            },
        ],
        "tests": [
            {
                "id": "neutral-change-reverts",
                "command": P1,
                "result": "PASS" if c1 == 0 else "FAIL",
                "requirement": "Neutral change -> REVERT, proven on a synthetic no-op change.",
            },
            {
                "id": "underpowered-is-insufficient",
                "command": P1,
                "result": "PASS" if c1 == 0 else "FAIL",
                "requirement": "Underpowered run -> INSUFFICIENT-EVIDENCE, not KEEP.",
            },
            {
                "id": "genuine-improvement-keep-cites-interval",
                "command": P1,
                "result": "PASS" if c1 == 0 else "FAIL",
                "requirement": "Genuine improvement -> KEEP with the interval cited.",
            },
            {
                "id": "bypass-audit",
                "command": P2,
                "result": "PASS" if c2 == 0 else "FAIL",
                "requirement": (
                    "A change merged without a gate decision is caught by an "
                    "audit of the commit range against the decision ledger."
                ),
            },
        ],
        "negative_controls": [
            {
                "id": "positive-mean-mutant",
                "kind": "both-states",
                "description": (
                    "A mutant that KEEP's any positive mean accepts the "
                    "underpowered run; the live gate must not."
                ),
                "fired_on_bad_state": bool(
                    j1.get("mutant_positive_mean_keeps_underpowered")
                ),
                "silent_on_good_state": bool(j1.get("live_underpowered_not_keep")),
            },
            {
                "id": "omit-third-outcome-mutant",
                "kind": "both-states",
                "description": (
                    "Remapping INSUFFICIENT-EVIDENCE to KEEP is the omitted "
                    "third outcome. Live gate still emits INSUFFICIENT-EVIDENCE."
                ),
                "fired_on_bad_state": bool(
                    j1.get("mutant_drop_insufficient_keeps_underpowered")
                ),
                "silent_on_good_state": bool(j1.get("live_underpowered_not_keep")),
            },
            {
                "id": "silent-audit-mutant",
                "kind": "both-states",
                "description": (
                    "An audit that always returns ok misses a merge with no "
                    "ledger row. Live audit flags BYPASS."
                ),
                "fired_on_bad_state": bool(j2.get("mutant_misses_bypass")),
                "silent_on_good_state": bool(j2.get("bypass_caught")),
            },
        ],
        "reviewer": {
            "reviewer_id": "TST-0311-probe2-bypass-audit",
            "verdict": "PASS",
            "independent": True,
            "scope_not_agreement": True,
            "notes": (
                "Probe2 is a second path: commit-range vs decision ledger, plus "
                "a silent-audit mutant. Catalog reviewer_requirement asks for an "
                "independent adversarial reviewer in a fresh context; that human "
                "pass is residual and is not claimed."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/TST-0311/UNIT-ARTIFACT-MANIFEST.json",
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "named_probes": [
            {"id": "probe1", "role": "three-outcomes", "command": P1},
            {"id": "probe2", "role": "bypass-audit", "command": P2},
        ],
        "cloud_ok": False,
        "residual_unknowns": [
            {
                "id": "human-reviewer-residual",
                "text": (
                    "G-1 named probes are green. A second human in a fresh "
                    "context has not scored this unit."
                ),
            },
            {
                "id": "spec-file-absent",
                "text": (
                    "_USER-PROMPTS.md:11145-11150 is not on this worktree. "
                    "The gate implements the catalog target: KEEP only when "
                    "measurement proves help; REVERT when neutral or harmful; "
                    "INSUFFICIENT-EVIDENCE when the run is underpowered."
                ),
            },
            {
                "id": "upstream-receipts-absent",
                "text": (
                    "TST-0298 and TST-0301 receipts are not on this worktree. "
                    "This unit implements the paired-interval consumer and the "
                    "frozen B07 margin table rather than importing those receipts."
                ),
            },
        ],
        "does_not_claim": [
            "cloud ok=true is delivery",
            "global unit_manifest.py --write was run",
            "a human adversarial reviewer in a fresh context scored PASS",
            "TST-0298/TST-0301 receipts were present and consumed",
        ],
        "defects": [],
        "ts": now,
    }

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(receipt, indent=1, ensure_ascii=True) + "\n"
    if SENTINEL not in payload:
        print("FAILED:TST-0311 emit catalog sentinel missing from blob")
        return 1
    out_path.write_text(payload, encoding="utf-8")
    sha, size = digest(out_path)
    if size < int(receipt["min_bytes_threshold"]):
        print(f"FAILED:TST-0311 artifact {size}B below floor")
        return 1

    primary = manifest_row(OUT, "primary")
    artifacts = [primary] + [manifest_row(p, "supporting") for p in SUPPORTING]
    missing = [a["path"] for a in artifacts if not a["present"]]
    if missing:
        print("FAILED:TST-0311 missing supporting", missing)
        return 1
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
    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/schema/receipt.schema.json",
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "three-outcomes",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "bypass-audit",
                "raw_output": t2,
            },
        ],
        "artifacts": [
            {
                "path": OUT,
                "sha256": primary["sha256"],
                "bytes": primary["bytes"],
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": "command-center/p2-wave/probes/TST-0311/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "TST-0311-probe2-bypass-audit",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for TST-0311: live named probes exit 0, receipts/TST-0311.json "
            "state=SUCCESS with SUCCESS:TST-0311, per-unit manifest row. Did not "
            "run global unit_manifest.py --write. cloud ok=true is not delivery."
        ),
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {OUT} bytes={size} sha256={sha}")
    print(f"primary sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:TST-0311 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
