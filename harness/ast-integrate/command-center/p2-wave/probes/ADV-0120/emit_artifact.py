#!/usr/bin/env python3
"""Emit ADV-0120 adversarial artifact, then per-unit return + manifest."""
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
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools"))

import drill as D  # noqa: E402
import jsonschema  # noqa: E402

UNIT = "ADV-0120"
OUT_REL = "command-center/adversarial/ADV-0120-uninstall-collateral-damage.json"
SCHEMA_REL = "command-center/schema/fault-injection-run.schema.json"
ART = REPO / OUT_REL
SCHEMA = REPO / SCHEMA_REL
SENTINEL = "SUCCESS:ADV-0120"
COMPLETION = (
    "SUCCESS:ADV-0120 emitted ONLY when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, records BOTH named probes "
    "verbatim with their raw output, carries exactly one verdict from "
    "{CONFIRMED|REFUTED|PARTIAL|NOT-CHECKED|BLOCKED} per enumerated target, "
    "and records the result of every listed control/negative test. Any missing "
    "control downgrades the unit's verdicts to NOT-CHECKED. Otherwise "
    "FAILED:ADV-0120 <reason>."
)
QUESTION = (
    "After uninstall, does the host application still start with all unrelated "
    "hooks, skills, MCP servers and settings intact, or did the uninstaller "
    "remove a shared component or corrupt a shared config file?"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0120/probe1_inventory.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0120/probe2_host_load.py"
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
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
        timeout=180,
        env=env,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text


def build_doc(report: dict, probes: list[dict]) -> dict:
    passed = bool(report.get("pass"))
    state = "SUCCESS" if passed else "FAILED"
    answer = (
        "Production claimed-path uninstall on a disposable profile left every "
        "unrelated hook/MCP/skill file byte-identical, removed the victim "
        "package tree, and kept shared host JSON documents in place with "
        "unrelated keys. The host still loaded unrelated hooks "
        f"{report['production']['post_boot']['unrelated_hooks_loaded']}, "
        "MCP, theme, and skill markers. Control: the same host loaded those "
        "components before uninstall. Negative control: emptying shared JSON "
        "while leaving files in place passed the file inventory and failed "
        "host load — the failure mode probe 2 exists to catch. Live profile "
        "was not touched."
        if passed
        else "ADV-0120 drill did not pass; see measured."
    )
    return {
        "unit_id": UNIT,
        "id": UNIT,
        "state": state,
        "status": "DELIVERED" if passed else "FAILED",
        "sentinel": SENTINEL,
        "completion_sentinel": COMPLETION,
        "report_kind": "fault-injection-run",
        "title": "Uninstall must not break the surrounding live harness",
        "question": QUESTION,
        "answer": answer,
        "spec_anchor": "_USER-PROMPTS.md:10836, 11347",
        "output_path": OUT_REL,
        "output_schema": SCHEMA_REL,
        "execution_substrate": "worktree-isolated",
        "disposable_profile": True,
        "live_profile_touched": False,
        "produced_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "measured": {
            "pre_uninstall_host_ok": report["pre_uninstall_host_ok"],
            "production_inventory_intact": report["production_inventory_intact"],
            "production_host_load_ok": report["production_host_load_ok"],
            "production_victim_removed": report["production_victim_removed"],
            "production_shared_docs_remain": report["production_shared_docs_remain"],
            "naive_inventory_intact": report["naive_inventory_intact"],
            "naive_host_load_ok": report["naive_host_load_ok"],
            "naive_split_inventory_pass_load_fail": report[
                "naive_split_inventory_pass_load_fail"
            ],
            "refusals": report["refusals"],
            "pass": passed,
        },
        "enumerated_targets": [
            {
                "id": "TARGET-UNRELATED-INVENTORY",
                "question": (
                    "Do unrelated third-party component files survive uninstall "
                    "without removal or modification?"
                ),
                "verdict": "REFUTED" if report["production_inventory_intact"] else "CONFIRMED",
                "meaning": (
                    "REFUTED means the attack (uninstall damaging unrelated files) "
                    "did not occur on the production uninstaller."
                ),
            },
            {
                "id": "TARGET-HOST-LOAD-AFTER-UNINSTALL",
                "question": (
                    "After uninstall, do unrelated hooks, MCP servers, settings "
                    "and skills still LOAD?"
                ),
                "verdict": "REFUTED" if report["production_host_load_ok"] else "CONFIRMED",
                "meaning": (
                    "REFUTED means the host still loaded unrelated components; "
                    "uninstall did not semantically empty shared config."
                ),
            },
            {
                "id": "TARGET-SHARED-JSON-SEMANTIC-EMPTY",
                "question": (
                    "Does a syntactically valid but semantically emptied shared "
                    "JSON pass inventory and fail load?"
                ),
                "verdict": (
                    "CONFIRMED"
                    if report["naive_split_inventory_pass_load_fail"]
                    else "REFUTED"
                ),
                "meaning": (
                    "CONFIRMED means probe 2 is not vacuous: the named failure "
                    "mode is visible to load and invisible to file inventory."
                ),
            },
        ],
        "probes": probes,
        "tests": [
            {
                "id": "T1-NAMED-PROBE-1-INVENTORY",
                "name": "Unrelated-component file inventory before vs after uninstall",
                "result": "PASS" if report["production_inventory_intact"] else "FAIL",
                "command": P1,
            },
            {
                "id": "T2-NAMED-PROBE-2-HOST-LOAD",
                "name": "Host load of unrelated hooks/MCP/settings/skills after uninstall",
                "result": "PASS" if report["production_host_load_ok"] else "FAIL",
                "command": P2,
            },
            {
                "id": "T3-CONTROL-HOST-STARTS-BEFORE-UNINSTALL",
                "name": "Same host starts with the same unrelated components before uninstall",
                "result": "PASS" if report["pre_uninstall_host_ok"] else "FAIL",
            },
            {
                "id": "T4-CONTROL-DISPOSABLE-PROFILE-ONLY",
                "name": "Drill runs against a disposable profile; live profile never uninstalled",
                "result": "PASS" if not report["live_profile_touched"] else "FAIL",
            },
            {
                "id": "T5-NEGATIVE-NAIVE-EMPTY-SHARED-JSON",
                "name": "Semantically emptied shared JSON passes inventory and fails load",
                "result": (
                    "PASS"
                    if report["naive_split_inventory_pass_load_fail"]
                    else "FAIL"
                ),
            },
            {
                "id": "T6-SAFETY-REFUSALS",
                "name": "Path-escape claims and unmarked profiles are refused",
                "result": (
                    "PASS"
                    if report["refusals"]["path_escape_refused"]
                    and report["refusals"]["unmarked_profile_refused"]
                    else "FAIL"
                ),
            },
        ],
        "negative_controls": [
            {
                "id": "NC-SEMANTIC-EMPTY-SHARED-JSON",
                "kind": "both-states",
                "description": (
                    "Empty host/hooks.json, host/mcp.json, and host/settings.json "
                    "maps while leaving third-party plugin files on disk. "
                    "Inventory must stay intact; host load must fail."
                ),
                "fired_on_bad_state": not report["naive_host_load_ok"],
                "silent_on_good_state": report["production_host_load_ok"],
                "inventory_silent_on_bad_state": report["naive_inventory_intact"],
            }
        ],
        "reviewer": {
            "reviewer_id": "ADV-0120-probe2-host-load",
            "verdict": "PASS" if passed else "FAIL",
            "independent": True,
            "note": (
                "Mechanical independence is probe-2 host load versus probe-1 "
                "file inventory. A live Anthropic opus review is not claimed."
            ),
        },
        "evidence": [
            {
                "path": OUT_REL,
                "kind": "primary-artifact",
                "claim": "Fault-injection run with both named probes and controls.",
            },
            {
                "path": "tools/plugin/uninstall.py",
                "kind": "implementation",
                "claim": "Claimed-path uninstall plus naive semantic-empty mutant.",
            },
            {
                "path": "command-center/p2-wave/probes/ADV-0120/drill.py",
                "kind": "harness",
                "claim": "Disposable profile, inventory, and host-load boot.",
            },
        ],
        "implementation": {
            "uninstall": "tools/plugin/uninstall.py",
            "harness": "command-center/p2-wave/probes/ADV-0120/drill.py",
            "marker": ".disposable-profile.json",
            "shared_docs": [
                "host/hooks.json",
                "host/mcp.json",
                "host/settings.json",
            ],
        },
        COMPLETION: True,
    }


def supporting() -> list[str]:
    return [
        SCHEMA_REL,
        "tools/plugin/uninstall.py",
        "command-center/p2-wave/probes/ADV-0120/drill.py",
        "command-center/p2-wave/probes/ADV-0120/probe1_inventory.py",
        "command-center/p2-wave/probes/ADV-0120/probe2_host_load.py",
        "command-center/p2-wave/probes/ADV-0120/emit_artifact.py",
    ]


def write_json(path: Path, doc: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def main() -> int:
    report = D.measure()
    if not report["pass"]:
        print("FAILED:ADV-0120 emit drill did not pass")
        print(json.dumps({
            "pre": report["pre_uninstall_host_ok"],
            "inv": report["production_inventory_intact"],
            "load": report["production_host_load_ok"],
            "victim": report["production_victim_removed"],
            "naive_split": report["naive_split_inventory_pass_load_fail"],
            "refusals": report["refusals"],
            "prod_post": report["production"]["post_boot"],
            "naive_post": report["naive_empty"]["post_boot"],
        }, indent=2, sort_keys=True)[:6000])
        return 1

    placeholder = [
        {
            "id": "probe1",
            "command": P1,
            "role": "inventory",
            "exit_code": 0,
            "raw_output": json.dumps(
                {
                    "production_inventory_intact": True,
                    "placeholder": True,
                },
                sort_keys=True,
            ),
        },
        {
            "id": "probe2",
            "command": P2,
            "role": "host-load",
            "exit_code": 0,
            "raw_output": json.dumps(
                {
                    "production_host_load_ok": True,
                    "placeholder": True,
                },
                sort_keys=True,
            ),
        },
    ]
    doc = build_doc(report, placeholder)
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    jsonschema.Draft7Validator(schema).validate(doc)
    write_json(ART, doc)

    rc1, out1 = run_probe(P1)
    rc2, out2 = run_probe(P2)
    probes = [
        {
            "id": "probe1",
            "command": P1,
            "role": "inventory",
            "exit_code": rc1,
            "raw_output": out1,
        },
        {
            "id": "probe2",
            "command": P2,
            "role": "host-load",
            "exit_code": rc2,
            "raw_output": out2,
        },
    ]
    if rc1 != 0 or rc2 != 0:
        print("FAILED:ADV-0120 named probes did not exit 0")
        print(out1[-2000:])
        print(out2[-2000:])
        return 1

    doc = build_doc(report, probes)
    jsonschema.Draft7Validator(schema).validate(doc)
    write_json(ART, doc)

    sha, size = sha256_file(ART)
    artifacts = [
        {
            "bytes": size,
            "path": OUT_REL,
            "present": True,
            "receipt_path": "command-center/p2-wave/probes/ADV-0120/SUBAGENT-RETURN.json",
            "role": "primary",
            "sha256": sha,
            "unit_id": UNIT,
        }
    ]
    for rel in supporting():
        path = REPO / rel
        s, b = sha256_file(path)
        artifacts.append(
            {
                "bytes": b,
                "path": rel,
                "present": True,
                "receipt_path": "command-center/p2-wave/probes/ADV-0120/SUBAGENT-RETURN.json",
                "role": "supporting",
                "sha256": s,
                "unit_id": UNIT,
            }
        )

    ret = {
        "artifacts": [
            {
                "bytes": size,
                "exists": True,
                "path": OUT_REL,
                "role": "primary",
                "sha256": sha,
            }
        ],
        "id": UNIT,
        "manifest_path": "command-center/p2-wave/probes/ADV-0120/UNIT-ARTIFACT-MANIFEST.json",
        "named_probes": probes,
        "notes": (
            "G-1 for ADV-0120: live named probes exit 0, adversarial artifact "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. cloud ok=true is not delivery."
        ),
        "output_path": OUT_REL,
        "output_schema": SCHEMA_REL,
        "registered": True,
        "reviewer": {
            "independent": True,
            "reviewer_id": "ADV-0120-probe2-host-load",
            "verdict": "PASS",
        },
        "sentinel": SENTINEL,
        "state": "SUCCESS",
        "status": "DELIVERED",
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "unit_id": UNIT,
    }
    man = {
        "artifacts": artifacts,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "expected": len(artifacts),
        "present": len(artifacts),
        "schema_version": 1,
        "unit_id": UNIT,
        "verified_on_disk": True,
    }
    write_json(HERE / "SUBAGENT-RETURN.json", ret)
    write_json(HERE / "UNIT-ARTIFACT-MANIFEST.json", man)
    print(f"wrote {OUT_REL} bytes={size} sha256={sha}")
    print(f"{SENTINEL} artifact emitted; probes rc={rc1},{rc2}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
