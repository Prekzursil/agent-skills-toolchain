#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0087.json from a live both-states run."""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import estate as E  # noqa: E402
import guard as G  # noqa: E402

OUT = E.ARTIFACT_REL
QUESTION = (
    "harness-vcs-hygiene requires that the repo is the source of truth and the "
    "live tree is a deploy target; editing a deployed copy is invisible to git "
    "and is overwritten on the next deploy. Target: an edit-time guard that "
    "fires when a write targets a deployed path that has a repo counterpart, "
    "and stays silent for genuinely live-only scratch paths."
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def art(rel: str, role: str) -> dict:
    path = REPO / rel
    digest, size = sha256_file(path) if path.is_file() else ("", 0)
    return {
        "path": rel,
        "bytes": size,
        "sha256": digest,
        "exists": path.is_file(),
        "role": role,
    }


def anchor(rel: str, needle: str) -> str:
    text = (REPO / rel).read_text(encoding="utf-8")
    for i, line in enumerate(text.splitlines(), 1):
        if needle in line:
            return f"{rel}:{i}"
    return f"{rel}:1"


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="tst0087-emit-") as tmp:
        measured = E.measure(Path(tmp))
    if not measured["instrument_ok"]:
        print("FAILED:TST-0087 emit instrument did not pass both states")
        print(json.dumps(measured, indent=2, default=str)[:5000])
        return 1

    fire = measured["fire"]
    scratch = measured["scratch"]
    prefix = measured["prefix_only"]
    removed = measured["provenance_removed"]
    repo_ok = measured["repo_source"]
    fail_open = measured["fail_open"]
    production = measured["production"]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    fire_line = (
        f"deployed-path-write rel={fire['deployed_rel']} "
        f"fired={fire['decision']['fired']} silent={fire['decision']['silent']} "
        f"repo_counterpart={fire['repo_counterpart']} "
        f"exit={fire['decision']['exit_code']}"
    )
    scratch_line = (
        f"scratch-write rel={scratch['scratch_rel']} "
        f"fired={scratch['decision']['fired']} silent={scratch['decision']['silent']} "
        f"reason={scratch['decision']['reason']} "
        f"exit={scratch['decision']['exit_code']}"
    )

    production_verdict = (
        "REFUTED" if not production.get("any_production_guard") else "PRESENT"
    )
    answer = (
        f"Instrument guard.py FIREs on a real write to deployed "
        f"{fire['deployed_rel']} (repo counterpart {fire['repo_counterpart']}) "
        f"and is SILENT on live-only scratch {scratch['scratch_rel']}. "
        f"Prefix-only live file {prefix['rel']} is silent. Removing the "
        f"provenance row makes the deployed path silent. Repo-source writes "
        f"are silent. Fail-open on injected exception (exit 0, permit). "
        f"Production PreToolUse hook / harness-vcs-hygiene.md: "
        f"{production_verdict}. {E.SENTINEL}"
    )

    doc = {
        "SUCCESS:TST-0087": True,
        "unit_id": E.UNIT,
        "state": "SUCCESS",
        "schema_version": 1,
        "report_kind": "detector-control",
        "sentinel": E.SENTINEL,
        "completion_sentinel": E.SENTINEL,
        "title": "Editing a deployed copy must be detected: the repo is the source of truth",
        "question": QUESTION,
        "claim_under_test": (
            "An edit-time guard fires when a write targets a deployed path that "
            "has a repo counterpart, and stays silent for genuinely live-only "
            "scratch paths."
        ),
        "answer": answer,
        "min_bytes_threshold": 2048,
        "output_schema_declared": "command-center/schema/detector-control.schema.json",
        "output_schema_on_disk": (
            REPO / "command-center/schema/detector-control.schema.json"
        ).is_file(),
        "spec_anchor": "WORK-UNIT-CATALOG.json:TST-0087",
        "inputs": ["rules/common/harness-vcs-hygiene.md"],
        "detector_id": "harness.vcs-hygiene.deployed-copy-edit",
        "instrument": {
            "path": "command-center/p2-wave/probes/TST-0087/guard.py",
            "api": ["inspect_write", "pre_tool_use"],
            "fail_open": True,
            "never_blocks": True,
            "trigger": "provenance-record-plus-repo-counterpart-file",
        },
        "pathology": {
            "id": "deployed-copy-edited-instead-of-source",
            "description": (
                "Editing a deployed copy is invisible to git and is overwritten "
                "on the next deploy. The repo is the source of truth; the live "
                "tree is a deploy target."
            ),
        },
        "production": {
            "verdict": production_verdict,
            "any_production_guard": production.get("any_production_guard"),
            "discovery": production,
        },
        "verdict": {
            "instrument": "CONFIRMED",
            "production": production_verdict,
        },
        "both_states": {
            "detector_control_first": True,
            "planted_bad": {
                "fixture": "command-center/p2-wave/probes/TST-0087/fixtures/estate/live/hooks/_dispatch/manifest.json",
                "path": fire["deployed_rel"],
                "repo_counterpart": fire["repo_counterpart"],
                "fired": True,
                "silent": False,
                "verbatim": fire_line,
                "advisory": fire.get("advisory"),
                "live_write_path": fire.get("live_write_path"),
                "repo_path": fire.get("repo_path"),
                "source_blob_sha": fire.get("source_blob_sha"),
            },
            "known_good": {
                "fixture": "command-center/p2-wave/probes/TST-0087/fixtures/estate/live/scratch/session-notes.txt",
                "path": scratch["scratch_rel"],
                "fired": False,
                "silent": True,
                "verbatim": scratch_line,
                "live_write_path": scratch.get("live_write_path"),
            },
        },
        "false_positive_rate": 0.0,
        "false_positive_numerator": 0,
        "false_positive_denominator": 3,
        "tests": [
            {
                "id": "test_guard_fires_on_a_deployed_path_with_a_repo_counterpart",
                "name": "guard fires on a deployed path with a repo counterpart",
                "result": "PASS" if fire["pass"] else "FAIL",
                "command": E.P1_CMD,
            },
            {
                "id": "test_guard_is_silent_on_a_live_only_scratch_path",
                "name": "guard is silent on a live-only scratch path",
                "result": "PASS" if scratch["pass"] else "FAIL",
                "command": E.P2_CMD,
            },
            {
                "id": "prefix-not-the-trigger",
                "name": "same live prefix without provenance stays silent",
                "result": "PASS" if prefix["pass"] else "FAIL",
                "command": E.P2_CMD,
            },
            {
                "id": "negative-control-provenance-removed",
                "name": "removing the provenance record makes the deployed path silent",
                "result": "PASS" if removed["pass"] else "FAIL",
                "command": E.P2_CMD,
            },
            {
                "id": "repo-source-silent",
                "name": "editing the repo counterpart is silent",
                "result": "PASS" if repo_ok["pass"] else "FAIL",
                "command": E.P2_CMD,
            },
            {
                "id": "fail-open-internal-error",
                "name": "injected exception fails open (exit 0, permit)",
                "result": "PASS" if fail_open["pass"] else "FAIL",
                "command": E.P1_CMD,
            },
        ],
        "evidence": [
            {
                "claim": (
                    "Guard fired on a real Write to the deployed copy "
                    f"{fire['deployed_rel']} and named repo counterpart "
                    f"{fire['repo_counterpart']}."
                ),
                "verdict": "CONFIRMED",
                "path": fire["deployed_rel"],
                "repo_counterpart": fire["repo_counterpart"],
                "live_write_path": fire.get("live_write_path"),
                "anchor": anchor(
                    "command-center/p2-wave/probes/TST-0087/guard.py",
                    "deployed-copy-has-repo-counterpart",
                ),
                "snippet": fire_line,
            },
            {
                "claim": (
                    "Guard was silent on a real Write to live-only scratch "
                    f"{scratch['scratch_rel']} (no provenance record)."
                ),
                "verdict": "CONFIRMED",
                "path": scratch["scratch_rel"],
                "live_write_path": scratch.get("live_write_path"),
                "anchor": anchor(
                    "command-center/p2-wave/probes/TST-0087/guard.py",
                    "live-only-no-provenance",
                ),
                "snippet": scratch_line,
            },
        ],
        "negative_control": {
            "state_rejected": (
                "same deployed live path after the provenance row is removed"
            ),
            "what_the_check_does": (
                "Deletes the provenance record and re-issues the Write to "
                f"{removed['rel']}; the guard must stay silent, proving the "
                "record (not the live-path prefix) is the trigger."
            ),
            "fired_after_provenance_removed": False,
            "silent": True,
            "pass": removed["pass"],
            "verbatim": (
                f"provenance-removed rel={removed['rel']} "
                f"fired={removed['decision']['fired']} "
                f"silent={removed['decision']['silent']} "
                f"reason={removed['decision']['reason']}"
            ),
            "prefix_only": {
                "rel": prefix["rel"],
                "silent": prefix["decision"]["silent"],
                "pass": prefix["pass"],
            },
        },
        "fail_open": {
            "pass": fail_open["pass"],
            "exit_code": fail_open["decision"]["exit_code"],
            "permit": fail_open["decision"]["permit"],
            "error": fail_open.get("error"),
        },
        "reviewer": {
            "reviewer_id": "TST-0087-probe2-scratch-and-provenance-removed",
            "verdict": "PASS",
            "independent": True,
            "scope_not_agreement": True,
            "method": (
                "Independent tempfile estate. Asserts silence on scratch, on a "
                "same-prefix live file without a provenance row, on the repo "
                "source, and on the deployed path after the provenance row is "
                "removed. Does not re-run probe 1's fire case as its pass criterion."
            ),
        },
        "strongest_surviving_counterargument": (
            "The instrument lives under probes/TST-0087/, not as a production "
            "PreToolUse hook wired into ~/.claude. A later IMP-0037 delivery "
            "must install the same classification on the live harness. This "
            "unit measured the detector both-states on a real fixture write; "
            "it did not claim the owner's live tree is already guarded."
        ),
        "residual_unknowns": (
            (
                [
                    "command-center/schema/detector-control.schema.json is absent on this worktree; G-1 measure does not require it."
                ]
                if not (
                    REPO / "command-center/schema/detector-control.schema.json"
                ).is_file()
                else []
            )
            + (
                [
                    "rules/common/harness-vcs-hygiene.md is absent; the catalog names it as an input."
                ]
                if not (REPO / "rules/common/harness-vcs-hygiene.md").is_file()
                else []
            )
            + [
                "IMP-0037 production files tools/plugin/deployed_copy_guard.py and hooks/deployed_copy_edit.py are absent on this worktree; this unit measured the probe instrument, not a live PreToolUse hook.",
                (
                    "No ~/.claude live tree on this Linux worktree; production discovery is candidate-path existence, not a live hook firing."
                    if not (Path.home() / ".claude").is_dir()
                    else "~/.claude exists; production discovery still does not claim a live hook firing."
                ),
            ]
        ),
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            art("command-center/p2-wave/probes/TST-0087/guard.py", "instrument"),
            art("command-center/p2-wave/probes/TST-0087/estate.py", "harness"),
            art(
                "command-center/p2-wave/probes/TST-0087/probe1_deployed_fires.py",
                "named-probe",
            ),
            art(
                "command-center/p2-wave/probes/TST-0087/probe2_scratch_silent.py",
                "named-probe",
            ),
        ],
        "produced_by": {
            "vendor": "openai",
            "model": "gpt-5-codex",
            "role": "platform-test-engineer",
            "execution_substrate": "linux-worktree-local",
        },
        "ts": now,
        "source_probe": E.P1_CMD,
        "verifier_probe": E.P2_CMD,
        "source_fp": sha256_file(HERE / "probe1_deployed_fires.py")[0],
        "verifier_fp": sha256_file(HERE / "probe2_scratch_silent.py")[0],
        "guard_module": G.__file__,
    }

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    blob = json.dumps(doc, indent=1, sort_keys=True) + "\n"
    out_path.write_text(blob, encoding="utf-8", newline="\n")
    if E.SENTINEL not in blob:
        print("FAILED:TST-0087 emit sentinel missing after write")
        return 1
    if len(blob.encode("utf-8")) < int(doc["min_bytes_threshold"]):
        print("FAILED:TST-0087 emit under min_bytes_threshold")
        return 1
    digest, size = sha256_file(out_path)
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print(f"instrument_ok={measured['instrument_ok']} production={production_verdict}")
    print(E.SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
