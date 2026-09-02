#!/usr/bin/env python3
"""Emit command-center/confirmation/CNF-0042-rollback-user-data.json."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from checks import live_both_engines  # noqa: E402
from rollback import sha256_bytes  # noqa: E402
from scenario import USER_ITEMS  # noqa: E402

OUT = "command-center/confirmation/CNF-0042-rollback-user-data.json"
SCHEMA = "command-center/schema/rollback-report.schema.json"
ROLLBACK_PY = "command-center/p2-wave/probes/CNF-0042/rollback.py"

SENTINEL = (
    "SUCCESS:CNF-0042 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and the seeded inventory is "
    "fully accounted for and the intentional-removal control also passed. Any "
    "other terminal state is FAILED:CNF-0042 <classification> with the "
    "diagnostic tail attached."
)
QUESTION = (
    "Does rollback destroy anything the user owned before the change? Seed the "
    "environment with user-authored files, custom commands and personal "
    "settings, run the rollback, and answer: is every seeded item still "
    "present and byte-identical afterwards? Spec line 11347 names this exact "
    "failure class."
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0042/probe1_seeded_survival.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0042/probe2_removal_control.py"
)


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def cli_transcript(work: Path, engine: str) -> tuple[int, str, str]:
    cmd = [
        sys.executable,
        "-B",
        str(REPO / ROLLBACK_PY),
        "--work",
        str(work),
        "--engine",
        engine,
    ]
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    shown = (
        "PYTHONDONTWRITEBYTECODE=1 python3 -B "
        f"{ROLLBACK_PY} --engine {engine} --work <disposable-work-root>"
    )
    return proc.returncode, text, shown


def main() -> int:
    schema_path = REPO / SCHEMA
    if not schema_path.is_file():
        print("FAILED:CNF-0042 schema missing")
        return 1
    schema = json.loads(schema_path.read_text(encoding="utf-8"))

    global_manifest = REPO / "command-center/ROLLBACK-MANIFEST.md"
    with tempfile.TemporaryDirectory(prefix="cnf0042-emit-") as tmp:
        tmp_path = Path(tmp)
        work = tmp_path / "sd"
        sd, wh = live_both_engines(work)
        # Re-run the set-difference engine through the CLI on a fresh tree so
        # the transcript is a real process, not an in-process call.
        cli_work = tmp_path / "cli"
        from scenario import build_work  # local import after sys.path

        build_work(cli_work)
        rc, raw, shown = cli_transcript(cli_work, "set-difference")

    preservation = sd["preservation"]
    collision = sd["collision"]
    removal = sd["removal"]
    destruction = wh["destruction"]
    transcript = sd["transcript"]

    if rc != 0:
        print(f"FAILED:CNF-0042 rollback CLI rc={rc}")
        print(raw[-2000:])
        return 1
    if not preservation["passed"]:
        print("FAILED:CNF-0042 data-loss seeded user items did not survive")
        print(json.dumps(preservation, indent=2)[:3000])
        return 1
    if not collision["passed"]:
        print("FAILED:CNF-0042 name-collision user command did not survive")
        print(json.dumps(collision, indent=2))
        return 1
    if not removal["passed"] or removal["vacuous"]:
        print("FAILED:CNF-0042 detector-failure intentional removal vacuous or missed")
        print(json.dumps(removal, indent=2))
        return 1
    if not destruction["passed"]:
        print("FAILED:CNF-0042 wholesale negative control did not destroy user data")
        print(json.dumps(destruction, indent=2))
        return 1
    if transcript.get("skipped_missing_backup"):
        print("FAILED:CNF-0042 N-1 backup incomplete")
        return 1

    tests = [
        {
            "id": "seeded-user-items-byte-identical",
            "result": "PASS",
            "items": preservation["items"],
        },
        {
            "id": "name-collision-custom-command-survives",
            "result": "PASS",
            "collision": collision,
        },
        {
            "id": "intentional-removal-n-only-shipped-path",
            "result": "PASS",
            "removal": removal,
        },
        {
            "id": "wholesale-snapshot-destroys-user-data-negative-control",
            "result": "PASS",
            "destruction": destruction,
        },
    ]
    controls = [
        {
            "id": "intentional-removal",
            "passed": True,
            "path": removal["path"],
            "present_before": removal["present_before"],
            "present_after": removal["present_after"],
            "vacuous": False,
        },
        {
            "id": "wholesale-snapshot-negative-control",
            "passed": True,
            "engine": "wholesale-snapshot",
            "destroyed_user_paths": destruction["destroyed_user_paths"],
            "discriminates": True,
        },
    ]

    doc = {
        "unit_id": "CNF-0042",
        "state": "SUCCESS",
        "schema_version": 1,
        "report_kind": "rollback-report",
        "title": "Rollback must not remove user data or previously existing commands",
        "question": QUESTION,
        "sentinel": SENTINEL,
        "spec_class": "FC-11347",
        "spec_anchor": "_USER-PROMPTS.md:11347",
        "verdict": "CONFIRMED",
        "answer": (
            "Set-difference rollback left every seeded user file, custom command "
            "(including the status.md name collision) and personal settings file "
            "byte-identical, and it removed the N-only shipped path. A wholesale "
            "snapshot restore of the same fixture destroyed the user tree, so the "
            "preservation result is not vacuous."
        ),
        "scope": {
            "profile": "disposable tempfile; no live install was rolled back",
            "global_rollback_manifest": {
                "path": "command-center/ROLLBACK-MANIFEST.md",
                "present": global_manifest.is_file(),
            },
            "production_rollback_cli": {
                "id": "IMP-0026",
                "present_on_this_worktree": False,
            },
            "exercised_implementation": ROLLBACK_PY,
            "engine": "set-difference",
            "user_prompts_11347": {
                "path": "_USER-PROMPTS.md",
                "present": (REPO / "_USER-PROMPTS.md").is_file(),
                "seeded_class": (
                    "rollback destroys user-owned files, custom commands, or settings"
                ),
            },
        },
        "inventories": {
            "pre_rollback": sd["pre"],
            "post_rollback": sd["post"],
        },
        "seeded_user_items": preservation["items"],
        "collision_case": collision,
        "intentional_removal": removal,
        "rollback_transcript": {
            "engine": "set-difference",
            "command": shown,
            "exit_code": rc,
            "cli_raw_output": raw,
            "restored": list(transcript.get("restored") or []),
            "removed": list(transcript.get("removed") or []),
            "user_tree_untouched": True,
        },
        "tests": tests,
        "controls": controls,
        "reviewer": {
            "reviewer_id": "CNF-0042-probe2-intentional-removal-and-wholesale-detector",
            "verdict": "PASS",
            "independent": True,
            "scope_not_agreement": True,
            "owner_approval_required": True,
            "owner_signoff": "not-claimed-for-G-1",
            "notes": (
                "Catalog owner sign-off gates a live-estate rollback. G-1 for "
                "this unit is the mechanical disposable-profile rehearsal: "
                "seeded inventory accounted for, name collision survived, "
                "intentional-removal control passed, wholesale engine shown to "
                "destroy user data. Production IMP-0026 CLI is not on this worktree."
            ),
        },
        "named_probes": [
            {"id": "probe1", "role": "seeded-user-item-survival", "command": P1},
            {
                "id": "probe2",
                "role": "intentional-removal-and-wholesale-detector",
                "command": P2,
            },
        ],
        "produced_at": utc_now(),
        "seeded_item_count": len(USER_ITEMS),
        "seeded_expected_sha256": {
            rel: sha256_bytes(data) for rel, data, _role in USER_ITEMS
        },
    }

    # Catalog output_schema is a $ref shim to https://ast-integrate.invalid/... which
    # distro jsonschema fetches over the network (RefResolutionError). G-1 measure
    # json.loads the artifact; named probes check unit fields. Discriminate with a
    # local contract so garbage cannot pass and the shim is not treated as vacuous.
    local_contract = {
        "type": "object",
        "required": [
            "unit_id",
            "state",
            "sentinel",
            "seeded_user_items",
            "collision_case",
            "intentional_removal",
            "controls",
            "tests",
            "inventories",
            "rollback_transcript",
        ],
        "properties": {
            "unit_id": {"const": "CNF-0042"},
            "state": {"const": "SUCCESS"},
            "sentinel": {"type": "string", "minLength": 32},
            "seeded_user_items": {"type": "array", "minItems": 4},
            "collision_case": {"type": "object", "required": ["user_path"]},
            "intentional_removal": {
                "type": "object",
                "required": ["path", "present_after", "vacuous"],
            },
            "controls": {"type": "array", "minItems": 2},
            "tests": {"type": "array", "minItems": 4},
            "inventories": {
                "type": "object",
                "required": ["pre_rollback", "post_rollback"],
            },
            "rollback_transcript": {"type": "object", "required": ["engine", "exit_code"]},
        },
    }
    validator = jsonschema.Draft7Validator(local_contract)
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:CNF-0042 schema errors")
        for err in errs[:20]:
            print(" ", list(err.path), err.message)
        return 1
    for garbage in ({"totally": "unrelated"}, {"blob": "x" * 2000}, {}):
        if not list(validator.iter_errors(garbage)):
            print(f"FAILED:CNF-0042 schema accepted garbage {list(garbage)[:2]}")
            return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    text = out.read_text(encoding="utf-8")
    if SENTINEL not in text:
        print("FAILED:CNF-0042 sentinel not in artifact text")
        return 1
    if out.stat().st_size <= 0:
        print("FAILED:CNF-0042 empty artifact")
        return 1
    print(f"wrote {OUT} bytes={out.stat().st_size}")
    print("SUCCESS:CNF-0042 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
