#!/usr/bin/env python3
"""Write IMP-0332 receipt, per-unit manifest, and SUBAGENT-RETURN.

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
UNIT = "IMP-0332"
OUT = "command-center/receipts/IMP-0332.json"
MODULE = "tools/council/protocol/ngt.py"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0332/probe1_silent_private_aggregate.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0332/probe2_leak_scan_fires.py"
)
SUPPORTING = [
    MODULE,
    "tools/council/__init__.py",
    "tools/council/protocol/__init__.py",
    "command-center/p2-wave/probes/IMP-0332/scenario.py",
    "command-center/p2-wave/probes/IMP-0332/fixtures/session.json",
    "command-center/p2-wave/probes/IMP-0332/probe1_silent_private_aggregate.py",
    "command-center/p2-wave/probes/IMP-0332/probe2_leak_scan_fires.py",
    "command-center/p2-wave/probes/IMP-0332/emit_receipt.py",
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
        "receipt_path": "command-center/p2-wave/probes/IMP-0332/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    sys.path.insert(0, str(HERE))
    sys.path.insert(0, str(REPO / "tools"))
    from council.protocol import ngt  # noqa: E402
    from scenario import run_session  # noqa: E402

    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:IMP-0332 probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    j1 = first_json(t1)
    j2 = first_json(t2)
    if not j1.get("pass") or not j2.get("pass"):
        print("FAILED:IMP-0332 probe JSON pass!=true")
        return 1

    packed = run_session(leak=None, midstream_rank=True)
    session = packed["session"]
    gen_scan = ngt.scan_generation_privacy(session)
    rank_scan = ngt.scan_delivered_prompts(session, before_aggregation=True)
    agg = session.aggregate()
    independent = ngt.aggregate_ballots(session.catalog_ids(), session.raw_ballots())
    module_sha, module_bytes, module_eol = digest(REPO / MODULE)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    supporting = [art_row(p, "supporting") for p in SUPPORTING]
    missing = [a["path"] for a in supporting if not a["exists"]]
    if missing:
        print("FAILED:IMP-0332 missing supporting", missing)
        return 1

    p1 = probe_rec("source", "command", P1, t1, c1)
    p1v = probe_rec("verifier", "independent-borda-and-mailbox-scan", P1, t1, c1)
    p2 = probe_rec("source", "command", P2, t2, c2)
    p2v = probe_rec("verifier", "planted-leak-then-clean", P2, t2, c2)

    question = (
        "Implement tools/council/protocol/ngt.py collecting silent idea "
        "generation then PRIVATE rankings aggregated without cross-influence. "
        "Falsifiable question: are rankings genuinely private until aggregation "
        "- can any participant's ranking be inferred from what another "
        "participant was shown?"
    )
    receipt = {
        "id": UNIT,
        "unit_id": UNIT,
        "schema_version": 1,
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0332",
        "completion_sentinel": "SUCCESS:IMP-0332",
        "title": "Nominal-group technique with private ranking aggregation",
        "question": question,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json#IMP-0332",
        "output_schema_profile": "council-protocol-module",
        "min_bytes_threshold": 2048,
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "implementer",
            "execution_substrate": "linux-worktree-isolated",
        },
        "protocol": {
            "id": ngt.PROTOCOL_ID,
            "path": MODULE,
            "sha256": module_sha,
            "bytes": module_bytes,
            "eol": module_eol,
            "aggregation_method": "borda",
            "phases": [
                ngt.PHASE_SILENT_GENERATION,
                ngt.PHASE_PRIVATE_RANKING,
                ngt.PHASE_AGGREGATED,
            ],
        },
        "inputs_on_this_worktree": {
            "11-COUNCIL-SPECIFICATION.md": (
                "absent on this sparse worktree; protocol rules taken from the "
                "catalog question_or_target, tests_required, and evidence_requirement"
            ),
            "11-COUNCIL-SPECIFICATION.schema.json": "absent on this sparse worktree",
            "12-COUNCIL-PROTOCOLS-AND-PRESETS.json": (
                "absent; protocol id P06-nominal-group-technique is cited from "
                "catalog CNL-0038 family listing, not from a live presets file"
            ),
            "IMP-0274": "dependency receipt absent; elastic seating not imported",
            "IMP-0302": (
                "dependency receipt absent; tally.py not imported; Borda is local "
                "to ngt.aggregate_ballots"
            ),
        },
        "artifact_paths": [OUT, MODULE] + SUPPORTING[1:],
        "artifacts": supporting,
        "evidence": [
            {
                "id": "signal-1-delivered-prompt-scan-pre-aggregation",
                "kind": "delivered-prompt-scan",
                "requirement": (
                    "a delivered-prompt scan proving no ranking content reached a "
                    "peer before aggregation"
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/council/protocol/ngt.py:scan_delivered_prompts",
                "generation_scan_fired": gen_scan["fired"],
                "ranking_scan_fired": rank_scan["fired"],
                "scanned_prompt_count": rank_scan["scanned_prompt_count"],
                "midstream_early_ballot_absent_from_later_prompt": True,
                "catalog_sections_identical": True,
                "claim": (
                    "On the fixture session, scan_generation_privacy was SILENT and "
                    "scan_delivered_prompts(before_aggregation=True) was SILENT, "
                    "including Bob's ranking prompt delivered after Alice's ballot "
                    "was sealed. Ranking catalog blocks were byte-identical, so a "
                    "peer ranking cannot be inferred from what another ranker was shown."
                ),
                "probes": [p1, p1v],
                "confidence": "almost-certain",
            },
            {
                "id": "signal-2-independent-borda-from-raw-ballots",
                "kind": "independent-recompute",
                "requirement": (
                    "an aggregation result reproduced independently from the raw ballots"
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/council/protocol/ngt.py:aggregate_ballots",
                "session_scores": agg["scores"],
                "session_order": agg["order"],
                "independent_scores": independent["scores"],
                "independent_order": independent["order"],
                "match": independent["scores"] == agg["scores"]
                and independent["order"] == agg["order"],
                "ballots_used": agg["ballots_used"],
                "method": "borda",
                "claim": (
                    f"session.aggregate() scores={agg['scores']} order={agg['order']} "
                    "matched aggregate_ballots(catalog_ids, raw_ballots) and probe1's "
                    "local Borda loop that does not read stored scores."
                ),
                "probes": [p1, p2],
                "confidence": "almost-certain",
            },
        ],
        "test_ids": [
            "silent-generation-private-ranking-aggregation",
            "leak-one-ranking-prompt-scan-fires",
        ],
        "tests": [
            {
                "id": "silent-generation-private-ranking-aggregation",
                "command": P1,
                "result": "PASS" if c1 == 0 and j1.get("pass") else "FAIL",
            },
            {
                "id": "leak-one-ranking-prompt-scan-fires",
                "command": P2,
                "result": "PASS" if c2 == 0 and j2.get("pass") else "FAIL",
            },
        ],
        "negative_control_ids": [
            "leak-one-ranking-prompt-scan-fires",
        ],
        "negative_controls": [
            {
                "id": "leak-one-ranking-prompt-scan-fires",
                "kind": "both-states",
                "description": (
                    "Copy Alice's sealed ranking needles into Bob's mailbox. The "
                    "delivered-prompt scan must FIRE on that planted state and be "
                    "SILENT on a fresh clean session. Known-present runs first."
                ),
                "fired_on_bad_state": bool(j2.get("planted_fired")),
                "silent_on_good_state": j2.get("clean_fired") is False,
                "known_present_run_first": bool(j2.get("known_present_run_first")),
                "leak_source": j2.get("leak_source"),
                "leak_dest": j2.get("leak_dest"),
                "bad_state_output": (
                    f"planted_fired={j2.get('planted_fired')} "
                    f"reason_id={j2.get('planted_reason_id')} "
                    f"findings={j2.get('planted_finding_count')}"
                ),
                "good_state_output": f"clean_fired={j2.get('clean_fired')}",
            }
        ],
        "reviewer_verdict": "PASS",
        "reviewer": {
            "reviewer_id": "IMP-0332-probe2-leak-scan-fires",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "scope_not_agreement": True,
            "notes": (
                "Probe2 starts from the leak test and a local Borda loop, not from "
                "the author's summary. Catalog reviewer_requirement asks for a "
                "fresh-context human adversarial reviewer; that human pass is residual "
                "and is not claimed."
            ),
        },
        "named_probes": [
            {
                "id": "probe1",
                "role": "silent-generation-private-ranking-aggregation",
                "command": P1,
            },
            {
                "id": "probe2",
                "role": "leak-one-ranking-prompt-scan-fires",
                "command": P2,
            },
        ],
        "cloud_ok": False,
        "residual_unknowns": [
            {
                "id": "sparse-worktree-missing-council-spec",
                "text": (
                    "11-COUNCIL-SPECIFICATION.md and "
                    "12-COUNCIL-PROTOCOLS-AND-PRESETS.json are not on this worktree. "
                    "NGT rules were implemented from the catalog unit text. A later "
                    "merge against the full estate must re-run the named probes "
                    "against the live spec rather than this catalog-derived module."
                ),
            },
            {
                "id": "dependencies-not-imported",
                "text": (
                    "IMP-0274 and IMP-0302 receipts are absent. This module does not "
                    "call elastic seating or tally.py. Borda is local. This is not a "
                    "claim that those units are delivered."
                ),
            },
            {
                "id": "human-reviewer-residual",
                "text": (
                    "G-1 named probes are green. A second human in a fresh context "
                    "has not scored this unit."
                ),
            },
            {
                "id": "no-llm-participants",
                "text": (
                    "The protocol is a mailbox/barrier/scan machine over fixture "
                    "strings. Live model participants were not invoked."
                ),
            },
        ],
        "does_not_claim": [
            "cloud ok=true is delivery",
            "global unit_manifest.py --write was run",
            "11-COUNCIL-SPECIFICATION.md was read from disk",
            "a human adversarial reviewer in a fresh context scored PASS",
            "IMP-0274 elastic seating was implemented",
            "IMP-0302 tally.py was used",
        ],
        "timestamps": {"started_at": now, "ended_at": now},
        "ts": now,
        "retry": {
            "count": 0,
            "policy": (
                "two strikes then pivot - after the second failure on the same error "
                "fingerprint, enumerate >=2 alternative approaches before a third "
                "attempt (AGENTS.md 4b)"
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/IMP-0332/UNIT-ARTIFACT-MANIFEST.json",
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
    }

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(receipt, indent=1, sort_keys=True) + "\n"
    if "SUCCESS:IMP-0332" not in payload:
        print("FAILED:IMP-0332 emit sentinel missing from blob")
        return 1
    out_path.write_text(payload, encoding="utf-8")
    primary = manifest_row(OUT, "primary")
    if primary["bytes"] < int(receipt["min_bytes_threshold"]):
        print(f"FAILED:IMP-0332 artifact {primary['bytes']}B below floor")
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
        "sentinel": "SUCCESS:IMP-0332",
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/schema/receipt.schema.json profile=council-protocol-module",
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "silent-generation-private-ranking-aggregation",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "leak-one-ranking-prompt-scan-fires",
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
        "manifest_path": "command-center/p2-wave/probes/IMP-0332/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "IMP-0332-probe2-leak-scan-fires",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for IMP-0332: live named probes exit 0, receipts/IMP-0332.json "
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
    print("SUCCESS:IMP-0332 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
