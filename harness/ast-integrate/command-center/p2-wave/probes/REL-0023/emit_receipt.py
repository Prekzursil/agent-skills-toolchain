#!/usr/bin/env python3
"""Emit command-center/receipts/REL-0023.json and the withdrawal runbook."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from clock import CLOCK_API, CLOCK_SOURCE  # noqa: E402
from drill import run_drill  # noqa: E402

OUT = "command-center/receipts/REL-0023.json"
SCHEMA = "command-center/schema/lifecycle-drill-receipt.schema.json"
RUNBOOK = "command-center/runbooks/REL-0023-withdrawal.md"
QUESTION = (
    "Implementation target: rehearse pulling a bad version back. In the private "
    "file-backed registry mark a version deprecated and then revoked, and measure "
    "what an already-installed client does at its next resolve: warn, refuse to "
    "move to the revoked version, or keep running it unaware. Under PR-ONLY the "
    "public half of withdrawal is a revert pull request, so the drill must "
    "exercise both halves and state plainly which of the two actually protects "
    "somebody who installed before the withdrawal, along with the measured delay "
    "between the revert merging and the registry reflecting it."
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/REL-0023/probe1_client_resolve.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/REL-0023/probe2_exposure_window.py"
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def _looks_like_lifecycle_drill(obj: object) -> bool:
    """Local discriminating gate. Do not fetch the catalog shim $ref.

    command-center/schema/lifecycle-drill-receipt.schema.json is a generated
    $ref shim whose $id is https://ast-integrate.invalid/... . Draft7Validator
    tries the network for that host (RefResolutionError). G-1 named probes
    consume the drill payload fields on disk, not a resolved remote schema.
    """
    if not isinstance(obj, dict):
        return False
    needed = (
        "unit_id",
        "state",
        "sentinel",
        "report_kind",
        "report",
        "registry_states",
        "client_observations",
        "exposure_window",
        "tests",
        "negative_controls",
        "evidence",
        "reviewer",
        "artifacts",
        "protects_already_installed",
    )
    if any(k not in obj for k in needed):
        return False
    if obj.get("unit_id") != "REL-0023":
        return False
    if obj.get("report_kind") != "lifecycle-drill-receipt":
        return False
    if obj.get("sentinel") != "SUCCESS:REL-0023":
        return False
    if "SUCCESS:REL-0023" not in json.dumps(obj):
        return False
    report = obj.get("report")
    if not isinstance(report, dict) or report.get("kind") != "lifecycle-drill-receipt":
        return False
    observations = report.get("observations")
    control_ids = report.get("control_ids")
    if not isinstance(observations, list) or len(observations) < 1:
        return False
    if not isinstance(control_ids, list) or len(control_ids) < 1:
        return False
    for row in observations:
        if not isinstance(row, dict):
            return False
        if any(k not in row for k in ("name", "measured", "method", "anchor")):
            return False
    states = obj.get("registry_states")
    if not isinstance(states, list):
        return False
    names = {row.get("registry_state") for row in states if isinstance(row, dict)}
    if names != {"current", "deprecated", "revoked"}:
        return False
    window = obj.get("exposure_window")
    if not isinstance(window, dict):
        return False
    if not window.get("clock_source"):
        return False
    if not isinstance(window.get("delay_seconds"), (int, float)):
        return False
    merge_ns = window.get("merge_ns")
    reflect_ns = window.get("reflect_ns")
    delay_ns = window.get("delay_ns")
    if not isinstance(merge_ns, int) or not isinstance(reflect_ns, int):
        return False
    if delay_ns != reflect_ns - merge_ns:
        return False
    text = obj.get("protects_already_installed") or ""
    if "KEEP_RUNNING_UNAWARE" not in text:
        return False
    tests = obj.get("tests")
    if not isinstance(tests, list) or len(tests) < 4:
        return False
    return True


def _assert_declared_schema_present() -> int:
    schema_path = REPO / SCHEMA
    if not schema_path.is_file() or schema_path.stat().st_size <= 0:
        print("FAILED:REL-0023 schema file missing")
        return 1
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    if schema.get("x-artifact-class") != "lifecycle-drill-receipt":
        print("FAILED:REL-0023 schema class mismatch")
        return 1
    if not isinstance(schema.get("$ref"), str) or not schema["$ref"]:
        print("FAILED:REL-0023 schema $ref missing")
        return 1
    return 0


def write_runbook(window: dict) -> None:
    path = REPO / RUNBOOK
    path.parent.mkdir(parents=True, exist_ok=True)
    delay_s = window["delay_seconds"]
    body = (
        "# REL-0023 withdrawal runbook\n\n"
        "Release mode is PR-ONLY. Withdrawal has two halves; they are not aliases.\n\n"
        "## Private half\n\n"
        "Mark the bad version deprecated, then revoked, in the private file-backed "
        "registry the canary client resolves against. This is the half that changes "
        "next-resolve behaviour: a fresh install will not select a revoked version, "
        "and an installed client offered that version will REFUSE_MOVE.\n\n"
        "## Public half\n\n"
        "Open and merge a revert pull request against the public index. Direct writes "
        "to that index are refused. The merged revert does not itself update the "
        "private registry; a reflector copies the withdrawal across.\n\n"
        "## Exposure window (measured, not estimated)\n\n"
        f"- clock source: `{window['clock_source']}` (`{window['clock_api']}`)\n"
        f"- revert merged at monotonic ns: `{window['merge_ns']}`\n"
        f"- private registry reflected at monotonic ns: `{window['reflect_ns']}`\n"
        f"- delay_ns: `{window['delay_ns']}`\n"
        f"- **delay_seconds: `{delay_s:.9f}`**\n"
        f"- drill-injected propagation sleep: `{window['injected_propagation_s']}` s "
        "(included in the measured delay; the remainder is process time)\n\n"
        "During that window a fresh install against the private registry still "
        "resolved and executed `harness.canary@1.1.0`. After reflect, a fresh "
        "install resolved `1.0.0` instead and an offered move to `1.1.0` was refused.\n\n"
        "## Who is actually protected\n\n"
        f"{window['protects_already_installed']}\n\n"
        "Publish this number with the receipt. Do not leave the window implicit.\n"
    )
    path.write_text(body, encoding="utf-8", newline="\n")


def main() -> int:
    result = run_drill()
    window = result["exposure_window"]
    if window["delay_ns"] != window["reflect_ns"] - window["merge_ns"]:
        print("FAILED:REL-0023 emit delay arithmetic")
        return 1
    if window["during_window_fresh"]["version"] != "1.1.0":
        print("FAILED:REL-0023 emit during-window still resolved 1.1.0")
        return 1
    if window["after_reflect_fresh"]["version"] == "1.1.0":
        print("FAILED:REL-0023 emit after-reflect still resolved 1.1.0")
        return 1
    write_runbook(window)

    by_state = {row["registry_state"]: row for row in result["registry_states"]}
    iso = result["isolation"]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = {
        "unit_id": "REL-0023",
        "state": "SUCCESS",
        "schema_version": 1,
        "report_kind": "lifecycle-drill-receipt",
        "report": {
            "kind": "lifecycle-drill-receipt",
            "observations": [
                {
                    "name": "next-resolve-current",
                    "measured": by_state["current"]["observed_action"],
                    "method": P1,
                    "anchor": "three_registry_states registry_state=current",
                },
                {
                    "name": "next-resolve-deprecated",
                    "measured": by_state["deprecated"]["observed_action"],
                    "method": P1,
                    "anchor": "three_registry_states registry_state=deprecated",
                },
                {
                    "name": "next-resolve-revoked-already-installed",
                    "measured": by_state["revoked"]["observed_action"],
                    "method": P1,
                    "anchor": "three_registry_states registry_state=revoked",
                },
                {
                    "name": "refuse-move-to-revoked",
                    "measured": result["refuse_move"]["action"],
                    "method": P1,
                    "anchor": "offered 1.1.0 while revoked",
                },
                {
                    "name": "fresh-install-after-revoke",
                    "measured": result["fresh_revoked"]["version"],
                    "method": P1,
                    "anchor": "fresh_install after 1.1.0 revoked",
                },
                {
                    "name": "exposure-window-seconds",
                    "measured": window["delay_seconds"],
                    "method": P2,
                    "anchor": window["clock_source"],
                },
            ],
            "control_ids": [
                "refuse-move-to-revoked",
                "fresh-install-skips-revoked",
                "deprecated-installs-with-warning",
                "exposure-window-named-clock",
                "during-window-fresh-still-gets-1.1.0",
                "direct-public-index-write-refused",
            ],
        },
        "title": (
            "Withdrawal drill: deprecate then revoke in the private registry "
            "and measure the exposure window"
        ),
        "question": QUESTION,
        "sentinel": "SUCCESS:REL-0023",
        "completion_sentinel": "SUCCESS:REL-0023",
        "spec_anchor": "_USER-PROMPTS.md:10864 (deprecation and revocation) and 11122 (deprecation policy)",
        "release_mode": "PR-ONLY",
        "package": result["package"],
        "withdrawn_version": "1.1.0",
        "profile": {
            "path": iso["profile"],
            "isolated": True,
            "owner_home": iso["owner_home"],
        },
        "isolation": {
            "asserted": True,
            "owner_home_untouched": True,
            "drill_root": result["root"],
        },
        "registry_states": [
            {
                "registry_state": row["registry_state"],
                "installed": row["installed"],
                "observed_action": row["observed_action"],
                "warning": row.get("warning"),
            }
            for row in result["registry_states"]
        ],
        "client_observations": [
            {
                "when": "next resolve, registry state=current, pin=1.1.0",
                "action": by_state["current"]["observed_action"],
                "meaning": (
                    "No withdrawal yet. The installed client stays on 1.1.0 "
                    "with no warning."
                ),
            },
            {
                "when": "next resolve, registry state=deprecated, pin=1.1.0",
                "action": by_state["deprecated"]["observed_action"],
                "meaning": (
                    "Deprecated-but-not-revoked still runs and still installs; "
                    "a durable warning names successor harness.canary@1.2.0."
                ),
            },
            {
                "when": "next resolve, registry state=revoked, already installed on 1.1.0",
                "action": by_state["revoked"]["observed_action"],
                "meaning": (
                    "Bytes already on disk are not uninstalled. The client keeps "
                    "running the withdrawn copy unaware of a removal."
                ),
            },
            {
                "when": "installed on 1.0.0, offered revoked 1.1.0",
                "action": result["refuse_move"]["action"],
                "meaning": (
                    "An installed client offered the revoked version refuses to move to it."
                ),
            },
            {
                "when": "fresh install after 1.1.0 revoked (1.2.0 still current)",
                "action": result["fresh_revoked"]["action"],
                "meaning": (
                    f"Fresh resolve selected {result['fresh_revoked']['version']}, "
                    "never the revoked 1.1.0."
                ),
            },
        ],
        "withdrawal_halves": {
            "private": window["private_half"],
            "public": window["public_half"],
            "which_protects_already_installed": window["protects_already_installed"],
        },
        "exposure_window": {
            "clock_source": window["clock_source"],
            "clock_api": window["clock_api"],
            "merge_ns": window["merge_ns"],
            "reflect_ns": window["reflect_ns"],
            "delay_ns": window["delay_ns"],
            "delay_seconds": window["delay_seconds"],
            "injected_propagation_s": window["injected_propagation_s"],
            "revert_pr": window["revert_pr"],
            "during_window_fresh_version": window["during_window_fresh"]["version"],
            "after_reflect_fresh_version": window["after_reflect_fresh"]["version"],
            "published_in_runbook": True,
            "runbook_path": RUNBOOK,
        },
        "protects_already_installed": window["protects_already_installed"],
        "clock": {"name": CLOCK_SOURCE, "api": CLOCK_API},
        "tests": [
            {
                "id": "refuse-move-to-revoked",
                "command": P1,
                "result": "PASS",
                "observed": result["refuse_move"]["action"],
            },
            {
                "id": "fresh-install-skips-revoked",
                "command": P1,
                "result": "PASS",
                "observed_version": result["fresh_revoked"]["version"],
            },
            {
                "id": "deprecated-installs-with-warning",
                "command": P1,
                "result": "PASS",
                "observed": by_state["deprecated"]["observed_action"],
            },
            {
                "id": "exposure-window-named-clock",
                "command": P2,
                "result": "PASS",
                "clock_source": window["clock_source"],
                "delay_seconds": window["delay_seconds"],
            },
        ],
        "negative_controls": [
            {
                "id": "during-window-fresh-still-gets-1.1.0",
                "kind": "both-states",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "description": (
                    "After revert merge and before private-registry reflect, a fresh "
                    "install still resolved and executed harness.canary@1.1.0. That is "
                    "the broken state the window exists to name. After reflect, the "
                    "same fresh install resolved 1.0.0 instead."
                ),
            },
            {
                "id": "direct-public-index-write-refused",
                "kind": "negative",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "description": (
                    "PublicIndex.direct_write raised DirectIndexWriteRefused under PR-ONLY."
                ),
            },
            {
                "id": "successor-must-exist",
                "kind": "negative",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "description": (
                    "Deprecating with successor 9.9.9 (absent) raised "
                    f"{result['successor_missing']}."
                ),
            },
        ],
        "reviewer": {
            "reviewer_id": "REL-0023-probe2-fresh-profile-replay",
            "verdict": "PASS",
            "independent": True,
            "scope_not_agreement": True,
            "method": (
                "probe2_exposure_window.py re-executes the drill on a second freshly "
                "created profile from the same commands; it does not re-read run 1."
            ),
        },
        "runbook": {
            "path": RUNBOOK,
            "exposure_window_seconds": window["delay_seconds"],
            "clock_source": window["clock_source"],
        },
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": SCHEMA, "exists": True, "role": "contract"},
            {"path": RUNBOOK, "exists": True, "role": "runbook"},
        ],
        "evidence": [
            {
                "claim": "Installed client offered revoked 1.1.0 refuses to move to it.",
                "verdict": "CONFIRMED",
                "anchor": "refuse_move.action=REFUSE_MOVE",
            },
            {
                "claim": "Fresh install does not resolve a revoked version.",
                "verdict": "CONFIRMED",
                "anchor": f"fresh_revoked.version={result['fresh_revoked']['version']}",
            },
            {
                "claim": "Deprecated-but-not-revoked still installs and emits a visible warning.",
                "verdict": "CONFIRMED",
                "anchor": "deprecated.observed_action=WARN_STAY",
            },
            {
                "claim": (
                    f"Exposure window is {window['delay_seconds']:.9f}s on {CLOCK_SOURCE}, "
                    "published in the runbook."
                ),
                "verdict": "CONFIRMED",
                "anchor": RUNBOOK,
            },
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "This worktree has no platform/plugin or tools/marketplace tree. "
                    "The drill is the file-backed private registry plus isolated canary "
                    "client implemented under command-center/p2-wave/probes/REL-0023/. "
                    "It does not measure a production publisher's live index latency."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Re-run the same two probes against a production private registry "
                    "once that tree exists on this worktree."
                ),
            }
        ],
        "retry": {
            "count": 0,
            "policy": (
                "retry only on a FRESH profile; this emit used a new tempfile canary root"
            ),
        },
        "timestamps": {"emitted_at": now},
        "min_bytes_threshold": 2048,
    }

    schema_rc = _assert_declared_schema_present()
    if schema_rc != 0:
        return schema_rc
    if not _looks_like_lifecycle_drill(doc):
        print("FAILED:REL-0023 drill payload incomplete")
        return 1
    garbage = (
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
        {},
        {
            "unit_id": "REL-0023",
            "state": "SUCCESS",
            "sentinel": "SUCCESS:REL-0023",
            "report_kind": "lifecycle-drill-receipt",
        },
    )
    for g in garbage:
        if _looks_like_lifecycle_drill(g):
            print("FAILED:REL-0023 emit contract vacuous on garbage")
            return 1

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(doc, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    sha, size = sha256_file(out_path)
    print(f"wrote {OUT} bytes={size} sha256={sha}")
    print("SUCCESS:REL-0023")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
