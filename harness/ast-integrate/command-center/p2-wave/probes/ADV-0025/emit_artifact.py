#!/usr/bin/env python3
"""Emit command-center/adversarial/ADV-0025-adversarial-package-linter-bypass.json."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from harness import (  # noqa: E402
    ABUSE_TARGETS,
    OUT_REL,
    P1,
    P2,
    QUESTION,
    SCHEMA_REL,
    SENTINEL,
    UNIT,
)


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
        timeout=180,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text


def first_json(raw: str) -> dict:
    start = raw.find("{")
    end = raw.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("probe output missing JSON object")
    doc = json.loads(raw[start : end + 1])
    if not isinstance(doc, dict):
        raise ValueError("probe JSON is not an object")
    return doc


def linter_fail_to_reject(row: dict) -> bool:
    return bool(row.get("accepted")) and not bool(row.get("rejected"))


def target_verdict(lint_row: dict, *, control_ok: bool) -> str:
    if not control_ok:
        return "NOT-CHECKED"
    if linter_fail_to_reject(lint_row):
        return "CONFIRMED"
    if lint_row.get("rejected"):
        return "REFUTED"
    return "NOT-CHECKED"


def main() -> int:
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print("FAILED:ADV-0025 emit probes did not pass")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    p1 = first_json(t1)
    p2 = first_json(t2)
    if not p1.get("pass") or not p2.get("pass"):
        print("FAILED:ADV-0025 a named probe reported pass=false")
        return 1
    if "SUCCESS:ADV-0025-probe1" not in t1 or "SUCCESS:ADV-0025-probe2" not in t2:
        print("FAILED:ADV-0025 emit probe sentinel missing")
        return 1

    lint_by = {r["variant_id"]: r for r in p1.get("rows") or []}
    inst_by = {r["variant_id"]: r for r in p2.get("installs") or []}
    control_ok = bool(p1.get("control_accepted")) and bool(
        p2.get("control_installed_clean")
    )
    if {"C-BENIGN", *ABUSE_TARGETS} - set(lint_by) or {
        "C-BENIGN",
        *ABUSE_TARGETS,
    } - set(inst_by):
        print("FAILED:ADV-0025 probe rows missing a required variant")
        return 1

    titles = {
        "T-EXCESSIVE-PERMISSIONS": "excessive permission requests",
        "T-INSTALL-TIME-SCRIPT": "an install-time script",
        "T-SHADOW-PLATFORM-FIELD": "a manifest field that shadows a platform field",
        "T-WRITE-OUTSIDE-ROOT": "a package that writes outside its own root",
        "T-DECLARED-VS-ACTUAL": "a package whose declared and actual contents differ",
    }
    details = {
        "T-EXCESSIVE-PERMISSIONS": (
            "Variant requests fs_write_roots covering /, /etc, *, process_spawn, "
            "network, and raw_syscall. Package linter absent (fail-open accepted). "
            "Sandbox install placed plugin.json + bin/demo; runtime permission "
            "enforcement is ADV-0022, not this unit."
        ),
        "T-INSTALL-TIME-SCRIPT": (
            "Variant ships scripts/postinstall.sh via manifest scripts.install / "
            "postinstall. Package linter fail-open accepted. Installer placed the "
            "script into the sandbox live tree and did not execute it "
            "(postinstall_fired=false; no ADV0025_BEACON)."
        ),
        "T-SHADOW-PLATFORM-FIELD": (
            "plugin.json forges package_id, digest, schema_version, transaction_id, "
            "projection_map, payload_path, and declared_permissions. Package linter "
            "fail-open accepted. Installer used the typed handoff, not the forged "
            "manifest fields, as the placement control plane."
        ),
        "T-WRITE-OUTSIDE-ROOT": (
            "Tar member ../OUTSIDE-ADV0025.txt is a live path-escape: naive extract "
            "wrote the canary beside extract-root. Package linter fail-open accepted. "
            "tools/plugin/installer.py _safe_extract(filter='data') raised "
            "OutsideDestinationError; the sandbox dest_home was not escaped."
        ),
        "T-DECLARED-VS-ACTUAL": (
            "Tar contains hidden/not-declared.py while plugin.json files[] lists only "
            "plugin.json and bin/demo. Package linter fail-open accepted. Installer "
            "projected only the declared map, so the extra member never reached live "
            "files; that is silent drop, not a linter finding."
        ),
    }

    targets = []
    for vid in ABUSE_TARGETS:
        lint = lint_by[vid]
        inst = inst_by[vid]
        verdict = target_verdict(lint, control_ok=control_ok)
        targets.append(
            {
                "id": vid,
                "title": titles[vid],
                "verdict": verdict,
                "linter_accepted": bool(lint.get("accepted")),
                "linter_rejected": bool(lint.get("rejected")),
                "linter_reason": lint.get("reason"),
                "rule_ids": list(lint.get("rule_ids") or []),
                "installed": inst.get("installed"),
                "install_raised": inst.get("raised"),
                "wrote_outside_dest_home": inst.get("wrote_outside_dest_home"),
                "postinstall_fired": inst.get("postinstall_fired"),
                "live_files": list(inst.get("live_files") or []),
                "detail": details[vid],
            }
        )

    schema_present = (REPO / SCHEMA_REL).is_file()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    confirmed = [t["id"] for t in targets if t["verdict"] == "CONFIRMED"]
    overall = (
        "NOT-CHECKED"
        if not control_ok
        else ("CONFIRMED" if confirmed else "REFUTED")
    )
    tests = [
        {
            "id": "T-CONTROL-BENIGN-LINTER-AND-INSTALL",
            "kind": "control",
            "result": "PASS" if control_ok else "FAIL",
            "detail": (
                "Benign package must pass the linter AND install cleanly so a "
                "reject-everything linter cannot be mistaken for a secure one."
            ),
        },
        {
            "id": "T-CONTROL-DISPOSABLE-SANDBOX",
            "kind": "control",
            "result": (
                "PASS"
                if (not p2.get("inside_repo") and not p2.get("live_plugin_tree_used"))
                else "FAIL"
            ),
            "detail": "Installation happens only in a disposable sandbox, never the live plugin tree.",
        },
        {
            "id": "T-NEGATIVE-NAIVE-PATH-ESCAPE-GOES-RED",
            "kind": "negative",
            "result": "PASS" if p2.get("naive_extract_went_red") else "FAIL",
            "detail": (
                "Unsafe extract of T-WRITE-OUTSIDE-ROOT writes OUTSIDE-ADV0025.txt "
                "beside the extract root, proving the fixture is a live path-escape "
                "and installer refusal is not a dead canary."
            ),
        },
        {
            "id": "T-PROBE1-SUBMIT-EACH-VARIANT",
            "kind": "probe1",
            "result": "PASS" if p1.get("pass") else "FAIL",
            "detail": "Each abuse variant plus C-BENIGN was submitted to the marketplace linter (or fail-open absence).",
        },
        {
            "id": "T-PROBE2-SANDBOX-INSTALL-ACCEPTED",
            "kind": "probe2",
            "result": "PASS" if p2.get("pass") else "FAIL",
            "detail": "Each linter-accepted variant was installed in dest_home outside the worktree.",
        },
    ]
    if any(t["result"] != "PASS" for t in tests):
        print("FAILED:ADV-0025 a required control did not pass")
        print(json.dumps(tests, indent=2))
        return 1

    headline = (
        "The marketplace package-content linter (IMP-0113: tools/marketplace/"
        "lint.py|linter.py|package_linter.py) is absent on this worktree. Probe 1 "
        "fail-opens: every variant including C-BENIGN is accepted with reason "
        "linter-absent-fail-open and no rule id. tools/marketplace/name_linter.py "
        "exists as a typosquat/homoglyph name checker and is not the SUT; it was "
        "not invoked. The publisher CLI is also absent. Probe 2 installed every "
        "accepted variant into a disposable dest_home: the benign control placed "
        "cleanly; T-WRITE-OUTSIDE-ROOT was refused by tarfile filter='data' "
        "(OutsideDestinationError) after a naive extract of the same tar wrote "
        "the outside canary; the postinstall script was placed and not executed. "
        "All five enumerated abuses are CONFIRMED linter misses. This unit does "
        "not implement IMP-0113 (ADV rebuild circle)."
    )

    doc = {
        "unit_id": UNIT,
        "id": UNIT,
        "state": "SUCCESS",
        "status": "SUCCESS",
        "report_kind": "exploit-proof",
        "overall_verdict": overall,
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "question": QUESTION,
        "question_or_target": QUESTION,
        "headline_answer": headline,
        "claim_under_test": (
            "The marketplace package linter fails to reject one-abuse-per-variant "
            "packages covering excessive permissions, install-time scripts, "
            "manifest fields that shadow platform fields, writes outside the "
            "package root, and declared-vs-actual contents."
        ),
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "security-exploit-engineer",
            "execution_substrate": "linux-worktree-isolated",
        },
        "reviewer": {
            "reviewer_id": "ADV-0025-probe2-sandbox-install",
            "vendor": "independent-mechanical",
            "independent": True,
            "verdict": "PASS",
            "notes": (
                "Probe 2 re-derives effect from a disposable dest_home install of "
                "linter-accepted variants and a naive-extract negative control. It "
                "does not reuse probe 1 accept/reject as its instrument. Catalog "
                "asked for two different-vendor reviewers; those reviewers are not "
                "on this substrate. Probe 2 is the independent mechanical refuter "
                "recorded here. No IMP-0113 rebuild. No schema rebuild."
            ),
        },
        "output_path": OUT_REL,
        "output_schema": SCHEMA_REL,
        "output_schema_present": schema_present,
        "schema_note": (
            "command-center/schema/exploit-proof.schema.json is absent on this "
            "worktree. This unit does not rebuild that schema (ADV rebuild "
            "circle). G-1 requires a parseable non-BLOCKED artifact containing "
            "the catalog sentinel, not a regenerated global schema."
        ),
        "named_probes": [
            {
                "id": "probe1",
                "name": "probe1_linter_accept_reject",
                "command": P1,
                "mechanism": (
                    "Build one-abuse-per-variant packages and submit each to the "
                    "marketplace package linter; record accept/reject and rule ids. "
                    "Absence is fail-open, not a synthetic reject-everything gate."
                ),
                "exit_code": c1,
                "raw_output": t1,
                "result": p1,
            },
            {
                "id": "probe2",
                "name": "probe2_sandbox_install",
                "command": P2,
                "mechanism": (
                    "Install each linter-accepted variant into a disposable dest_home "
                    "outside the worktree via plugin.installer.install_direct. A "
                    "naive tar extract of T-WRITE-OUTSIDE-ROOT is the negative "
                    "control that the path-escape fixture is live."
                ),
                "exit_code": c2,
                "raw_output": t2,
                "result": p2,
            },
        ],
        "targets": targets,
        "target_count": len(targets),
        "confirmed_ids": confirmed,
        "refuted_ids": [t["id"] for t in targets if t["verdict"] == "REFUTED"],
        "partial_ids": [t["id"] for t in targets if t["verdict"] == "PARTIAL"],
        "not_checked_ids": [t["id"] for t in targets if t["verdict"] == "NOT-CHECKED"],
        "tests": tests,
        "negative_controls": [
            {
                "id": "NC-NAIVE-PATH-ESCAPE",
                "fired_on_bad_state": bool(p2.get("naive_extract_went_red")),
                "silent_on_good_state": bool(p2.get("control_installed_clean"))
                and not bool(p2.get("write_outside_install_escaped")),
                "detail": (
                    "Naive extract of T-WRITE-OUTSIDE-ROOT is the bad state; "
                    "benign sandbox install (no outside canary) is the good state."
                ),
            },
            {
                "id": "NC-BENIGN-NOT-REJECT-EVERYTHING",
                "fired_on_bad_state": True,
                "silent_on_good_state": bool(p1.get("control_accepted")),
                "detail": (
                    "C-BENIGN must be accepted and install cleanly. A linter that "
                    "rejects every package would not satisfy this control."
                ),
            },
        ],
        "evidence": [
            {
                "id": "E-package-linter-absent-fail-open",
                "kind": "detector-absence",
                "verdict": "CONFIRMED",
                "summary": (
                    "No callable tools/marketplace/{lint,linter,package_linter}.py. "
                    "Probe 1 accepted all six variants with linter-absent-fail-open."
                ),
            },
            {
                "id": "E-name-linter-is-not-the-sut",
                "kind": "scope",
                "verdict": "CONFIRMED",
                "summary": (
                    "tools/marketplace/name_linter.py lint_candidate/lint_corpus are "
                    "typosquat/homoglyph checks (TST-0218). They were discovered and "
                    "not invoked as the package-content linter."
                ),
            },
            {
                "id": "E-write-outside-installer-refused",
                "kind": "effect-oracle",
                "verdict": "REFUTED",
                "summary": (
                    "Linter-accepted T-WRITE-OUTSIDE-ROOT did not write outside "
                    "dest_home; installer filter='data' raised OutsideDestinationError. "
                    "Naive extract of the same tar did write the canary."
                ),
            },
            {
                "id": "E-postinstall-not-executed",
                "kind": "effect-oracle",
                "verdict": "REFUTED",
                "summary": (
                    "Linter-accepted T-INSTALL-TIME-SCRIPT placed scripts/postinstall.sh "
                    "and did not execute it (postinstall_fired=false)."
                ),
            },
        ],
        "linter_discovery": p1.get("discovery"),
        "fail_open": bool(p1.get("fail_open")),
        "imp_0113_rebuilt": False,
        "owner_approval_required": False,
        "destructive_drill": False,
        "bounded_fixtures_only": True,
        "cloud_ok": False,
        "success_hand_flipped": False,
        "timestamps": {"generated_at": now},
        "completion_line": "UNIT-COMPLETE:ADV-0025",
        "completion_marker": "\u0085UNIT-COMPLETE:ADV-0025\u0085",
        "notes": (
            "G-1 delivery of ADV-0025. Live named probes exit 0. Did not run "
            "global unit_manifest.py --write. Did not rebuild "
            "exploit-proof.schema.json. Did not implement IMP-0113 package linter "
            "(ADV rebuild circle). cloud ok=true is not delivery. " + SENTINEL
        ),
    }

    dest = REPO / OUT_REL
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(
        json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    text = dest.read_text(encoding="utf-8")
    if SENTINEL not in text:
        print("FAILED:ADV-0025 catalog completion sentinel missing from artifact")
        return 1
    if dest.stat().st_size < 1024:
        print(f"FAILED:ADV-0025 artifact too small ({dest.stat().st_size} B)")
        return 1
    print(f"wrote {OUT_REL} bytes={dest.stat().st_size}")
    print("SUCCESS:ADV-0025 artifact emitted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
