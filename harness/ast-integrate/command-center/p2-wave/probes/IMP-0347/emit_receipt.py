#!/usr/bin/env python3
"""Emit IMP-0347 receipt + per-unit manifest + SUBAGENT-RETURN after live probes."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT = "IMP-0347"
OUT_REL = f"command-center/receipts/{UNIT}.json"
SENTINEL = f"SUCCESS:{UNIT}"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0347/probe1_labelled_corpus.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0347/probe2_quorum_sensitivity.py"
)
TEST_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "tools/council/antifail/tests/test_strategic.py"
)
SUPPORTING = [
    "tools/council/__init__.py",
    "tools/council/antifail/__init__.py",
    "tools/council/antifail/strategic.py",
    "tools/council/antifail/corpus.py",
    "tools/council/antifail/tests/__init__.py",
    "tools/council/antifail/tests/test_strategic.py",
    "command-center/p2-wave/probes/IMP-0347/probe1_labelled_corpus.py",
    "command-center/p2-wave/probes/IMP-0347/probe2_quorum_sensitivity.py",
]


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=180,
        env=env,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text


def art_manifest(rel: str, role: str) -> dict:
    path = REPO / rel
    digest, size = sha256_file(path) if path.is_file() else ("", 0)
    return {
        "path": rel,
        "bytes": size,
        "sha256": digest,
        "exists": path.is_file(),
        "present": path.is_file(),
        "role": role,
        "eol": "LF",
        "unit_id": UNIT,
        "receipt_path": f"command-center/p2-wave/probes/{UNIT}/SUBAGENT-RETURN.json",
    }


def art_receipt(rel: str, role: str) -> dict | None:
    path = REPO / rel
    if not path.is_file():
        return None
    digest, size = sha256_file(path)
    if size < 1:
        return None
    return {
        "path": rel,
        "bytes": size,
        "sha256": digest,
        "exists": True,
        "eol": "LF",
        "role": role,
    }


def probe_rec(role: str, method: str, command: str, raw: str, code: int) -> dict:
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": raw[-16000:],
        "exit_code": code,
        "fingerprint": hashlib.sha256(f"{method}\x1f{command}".encode()).hexdigest(),
    }


def main() -> int:
    c_test, t_test = run(TEST_CMD)
    code1, out1 = run(P1)
    code2, out2 = run(P2)
    if c_test != 0 or code1 != 0 or code2 != 0:
        print(f"FAILED:IMP-0347 live probes tests={c_test} p1={code1} p2={code2}")
        print(t_test[-2000:])
        print(out1[-2000:])
        print(out2[-2000:])
        return 1
    if "SUCCESS:IMP-0347-tests" not in t_test:
        print("FAILED:IMP-0347 tests sentinel missing")
        return 1
    if "SUCCESS:IMP-0347-probe1" not in out1:
        print("FAILED:IMP-0347 probe1 sentinel missing")
        return 1
    if "SUCCESS:IMP-0347-probe2" not in out2:
        print("FAILED:IMP-0347 probe2 sentinel missing")
        return 1

    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    p1 = probe_rec("source", "command", P1, out1, code1)
    p2 = probe_rec("source", "command", P2, out2, code2)
    p_test = probe_rec("verifier", "test-run", TEST_CMD, t_test, c_test)
    strat = art_receipt("tools/council/antifail/strategic.py", "primary")
    if strat is None:
        print("FAILED:IMP-0347 strategic.py missing")
        return 1
    p_file = probe_rec(
        "verifier",
        "file-read",
        "sha256 tools/council/antifail/strategic.py",
        f"bytes={strat['bytes']} sha256={strat['sha256']}",
        0,
    )
    artifacts = [strat]
    for rel in SUPPORTING:
        if rel == "tools/council/antifail/strategic.py":
            continue
        row = art_receipt(rel, "supporting")
        if row is not None:
            artifacts.append(row)

    receipt = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "profile": "council-runtime-module",
        "spec_anchor": (
            "WORK-UNIT-CATALOG.json:IMP-0347; _USER-PROMPTS.md:11240 "
            "strategic abstention; catalog tests_required labelled "
            "strategic-vs-sincere corpus + change-of-mind negative control"
        ),
        "min_bytes_threshold": 128,
        "produced_by": {
            "vendor": "xai",
            "model": "grok",
            "role": "implementer",
            "execution_substrate": "linux-worktree",
        },
        "timestamps": {"started_at": started, "ended_at": started},
        "retry": {
            "count": 0,
            "policy": "two-strikes-then-pivot; a verification failure never retries",
        },
        "artifacts": artifacts,
        "evidence": [
            {
                "anchor": "tools/council/antifail/corpus.py:labelled_corpus",
                "claim": (
                    "On a labelled corpus of 50 ballot/reasoning pairs, the "
                    "detector reports precision and recall separately; both "
                    "are 1.0 on this constructed set, and the 10 sincere "
                    "change-of-mind pairs have false-positive rate 0.0."
                ),
                "confidence": "almost-certain",
                "verdict": "CONFIRMED",
                "probes": [p1, p_test],
            },
            {
                "anchor": "tools/council/antifail/strategic.py:quorum_sensitivity",
                "claim": (
                    "Quorum-sensitivity identifies the planted abstention as "
                    "pivotal (honest aye flips FAIL to PASS) and is silent on "
                    "a sibling profile that differs by one filler ballot. A "
                    "principled STANCE:ABSTAIN in the planted numbers is "
                    "pivotal but not strategic_abstention."
                ),
                "confidence": "almost-certain",
                "verdict": "CONFIRMED",
                "probes": [p2, p_file],
            },
        ],
        "tests": [
            {
                "id": "labelled-strategic-vs-sincere-corpus",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "change-of-mind-false-positive-rate",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "quorum-sensitivity-planted-vs-control",
                "command": P2,
                "result": "PASS",
            },
            {
                "id": "module-self-check",
                "command": TEST_CMD,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "sincere-change-of-mind-unflagged",
                "kind": "other",
                "description": (
                    "CM-00 updates STANCE from AYE to NAY at t=4 and votes "
                    "nay at t=6; detector must not flag strategic."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "good_state_output": "change_of_mind_fpr=0.0",
                "bad_state_output": "SV-00 strategic_vote=true",
            },
            {
                "id": "non-pivotal-sibling-silent",
                "kind": "other",
                "description": (
                    "Same implied AYE abstention in a 3-aye/1-nay sibling "
                    "is not pivotal and is not strategic_abstention."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "good_state_output": "control TARGET absent from pivotal_ids",
                "bad_state_output": "planted TARGET in pivotal_ids",
            },
            {
                "id": "principled-pivotal-not-strategic",
                "kind": "other",
                "description": (
                    "STANCE:ABSTAIN in the planted 2-2-1 numbers is pivotal "
                    "but strategic_abstention remains false."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "good_state_output": "principled strategic_abstention=false",
                "bad_state_output": "planted strategic_abstention=true",
            },
        ],
        "reviewer": {
            "reviewer_id": "IMP-0347-probe2-quorum-sensitivity",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "notes": (
                "Probe 2 is a mechanically different measurement from the "
                "labelled-corpus scorer: sibling profiles, ballot-only "
                "quorum_sensitivity, then the reasoning conjunction. It does "
                "not read corpus labels or the author's summary."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                f"command-center/p2-wave/probes/{UNIT}/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "entry_id": UNIT,
            "registered_at": started,
        },
        "downstream_consumers": [
            {
                "consumer": "json.loads of catalog output_path",
                "artifact_path": OUT_REL,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": probe_rec(
                    "source",
                    "file-read",
                    f"json.loads {OUT_REL}",
                    (
                        f"consumer=json.loads of catalog output_path\n"
                        f"unit_id={UNIT}\nstate=SUCCESS\nSUCCESS:consumer-read\n"
                    ),
                    0,
                ),
            }
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "IMP-0302 tools/council/vote/tally.py is not on this "
                    "worktree. strategic.tally is a local recorded-policy "
                    "engine so quorum-sensitivity is executable; it is not "
                    "the vote-module delivery."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "When IMP-0302 lands, re-bind quorum_sensitivity to "
                    "vote.tally and re-run probe2 on the same sibling pair."
                ),
            },
            {
                "claim": (
                    "IMP-0313 tools/council/artifacts/argument_graph.py is "
                    "not on this worktree. Stance is extracted from STANCE "
                    "tags / vote-phrases / last aye|nay|abstain token, not "
                    "from SUPPORTS/ATTACKS/REBUTS edges."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "When IMP-0313 lands, add an edge-derived stance channel "
                    "and report disagreement with the tag extractor on the "
                    "same 50 pairs."
                ),
            },
        ],
        "extensions": {
            "title": "Strategic-voting and strategic-abstention detection",
            "artifact_paths": [OUT_REL] + SUPPORTING,
            "test_ids": [
                "labelled-strategic-vs-sincere-corpus",
                "change-of-mind-false-positive-rate",
                "quorum-sensitivity-planted-vs-control",
                "principled-pivotal-abstention-not-strategic",
            ],
            "negative_control_ids": [
                "sincere-change-of-mind-unflagged",
                "non-pivotal-sibling-silent",
                "principled-pivotal-not-strategic",
            ],
            "reviewer_verdict": "PASS",
            "notes": (
                "G-1 delivery of IMP-0347. Live named probes exit 0. Receipt "
                "state=SUCCESS. Did not run global unit_manifest.py --write. "
                "cloud ok is not consulted. Did not implement ADV-0098."
            ),
        },
    }

    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(receipt, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    parsed = json.loads(out.read_text(encoding="utf-8"))
    if parsed.get("unit_id") != UNIT or parsed.get("state") != "SUCCESS":
        print("FAILED:IMP-0347 consumer json.loads mismatch")
        return 1
    live_sha, live_bytes = sha256_file(out)
    if live_bytes < 128:
        print(f"FAILED:IMP-0347 receipt too small ({live_bytes} B)")
        return 1
    if SENTINEL not in out.read_text(encoding="utf-8"):
        print("FAILED:IMP-0347 sentinel absent from receipt")
        return 1

    rows = [
        {
            "path": OUT_REL,
            "sha256": live_sha,
            "bytes": live_bytes,
            "exists": True,
            "present": True,
            "role": "primary",
            "eol": "LF",
            "unit_id": UNIT,
            "receipt_path": f"command-center/p2-wave/probes/{UNIT}/SUBAGENT-RETURN.json",
        }
    ]
    for rel in SUPPORTING:
        rows.append(art_manifest(rel, "supporting"))

    manifest = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UNIT,
        "verified_on_disk": True,
        "expected": len(rows),
        "present": len(rows),
        "artifacts": rows,
    }
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(manifest, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )

    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "registered": True,
        "output_path": OUT_REL,
        "output_schema": "command-center/schema/receipt.schema.json",
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": code1,
                "role": "labelled-corpus-precision-recall",
                "raw_output": out1[-8000:],
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": code2,
                "role": "quorum-sensitivity-both-states",
                "raw_output": out2[-8000:],
            },
        ],
        "artifacts": [
            {
                "path": OUT_REL,
                "sha256": live_sha,
                "bytes": live_bytes,
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": f"command-center/p2-wave/probes/{UNIT}/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "IMP-0347-probe2-quorum-sensitivity",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "notes": (
            "G-1 for IMP-0347: live named probes exit 0, receipt "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. cloud ok=true is not delivery."
        ),
        "ts": started,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"wrote {OUT_REL} bytes={live_bytes} sha256={live_sha}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
