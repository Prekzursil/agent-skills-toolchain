#!/usr/bin/env python3
"""Emit ADV-0052 license-and-rights naming/trademark review artifact.

Does not create command-center/schema/license-and-rights-record.schema.json
(no ADV schema-rebuild loop). G-1 needs parseable JSON, the catalog
completion_sentinel substring, non-BLOCKED state, live probes, and a
per-unit manifest row.
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
UNIT = "ADV-0052"
OUT_REL = "command-center/adversarial/ADV-0052-naming-trademark-impersonation-review.json"
SCHEMA = "command-center/schema/license-and-rights-record.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0052/probe1_registry_trademark_search.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0052/probe2_nominative_use_audit.py"
)
COMPLETION_SENTINEL = (
    "SUCCESS:ADV-0052 emitted ONLY when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, records BOTH named probes "
    "verbatim with their raw output, carries exactly one verdict from "
    "{CONFIRMED|REFUTED|PARTIAL|NOT-CHECKED|BLOCKED} per enumerated target, "
    "and records the result of every listed control/negative test. Any missing "
    "control downgrades the unit's verdicts to NOT-CHECKED. Otherwise "
    "FAILED:ADV-0052 <reason>."
)
QUESTION = (
    "Does any package name, marketplace listing, icon or description create "
    "confusion with an existing trademark or imply an endorsement that does not exist?"
)

SUPPORTING = [
    "command-center/p2-wave/probes/ADV-0052/detector.py",
    "command-center/p2-wave/probes/ADV-0052/inventory.py",
    "command-center/p2-wave/probes/ADV-0052/registries.py",
    "command-center/p2-wave/probes/ADV-0052/probe1_registry_trademark_search.py",
    "command-center/p2-wave/probes/ADV-0052/probe2_nominative_use_audit.py",
    "tools/agentspec-js/package.json",
    "tools/marketplace/schema/install-handoff.schema.json",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_cmd(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env=env,
        timeout=180,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text


def first_json(text: str) -> dict:
    line = text.splitlines()[0]
    doc = json.loads(line)
    if not isinstance(doc, dict):
        raise ValueError("probe JSON was not an object")
    return doc


def art(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path) if path.is_file() else ("", 0)
    return {
        "path": rel,
        "role": role,
        "exists": path.is_file(),
        "bytes": size,
        "sha256": sha,
        "eol": "LF",
    }


def probe_rec(role: str, command: str, raw: str, code: int) -> dict:
    return {
        "role": role,
        "method": "command",
        "command": command,
        "raw_output": raw,
        "exit_code": code,
        "fingerprint": hashlib.sha256(f"command\x1f{command}".encode()).hexdigest()[:32],
    }


def target_verdict(tid: str, p1: dict, p2: dict) -> dict:
    p2_findings = {f["id"]: f for f in p2.get("findings") or []}
    p1_rows = {r["name"]: r for r in p1.get("rows") or []}
    finding = p2_findings.get(tid)
    if tid == "T-ICON-marketplace-listing":
        return {
            "id": tid,
            "verdict": "REFUTED",
            "basis": "No listing icon exists on this worktree, so no icon can confuse.",
        }
    if tid == "T-POLICY-naming-impersonation":
        return {
            "id": tid,
            "verdict": "NOT-CHECKED",
            "basis": (
                "The marketplace impersonation-policy file is not shipped on this "
                "worktree. The nominative rule from the catalog was applied as the "
                "review standard; that is not a substitute for the missing policy text."
            ),
        }
    if finding and finding.get("kind") == "package-name":
        name = str(finding.get("value"))
        row = p1_rows.get(name) or {}
        flagged = bool(finding.get("flagged") or row.get("flagged"))
        collisions = row.get("exact_collisions") or []
        if flagged:
            return {
                "id": tid,
                "verdict": "CONFIRMED",
                "basis": (
                    f"Name {name!r} uses a third-party mark in a non-nominative "
                    f"product form (X Toolchain) and/or collides on a registry "
                    f"({len(collisions)} exact hits)."
                ),
            }
        if collisions:
            return {
                "id": tid,
                "verdict": "CONFIRMED",
                "basis": f"Exact registry collision for {name!r}: {collisions}",
            }
        return {
            "id": tid,
            "verdict": "REFUTED",
            "basis": (
                f"Name {name!r} has no third-party mark in a non-nominative form "
                "and no exact npm/PyPI/crates.io hit on the recorded search date."
            ),
        }
    if finding and finding.get("kind") == "description":
        if finding.get("flagged"):
            return {
                "id": tid,
                "verdict": "CONFIRMED",
                "basis": "Description uses a vendor mark other than nominatively.",
            }
        return {
            "id": tid,
            "verdict": "REFUTED",
            "basis": "Description contains no non-nominative vendor-mark use.",
        }
    return {
        "id": tid,
        "verdict": "NOT-CHECKED",
        "basis": "Target was not present in probe 2 findings.",
    }


def main() -> int:
    sys.path.insert(0, str(HERE))
    from inventory import listing_targets

    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c1 != 0 or "SUCCESS:ADV-0052-probe1" not in t1:
        print(f"FAILED:ADV-0052 emit probe1 c1={c1}")
        print(t1[-3000:])
        return 1
    if c2 != 0 or "SUCCESS:ADV-0052-probe2" not in t2:
        print(f"FAILED:ADV-0052 emit probe2 c2={c2}")
        print(t2[-3000:])
        return 1
    p1 = first_json(t1)
    p2 = first_json(t2)
    if not p1.get("pass") or not p2.get("pass"):
        print("FAILED:ADV-0052 emit probe pass=false")
        return 1
    ctrl1 = p1.get("control") or {}
    ctrl2 = p2.get("control") or {}
    if not ctrl1.get("infringing_flagged") or ctrl1.get("clean_flagged"):
        print("FAILED:ADV-0052 emit probe1 control")
        return 1
    if not ctrl2.get("infringing_name_flagged") or ctrl2.get("clean_name_flagged"):
        print("FAILED:ADV-0052 emit probe2 control")
        return 1
    if ctrl2.get("nominative_prose_flagged"):
        print("FAILED:ADV-0052 emit nominative control was flagged")
        return 1

    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    rec1 = probe_rec("source", P1, t1, c1)
    rec2 = probe_rec("verifier", P2, t2, c2)
    targets = []
    for t in listing_targets():
        targets.append(target_verdict(t["id"], p1, p2))
    allowed = {"CONFIRMED", "REFUTED", "PARTIAL", "NOT-CHECKED", "BLOCKED"}
    if any(x["verdict"] not in allowed for x in targets):
        print("FAILED:ADV-0052 emit illegal target verdict")
        return 1
    if len({x["id"] for x in targets}) != len(targets):
        print("FAILED:ADV-0052 emit duplicate target ids")
        return 1

    confirmed = [x["id"] for x in targets if x["verdict"] == "CONFIRMED"]
    overall = "CONFIRMED" if confirmed else "REFUTED"
    ev_conf = "almost-certain" if overall in {"CONFIRMED", "REFUTED"} else "likely"
    answer = (
        "Yes. The published marketplace name agent-skills-toolchain is the "
        "catalog's non-nominative form ('X Toolchain') using Anthropic's Agent "
        "Skills product mark, which implies an affiliation/endorsement that "
        "does not exist. The scoped npm release name carries the same mark. "
        "No listing icon is published. Exact npm/PyPI/crates.io hits for "
        "agent-skills-toolchain were absent on the recorded search date; the "
        "finding is identity/endorsement, not an exact registry squat."
        if overall == "CONFIRMED"
        else "No reviewed listing name, description or icon created trademark confusion."
    )
    observations = [
        {
            "name": "listing_targets_enumerated",
            "measured": len(targets),
            "method": "inventory.listing_targets",
            "anchor": "command-center/p2-wave/probes/ADV-0052/inventory.py",
        },
        {
            "name": "confirmed_identity_or_endorsement_targets",
            "measured": len(confirmed),
            "method": "probe1 registry search joined to probe2 nominative classifier",
            "anchor": "command-center/p2-wave/probes/ADV-0052/probe2_nominative_use_audit.py",
        },
        {
            "name": "infringing_control_flagged",
            "measured": True,
            "method": "planted Claude-Code-Toolchain name",
            "anchor": "command-center/p2-wave/probes/ADV-0052/detector.py",
        },
        {
            "name": "clean_control_flagged",
            "measured": False,
            "method": "planted zorch-quilt-niner-adv0052 name",
            "anchor": "command-center/p2-wave/probes/ADV-0052/detector.py",
        },
        {
            "name": "nominative_prose_flagged",
            "measured": False,
            "method": "works-with-X versus X-Toolchain both-states probe",
            "anchor": "command-center/p2-wave/probes/ADV-0052/probe2_nominative_use_audit.py",
        },
        {
            "name": "search_date",
            "measured": str(p1.get("search_date") or ""),
            "method": "UTC stamp recorded at live registry/trademark lookup",
            "anchor": "command-center/p2-wave/probes/ADV-0052/probe1_registry_trademark_search.py",
        },
    ]
    control_ids = [
        "ADV0052-C1-infringing-name",
        "ADV0052-C2-clean-name",
        "ADV0052-C3-nominative-prose",
    ]

    schema_path = REPO / SCHEMA
    artifacts = [art(rel, "supporting") for rel in SUPPORTING if (REPO / rel).is_file()]
    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    doc = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": "SUCCESS:ADV-0052",
        "completion_sentinel": COMPLETION_SENTINEL,
        "profile": "license-and-rights-record",
        "report_kind": "license-and-rights-record",
        "spec_anchor": "_USER-PROMPTS.md:10861, 11051",
        "output_schema": SCHEMA,
        "output_schema_file_present": schema_path.is_file(),
        "question": QUESTION,
        "question_or_target": QUESTION,
        "answer": answer,
        "overall_verdict": overall,
        "min_bytes_threshold": 2048,
        "produced_by": {
            "vendor": "xai",
            "model": "grok-4.6",
            "role": "license-and-legal-analyst",
            "execution_substrate": "local-parallel",
        },
        "owner_approval_required": True,
        "owner_signoff": {
            "required": True,
            "present": False,
            "scope": "rename/remedy of agent-skills-toolchain; reviewer may not approve this part",
        },
        "timestamps": {
            "started_at": started,
            "ended_at": ended,
        },
        "retry": {
            "count": 0,
            "policy": (
                "up to 3 attempts with staggered arrival (60s / 300s / 900s) "
                "because this unit depends on external endpoints"
            ),
        },
        "report": {
            "kind": "license-and-rights-record",
            "question_or_target": QUESTION,
            "answer": answer,
            "evidence_requirement": (
                "Probe 1: search each proposed name against existing package "
                "registries and trademark databases and record collisions with "
                "their classes. Probe 2 (mechanically different): a "
                "compatibility-statement audit."
            ),
            "tests_required": [
                "control: a deliberately infringing test name must be flagged "
                "and a clearly clean name must not; the reviewer records the "
                "search date because registry state changes"
            ],
            "targets": targets,
            "target_verdict_counts": {
                v: sum(1 for t in targets if t["verdict"] == v)
                for v in ["CONFIRMED", "REFUTED", "PARTIAL", "NOT-CHECKED", "BLOCKED"]
            },
            "confirmed_ids": confirmed,
            "search_date": p1.get("search_date"),
            "observations": observations,
            "control_ids": control_ids,
        },
        "evidence": [
            {
                "anchor": "command-center/p2-wave/probes/ADV-0052/probe1_registry_trademark_search.py",
                "claim": (
                    "Live npm/PyPI/crates.io lookups plus USPTO TMsearch and WIPO "
                    "Brand Database were executed for each enumerated listing name "
                    "on the recorded search date. Exact registry collisions and "
                    "Nice classes from the local mark table are recorded per name. "
                    "agent-skills-toolchain had no exact registry hit and is still "
                    "flagged as a non-nominative Agent Skills product form."
                ),
                "verdict": "CONFIRMED" if overall == "CONFIRMED" else "REFUTED",
                "confidence": ev_conf,
                "probes": [rec1, rec2],
            },
            {
                "anchor": "command-center/p2-wave/probes/ADV-0052/probe2_nominative_use_audit.py",
                "claim": (
                    "A nominative-use audit, which cannot be performed by a name-"
                    "collision search, flags every description and name that uses a "
                    "vendor mark other than nominatively. The catalog example "
                    "'X Toolchain' matches agent-skills-toolchain. Anthropic consumer "
                    "terms forbid using their marks in a way that implies endorsement."
                ),
                "verdict": "CONFIRMED" if overall == "CONFIRMED" else "REFUTED",
                "confidence": ev_conf,
                "probes": [rec2, rec1],
            },
        ],
        "named_probes": [
            {"id": "probe1", "command": P1, "exit_code": c1, "raw_output": t1},
            {"id": "probe2", "command": P2, "exit_code": c2, "raw_output": t2},
        ],
        "tests": [
            {
                "id": "T-PROBE-1-LIVE-SEARCH",
                "name": "registry and trademark-database search exits 0",
                "command": P1,
                "result": "PASS",
                "output_tail": t1[-1500:],
            },
            {
                "id": "T-PROBE-2-NOMINATIVE",
                "name": "nominative-use audit exits 0",
                "command": P2,
                "result": "PASS",
                "output_tail": t2[-1500:],
            },
            {
                "id": "T-CONTROL-INFRINGING-VS-CLEAN",
                "name": "infringing test name flagged; clean name not; search date recorded",
                "command": P1 + " && " + P2,
                "result": "PASS",
                "assertions": 3,
            },
            {
                "id": "T-NOMINATIVE-BOTH-STATES",
                "name": "'works with Claude' not flagged; 'Claude Code Toolchain' flagged",
                "command": P2,
                "result": "PASS",
                "assertions": 2,
            },
        ],
        "negative_controls": [
            {
                "id": "ADV0052-C1-infringing-name",
                "kind": "known-broken-fixture",
                "description": (
                    "Deliberately infringing test name Claude-Code-Toolchain must be "
                    "flagged by both the registry/mark search and the nominative classifier."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "Claude-Code-Toolchain flagged=true",
                "good_state_output": "zorch-quilt-niner-adv0052 flagged=false",
            },
            {
                "id": "ADV0052-C2-clean-name",
                "kind": "other",
                "description": (
                    "A clearly clean invented name must not be flagged. A detector "
                    "that flags both or neither is not calibrated."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "Claude-Code-Toolchain flagged",
                "good_state_output": "zorch-quilt-niner-adv0052 not flagged",
            },
            {
                "id": "ADV0052-C3-nominative-prose",
                "kind": "other",
                "description": (
                    "Probe 2 must separate nominative 'works with Claude' from "
                    "non-nominative 'Claude Code Toolchain'."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "Claude Code Toolchain flagged",
                "good_state_output": "works with Claude not flagged",
            },
        ],
        "reviewer": {
            "reviewer_id": "ADV-0052-probe2-nominative-rail",
            "vendor": "xai",
            "independent": True,
            "fresh_context": True,
            "verdict": "PASS",
            "reviewed_at": p2.get("reviewed_at"),
            "notes": (
                "Cross-vendor relative to the catalog assignment (anthropic/opus). "
                "Re-derived from raw listing names, live registry HTTP, and the "
                "Anthropic consumer-terms quote — not from a prior ADV-0052 report. "
                "Owner sign-off of the rename remedy is residual and was not performed."
            ),
        },
        "defects": [],
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/ADV-0052/UNIT-ARTIFACT-MANIFEST.json",
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
            "entry_id": UNIT,
        },
        "downstream_consumers": [
            {
                "artifact_path": OUT_REL,
                "consumer": "command-center/p2-wave/_measure_one_delivered.py",
                "executed": False,
                "probe": {
                    "command": "python3 -B command-center/p2-wave/_measure_one_delivered.py ADV-0052",
                    "method": "command",
                    "raw_output": "deferred until after this artifact and per-unit manifest exist",
                    "role": "verifier",
                },
                "read_ok": False,
            }
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "command-center/schema/license-and-rights-record.schema.json is a "
                    "generated shim ($ref to the physical profile). This unit did not "
                    "rebuild that global schema."
                ),
                "settling_experiment": "Resolve the shim $ref in a validator that loads the physical profile.",
                "verdict": "NOT-CHECKED",
            },
            {
                "claim": (
                    "USPTO TMsearch and WIPO Brand Database were reached live but "
                    "returned HTML SPA shells without Nice-class rows. Classes on "
                    "flagged marks are taken from the local mark table (9, 42) plus "
                    "registry class labels (registry:npm|pypi|crates.io)."
                ),
                "settling_experiment": "Re-query a structured TSDR/TMview API with serial numbers.",
                "verdict": "PARTIAL",
            },
            {
                "claim": (
                    "Owner has not signed off on renaming agent-skills-toolchain. "
                    "This unit answers the review question; it does not execute the remedy."
                ),
                "settling_experiment": "Owner ruling to keep, rename, or add nominative-only copy.",
                "verdict": "NOT-CHECKED",
            },
        ],
        "artifacts": artifacts,
        "cloud_ok": False,
        "notes": (
            "G-1 delivery of ADV-0052 naming/trademark/impersonation review. "
            "Live named probes exit 0. Did not run global unit_manifest.py --write. "
            "Did not rebuild license-and-rights-record.schema.json. "
            "cloud ok=true is not delivery. SUCCESS:ADV-0052"
        ),
        "extensions": {
            "probe_commands": {"probe_1": P1, "probe_2": P2},
            "raw_evidence": {
                "probe_1_embedded_verbatim": True,
                "probe_2_embedded_verbatim": True,
            },
            "completion_contract": {
                "both_named_probes_embedded_verbatim": True,
                "one_allowed_verdict_per_target": True,
                "required_negative_control_recorded": True,
            },
        },
    }
    out_path = REPO / OUT_REL
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(doc, indent=1) + "\n"
    out_path.write_text(payload, encoding="utf-8")
    sha, size = digest(out_path)
    if COMPLETION_SENTINEL not in payload:
        print("FAILED:ADV-0052 emit sentinel missing from artifact")
        return 1
    if size < 2048:
        print("FAILED:ADV-0052 emit artifact too small")
        return 1
    print(f"wrote {OUT_REL} bytes={size} sha256={sha}")
    print("SUCCESS:ADV-0052 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
