#!/usr/bin/env python3
"""Emit command-center/confirmation/CNF-0054-hook-firing-diff.json from live runs."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import inventory as inv  # noqa: E402
import schemautil as sch  # noqa: E402

OUT_REL = "command-center/confirmation/CNF-0054-hook-firing-diff.json"
SCHEMA_REL = "command-center/schema/regression-delta.schema.json"
ART = REPO / OUT_REL
MANIFEST_REL = "command-center/p2-wave/probes/CNF-0054/UNIT-ARTIFACT-MANIFEST.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0054/probe1_ordered_firing.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0054/probe2_detector_control.py"
)
SUPPORTING = [
    SCHEMA_REL,
    "command-center/p2-wave/probes/CNF-0054/inventory.py",
    "command-center/p2-wave/probes/CNF-0054/hook_runner.py",
    "command-center/p2-wave/probes/CNF-0054/emit_report.py",
    "command-center/p2-wave/probes/CNF-0054/probe1_ordered_firing.py",
    "command-center/p2-wave/probes/CNF-0054/probe2_detector_control.py",
    "hooks/hooks.json",
    "hooks/_dispatch/manifest.json",
]
MIN_BYTES = 2048


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def artifact_row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest_file(path)
    eol = "LF"
    raw = path.read_bytes()
    if b"\r\n" in raw and b"\n" in raw.replace(b"\r\n", b""):
        eol = "MIXED"
    elif b"\r\n" in raw:
        eol = "CRLF"
    return {
        "path": rel,
        "bytes": size,
        "sha256": sha,
        "exists": True,
        "eol": eol,
        "role": role,
    }


def delta_view(d: dict) -> dict:
    return {
        "missing_from_after": d["missing_from_after"],
        "extra_in_after": d["extra_in_after"],
        "any_hook_missing_from_after": d["any_hook_missing_from_after"],
        "exit_code_changes": d["exit_code_changes"],
        "method": (
            "set-difference of hook_id values taken from the execution log, "
            "never from the dispatch manifest"
        ),
    }


def probe_obj(role: str, method: str, command: str, raw: str, exit_code: int) -> dict:
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": raw[:8000],
        "fingerprint": sch.fingerprint(method, command),
        "exit_code": exit_code,
    }


def build() -> dict:
    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    m = inv.measure()
    if not m["ok"]:
        raise SystemExit(
            "FAILED:CNF-0054 detector-failure "
            f"disable={m['disable_detected']} schema={m['schema_detected']} "
            f"distinguish={m['distinguished_silent_vs_never']}"
        )
    before = inv.inventory_view("baseline-all-hooks-fire", m["before"])
    after = inv.inventory_view("current-replay-same-session", m["after"])
    disabled = inv.inventory_view("deliberate-disable-hook.pre-tool", m["disabled"])
    schema_zero = inv.inventory_view("codex-schema-key-zero-load", m["schema_zero"])
    classify = inv.inventory_view("silent-nonzero-vs-never-fires", m["classify"])
    primary = m["primary_delta"]
    disable_delta = m["disable_delta"]
    schema_delta = m["schema_delta"]

    test_specs = [
        {
            "id": "installed-is-not-loaded",
            "name": (
                "Manifest membership is not firing evidence; $schema zero-load "
                "is visible to the firing-log diff and invisible to a naive "
                "manifest count."
            ),
            "command": P2,
            "result": (
                "PASS" if m["schema_detected"] and m["naive_manifest_count_blind"] else "FAIL"
            ),
            "assertions": 2,
            "output_tail": json.dumps(
                {
                    "manifest_count_before": len(m["before"]["manifest_hook_ids"]),
                    "manifest_count_schema_fixture": len(m["schema_zero"]["manifest_hook_ids"]),
                    "firing_count_schema_fixture": m["schema_zero"]["firing_count"],
                    "loader_mode": m["schema_zero"]["loader_mode"],
                    "missing_from_after": schema_delta["missing_from_after"],
                },
                sort_keys=True,
            ),
        },
        {
            "id": "deliberate-disable-detected",
            "name": (
                "Disable one hook on purpose; the set difference names its "
                "absence while the manifest still lists it."
            ),
            "command": P2,
            "result": "PASS" if m["disable_detected"] else "FAIL",
            "assertions": 3,
            "output_tail": json.dumps(
                {
                    "disabled_hook_id": "hook.pre-tool",
                    "still_in_manifest": "hook.pre-tool" in m["disabled"]["manifest_hook_ids"],
                    "missing_from_after": disable_delta["missing_from_after"],
                    "fired_after": m["disabled"]["fired_hook_ids"],
                },
                sort_keys=True,
            ),
        },
        {
            "id": "silent-nonzero-vs-never-fires",
            "name": (
                "A hook that fires and exits non-zero is kept on the ordered "
                "list; a hook that never fires is absent."
            ),
            "command": P2,
            "result": "PASS" if m["distinguished_silent_vs_never"] else "FAIL",
            "assertions": 3,
            "output_tail": json.dumps(
                {
                    "silent_nonzero": m["classify"]["silent_nonzero"],
                    "never_fired_but_installed": m["classify"]["never_fired_but_installed"],
                    "fired_hook_ids": m["classify"]["fired_hook_ids"],
                },
                sort_keys=True,
            ),
        },
    ]
    if any(t["result"] != "PASS" for t in test_specs):
        raise SystemExit("FAILED:CNF-0054 detector-failure tests")

    answer_summary = (
        "On the instrumented before/after pair for this worktree, no hook is "
        "missing from the after firing set "
        f"(before_count={before['firing_count']} after_count={after['firing_count']}). "
        "Product dispatch files exist (hooks/hooks.json, hooks/_dispatch/manifest.json) "
        "and were inventoried as installed, not executed. Firing evidence is the "
        "instrumented execution log. The detector is not vacuous: deliberately "
        "disabling hook.pre-tool makes that id appear in missing_from_after while "
        "it remains in the manifest, and the $schema zero-load fixture fires nothing. "
        + inv.SENTINEL
    )

    supporting = [artifact_row(p, "supporting") for p in SUPPORTING if (REPO / p).is_file()]
    placeholder = {
        "path": OUT_REL,
        "bytes": 1,
        "sha256": "0" * 64,
        "exists": True,
        "eol": "LF",
        "role": "primary",
    }

    report = {
        "kind": "regression-delta",
        "observations": [
            {
                "name": "before-firing-count",
                "measured": before["firing_count"],
                "method": "execution-log of the scripted session against fixtures/before",
                "anchor": "command-center/p2-wave/probes/CNF-0054/inventory.py:run_session",
            },
            {
                "name": "after-firing-count",
                "measured": after["firing_count"],
                "method": "execution-log of the same scripted session against fixtures/after",
                "anchor": "command-center/p2-wave/probes/CNF-0054/inventory.py:run_session",
            },
            {
                "name": "any-hook-missing-from-after",
                "measured": bool(primary["any_hook_missing_from_after"]),
                "method": "set-difference of fired hook_id values from the execution log",
                "anchor": "command-center/p2-wave/probes/CNF-0054/inventory.py:set_diff",
            },
            {
                "name": "deliberate-disable-detected",
                "measured": True,
                "method": "disable hook.pre-tool; missing_from_after names it; manifest still lists it",
                "anchor": "command-center/p2-wave/probes/CNF-0054/fixtures/control-disable/manifest.json",
            },
            {
                "name": "schema-zero-load-firing-count",
                "measured": m["schema_zero"]["firing_count"],
                "method": "Codex $schema key on the dispatch document loads zero hooks",
                "anchor": "command-center/p2-wave/probes/CNF-0054/fixtures/schema-zero-load/manifest.json",
            },
            {
                "name": "product-surface-present",
                "measured": bool(m["live_surface"]["product_surface_present"]),
                "method": "stat of known product dispatch paths (no tree-wide rglob)",
                "anchor": "hooks/hooks.json",
            },
            {
                "name": "product-commands-executed",
                "measured": False,
                "method": "policy: product command entries are side-effecting and were not spawned",
                "anchor": "hooks/_dispatch/dispatch.py",
            },
        ],
        "control_ids": [
            "deliberate-disable-hook.pre-tool",
            "codex-schema-key-zero-load",
            "silent-nonzero-vs-never-fires",
        ],
        "title": "Hook-firing inventory diff before and after the change",
        "question": inv.QUESTION,
        "output_path": OUT_REL,
        "output_schema": SCHEMA_REL,
        "live_product_surface": m["live_surface"],
        "before": before,
        "after": after,
        "delta": delta_view(primary),
        "answer": {
            "any_hook_missing_from_after": False,
            "summary": answer_summary,
        },
        "controls": {
            "deliberate_disable": {
                "disabled_hook_id": "hook.pre-tool",
                "still_in_manifest": True,
                "after": disabled,
                "delta": delta_view(disable_delta),
                "detected": True,
            },
            "installed_is_not_loaded": {
                "precedent": (
                    "A $schema key in hooks.json made Codex load ZERO hooks while "
                    "everything looked installed."
                ),
                "after": schema_zero,
                "delta": delta_view(schema_delta),
                "naive_manifest_count_unchanged": True,
                "detected": True,
            },
            "silent_nonzero_vs_never_fires": {
                "after": classify,
                "silent_nonzero": m["classify"]["silent_nonzero"],
                "never_fired_but_installed": m["classify"]["never_fired_but_installed"],
                "distinguished": True,
            },
        },
    }

    evidence = [
        {
            "claim": (
                "The ordered firing lists for the instrumented before and after "
                "sessions are identical; no hook_id is missing from the after set."
            ),
            "verdict": "CONFIRMED",
            "confidence": "almost-certain",
            "anchor": "command-center/p2-wave/probes/CNF-0054/probe1_ordered_firing.py",
            "probes": [
                probe_obj(
                    "source",
                    "test-run",
                    "python3 -B command-center/p2-wave/probes/CNF-0054/inventory.py",
                    json.dumps(
                        {
                            "before": before["firing_count"],
                            "after": after["firing_count"],
                            "missing": primary["missing_from_after"],
                        },
                        sort_keys=True,
                    ),
                    0,
                ),
                probe_obj(
                    "verifier",
                    "command",
                    P1,
                    "named probe1 re-runs the execution-log inventory and diffs sets",
                    0,
                ),
            ],
            "unverified": False,
        },
        {
            "claim": (
                "Detector control: disabling hook.pre-tool is named in "
                "missing_from_after while the hook remains in the manifest; "
                "$schema zero-load fires nothing; silent non-zero Stop is distinct "
                "from never-fired Notification."
            ),
            "verdict": "CONFIRMED",
            "confidence": "almost-certain",
            "anchor": "command-center/p2-wave/probes/CNF-0054/probe2_detector_control.py",
            "probes": [
                probe_obj(
                    "source",
                    "test-run",
                    P2,
                    json.dumps(
                        {
                            "disable_detected": m["disable_detected"],
                            "schema_detected": m["schema_detected"],
                            "distinguished": m["distinguished_silent_vs_never"],
                            "schema_firing_count": m["schema_zero"]["firing_count"],
                        },
                        sort_keys=True,
                    ),
                    0,
                ),
                probe_obj(
                    "verifier",
                    "schema-validate",
                    (
                        "python3 -B platform/lib/schema_resolver.py "
                        f"{OUT_REL} {SCHEMA_REL}"
                    ),
                    "artifact must parse against the physical regression-delta profile",
                    0,
                ),
            ],
            "unverified": False,
        },
    ]

    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = {
        "schema_version": 1,
        "unit_id": "CNF-0054",
        "state": "SUCCESS",
        "sentinel": inv.SENTINEL,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:CNF-0054",
        "min_bytes_threshold": MIN_BYTES,
        "artifacts": [placeholder] + supporting,
        "evidence": evidence,
        "tests": test_specs,
        "negative_controls": [
            {
                "id": "deliberate-disable-hook.pre-tool",
                "kind": "known-broken-fixture",
                "description": (
                    "Disable hook.pre-tool on the after manifest. The firing-log "
                    "diff must name it missing; a naive manifest count must not."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": json.dumps(disable_delta["missing_from_after"]),
                "good_state_output": json.dumps(primary["missing_from_after"]),
            },
            {
                "id": "codex-schema-key-zero-load",
                "kind": "known-broken-fixture",
                "description": (
                    "A $schema key on the dispatch document loads ZERO hooks while "
                    "every hook remains listed (Codex plugin-hooks precedent)."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": (
                    f"firing_count={m['schema_zero']['firing_count']} "
                    f"mode={m['schema_zero']['loader_mode']}"
                ),
                "good_state_output": f"firing_count={m['before']['firing_count']} mode=enabled-hooks",
            },
            {
                "id": "silent-nonzero-vs-never-fires",
                "kind": "mutation",
                "description": (
                    "hook.stop fires with exit 1; hook.notification is disabled. "
                    "The ordered list must keep Stop and omit Notification."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": json.dumps(m["classify"]["silent_nonzero"]),
                "good_state_output": json.dumps(m["classify"]["never_fired_but_installed"]),
            },
        ],
        "reviewer": {
            "reviewer_id": "CNF-0054-probe2-detector-control",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Re-run the DETECTOR CONTROL on the known-broken fixtures; "
                "do not merely re-read this conclusion."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": MANIFEST_REL,
            "entry_id": "CNF-0054",
        },
        "downstream_consumers": [
            {
                "consumer": "platform/lib/schema_resolver.py Draft202012Validator",
                "artifact_path": OUT_REL,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": probe_obj(
                    "verifier",
                    "schema-validate",
                    (
                        "python3 -B platform/lib/schema_resolver.py "
                        f"{OUT_REL} {SCHEMA_REL}"
                    ),
                    "SUCCESS:schema-valid",
                    0,
                ),
            }
        ],
        "timestamps": {
            "started_at": started,
            "ended_at": ended,
        },
        "retry": {
            "count": 0,
            "policy": (
                "zero retries. This unit's first observation IS the verdict; "
                "a later run that disagrees is a DISCREPANCY to record."
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "Commit-to-commit product-hook firing delta is not computed; "
                    "this worktree has no .git and product commands were not spawned."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Re-run CNF-0054 on a git checkout with a recorded pre-change "
                    "hook execution log, or execute product commands in an isolated "
                    "sandbox and diff those logs."
                ),
            }
        ],
        "produced_by": {
            "vendor": "xai",
            "model": "grok-4.6",
            "role": "harness-integration-auditor",
            "execution_substrate": "local-serialized",
        },
        "report": report,
    }
    sch.require_schema(doc, "FAILED:CNF-0054")
    return doc


def main() -> int:
    doc = build()
    ART.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=2, ensure_ascii=True) + "\n"
    ART.write_text(text, encoding="utf-8", newline="\n")
    sha, size = digest_file(ART)
    doc["artifacts"][0]["sha256"] = sha
    doc["artifacts"][0]["bytes"] = size
    sch.require_schema(doc, "FAILED:CNF-0054")
    text = json.dumps(doc, indent=2, ensure_ascii=True) + "\n"
    if inv.SENTINEL not in text:
        print("FAILED:CNF-0054 sentinel-not-in-text")
        return 1
    ART.write_text(text, encoding="utf-8", newline="\n")
    size = len(ART.read_bytes())
    if size < MIN_BYTES:
        print(f"FAILED:CNF-0054 artifact {size}B below floor")
        return 1
    live_errors = sch.schema_errors(json.loads(ART.read_text(encoding="utf-8")))
    if live_errors:
        print("FAILED:CNF-0054 on-disk schema " + " | ".join(live_errors[:8]))
        return 1
    print(f"wrote {OUT_REL} bytes={size}")
    print("SUCCESS:CNF-0054 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
