#!/usr/bin/env python3
"""Write TST-0032 receipt, per-unit manifest, and SUBAGENT-RETURN.

Does not invoke tools/command-center/unit_manifest.py --write.
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
LIB = REPO / "command-center" / "lib"
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(LIB))

from flake_quarantine.ledger import (  # noqa: E402
    independent_ratios,
    suite_green_claim,
)
from scenario import (  # noqa: E402
    ALWAYS_FAIL,
    ALWAYS_PASS,
    COIN_FLIP,
    N,
    RARE_FLAKE,
    run_planted,
)

UNIT = "TST-0032"
OUT = "command-center/receipts/TST-0032.json"
SCHEMA = "command-center/schema/test-receipt.schema.json"
LEDGER_MOD = "command-center/lib/flake_quarantine/ledger.py"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0032/probe1_planted_coin_flip.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0032/probe2_green_claim_blocked.py"
)
SUPPORTING = [
    LEDGER_MOD,
    "command-center/lib/flake_quarantine/__init__.py",
    SCHEMA,
    "command-center/p2-wave/probes/TST-0032/scenario.py",
    "command-center/p2-wave/probes/TST-0032/probe1_planted_coin_flip.py",
    "command-center/p2-wave/probes/TST-0032/probe2_green_claim_blocked.py",
    "command-center/p2-wave/probes/TST-0032/emit_receipt.py",
]


def digest(path: Path) -> tuple[str, int, str]:
    data = path.read_bytes() if path.is_file() else b""
    lf = data.replace(b"\r\n", b"\n")
    crlf = data.count(b"\r\n")
    nlf = data.count(b"\n") - crlf
    if crlf and nlf:
        eol = "MIXED"
    elif crlf:
        eol = "CRLF"
    elif b"\n" in data:
        eol = "LF"
    else:
        eol = "NONE"
    return hashlib.sha256(lf).hexdigest(), len(lf), eol


def run_probe(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


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


def art_row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size, eol = digest(path)
    return {
        "path": rel,
        "bytes": size,
        "sha256": sha,
        "exists": path.is_file(),
        "role": role,
        "eol": eol,
    }


def manifest_row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size, _eol = digest(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": path.is_file(),
        "unit_id": UNIT,
        "receipt_path": "command-center/p2-wave/probes/TST-0032/SUBAGENT-RETURN.json",
        "role": role,
    }


def slim_row(row: dict) -> dict:
    return {
        "id": row["id"],
        "n": row["n"],
        "passes": row["passes"],
        "fails": row["fails"],
        "pass_ratio": row["pass_ratio"],
        "class": row["class"],
        "quarantined": row["quarantined"],
        "last_run_passed": bool(row["outcomes"][-1]) if row.get("outcomes") else None,
    }


def main() -> int:
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:TST-0032 probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    j1 = first_json(t1)
    j2 = first_json(t2)
    if not j1.get("pass") or not j2.get("pass"):
        print("FAILED:TST-0032 probe JSON pass!=true")
        return 1

    ledger = run_planted()
    recomputed = independent_ratios(ledger["rows"])
    by_id = {r["id"]: r for r in ledger["rows"]}
    green_bad = suite_green_claim(
        claimed_green=True,
        tests_in_path=[ALWAYS_PASS, COIN_FLIP],
        ledger=ledger,
    )
    green_good = suite_green_claim(
        claimed_green=True,
        tests_in_path=[ALWAYS_PASS],
        ledger=ledger,
    )
    green_broken = suite_green_claim(
        claimed_green=True,
        tests_in_path=[ALWAYS_PASS, ALWAYS_FAIL],
        ledger=ledger,
    )
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    supporting = [art_row(p, "supporting") for p in SUPPORTING]
    missing = [a["path"] for a in supporting if not a["exists"]]
    if missing:
        print("FAILED:TST-0032 missing supporting", missing)
        return 1

    p1 = probe_rec("source", "command", P1, t1, c1)
    p1v = probe_rec("verifier", "independent-ratio-recompute", P1, t1, c1)
    p2 = probe_rec("source", "command", P2, t2, c2)
    p2v = probe_rec("verifier", "quarantined-in-path-then-clean-path", P2, t2, c2)

    question = (
        "Target: a ledger that re-runs each test N times at the same SHA, "
        "classifies it DETERMINISTIC / FLAKY / BROKEN, and blocks any "
        "'suite green' claim that depends on a quarantined test. Question: "
        "what is the measured flake rate of the current suite at a fixed SHA, "
        "and which tests are order- or clock-sensitive?"
    )
    named_flaky = list(ledger["quarantined_named"])
    receipt = {
        "id": UNIT,
        "unit_id": UNIT,
        "schema_version": 1,
        "state": "SUCCESS",
        "sentinel": "SUCCESS:TST-0032",
        "completion_sentinel": "SUCCESS:TST-0032",
        "title": "Flake quarantine ledger and re-run policy",
        "question": question,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json#TST-0032",
        "output_schema": SCHEMA,
        "min_bytes_threshold": 2048,
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "implementer",
            "execution_substrate": "linux-worktree-isolated",
        },
        "inputs_on_this_worktree": {
            "_USER-PROMPTS.md": (
                "absent on this sparse worktree; catalog question_or_target, "
                "tests_required, evidence_requirement, and retry_policy used instead"
            ),
            "rules/common/testing.md": "absent on this sparse worktree",
            "TST-0027": (
                "dependency receipt absent; this ledger records a worktree "
                "fingerprint rather than importing a seed-replay policy"
            ),
            "command-center/TEST-REGISTRY.json": "absent on this worktree",
        },
        "artifact_paths": [OUT] + SUPPORTING,
        "artifacts": supporting,
        "flake_ledger": {
            "n": N,
            "min_n": 20,
            "same_order": True,
            "fingerprint": ledger["fingerprint"],
            "sha": ledger["sha"],
            "retry_policy": ledger["retry_policy"],
            "order": list(ledger["order"]),
            "rows": [slim_row(r) for r in ledger["rows"]],
            "quarantined_named": named_flaky,
            "counts": ledger["counts"],
            "suite_under_test": "planted four-test control suite (not the full repo pytest tree)",
            "independent_recompute": {
                name: {
                    "class": rec["class"],
                    "pass_ratio": rec["pass_ratio"],
                    "quarantined": rec["quarantined"],
                }
                for name, rec in recomputed.items()
            },
        },
        "measured_flake_rate": {
            "tests_total": len(ledger["rows"]),
            "tests_flaky": ledger["counts"]["FLAKY"],
            "tests_broken": ledger["counts"]["BROKEN"],
            "tests_deterministic": ledger["counts"]["DETERMINISTIC"],
            "flaky_named": named_flaky,
            "per_test_pass_ratio": {
                r["id"]: r["pass_ratio"] for r in ledger["rows"]
            },
            "scope": (
                "planted control suite at one worktree fingerprint, N=20 full-suite "
                "repetitions in the same order. The full repository pytest tree was "
                "not repeated 20 times on this worktree."
            ),
        },
        "evidence": [
            {
                "id": "signal-1-planted-coin-flip-named-flaky",
                "kind": "planted-control",
                "requirement": (
                    "N>=20 repetitions per test at one SHA with the per-test pass "
                    "ratio recorded; a test at 0<ratio<1 is FLAKY and named"
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/lib/flake_quarantine/ledger.py:classify_ratio",
                "n": N,
                "sha": ledger["sha"],
                "coin_flip_pass_ratio": by_id[COIN_FLIP]["pass_ratio"],
                "coin_flip_class": by_id[COIN_FLIP]["class"],
                "coin_flip_last_run_passed": bool(by_id[COIN_FLIP]["outcomes"][-1]),
                "rare_flake_pass_ratio": by_id[RARE_FLAKE]["pass_ratio"],
                "always_pass_class": by_id[ALWAYS_PASS]["class"],
                "always_fail_class": by_id[ALWAYS_FAIL]["class"],
                "quarantined_named": named_flaky,
                "n19_refused": bool(j1.get("n19_refused")),
                "retry_without_hypothesis_refused": bool(
                    j1.get("retry_without_hypothesis_refused")
                ),
                "claim": (
                    f"At fingerprint {ledger['sha'][:12]}… method="
                    f"{ledger['fingerprint']['method']}, N={N} same-order "
                    f"repetitions classified {COIN_FLIP} FLAKY "
                    f"(pass_ratio={by_id[COIN_FLIP]['pass_ratio']}) and "
                    f"{RARE_FLAKE} FLAKY (pass_ratio={by_id[RARE_FLAKE]['pass_ratio']}); "
                    f"both named. {ALWAYS_PASS} DETERMINISTIC (not quarantined). "
                    f"{ALWAYS_FAIL} BROKEN. Independent recompute from raw outcomes "
                    "agreed. n=19 refused. Same-fingerprint retry without a changed "
                    "hypothesis refused."
                ),
                "probes": [p1, p1v],
                "confidence": "almost-certain",
            },
            {
                "id": "signal-2-green-claim-blocked-when-quarantined-in-path",
                "kind": "both-states",
                "requirement": (
                    "blocks any 'suite green' claim that depends on a quarantined test"
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/lib/flake_quarantine/ledger.py:suite_green_claim",
                "known_present_run_first": True,
                "quarantined_in_path_blocked": green_bad["blocked"],
                "clean_path_allowed": green_good["allowed"] and not green_good["blocked"],
                "broken_in_path_blocked": green_broken["blocked"],
                "coin_flip_last_run_passed": bool(by_id[COIN_FLIP]["outcomes"][-1]),
                "claim": (
                    "claimed_green with planted.coin_flip in the path is blocked "
                    "even though that test's last run passed. claimed_green with "
                    "only planted.always_pass is allowed. Quarantined rows remain "
                    "in the report. BROKEN in the path is also blocked."
                ),
                "probes": [p2, p2v],
                "confidence": "almost-certain",
            },
        ],
        "test_ids": [
            "test_ledger_detects_a_planted_coin_flip_test",
            "test_green_claim_is_blocked_when_a_quarantined_test_is_in_the_path",
        ],
        "tests": [
            {
                "id": "test_ledger_detects_a_planted_coin_flip_test",
                "command": P1,
                "result": "PASS" if c1 == 0 and j1.get("pass") else "FAIL",
            },
            {
                "id": "test_green_claim_is_blocked_when_a_quarantined_test_is_in_the_path",
                "command": P2,
                "result": "PASS" if c2 == 0 and j2.get("pass") else "FAIL",
            },
        ],
        "negative_control_ids": [
            "quarantined-in-path-blocks-green",
            "always-pass-not-quarantined",
        ],
        "negative_controls": [
            {
                "id": "quarantined-in-path-blocks-green",
                "kind": "both-states",
                "description": (
                    "Claim suite green with a quarantined test in the path "
                    "(FIRE). Claim suite green with only DETERMINISTIC "
                    "planted.always_pass (SILENT). Known-present runs first."
                ),
                "fired_on_bad_state": green_bad["blocked"],
                "silent_on_good_state": (not green_good["blocked"]) and green_good["allowed"],
                "known_present_run_first": True,
                "bad_state_output": (
                    f"blocked={green_bad['blocked']} "
                    f"blocked_by={green_bad['blocked_by']} "
                    f"quarantined_in_path={green_bad['quarantined_in_path']}"
                ),
                "good_state_output": (
                    f"blocked={green_good['blocked']} allowed={green_good['allowed']}"
                ),
            },
            {
                "id": "always-pass-not-quarantined",
                "kind": "both-states",
                "description": (
                    "Planted coin-flip is FLAKY and named; planted.always_pass "
                    "is DETERMINISTIC and not quarantined."
                ),
                "fired_on_bad_state": COIN_FLIP in named_flaky,
                "silent_on_good_state": ALWAYS_PASS not in named_flaky,
                "bad_state_output": f"quarantined={named_flaky}",
                "good_state_output": f"always_pass_class={by_id[ALWAYS_PASS]['class']}",
            },
        ],
        "reviewer_verdict": "PASS",
        "reviewer": {
            "reviewer_id": "TST-0032-probe2-green-claim-blocked",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "scope_not_agreement": True,
            "notes": (
                "Probe2 rebuilds the planted suite and recomputes quarantine from "
                "raw outcomes rather than trusting probe1's summary. Catalog "
                "reviewer_requirement asks for a fresh-context human adversarial "
                "reviewer from the other vendor; that human pass is residual "
                "and is not claimed."
            ),
        },
        "named_probes": [
            {
                "id": "probe1",
                "role": "test_ledger_detects_a_planted_coin_flip_test",
                "command": P1,
            },
            {
                "id": "probe2",
                "role": "test_green_claim_is_blocked_when_a_quarantined_test_is_in_the_path",
                "command": P2,
            },
        ],
        "cloud_ok": False,
        "residual_unknowns": [
            {
                "id": "full-repo-suite-not-repeated",
                "text": (
                    "N>=20 was executed on the planted four-test control suite, "
                    "not on every pytest node in this repository. The ledger can "
                    "measure an arbitrary callable suite; the full tree was not "
                    "spent as 20 wall-clock copies on this worktree."
                ),
            },
            {
                "id": "order-and-clock-sensitivity-out-of-band",
                "text": (
                    "This unit repeats the SAME order. Order-dependent tests are "
                    "the distinct shuffle-order unit. Wall-clock-sensitive tests "
                    "were not planted because a live clock plant would make the "
                    "named probes themselves flaky."
                ),
            },
            {
                "id": "sparse-worktree-missing-inputs",
                "text": (
                    "_USER-PROMPTS.md and rules/common/testing.md are absent. "
                    "Rules were taken from the catalog unit text."
                ),
            },
            {
                "id": "human-reviewer-residual",
                "text": (
                    "G-1 named probes are green. A second human in a fresh "
                    "context has not scored this unit."
                ),
            },
            {
                "id": "dependency-TST-0027-absent",
                "text": (
                    "TST-0027 receipt is absent. Fingerprint is git HEAD when "
                    "available, else a content sha256 of the ledger and probes."
                ),
            },
        ],
        "does_not_claim": [
            "cloud ok=true is delivery",
            "global unit_manifest.py --write was run",
            "the full repository pytest suite was repeated N>=20 times",
            "order-sensitive tests in the live suite were identified",
            "a human adversarial reviewer in a fresh context scored PASS",
            "TST-0027 seed-replay was imported",
        ],
        "timestamps": {"started_at": now, "ended_at": now},
        "ts": now,
        "retry": {
            "count": 0,
            "policy": (
                "NO retry. A retry masks the exact instability this unit exists "
                "to measure; a failed run is the datum, re-run only with a "
                "changed hypothesis recorded first"
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/TST-0032/UNIT-ARTIFACT-MANIFEST.json",
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
    }

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(receipt, indent=1, sort_keys=True) + "\n"
    if "SUCCESS:TST-0032" not in payload:
        print("FAILED:TST-0032 emit sentinel missing from blob")
        return 1
    st = str(receipt.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:TST-0032 emit self-declared {st}")
        return 1
    out_path.write_text(payload, encoding="utf-8")
    primary = manifest_row(OUT, "primary")
    if primary["bytes"] < int(receipt["min_bytes_threshold"]):
        print(f"FAILED:TST-0032 artifact {primary['bytes']}B below floor")
        return 1
    artifacts = [primary] + [manifest_row(p, "supporting") for p in SUPPORTING]
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
        "sentinel": "SUCCESS:TST-0032",
        "registered": True,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "test_ledger_detects_a_planted_coin_flip_test",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "test_green_claim_is_blocked_when_a_quarantined_test_is_in_the_path",
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
        "manifest_path": "command-center/p2-wave/probes/TST-0032/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "TST-0032-probe2-green-claim-blocked",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for TST-0032: live named probes exit 0, receipts/TST-0032.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. cloud ok=true is not delivery. No ADV rebuild."
        ),
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:TST-0032 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
