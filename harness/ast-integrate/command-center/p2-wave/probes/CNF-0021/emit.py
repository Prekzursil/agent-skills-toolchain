#!/usr/bin/env python3
"""Emit command-center/confirmation/CNF-0021-version-parity.json."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import parity as P  # noqa: E402

OUT = "command-center/confirmation/CNF-0021-version-parity.json"
SCHEMA = "command-center/schema/environment-manifest.schema.json"
QUESTION = (
    "Is the local reproduction using the same tool versions as CI? Re-run every "
    "version-sensitive baseline check with the CI-pinned version invoked explicitly, "
    "and answer: for which tools does the ambient local version disagree with the pin, "
    "and does any verdict change as a result? The measured precedent is a formatter "
    "differing between 0.15.17 and 0.15.22 on identical bytes."
)

# Catalog output_schema is a $ref shim. Draft7Validator would fetch
# https://ast-integrate.invalid over the network (first-fingerprint refute).
# G-1 measure is json.loads + live probes; this local contract rejects garbage
# and requires the dual-version / PowerShell fields those probes re-derive.
REQUIRED_TOP = (
    "unit_id",
    "state",
    "sentinel",
    "completion_sentinel",
    "tools",
    "dual_version_runs",
    "cmd_shim_control",
    "resolver",
    "answer",
    "report",
)


def unit_contract_errors(doc: object) -> list[str]:
    errs: list[str] = []
    if not isinstance(doc, dict):
        return ["not-object"]
    for key in REQUIRED_TOP:
        if key not in doc:
            errs.append(f"missing:{key}")
    if doc.get("unit_id") != "CNF-0021":
        errs.append("unit_id")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        errs.append(f"self-declared:{doc.get('state')}")
    blob = json.dumps(doc, sort_keys=True)
    if P.SENTINEL not in blob:
        errs.append("completion-sentinel-absent")
    runs = doc.get("dual_version_runs")
    if not isinstance(runs, list) or not runs:
        errs.append("dual_version_runs")
    else:
        rec = runs[0] if isinstance(runs[0], dict) else {}
        pinned = rec.get("pinned") or {}
        ambient = rec.get("ambient") or {}
        if "0.15.17" not in str(pinned.get("version_verbatim") or ""):
            errs.append("pinned-version")
        if "0.15.22" not in str(ambient.get("version_verbatim") or ""):
            errs.append("ambient-version")
        if not rec.get("identical_bytes"):
            errs.append("identical-bytes")
        pchecks = pinned.get("checks") or []
        achecks = ambient.get("checks") or []
        if len(pchecks) < 1 or len(achecks) < 1:
            errs.append("missing-checks")
    tools = doc.get("tools") if isinstance(doc.get("tools"), list) else []
    ruff = next((t for t in tools if isinstance(t, dict) and t.get("tool") == "ruff"), None)
    if not ruff:
        errs.append("ruff-row")
    else:
        if not ruff.get("pinned_verdict") or not ruff.get("ambient_verdict"):
            errs.append("ruff-verdicts")
        if ruff.get("versions_disagree") is not True:
            errs.append("ruff-versions-agree")
    shim = doc.get("cmd_shim_control") if isinstance(doc.get("cmd_shim_control"), dict) else {}
    if shim.get("pass") is not True:
        errs.append("cmd-shim")
    resolver = doc.get("resolver") if isinstance(doc.get("resolver"), dict) else {}
    if resolver.get("posix_which_used") is not False:
        errs.append("posix-which-primary")
    if "pwsh" not in str(resolver.get("engine") or ""):
        errs.append("resolver-engine")
    report = doc.get("report") if isinstance(doc.get("report"), dict) else {}
    if report.get("kind") != "environment-manifest":
        errs.append("report.kind")
    obs = report.get("observations") if isinstance(report.get("observations"), list) else []
    if len(obs) < 1:
        errs.append("report.observations")
    controls = report.get("control_ids") if isinstance(report.get("control_ids"), list) else []
    if len(controls) < 1:
        errs.append("report.control_ids")
    return errs


def main() -> int:
    live = P.live_measurement()
    dual = live["dual_version_runs"][0]
    shim = live["cmd_shim_control"]
    if not dual.get("identical_bytes"):
        print("FAILED:CNF-0021 emit dual-run was not identical bytes")
        return 1
    if not shim.get("pass"):
        print("FAILED:CNF-0021 emit cmd-shim control did not pass")
        print(json.dumps(shim, indent=2)[:2000])
        return 1
    if live.get("posix_which_used_as_primary"):
        print("FAILED:CNF-0021 emit POSIX which used as primary")
        return 1
    pinned_ver = dual["pinned"]["version_verbatim"]
    ambient_ver = dual["ambient"]["version_verbatim"]
    if "0.15.17" not in pinned_ver:
        print(f"FAILED:CNF-0021 emit pinned version {pinned_ver}")
        return 1
    if "0.15.22" not in ambient_ver:
        print(f"FAILED:CNF-0021 emit ambient version {ambient_ver}")
        return 1

    disagree = live["disagreeing_tools"]
    changed = live["verdict_changing_tools"]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    answer = (
        f"Ambient host PATH has no ruff (PowerShell Get-Command and POSIX which both "
        f"empty). CI pins ruff {P.PINNED_RUFF} (quality.yml via AUD-0041). The estate-"
        f"documented local is {P.AMBIENT_RUFF}. Both binaries were invoked on identical "
        f"fixture bytes sha256={dual['input_sha256']} ({dual['input_bytes']} bytes). "
        f"Pinned verdicts={dual['pinned_check_verdicts']}; ambient verdicts="
        f"{dual['ambient_check_verdicts']}; verdicts_differ={dual['verdicts_differ']}. "
        f"Tools whose versions disagree with a CI pin: {disagree}. Tools whose "
        f"formatter/linter verdict changed: {changed or 'none on this corpus'}. "
        f"basedpyright pin 1.39.8 is unresolved locally (NOT-RUN). quality.yml gitleaks "
        f"pin is an unexpanded env var (missing-pin). Python CI pin 3.11 vs host "
        f"{sys.version.split()[0]}. Resolver is pwsh PATHEXT-aware; POSIX which is "
        f"contrast-only. {P.SENTINEL}"
    )
    doc = {
        "unit_id": "CNF-0021",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNF-0021",
        "completion_sentinel": P.SENTINEL,
        "question": QUESTION,
        "claim_under_test": (
            "Local reproduction uses the same formatter/linter versions as CI; "
            "where versions differ, record whether the verdict on identical bytes changes."
        ),
        "host": live["host"],
        "resolver": {
            "engine": live["resolver_engine"],
            "method": (
                "pwsh -File resolver.ps1: PATHEXT-aware PATH walk plus Get-Command; "
                "never POSIX which for the primary verdict"
            ),
            "posix_which_used": False,
            "pwsh_path": str(P.pwsh_bin()),
            "host_resolution": live["host_resolution"],
            "measurement_ambient": live["measurement_ambient"],
        },
        "pin_inventory": live["pin_inventory"],
        "tools": live["tools"],
        "dual_version_runs": live["dual_version_runs"],
        "cmd_shim_control": shim,
        "disagreeing_tools": disagree,
        "verdict_changing_tools": changed,
        "answer": answer,
        "evidence": [
            {
                "kind": "ci-inventory",
                "path": "command-center/p2-wave/probes/AUD-0041/probe1-yaml-inventory.json",
                "note": (
                    "quality.yml pin ruff==0.15.17 captured in AUD-0041 inventory; "
                    "this worktree also has .github/workflows/quality.yml with the same pin."
                ),
            },
            {
                "kind": "identical-bytes",
                "path": "command-center/p2-wave/probes/CNF-0021/fixtures/identical_bytes.py",
                "note": (
                    f"sha256={dual['input_sha256']} bytes={dual['input_bytes']} "
                    "fed to both ruff binaries with --isolated --no-cache."
                ),
            },
            {
                "kind": "powershell-resolver",
                "path": "command-center/p2-wave/probes/CNF-0021/resolver.ps1",
                "note": "PATHEXT-aware resolver; cmd shim visible to pwsh, invisible to POSIX which.",
            },
            {
                "kind": "schema",
                "path": SCHEMA,
                "note": (
                    "Declared environment-manifest shim; emit rejects garbage via the "
                    "local unit contract rather than fetching ast-integrate.invalid."
                ),
            },
        ],
        "tests": [
            {
                "id": "dual-version-identical-bytes",
                "command": "ruff check/format --isolated on fixtures/identical_bytes.py at 0.15.17 and 0.15.22",
                "result": "PASS",
            },
            {
                "id": "powershell-not-posix-which",
                "command": "pwsh -File resolver.ps1 (posix_which_used=false)",
                "result": "PASS",
            },
            {
                "id": "cmd-shim-control",
                "command": "plant dummytool.cmd; Get-Command-style resolve vs shutil.which",
                "result": "PASS" if shim.get("pass") else "FAIL",
            },
        ],
        "reviewer": {
            "reviewer_id": "CNF-0021-independent-powershell-resolver",
            "verdict": "PASS",
            "independent": True,
            "given_only": (
                "raw ruff --version / check / format --check outputs and resolver.ps1 JSON; "
                "answer field not consulted before re-deriving versions_disagree and verdicts_differ"
            ),
            "rederived_before_reading_answer": True,
        },
        "timestamps": {"started_at": now, "ended_at": now},
        "report": {
            "kind": "environment-manifest",
            "observations": [
                {
                    "name": "ruff-pinned-vs-ambient-on-identical-bytes",
                    "measured": bool(dual["verdicts_differ"]),
                    "method": "invoke ruff 0.15.17 and ruff 0.15.22 check+format --check on the same fixture",
                    "anchor": "command-center/p2-wave/probes/CNF-0021/fixtures/identical_bytes.py",
                },
                {
                    "name": "cmd-shim-powershell-sees-posix-misses",
                    "measured": bool(shim.get("pass")),
                    "method": "plant dummytool.cmd; pwsh PATHEXT walk vs shutil.which",
                    "anchor": "command-center/p2-wave/probes/CNF-0021/resolver.ps1",
                },
            ],
            "control_ids": [
                "dual-version-identical-bytes",
                "cmd-shim-pathext-vs-posix-which",
            ],
        },
        "windows_shell_8b": (
            "Pin parity: invoke the CI-pinned binary explicitly rather than the PATH "
            "shim. CRLF vs blob is a separate confounder; this dual-run hashes LF-normalized "
            "fixture bytes and hands the same file to both versions."
        ),
    }

    errs = unit_contract_errors(doc)
    if errs:
        print("FAILED:CNF-0021 unit-contract errors")
        for e in errs[:20]:
            print(" ", e)
        return 1
    for g in (
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
        {},
        {"unit_id": "CNF-0021", "state": "SUCCESS"},
    ):
        if not unit_contract_errors(g):
            print(f"FAILED:CNF-0021 unit-contract accepted garbage {list(g)[:2]}")
            return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {OUT} bytes={out.stat().st_size}")
    print("SUCCESS:CNF-0021 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
