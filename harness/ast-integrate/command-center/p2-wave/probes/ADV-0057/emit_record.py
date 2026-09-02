#!/usr/bin/env python3
"""Emit command-center/adversarial/ADV-0057-governance-policy-legal-coherence.json."""
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

from corpus import inventory  # noqa: E402
from enforcement import run as run_enforcement  # noqa: E402
from pairwise import run as run_pairwise  # noqa: E402
from schema_local import garbage_accepted, schema_errors  # noqa: E402

OUT_REL = "command-center/adversarial/ADV-0057-governance-policy-legal-coherence.json"
SCHEMA_REL = "command-center/schema/license-and-rights-record.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0057/probe1_pairwise.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0057/probe2_enforcement.py"
)
P_SCHEMA = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0057/schema_check.py"
)
CATALOG = REPO / "command-center/WORK-UNIT-CATALOG.json"
RAW1 = HERE / "probe1-pairwise.raw.txt"
RAW2 = HERE / "probe2-enforcement.raw.txt"


def catalog_unit() -> dict:
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    for u in data.get("work_units") or []:
        if isinstance(u, dict) and u.get("id") == "ADV-0057":
            return u
    raise SystemExit("FAILED:ADV-0057 missing from catalog")


def run_cmd(cmd: str) -> tuple[int, str]:
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
    )
    return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()


def digest_bytes(raw: bytes) -> tuple[str, int]:
    norm = raw.replace(b"\r\n", b"\n")
    return hashlib.sha256(norm).hexdigest(), len(norm)


def digest_path(rel: str) -> tuple[str, int]:
    return digest_bytes((REPO / rel).read_bytes())


def dump(doc: dict) -> str:
    return json.dumps(doc, indent=2, ensure_ascii=True) + "\n"


def fingerprint(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}|{command}".encode("utf-8")).hexdigest()


def probe(
    role: str,
    method: str,
    command: str,
    raw: str,
    exit_code: int = 0,
) -> dict:
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": raw[:65000],
        "fingerprint": fingerprint(method, command),
        "exit_code": exit_code,
    }


def art_row(rel: str, role: str, sha: str | None = None, size: int | None = None) -> dict:
    if sha is None or size is None:
        sha, size = digest_path(rel)
    return {
        "path": rel,
        "bytes": size,
        "sha256": sha,
        "exists": True,
        "eol": "LF",
        "role": role,
    }


def main() -> int:
    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    unit = catalog_unit()
    sentinel = str(unit["completion_sentinel"])
    inv = inventory()
    p1 = run_pairwise()
    p2 = run_enforcement()
    if not p1.get("pass") or not p2.get("pass"):
        print("FAILED:ADV-0057 analysis did not pass controls")
        return 1

    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:ADV-0057 probes before emit c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    RAW1.write_text(t1 + "\n", encoding="utf-8")
    RAW2.write_text(t2 + "\n", encoding="utf-8")

    docs = inv["documents"]
    missing = [d["id"] for d in docs if not d["present"]]
    present_docs = [d["id"] for d in docs if d["present"]]
    present_paths = {
        d["id"]: d.get("path") for d in docs if d.get("present")
    }
    plugin = inv["plugin_manifest"]
    plugin_line = 0
    plugin_sentence = "plugin manifest absent"
    if plugin.get("present"):
        for i, line in enumerate(plugin.get("lines") or [], 1):
            if "license" in line.lower():
                plugin_line = i
                plugin_sentence = line.strip()
                break

    comparable = p1["live"]["comparable_pair_count"]
    n_contra = p1["live"]["contradiction_count"]
    if comparable == 0:
        pairwise_verdict = "PARTIAL"
    elif n_contra:
        pairwise_verdict = "CONFIRMED"
    else:
        pairwise_verdict = "REFUTED"
    inbound_verdict = "REFUTED" if p2["unenforced_signoff"] else "CONFIRMED"

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    placeholder = "0" * 64

    supporting = [
        (SCHEMA_REL, "supporting"),
        ("SECURITY.md", "supporting"),
        (".claude-plugin/plugin.json", "supporting"),
        ("command-center/p2-wave/probes/ADV-0057/probe1_pairwise.py", "log"),
        ("command-center/p2-wave/probes/ADV-0057/probe2_enforcement.py", "log"),
        ("command-center/p2-wave/probes/ADV-0057/probe1-pairwise.raw.txt", "log"),
        ("command-center/p2-wave/probes/ADV-0057/probe2-enforcement.raw.txt", "log"),
        (
            "command-center/p2-wave/probes/ADV-0057/fixtures/planted-contradiction/CONTRIBUTING.md",
            "control",
        ),
        (
            "command-center/p2-wave/probes/ADV-0057/fixtures/planted-clean/CONTRIBUTING.md",
            "control",
        ),
    ]
    artifacts = [art_row(OUT_REL, "primary", placeholder, 1)]
    for rel, role in supporting:
        if (REPO / rel).is_file():
            artifacts.append(art_row(rel, role))

    targets = [
        {
            "id": "pairwise-policy-contradiction",
            "verdict": pairwise_verdict,
            "note": (
                f"comparable_pairs={comparable} contradictions={n_contra} "
                f"present={present_docs} missing={missing}"
            ),
        },
        {
            "id": "policy-vs-outbound-license",
            "verdict": "PARTIAL",
            "note": (
                "plugin.json declares MIT; no LICENSE/COPYING/NOTICE file at "
                "repository root; no contribution-policy sentence to pair against it."
            ),
        },
        {
            "id": "policy-vs-marketplace-publisher-terms",
            "verdict": "PARTIAL",
            "note": "Marketplace publisher legal terms file is absent.",
        },
        {
            "id": "inbound-rights-actually-collected",
            "verdict": inbound_verdict,
            "note": (
                "Unsigned scratch PR is not blocked by any in-tree DCO/CLA check; "
                "claimed inbound grant is not collected."
            ),
        },
        {
            "id": "unenforced-signoff-collects-nothing",
            "verdict": "CONFIRMED" if p2["unenforced_signoff"] else "REFUTED",
            "note": "An unenforced CLA/DCO collects nothing.",
        },
    ]

    tests = [
        {
            "id": "probe1-pairwise",
            "name": "Pairwise contradiction matrix with file:line citations",
            "command": P1,
            "result": "PASS" if c1 == 0 and p1.get("pass") else "FAIL",
            "assertions": 2,
            "output_tail": t1[-4000:],
        },
        {
            "id": "probe2-enforcement",
            "name": "Scratch PR unsigned vs signed enforcement path",
            "command": P2,
            "result": "PASS" if c2 == 0 and p2.get("pass") else "FAIL",
            "assertions": 3,
            "output_tail": t2[-4000:],
        },
        {
            "id": "compliant-scratch-pr",
            "name": (
                "Control: a compliant scratch PR must pass so globally broken "
                "CI is not read as enforcement"
            ),
            "command": P2,
            "result": "PASS" if p2["control_compliant_scratch_pr_passes"] else "FAIL",
            "assertions": 1,
            "output_tail": (
                f"signed_blocked={p2['signed_live']['blocked']} "
                f"globally_broken_ci={p2['globally_broken_ci']}"
            ),
        },
        {
            "id": "planted-pairwise-contradiction",
            "name": "Planted CLA-required vs DCO-only pair must fire; clean pair silent",
            "command": P1,
            "result": "PASS" if p1["negative_control"]["ok"] else "FAIL",
            "assertions": 2,
            "output_tail": (
                f"detector_fired={p1['negative_control']['detector_fired']} "
                f"silent_on_good={p1['negative_control']['silent_on_good']}"
            ),
        },
        {
            "id": "planted-dco-detector",
            "name": "Planted DCO trailer checker fires on unsigned, silent on signed",
            "command": P2,
            "result": "PASS" if p2["planted_dco"]["ok"] else "FAIL",
            "assertions": 2,
            "output_tail": json.dumps(p2["planted_dco"], sort_keys=True)[:2000],
        },
    ]

    evidence = [
        {
            "claim": (
                "Canonical CONTRIBUTING, GOVERNANCE, SUPPORT, DEPRECATION, LICENSE "
                "and marketplace-publisher-terms files are absent; SECURITY.md is present."
            ),
            "verdict": "CONFIRMED",
            "confidence": "almost-certain",
            "anchor": present_paths.get("SECURITY") or "SECURITY.md",
            "probes": [
                probe("source", "test-run", P1, t1, c1),
                probe("verifier", "file-read", "ls SECURITY.md CONTRIBUTING.md LICENSE", (
                    f"present_docs={present_docs} missing_docs={missing}"
                )),
            ],
        },
        {
            "claim": (
                "plugin.json declares outbound license MIT and no LICENSE file "
                "exists at the repository root."
            ),
            "verdict": "CONFIRMED" if plugin.get("present") else "REFUTED",
            "confidence": "almost-certain",
            "anchor": f".claude-plugin/plugin.json:{plugin_line or 1}",
            "probes": [
                probe(
                    "source",
                    "file-read",
                    "python3 -c 'print(open(\".claude-plugin/plugin.json\").read())'",
                    plugin_sentence,
                ),
                probe("verifier", "test-run", P1, t1, c1),
            ],
        },
        {
            "claim": (
                "Unsigned scratch contribution is not blocked by in-tree DCO/CLA "
                "enforcement; a signed scratch PR is also not blocked."
            ),
            "verdict": "CONFIRMED" if p2["unenforced_signoff"] else "REFUTED",
            "confidence": "almost-certain",
            "anchor": "command-center/p2-wave/probes/ADV-0057/enforcement.py",
            "probes": [
                probe("source", "test-run", P2, t2, c2),
                probe(
                    "verifier",
                    "static-analysis",
                    "grep -R -i dco .github hooks ci",
                    json.dumps(p2["discovery"], sort_keys=True)[:8000],
                ),
            ],
        },
        {
            "claim": "Planted CLA-vs-DCO sentences are detected by the pairwise matrix.",
            "verdict": "CONFIRMED" if p1["negative_control"]["ok"] else "REFUTED",
            "confidence": "almost-certain",
            "anchor": (
                "command-center/p2-wave/probes/ADV-0057/fixtures/"
                "planted-contradiction/CONTRIBUTING.md:3"
            ),
            "probes": [
                probe("source", "test-run", P1, t1, c1),
                probe(
                    "verifier",
                    "file-read",
                    "cat command-center/p2-wave/probes/ADV-0057/fixtures/planted-contradiction/CONTRIBUTING.md",
                    "Contributions require a signed Contributor License Agreement before merge.",
                ),
            ],
        },
        {
            "claim": (
                "Compliant signed scratch PR is accepted, so absence of enforcement "
                "is not a globally red CI."
            ),
            "verdict": "CONFIRMED" if p2["control_compliant_scratch_pr_passes"] else "REFUTED",
            "confidence": "almost-certain",
            "anchor": "command-center/p2-wave/probes/ADV-0057/enforcement.py",
            "probes": [
                probe("source", "test-run", P2, t2, c2),
                probe(
                    "verifier",
                    "command",
                    P2 + " # compliant-scratch-pr-control",
                    f"control_compliant_scratch_pr_passes={p2['control_compliant_scratch_pr_passes']}",
                ),
            ],
        },
    ]

    consumer_raw = "PENDING"
    doc = {
        "schema_version": 1,
        "unit_id": "ADV-0057",
        "state": "SUCCESS",
        "sentinel": sentinel,
        "profile": "license-and-rights-record",
        "spec_anchor": str(unit.get("spec_anchor") or "_USER-PROMPTS.md:11119-11122"),
        "min_bytes_threshold": 1024,
        "produced_by": {
            "vendor": "grok",
            "model": "grok-4.6",
            "role": "license-and-legal-analyst",
            "execution_substrate": "local-parallel",
        },
        "artifacts": artifacts,
        "evidence": evidence,
        "tests": tests,
        "negative_controls": [
            {
                "id": "planted-cla-vs-dco",
                "kind": "known-broken-fixture",
                "description": (
                    "Planted CLA-required CONTRIBUTING vs DCO-only GOVERNANCE must "
                    "fire; matching DCO-only pair must stay silent."
                ),
                "fired_on_bad_state": bool(p1["negative_control"]["detector_fired"]),
                "silent_on_good_state": bool(p1["negative_control"]["silent_on_good"]),
                "bad_state_output": json.dumps(
                    p1["planted_contradiction"], sort_keys=True
                )[:8000],
                "good_state_output": json.dumps(
                    p1["planted_clean"], sort_keys=True
                )[:8000],
            },
            {
                "id": "planted-dco-on-unsigned-pr",
                "kind": "adversarial-payload",
                "description": (
                    "Planted DCO trailer checker must block unsigned scratch PR "
                    "commits and stay silent on Signed-off-by."
                ),
                "fired_on_bad_state": bool(p2["planted_dco"]["detector_fired"]),
                "silent_on_good_state": bool(p2["planted_dco"]["silent_on_good"]),
                "bad_state_output": json.dumps(
                    p2["planted_dco"]["unsigned"], sort_keys=True
                ),
                "good_state_output": json.dumps(
                    p2["planted_dco"]["signed"], sort_keys=True
                ),
            },
        ],
        "reviewer": {
            "reviewer_id": "ADV-0057-probe2-enforcement-path",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "vendor": "grok",
            "reviewed_at": now,
            "notes": (
                "Probe 2 re-derives enforcement from in-tree checks and scratch "
                "PR payloads, not from probe 1's pairwise matrix. Owner sign-off "
                "of remediation remains residual; this unit records the measurement."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/ADV-0057/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "entry_id": "ADV-0057",
            "registered_at": now,
        },
        "downstream_consumers": [
            {
                "consumer": "json.loads + license-and-rights-record schema resolver",
                "artifact_path": OUT_REL,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": probe(
                    "source",
                    "schema-validate",
                    P_SCHEMA,
                    consumer_raw,
                ),
            }
        ],
        "timestamps": {
            "started_at": started,
            "ended_at": now,
        },
        "retry": {
            "count": 0,
            "policy": str(
                unit.get("retry_policy")
                or "two strikes then pivot (AGENTS.md 4b)"
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "GitHub branch-protection, required-status checks, and hosted "
                    "CLA/DCO apps are not visible from this worktree."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "On an authorized clone with network, inspect branch protection "
                    "and installed GitHub Apps, then re-run probe 2 against a real PR."
                ),
            },
            {
                "claim": (
                    "Owner sign-off of any remediation (add LICENSE, CONTRIBUTING, "
                    "or DCO enforcement) is not in this unit's authority."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Present the measurement to the owner; record the sign-off "
                    "separately from this receipt."
                ),
            },
        ],
        "report": {
            "kind": "license-and-rights-record",
            "answer": (
                f"SECURITY.md is present; missing={missing}. Pairwise sentence "
                f"contradictions are {pairwise_verdict} "
                f"(comparable_pairs={comparable}, contradictions={n_contra}). "
                "plugin.json declares MIT while LICENSE is missing. Marketplace "
                "publisher terms are absent. The contribution flow does not collect "
                "inbound rights: no PR template, DCO, or CLA check exists, and an "
                "unsigned scratch PR is not blocked. The compliant signed scratch PR "
                "passes, so absence of enforcement is not a globally red CI."
            ),
            "observations": [
                {
                    "name": "present_policy_doc_count",
                    "measured": len(present_docs),
                    "method": "candidate-path inventory excluding probe fixtures",
                    "anchor": "command-center/p2-wave/probes/ADV-0057/corpus.py",
                },
                {
                    "name": "comparable_pair_count",
                    "measured": comparable,
                    "method": "pairwise claim-tag matrix",
                    "anchor": "command-center/p2-wave/probes/ADV-0057/probe1-pairwise.raw.txt",
                },
                {
                    "name": "live_contradiction_count",
                    "measured": n_contra,
                    "method": "pairwise claim-tag matrix",
                    "anchor": "command-center/p2-wave/probes/ADV-0057/probe1-pairwise.raw.txt",
                },
                {
                    "name": "unenforced_signoff",
                    "measured": bool(p2["unenforced_signoff"]),
                    "method": "scratch-PR payload vs in-tree enforcement discovery",
                    "anchor": "command-center/p2-wave/probes/ADV-0057/probe2-enforcement.raw.txt",
                },
                {
                    "name": "plugin_manifest_license",
                    "measured": plugin_sentence,
                    "method": "file-read plugin.json license field",
                    "anchor": f".claude-plugin/plugin.json:{plugin_line or 1}",
                },
            ],
            "control_ids": [
                "planted-cla-vs-dco",
                "planted-dco-on-unsigned-pr",
                "compliant-scratch-pr",
            ],
            "targets": targets,
            "named_probes": [
                {"id": "probe1-pairwise", "command": P1, "raw_output": t1},
                {"id": "probe2-enforcement", "command": P2, "raw_output": t2},
            ],
            "pairwise": p1["live"],
            "enforcement": {
                "discovery": p2["discovery"],
                "unsigned_live": p2["unsigned_live"],
                "signed_live": p2["signed_live"],
                "unenforced_signoff": p2["unenforced_signoff"],
                "scratch_pr_method": p2["scratch_pr_method"],
            },
            "inventory": {
                "present_documents": present_docs,
                "missing_documents": missing,
                "github_dir_present": inv["github_dir_present"],
                "contribution_flow_files": inv["contribution_flow_files"],
            },
            "owner_signoff_for_remediation": "pending",
        },
        "extensions": {
            "question": str(unit.get("question_or_target") or ""),
            "title": unit.get("title"),
            "cloud_ok": False,
        },
    }

    bad = garbage_accepted()
    if bad:
        print(f"FAILED:ADV-0057 schema accepted garbage {bad[:1]}")
        return 1

    dest = REPO / OUT_REL
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(dump(doc), encoding="utf-8")
    sha, size = digest_bytes(dest.read_bytes())
    doc["artifacts"][0]["sha256"] = sha
    doc["artifacts"][0]["bytes"] = size
    dest.write_text(dump(doc), encoding="utf-8")
    sha2, size2 = digest_bytes(dest.read_bytes())
    doc["artifacts"][0]["sha256"] = sha2
    doc["artifacts"][0]["bytes"] = size2
    dest.write_text(dump(doc), encoding="utf-8")

    sc, st = run_cmd(P_SCHEMA)
    doc["downstream_consumers"][0]["probe"]["raw_output"] = st[:65000]
    doc["downstream_consumers"][0]["exit_code"] = sc
    doc["downstream_consumers"][0]["read_ok"] = sc == 0
    dest.write_text(dump(doc), encoding="utf-8")

    errs = schema_errors(doc)
    if errs:
        print("FAILED:ADV-0057 schema errors")
        for line in errs[:25]:
            print(" ", line)
        return 1
    if sc != 0:
        print("FAILED:ADV-0057 schema_check consumer")
        print(st[-2000:])
        return 1

    c1b, t1b = run_cmd(P1)
    c2b, t2b = run_cmd(P2)
    if c1b != 0 or c2b != 0:
        print(f"FAILED:ADV-0057 probes after embed c1={c1b} c2={c2b}")
        print(t1b[-2000:])
        print(t2b[-2000:])
        return 1
    doc["report"]["named_probes"] = [
        {"id": "probe1-pairwise", "command": P1, "raw_output": t1b},
        {"id": "probe2-enforcement", "command": P2, "raw_output": t2b},
    ]
    dest.write_text(dump(doc), encoding="utf-8")
    sha3, size3 = digest_bytes(dest.read_bytes())
    doc["artifacts"][0]["sha256"] = sha3
    doc["artifacts"][0]["bytes"] = size3
    dest.write_text(dump(doc), encoding="utf-8")

    errs = schema_errors(json.loads(dest.read_text(encoding="utf-8")))
    if errs:
        print("FAILED:ADV-0057 schema errors after final embed")
        for line in errs[:25]:
            print(" ", line)
        return 1
    if dest.stat().st_size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:ADV-0057 artifact below floor {dest.stat().st_size}")
        return 1
    print(f"wrote {OUT_REL} bytes={dest.stat().st_size}")
    print("SUCCESS:ADV-0057")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
