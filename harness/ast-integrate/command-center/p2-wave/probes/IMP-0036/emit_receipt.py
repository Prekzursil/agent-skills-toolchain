#!/usr/bin/env python3
"""Emit command-center/receipts/IMP-0036.json from live probe measurements."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools"))

OUT = "command-center/receipts/IMP-0036.json"
SCHEMA_PACKET = "tools/plugin/schema/divergence-decision.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0036/probe1_packets.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0036/probe2_independent_differ.py"
)
T1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "tools/plugin/tests/test_divergence_packet.py"
)
QUESTION = (
    "For every file classified DIVERGED, emit a reviewable decision packet "
    "containing both unique-line sets, the last repo commit touching the path, "
    "the live mtime, and a recommended action — and make the tooling refuse to "
    "act on a DIVERGED file until a recorded decision exists. Provenance, not "
    "size, decides authorship."
)


def sha_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:32]


def find_line(rel: str, snippet: str) -> int:
    path = REPO / rel
    text = path.read_text(encoding="utf-8")
    idx = text.find(snippet)
    if idx < 0:
        raise SystemExit(f"FAILED:IMP-0036 snippet not in {rel}: {snippet[:80]}")
    return text[:idx].count("\n") + 1


def ev(rel: str, snippet: str, kind: str, claim: str) -> dict:
    line = find_line(rel, snippet)
    return {
        "path": rel,
        "line": line,
        "snippet": snippet,
        "kind": kind,
        "claim": claim,
        "anchor": f"{rel}:{line}",
    }


def run(cmd: str) -> tuple[int, str]:
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=120,
    )
    return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()


def main() -> int:
    rc_t, out_t = run(T1)
    rc1, out1 = run(P1)
    rc2, out2 = run(P2)
    if rc_t != 0 or rc1 != 0 or rc2 != 0:
        print("FAILED:IMP-0036 emit probes")
        print(out_t[-2000:])
        print(out1[-2000:])
        print(out2[-2000:])
        return 1

    p1 = json.loads((HERE / "probe1-packets.raw.json").read_text(encoding="utf-8"))
    p2 = json.loads((HERE / "probe2-independent.raw.json").read_text(encoding="utf-8"))
    packets = p1["packets"]
    n = len(packets)
    if n != 28:
        print(f"FAILED:IMP-0036 emit expected 28 packets, got {n}")
        return 1

    e1 = ev(
        "tools/plugin/packet.py",
        'action = HOLD',
        "live-tree",
        "DIVERGED packets recommend HOLD-FOR-RECORDED-DECISION and never auto-resolve.",
    )
    e2 = ev(
        "tools/plugin/gate.py",
        "DIVERGED-NO-RECORDED-DECISION",
        "live-tree",
        "Acting on DIVERGED without a recorded decision is refused.",
    )
    e3 = ev(
        "tools/plugin/packet.py",
        '"kind": ADVISORY',
        "live-tree",
        "Recommendation is kind=advisory and may_authorize_act=false.",
    )
    e4 = ev(
        "tools/plugin/packet.py",
        '"kind": RECORDED',
        "live-tree",
        "Decision is kind=recorded, machine-distinguishable from recommendation.",
    )
    e5 = ev(
        "tools/plugin/packet.py",
        "mtime_is_authorship_signal",
        "live-tree",
        "mtime is recorded on the packet and is never an authorship signal.",
    )
    e6 = ev(
        "tools/plugin/independent_differ.py",
        "blake2s",
        "live-tree",
        "Independent differ re-extracts unique lines via blake2s digest sets.",
    )
    e7 = ev(
        "command-center/WORK-UNIT-CATALOG.json",
        "Diverged-file decision packet (never auto-resolve)",
        "dossier",
        "Catalog unit IMP-0036 contracts the packet and the refuse-to-act gate.",
    )

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    (REPO / "command-center" / "receipts").mkdir(parents=True, exist_ok=True)

    doc = {
        "unit_id": "IMP-0036",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0036",
        "completion_sentinel": "SUCCESS:IMP-0036",
        "schema_version": 1,
        "title": "Diverged-file decision packet (never auto-resolve)",
        "question": QUESTION,
        "question_or_target": QUESTION,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:IMP-0036",
        "min_bytes_threshold": 2048,
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "implementer",
            "execution_substrate": "headless-linux",
        },
        "implementation": {
            "packet_module": "tools/plugin/packet.py",
            "gate_module": "tools/plugin/gate.py",
            "classifier_module": "tools/plugin/classifier.py",
            "independent_differ": "tools/plugin/independent_differ.py",
            "schema": SCHEMA_PACKET,
            "tests": "tools/plugin/tests/test_divergence_packet.py",
        },
        "measurement": {
            "host_present_trees": p1["host_present_trees"],
            "cited_owner_live_tree": False,
            "packet_count": n,
            "nonempty_unique_one_side": p1["nonempty_unique_one_side"],
            "both_unique_sets": p1["both_unique_sets"],
            "by_classification": p1["by_classification"],
            "independent_set_equality": p2["set_equality"],
            "diverged_refused_without_decision": p2["diverged_refused_without_decision"],
            "diverged_allowed_after_record": p2["diverged_allowed_after_record"],
            "one_directional_mutant_misclassified": p2[
                "one_directional_mutant_misclassified"
            ],
            "mtime_not_authorship": p2["mtime_not_authorship"],
            "size_not_authorship": p2["size_not_authorship"],
            "fixture_note": (
                "This Linux worktree has no live ~/.claude/rules tree. "
                "Packets were generated for 28 reconstructed content-differing "
                "fixture pairs (F6 cardinality), not the owner's 2026-08-09 live bytes."
            ),
        },
        "evidence": [
            {
                **e1,
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "probes": [
                    {
                        "command": P1,
                        "exit_code": rc1,
                        "fingerprint": sha_text(P1 + out1),
                        "method": "command",
                        "raw_output": out1[-1200:],
                        "role": "source",
                    },
                    {
                        "command": P2,
                        "exit_code": rc2,
                        "fingerprint": sha_text(P2 + out2),
                        "method": "command",
                        "raw_output": out2[-1200:],
                        "role": "verifier",
                    },
                ],
            },
            {
                **e2,
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "probes": [
                    {
                        "command": P2,
                        "exit_code": rc2,
                        "fingerprint": sha_text(P2 + "gate"),
                        "method": "command",
                        "raw_output": out2[-1200:],
                        "role": "source",
                    },
                    {
                        "command": T1,
                        "exit_code": rc_t,
                        "fingerprint": sha_text(T1 + out_t),
                        "method": "command",
                        "raw_output": out_t[-800:],
                        "role": "verifier",
                    },
                ],
            },
            e3,
            e4,
            e5,
            e6,
            e7,
        ],
        "tests": [
            {
                "id": "test_packet_contains_both_unique_sets",
                "name": "DIVERGED packet contains both unique-line sets",
                "command": T1,
                "result": "PASS",
            },
            {
                "id": "T-PROBE-1-PACKETS",
                "name": "28 content-differing packets, unique lines on at least one side",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "T-PROBE-2-INDEPENDENT-DIFFER",
                "name": "blake2s differ set-equals packet unique lines; refuse without decision",
                "command": P2,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "act-diverged-without-decision",
                "kind": "known-broken-fixture",
                "description": (
                    "Acting on a DIVERGED file with only an advisory recommendation "
                    "must be refused (DIVERGED-NO-RECORDED-DECISION)."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "refused reason=DIVERGED-NO-RECORDED-DECISION",
                "good_state_output": "ok after record_decision KEEP-BOTH",
            },
            {
                "id": "one-directional-classifier-mutant",
                "kind": "mutation",
                "description": (
                    "A one-directional repo-extra classifier labels DIVERGED as "
                    "REPO-AHEAD. The two-directional classifier does not."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "mutant=REPO-AHEAD",
                "good_state_output": "classification=DIVERGED",
            },
        ],
        "reviewer": {
            "reviewer_id": "IMP-0036-independent-blake2s-differ",
            "independent": True,
            "fresh_context": True,
            "verdict": "PASS",
            "scope_not_agreement": True,
            "method": (
                "Re-extract unique lines with blake2s digest-set difference "
                "(tools/plugin/independent_differ.py), not plugin.lines str-set "
                "difference. Require exact set equality. Confirm mtime/size flags "
                "are false and DIVERGED act is refused until a recorded decision."
            ),
        },
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": SCHEMA_PACKET, "exists": True, "role": "supporting"},
            {
                "path": "tools/plugin/packet.py",
                "exists": True,
                "role": "supporting",
            },
            {
                "path": "tools/plugin/gate.py",
                "exists": True,
                "role": "supporting",
            },
            {
                "path": "tools/plugin/tests/test_divergence_packet.py",
                "exists": True,
                "role": "control",
            },
            {
                "path": "command-center/p2-wave/probes/IMP-0036/packets.json",
                "exists": True,
                "role": "supporting",
            },
        ],
        "named_probes": [
            {"id": "probe1", "command": P1, "role": "packet-generation"},
            {"id": "probe2", "command": P2, "role": "independent-differ"},
        ],
        "manifest_registration": {
            "manifest_path": (
                "command-center/p2-wave/probes/IMP-0036/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "registered": True,
            "global_catalog_write": False,
        },
        "downstream_consumers": [
            {
                "artifact_path": OUT,
                "consumer": "command-center/p2-wave/_measure_one_delivered.py",
                "executed": False,
                "read_ok": False,
                "note": (
                    "Named probes in this receipt re-ran exit 0 before write. "
                    "G-1 measure is a later verifier and is not claimed here."
                ),
                "probe": {
                    "command": "python3 command-center/p2-wave/_measure_one_delivered.py IMP-0036",
                    "method": "command",
                    "role": "verifier",
                },
            }
        ],
        "retry": {"count": 0, "policy": "two-strikes-then-pivot"},
        "residual_unknowns": [
            {
                "claim": (
                    "Owner live ~/.claude/rules 28-file byte identity versus these "
                    "fixtures is NOT-CHECKED on this Linux worktree (host trees absent)."
                ),
                "settling_experiment": (
                    "Re-run probe1_packets.py against a machine that has the live "
                    "rules tree and require 28 packets over those paths."
                ),
                "verdict": "NOT-CHECKED",
            }
        ],
        "timestamps": {"started_at": "2026-08-24T18:35:00Z", "ended_at": now},
        "answer": (
            "DIVERGED files get a reviewable packet (both unique-line sets, git log "
            "%cI, live mtime, advisory HOLD) and the gate refuses to act until a "
            "recorded decision exists. Provenance is unique-line sets, not size or "
            "mtime. SUCCESS:IMP-0036"
        ),
    }
    path = REPO / OUT
    path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {OUT} bytes={path.stat().st_size}")
    print("SUCCESS:IMP-0036 receipt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
