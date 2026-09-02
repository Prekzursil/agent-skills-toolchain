#!/usr/bin/env python3
"""Named probe 2: mutation exit codes for the armed completeness gate.

An independent incomplete-catalog attempt: delete the defaults block, delete
one overridable key, and plant an empty completion_sentinel. The gate is armed
only if those runs exit non-zero under --require-complete, and the unmutated
catalog stays silent (exit 0) in the same isolated CLI. Presence of the flag
in a YAML file is not this probe's pass condition.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools" / "command-center"))

import catalog as cat  # noqa: E402
from harness import run_validate_cli  # noqa: E402

ART = REPO / "command-center" / "receipts" / "CC-0001.json"
SENTINEL = "SUCCESS:CC-0001"
CI_REL = ".github/workflows/command-center.yml"


def fail(msg: str) -> int:
    print(f"FAILED:CC-0001-probe2 {msg}")
    return 1


def main() -> int:
    live = cat.load()

    good = run_validate_cli(live, require_complete=True)
    print(f"live_require_complete rc={good['exit_code']} v_fields={good['v_fields']}")
    if good["exit_code"] != 0:
        print(good["output_tail"])
        return fail("unmutated catalog not silent under --require-complete")
    if good["v_fields"] or not good["success_marker"]:
        return fail("unmutated catalog emitted V-FIELDS or missed SUCCESS")

    deleted = copy.deepcopy(live)
    del deleted["defaults"]
    mut_block = run_validate_cli(deleted, require_complete=True)
    print(
        f"deleted_defaults_require_complete rc={mut_block['exit_code']} "
        f"v_defaults={mut_block['v_defaults']} v_fields={mut_block['v_fields']}"
    )
    if mut_block["exit_code"] == 0:
        return fail("defaults-block deletion exited 0 under --require-complete")
    if not mut_block["v_defaults"]:
        return fail("defaults-block deletion did not report V-DEFAULTS")

    one = copy.deepcopy(live)
    del one["defaults"]["timeout_seconds"]
    mut_one = run_validate_cli(one, require_complete=True)
    print(
        f"deleted_timeout_require_complete rc={mut_one['exit_code']} "
        f"v_defaults={mut_one['v_defaults']} v_fields={mut_one['v_fields']}"
    )
    if mut_one["exit_code"] == 0:
        return fail("single-field defaults deletion exited 0")
    if not (mut_one["v_defaults"] and mut_one["v_fields"]):
        return fail("single-field deletion missed V-DEFAULTS or V-FIELDS")

    # Discriminator for the flag itself (V-DEFAULTS already catches block deletion).
    sentinel_bad = copy.deepcopy(live)
    sentinel_bad["items"][0]["completion_sentinel"] = ""
    bare = run_validate_cli(sentinel_bad, require_complete=False)
    armed = run_validate_cli(sentinel_bad, require_complete=True)
    print(
        f"empty_sentinel_bare rc={bare['exit_code']} v_fields={bare['v_fields']} "
        f"empty_sentinel_armed rc={armed['exit_code']} v_fields={armed['v_fields']}"
    )
    if bare["exit_code"] != 0:
        print(bare["output_tail"])
        return fail("empty sentinel with flag off should stay silent (V-FIELDS disarmed)")
    if armed["exit_code"] == 0 or not armed["v_fields"]:
        return fail("empty sentinel with --require-complete did not arm V-FIELDS")

    if not ART.is_file():
        return fail("receipt missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if SENTINEL not in text:
        return fail("sentinel-absent")
    stored = doc.get("mutation_runs") or {}
    if stored.get("live_require_complete_exit") != 0:
        return fail("receipt live exit not 0")
    if stored.get("deleted_defaults_exit") in (None, 0):
        return fail("receipt did not cite a non-zero defaults-deletion exit")
    if stored.get("deleted_timeout_exit") in (None, 0):
        return fail("receipt did not cite a non-zero single-field exit")
    if stored.get("empty_sentinel_bare_exit") != 0:
        return fail("receipt empty-sentinel-bare exit")
    if stored.get("empty_sentinel_armed_exit") in (None, 0):
        return fail("receipt empty-sentinel-armed exit")

    ci = REPO / CI_REL
    if not ci.is_file():
        return fail(f"{CI_REL} missing")
    ci_text = ci.read_text(encoding="utf-8")
    if "validate.py --require-complete" not in ci_text:
        return fail("CI file does not invoke validate.py --require-complete")
    # Supporting check only — the pass condition above is the mutation exit codes.
    print(f"ci_invocation_present={True} path={CI_REL}")

    print(
        json.dumps(
            {
                "live_require_complete_exit": good["exit_code"],
                "deleted_defaults_exit": mut_block["exit_code"],
                "deleted_timeout_exit": mut_one["exit_code"],
                "empty_sentinel_bare_exit": bare["exit_code"],
                "empty_sentinel_armed_exit": armed["exit_code"],
                "reviewer": "incomplete-catalog-attempt",
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:CC-0001-probe2 mutation-exit-codes require-complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
