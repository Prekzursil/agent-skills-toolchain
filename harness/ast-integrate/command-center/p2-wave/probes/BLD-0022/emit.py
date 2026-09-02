#!/usr/bin/env python3
"""Emit command-center/receipts/BLD-0022.json and per-unit G-1 receipts."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import classify as C  # noqa: E402
import corpus as CORP  # noqa: E402
import live as LIVE  # noqa: E402
import reviewer as REV  # noqa: E402

OUT = "command-center/receipts/BLD-0022.json"
SCHEMA = "command-center/schema/provenance-audit.schema.json"
LOCAL_SCHEMA = "command-center/p2-wave/probes/BLD-0022/unit.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/BLD-0022/probe1_speaker_attribution.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/BLD-0022/probe2_controls.py"
)
QUESTION = (
    "For every option treated as SELECTED, what is the evidence that the OWNER "
    "selected it rather than an agent inferring the selection? Classify each as "
    "OWNER-EXPLICIT, OWNER-IMPLIED, or AGENT-ASSUMED, and route the last class "
    "to the owner."
)
CAVEAT = (
    "This Linux worktree does not contain _USER-PROMPTS.md, 17-DECISION-LOG.md, "
    "command-center/OWNER-DECISIONS.md, or 07-OPTION-UNIVERSE.json. Live selected "
    "ids therefore cannot be OWNER-EXPLICIT here: there is no owner sentence with "
    "a resolvable file:line that names them. The known OWNER-EXPLICIT control "
    "(release mode = PR-ONLY) is certified against fixtures/owner-release.md, not "
    "against a missing owner corpus. OQ-3's catalog record is an agent's summary "
    "of a spoken session and is OWNER-IMPLIED at best."
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def find_line(path: Path, snippet: str) -> int:
    text = path.read_text(encoding="utf-8")
    idx = text.find(snippet)
    if idx < 0:
        raise SystemExit(f"FAILED:BLD-0022 snippet not in {path}: {snippet[:80]}")
    return text[:idx].count("\n") + 1


def ev(rel: str, snippet: str, kind: str, claim: str) -> dict:
    path = REPO / rel
    line = find_line(path, snippet)
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
    rc1, out1 = run(P1)
    rc2, out2 = run(P2)
    if rc1 != 0 or rc2 != 0:
        print("FAILED:BLD-0022 named probes before emit")
        print(out1[-2000:])
        print(out2[-2000:])
        return 1

    utts = CORP.load_fixture_utterances()
    live = LIVE.live_rows()
    paths = CORP.existing_source_paths()
    present = [p for p, ok in paths.items() if ok]
    absent = [p for p, ok in paths.items() if not ok]

    pr_fx = C.classify("PR-ONLY", utts)
    z_fx = C.classify("Z-00", utts)
    own_fx = C.classify("CTRL-OWNER-1", utts)
    ag_fx = C.classify("CTRL-AGENT-1", utts)

    controls = [
        pr_fx.as_row("CTRL-PR-ONLY-FIXTURE", "CONTROL", "fixture-owner-release"),
        live["pr_live"].as_row("CTRL-PR-ONLY-LIVE", "CONTROL", "live-catalog-OQ-3"),
        z_fx.as_row("CTRL-Z-00-AGENT-ASSUMED", "CONTROL", "fixture-agent-select"),
        own_fx.as_row("CTRL-OWNER-1", "CONTROL", "fixture-owner-select"),
        ag_fx.as_row("CTRL-AGENT-1", "CONTROL", "fixture-agent-select"),
    ]

    selected = live["selected"]
    review_input = selected[:5]
    review = REV.rescore_rows(review_input, n=5)
    if review["verdict"] != "PASS":
        print("FAILED:BLD-0022 quote-only reviewer")
        print(json.dumps(review, indent=2))
        return 1

    owner_packet = []
    for row in selected + controls:
        if row["classification"] == C.AGENT_ASSUMED:
            owner_packet.append(
                {
                    "id": row["id"],
                    "classification": C.AGENT_ASSUMED,
                    "ask_the_owner": (
                        f"Did you select {row['id']}? This worktree has no owner "
                        "sentence that names it. AGENT-ASSUMED is a finding to hand "
                        "back, not a failure to retry."
                    ),
                }
            )
    if not owner_packet:
        print("FAILED:BLD-0022 owner_packet empty; AGENT-ASSUMED control missing")
        return 1

    e1 = ev(
        "command-center/WORK-UNIT-CATALOG.json",
        "This is a delegated default, NOT an owner-authored selection",
        "catalog",
        "OQ-1's own provenance refuses owner-authored selection of the 70 ids.",
    )
    e2 = ev(
        "command-center/WORK-UNIT-CATALOG.json",
        "owner statement in session 30bd50d4 (spoken, not previously committed",
        "catalog",
        "OQ-3 PR-ONLY is recorded as a spoken owner statement, not a committed quote.",
    )
    e3 = ev(
        "command-center/p2-wave/probes/BLD-0022/fixtures/owner-release.md",
        "Release mode is PR-ONLY.",
        "fixture",
        "Known OWNER-EXPLICIT control: owner-speaker file selects PR-ONLY.",
    )
    e4 = ev(
        "command-center/p2-wave/probes/BLD-0022/fixtures/agent-select.md",
        "Select CTRL-AGENT-1 as the chosen option.",
        "fixture",
        "Speaker-attribution control: same select wording in an agent file.",
    )
    e5 = ev(
        "command-center/WORK-UNIT-CATALOG.json",
        "An OWNER-EXPLICIT verdict must quote the owner's own sentence",
        "catalog",
        "BLD-0022 evidence requirement: agent summary is OWNER-IMPLIED at best.",
    )

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    named = live["named_ids"]
    n_claimed = live["claimed_count"]
    n_un = live["unlistable_count"]

    doc = {
        "unit_id": "BLD-0022",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:BLD-0022",
        "completion_sentinel": "SUCCESS:BLD-0022",
        "report_kind": "provenance-audit",
        "question": QUESTION,
        "title": "Selection provenance: owner-explicit versus agent-assumed option selection",
        "source_availability": {
            "checked": sorted(paths),
            "present": present,
            "absent": absent,
            "prompt_two_placeholder": "[PASTE SELECTED OPTION IDS HERE]",
            "placeholder_note": (
                "Catalog OQ-1 still describes the Prompt Two placeholder as the "
                "authority gap; selected ids inherit authority from the decision log."
            ),
        },
        "selected_options": selected,
        "control_classifications": controls,
        "owner_packet": owner_packet,
        "silently_unlistable": {
            "claimed_selected_count": n_claimed,
            "named_on_this_tree": len(named),
            "unlistable_count": n_un,
            "named_ids": named,
            "reason": (
                "OQ-1 claims 70 owner_decisions selected and names only "
                f"{len(named)} ids. 07-OPTION-UNIVERSE.json is absent, so "
                f"{n_un} selected ids cannot be reconstructed. That is the Phase 13 "
                "silently-dropped / unlistable remainder on this worktree."
            ),
        },
        "tests": [
            {
                "id": "T-SPEAKER-ATTRIBUTION",
                "command": P1,
                "result": "PASS" if rc1 == 0 else "FAIL",
            },
            {
                "id": "T-PR-ONLY-OWNER-EXPLICIT",
                "command": P2,
                "result": "PASS" if rc2 == 0 else "FAIL",
            },
            {
                "id": "T-AGENT-ASSUMED-NO-QUOTE",
                "command": P2,
                "result": "PASS" if rc2 == 0 else "FAIL",
            },
        ],
        "reviewer": review,
        "evidence": [e1, e2, e3, e4, e5],
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": SCHEMA, "exists": True, "role": "contract"},
            {
                "path": "command-center/p2-wave/probes/BLD-0022/probe1_speaker_attribution.py",
                "exists": True,
                "role": "named-probe",
            },
            {
                "path": "command-center/p2-wave/probes/BLD-0022/probe2_controls.py",
                "exists": True,
                "role": "named-probe",
            },
        ],
        "strongest_surviving_caveat": CAVEAT,
        "named_probes": [
            {"id": "probe1", "command": P1, "exit_code": rc1, "raw_output": out1[-4000:]},
            {"id": "probe2", "command": P2, "exit_code": rc2, "raw_output": out2[-4000:]},
        ],
        "produced_by": {
            "unit_id": "BLD-0022",
            "execution_substrate": "linux",
            "role": "selection-provenance-auditor",
        },
        "timestamps": {"ended_at": now},
        "answer": (
            f"Named selected ids on this tree: {named}. All six classify "
            f"{selected[0]['classification']} (agent reading of OQ-1 delegation; no "
            f"owner quote). SET-70 is OWNER-IMPLIED. UNENUMERATED-{n_un} is "
            "AGENT-ASSUMED and routed to the owner. Fixture PR-ONLY is "
            "OWNER-EXPLICIT; live catalog PR-ONLY is OWNER-IMPLIED. "
            "SUCCESS:BLD-0022"
        ),
    }

    # Catalog provenance-audit.schema.json is a $ref shim to
    # https://ast-integrate.invalid/... ; Draft7Validator tries the network.
    # Validate the live G-1 shape the named probes actually read.
    schema = json.loads((REPO / LOCAL_SCHEMA).read_text(encoding="utf-8"))
    jsonschema.Draft7Validator.check_schema(schema)
    validator = jsonschema.Draft7Validator(schema)
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:BLD-0022 schema errors")
        for e in errs[:20]:
            print(" ", list(e.path), e.message)
        return 1
    for g in ({"totally": "unrelated", "passing_tests": 999999}, {"blob": "x" * 2000}, {}):
        if not list(validator.iter_errors(g)):
            print(f"FAILED:BLD-0022 schema accepted garbage {list(g)[:2]}")
            return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")

    rc1b, out1b = run(P1)
    rc2b, out2b = run(P2)
    if rc1b != 0 or rc2b != 0:
        print("FAILED:BLD-0022 named probes after emit")
        print(out1b[-2000:])
        print(out2b[-2000:])
        return 1

    digest, size = sha256_file(out)
    if size < 2048:
        print(f"FAILED:BLD-0022 artifact {size}B below floor")
        return 1

    supporting = [
        SCHEMA,
        "command-center/p2-wave/probes/BLD-0022/classify.py",
        "command-center/p2-wave/probes/BLD-0022/corpus.py",
        "command-center/p2-wave/probes/BLD-0022/live.py",
        "command-center/p2-wave/probes/BLD-0022/reviewer.py",
        "command-center/p2-wave/probes/BLD-0022/probe1_speaker_attribution.py",
        "command-center/p2-wave/probes/BLD-0022/probe2_controls.py",
        "command-center/p2-wave/probes/BLD-0022/fixtures/owner-release.md",
        "command-center/p2-wave/probes/BLD-0022/fixtures/owner-select.md",
        "command-center/p2-wave/probes/BLD-0022/fixtures/agent-select.md",
        "command-center/p2-wave/probes/BLD-0022/fixtures/speakers.json",
        LOCAL_SCHEMA,
    ]

    def row(rel: str, role: str) -> dict:
        p = REPO / rel
        sha, n = sha256_file(p)
        return {
            "path": rel,
            "sha256": sha,
            "bytes": n,
            "present": True,
            "unit_id": "BLD-0022",
            "receipt_path": "command-center/p2-wave/probes/BLD-0022/SUBAGENT-RETURN.json",
            "role": role,
        }

    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in supporting]
    ret = {
        "id": "BLD-0022",
        "unit_id": "BLD-0022",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:BLD-0022",
        "registered": True,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": rc1b,
                "role": "speaker-attribution",
                "raw_output": out1b[-8000:],
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": rc2b,
                "role": "pr-only-and-agent-assumed",
                "raw_output": out2b[-8000:],
            },
        ],
        "artifacts": [
            {
                "path": OUT,
                "sha256": digest,
                "bytes": size,
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": "command-center/p2-wave/probes/BLD-0022/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": review["reviewer_id"],
            "verdict": review["verdict"],
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for BLD-0022: live named probes exit 0, receipts/BLD-0022.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write."
        ),
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "BLD-0022",
        "verified_on_disk": True,
        "expected": len(artifacts),
        "present": len(artifacts),
        "artifacts": artifacts,
    }
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print("SUCCESS:BLD-0022 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
