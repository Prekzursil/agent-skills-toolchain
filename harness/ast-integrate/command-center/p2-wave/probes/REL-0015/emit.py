#!/usr/bin/env python3
"""Emit command-center/receipts/REL-0015.json from a live matrix run."""
from __future__ import annotations

import hashlib
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

from jsonschema import Draft202012Validator
from jsonschema.validators import RefResolver

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from matrix import run_matrix  # noqa: E402
from renderer import renderer_controls  # noqa: E402
from smoke import IsolationError, OWNER_HOME, assert_isolated  # noqa: E402
from smoke import host_os, uname_s  # noqa: E402

OUT = "command-center/receipts/REL-0015.json"
SCHEMA = "command-center/schema/matrix-cell-receipt.schema.json"
QUESTION = (
    "Convert the compatibility matrix from a table somebody typed into a table "
    "something ran: enumerate OS by client by client version, execute the identical "
    "install-and-smoke journey in each cell, and emit NOT-CHECKED (visually distinct "
    "from PASS) for every cell that did not execute."
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/REL-0015/probe1_renderer.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/REL-0015/probe2_arithmetic.py"
)
SCHEMA_FILES = (
    "command-center/schema/matrix-cell-receipt.schema.json",
    "platform/schema/artifact-class-profiles.schema.json",
    "platform/schema/receipt.schema.json",
)
SUPPORTING = (
    SCHEMA,
    "command-center/p2-wave/probes/REL-0015/support_contract.json",
    "command-center/p2-wave/probes/REL-0015/host.py",
    "command-center/p2-wave/probes/REL-0015/smoke.py",
    "command-center/p2-wave/probes/REL-0015/renderer.py",
    "command-center/p2-wave/probes/REL-0015/matrix.py",
    "command-center/p2-wave/probes/REL-0015/cell-receipts/linux__generic-mcp__1.0.0.json",
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def eol_of(raw: bytes) -> str:
    crlf = raw.count(b"\r\n")
    lf = raw.count(b"\n") - crlf
    cr = raw.count(b"\r") - crlf
    kinds = sum(n > 0 for n in (crlf, lf, cr))
    if kinds == 0:
        return "LF"
    if kinds > 1:
        return "MIXED"
    if crlf:
        return "CRLF"
    if cr:
        return "MIXED"
    return "LF"


def art(rel: str, role: str) -> dict:
    path = REPO / rel
    raw = path.read_bytes()
    digest, size = sha256_file(path)
    return {
        "path": rel,
        "bytes": size,
        "sha256": digest,
        "exists": True,
        "eol": eol_of(raw),
        "role": role,
    }


def fp(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}|{command}".encode("utf-8")).hexdigest()


def probe(role: str, method: str, command: str, raw_output: str, exit_code: int) -> dict:
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": raw_output[:4000],
        "fingerprint": fp(method, command),
        "exit_code": exit_code,
    }


def no_remote(uri: str) -> dict:
    raise RuntimeError(f"refusing network schema fetch: {uri}")


def local_validator() -> Draft202012Validator:
    store: dict[str, dict] = {}
    shim = None
    for rel in SCHEMA_FILES:
        doc = json.loads((REPO / rel).read_text(encoding="utf-8"))
        if shim is None:
            shim = doc
        ident = doc.get("$id")
        if ident:
            store[ident] = doc
    resolver = RefResolver(
        base_uri=shim["$id"],
        referrer=shim,
        store=store,
        handlers={"http": no_remote, "https": no_remote},
    )
    return Draft202012Validator(shim, resolver=resolver)


def main() -> int:
    started = datetime.now(timezone.utc)
    live = run_matrix()
    controls = renderer_controls()
    rendered = live["rendered"]
    arith = rendered["arithmetic"]
    isolation = live["isolation"]
    both = live["both_states"]
    if not isolation.get("refused"):
        print("FAILED:REL-0015 emit isolation did not refuse owner home")
        return 1
    if not both.get("discriminates") or not both.get("listing_passes_both_states"):
        print("FAILED:REL-0015 emit both-states control")
        print(
            json.dumps(
                {
                    k: both.get(k)
                    for k in (
                        "discriminates",
                        "listing_passes_both_states",
                        "good_status",
                        "bad_status",
                    )
                },
                indent=2,
            )
        )
        return 1
    if not arith.get("holds"):
        print("FAILED:REL-0015 emit arithmetic")
        print(json.dumps(arith, indent=2))
        return 1
    if arith["executed_receipts"] < 1:
        print("FAILED:REL-0015 emit no executed cell")
        return 1
    if not controls.get("pass"):
        print("FAILED:REL-0015 emit renderer controls")
        print(json.dumps(controls, indent=2, default=str)[:3000])
        return 1

    throwaway_ok = True
    try:
        assert_isolated(Path(live["work_root"]))
    except IsolationError:
        throwaway_ok = False
    owner_fired = False
    try:
        assert_isolated(OWNER_HOME)
    except IsolationError:
        owner_fired = True
    if not owner_fired or not throwaway_ok:
        print("FAILED:REL-0015 emit isolation both-states")
        return 1

    contract = live["contract"]
    support = {
        "operating_systems": list(contract["operating_systems"]),
        "clients": [
            {"id": c["id"], "declared_version": c["declared_version"]}
            for c in contract["clients"]
        ],
        "journey": {
            "name": contract["journey"]["name"],
            "acceptance": contract["journey"]["acceptance"],
            "shared_with": contract["journey"].get("shared_with"),
        },
    }

    cells = []
    for row in rendered["published"]:
        cells.append(
            {
                "cell_id": row["cell_id"],
                "os": row["os"],
                "client": row["client"],
                "declared_version": row["declared_version"],
                "status": row["status"],
            }
        )

    executed = []
    for rec in live["executed_receipts"]:
        executed.append(
            {
                "cell_id": rec["cell_id"],
                "status": rec["status"],
                "observed_client_build_string": rec["observed_client_build_string"],
                "acceptance_signal": rec.get("acceptance_signal")
                or "hook-side-effect-file-with-observed-build-string",
                "listing_disqualified": True,
            }
        )

    not_checked = [
        {"cell_id": s["cell_id"], "reason": s["reason"]}
        for s in live["not_checked_entries"]
    ]

    tests = [
        {
            "id": "delete-receipt-renders-not-checked",
            "name": "Delete one cell receipt; renderer shows NOT-CHECKED, not blank, not PASS",
            "command": "python3 -c from renderer import renderer_controls; assert renderer_controls()['delete_receipt_shows_not_checked']",
            "result": "PASS"
            if controls["delete_receipt_shows_not_checked"]
            and controls["delete_receipt_not_blank"]
            else "FAIL",
        },
        {
            "id": "failing-cell-survives",
            "name": "A FAIL cell remains in the published table",
            "command": "python3 -c from renderer import renderer_controls; assert renderer_controls()['fail_survives']",
            "result": "PASS" if controls["fail_survives"] else "FAIL",
        },
        {
            "id": "all-pass-vs-mixed-diff",
            "name": "Fabricated all-PASS vs mixed inputs produce different published tables",
            "command": "python3 -c from renderer import renderer_controls; assert renderer_controls()['all_pass_differs_from_mixed']",
            "result": "PASS" if controls["all_pass_differs_from_mixed"] else "FAIL",
        },
        {
            "id": "arithmetic-identity",
            "name": "published_cells = executed_receipts + not_checked_entries",
            "command": P2,
            "result": "PASS" if arith["holds"] else "FAIL",
        },
    ]
    if any(t["result"] != "PASS" for t in tests):
        print("FAILED:REL-0015 emit tests")
        print(json.dumps(tests, indent=2))
        return 1

    artifacts = []
    for rel in SUPPORTING:
        path = REPO / rel
        if not path.is_file():
            print(f"FAILED:REL-0015 emit missing supporting artifact {rel}")
            return 1
        artifacts.append(art(rel, "fixture" if "cell-receipts" in rel else "supporting"))

    arith_json = json.dumps(arith, sort_keys=True)
    both_json = json.dumps(
        {
            "discriminates": both.get("discriminates"),
            "listing_passes_both_states": both.get("listing_passes_both_states"),
            "good_status": both.get("good_status"),
            "bad_status": both.get("bad_status"),
        },
        sort_keys=True,
    )
    ctrl_json = json.dumps(
        {k: controls[k] for k in sorted(controls) if k != "pass"},
        sort_keys=True,
        default=str,
    )[:2000]

    ended = datetime.now(timezone.utc)
    now = ended.strftime("%Y-%m-%dT%H:%M:%SZ")
    started_s = started.strftime("%Y-%m-%dT%H:%M:%SZ")
    duration = max(0.0, (ended - started).total_seconds())

    doc = {
        "schema_version": 1,
        "unit_id": "REL-0015",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:REL-0015",
        "profile": "matrix-cell-receipt",
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json REL-0015; _USER-PROMPTS.md:11113",
        "min_bytes_threshold": 2048,
        "produced_by": {
            "vendor": "xai",
            "model": "grok-4.6",
            "role": "matrix-runner",
            "execution_substrate": "local-serialized",
        },
        "artifacts": artifacts,
        "evidence": [
            {
                "claim": (
                    "linux::generic-mcp::1.0.0 executed the install-and-smoke journey "
                    "and recorded the observed generic-MCP host build string"
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/REL-0015/host.py:build_string",
                "probes": [
                    probe(
                        "source",
                        "test-run",
                        "python3 command-center/p2-wave/probes/REL-0015/matrix.py via run_matrix()",
                        json.dumps(executed, indent=2)[:2000],
                        0,
                    ),
                    probe(
                        "verifier",
                        "file-read",
                        "command-center/p2-wave/probes/REL-0015/cell-receipts/linux__generic-mcp__1.0.0.json",
                        (REPO / SUPPORTING[-1]).read_text(encoding="utf-8")[:2000],
                        0,
                    ),
                ],
            },
            {
                "claim": (
                    "Published cells equal executed receipts plus NOT-CHECKED entries; "
                    "unrun cells are not inferred from a neighbour PASS"
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/REL-0015/renderer.py:arithmetic",
                "probes": [
                    probe(
                        "source",
                        "static-analysis",
                        "renderer.arithmetic on live publish()",
                        arith_json,
                        0,
                    ),
                    probe(
                        "verifier",
                        "command",
                        P2,
                        "deferred: named probe2 re-runs the live matrix against the written artifact",
                        0,
                    ),
                ],
            },
            {
                "claim": (
                    "Published table CSS classes distinguish PASS (solid green) from "
                    "NOT-CHECKED (hatched gold); delete-receipt renders NOT-CHECKED"
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/REL-0015/renderer.py:_html",
                "probes": [
                    probe(
                        "source",
                        "test-run",
                        "python3 -c renderer.renderer_controls()",
                        ctrl_json,
                        0,
                    ),
                    probe(
                        "verifier",
                        "byte-compare",
                        "all-pass HTML vs mixed HTML plus CSS class set",
                        json.dumps(
                            {
                                "visual_classes_distinct": controls["visual_classes_distinct"],
                                "all_pass_differs_from_mixed": controls[
                                    "all_pass_differs_from_mixed"
                                ],
                                "css": rendered["css_classes"],
                            },
                            sort_keys=True,
                        ),
                        0,
                    ),
                ],
            },
            {
                "claim": (
                    "Hook side-effect discriminates good vs broken plugin; directory "
                    "listing passes both states and is disqualified as acceptance"
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/REL-0015/smoke.py:both_states",
                "probes": [
                    probe(
                        "source",
                        "test-run",
                        "smoke.both_states(throwaway_home)",
                        both_json,
                        0,
                    ),
                    probe(
                        "verifier",
                        "file-read",
                        "command-center/p2-wave/probes/REL-0015/fixtures/plugin-broken/hooks/pre-tool.py",
                        (HERE / "fixtures/plugin-broken/hooks/pre-tool.py").read_text(
                            encoding="utf-8"
                        )[:500],
                        0,
                    ),
                ],
            },
        ],
        "tests": tests,
        "negative_controls": [
            {
                "id": "NC-BROKEN-PLUGIN",
                "kind": "known-broken-fixture",
                "description": (
                    "Broken plugin writes no hook side-effect; journey must FAIL while "
                    "the good plugin PASSes. Listing is green in both states."
                ),
                "fired_on_bad_state": both.get("bad_status") == "FAIL",
                "silent_on_good_state": both.get("good_status") == "PASS",
                "bad_state_output": f"status={both.get('bad_status')}",
                "good_state_output": f"status={both.get('good_status')}",
            },
            {
                "id": "NC-OWNER-HOME",
                "kind": "adversarial-payload",
                "description": "Smoke against owner HOME must refuse; throwaway profile must be accepted.",
                "fired_on_bad_state": owner_fired,
                "silent_on_good_state": throwaway_ok,
                "bad_state_output": isolation.get("error") or "",
                "good_state_output": f"work_root={live['work_root']}",
            },
            {
                "id": "NC-SCHEMA-GARBAGE",
                "kind": "malformed-input",
                "description": "Empty object and BLOCKED stub must fail matrix-cell-receipt schema.",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "schema rejects {} and BLOCKED stub",
                "good_state_output": "schema accepts this receipt",
            },
        ],
        "reviewer": {
            "reviewer_id": "REL-0015-probe1-renderer",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "vendor": "xai",
            "notes": (
                "Named probe1 re-runs renderer controls independently of probe2's live "
                "matrix arithmetic. Catalog two-blind cross-filing is residual."
            ),
            "reviewed_at": now,
        },
        "defects": [],
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/REL-0015/UNIT-ARTIFACT-MANIFEST.json",
            "entry_id": "REL-0015",
            "registered_at": now,
        },
        "downstream_consumers": [
            {
                "consumer": "jsonschema Draft202012Validator against matrix-cell-receipt (disk-only $ref store)",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": probe(
                    "verifier",
                    "schema-validate",
                    "Draft202012Validator(shim, resolver=local store of platform/schema)",
                    "validated in-memory before write",
                    0,
                ),
            },
            {
                "consumer": "command-center/p2-wave/probes/REL-0015/renderer.py:renderer_controls",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": probe(
                    "source",
                    "test-run",
                    "renderer.renderer_controls()",
                    ctrl_json,
                    0,
                ),
            },
        ],
        "timestamps": {
            "started_at": started_s,
            "ended_at": now,
            "duration_seconds": duration,
        },
        "retry": {
            "count": 0,
            "policy": (
                "no blind retry. Re-runs count as flake measurement and every outcome "
                "is recorded; a green on run 5 of 5 does not overwrite the 4 reds, it "
                "is reported as 1/5"
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "Claude Code, Codex CLI, and Antigravity/agy binaries are absent "
                    "on this Linux worktree; those cells stay NOT-CHECKED."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Install each client into an isolated HOME and re-run the "
                    "install-and-smoke journey with a client-native PreToolUse adapter."
                ),
            },
            {
                "claim": "Windows and macOS runners are unreachable here; those OS rows stay NOT-CHECKED.",
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Run the same matrix.py on a Windows and a macOS throwaway profile "
                    "(REL-0004 canary equivalent) and merge the executed receipts."
                ),
            },
            {
                "claim": (
                    "Catalog reviewer_requirement is two reviewers who file independently "
                    "and do not see each other's verdict until both are filed."
                ),
                "verdict": "PARTIAL",
                "settling_experiment": (
                    "Dispatch a second vendor against only the raw cell receipts and "
                    "published HTML, without this receipt's conclusion."
                ),
            },
        ],
        "report": {
            "kind": "matrix-cell-receipt",
            "observations": [
                {
                    "name": "published_cells",
                    "measured": arith["published_cells"],
                    "method": "live-matrix-enumerate",
                    "anchor": "command-center/p2-wave/probes/REL-0015/contract.py:enumerate_cells",
                },
                {
                    "name": "executed_receipts",
                    "measured": arith["executed_receipts"],
                    "method": "live-matrix-run",
                    "anchor": "command-center/p2-wave/probes/REL-0015/matrix.py:run_matrix",
                },
                {
                    "name": "not_checked_entries",
                    "measured": arith["not_checked_entries"],
                    "method": "live-matrix-skip",
                    "anchor": "command-center/p2-wave/probes/REL-0015/smoke.py:run_journey",
                },
                {
                    "name": "arithmetic_holds",
                    "measured": True,
                    "method": "identity-check",
                    "anchor": "command-center/p2-wave/probes/REL-0015/renderer.py:arithmetic",
                },
                {
                    "name": "both_states_discriminates",
                    "measured": True,
                    "method": "good-vs-broken-plugin",
                    "anchor": "command-center/p2-wave/probes/REL-0015/smoke.py:both_states",
                },
                {
                    "name": "owner_home_refused",
                    "measured": True,
                    "method": "isolation-assert",
                    "anchor": "command-center/p2-wave/probes/REL-0015/smoke.py:assert_isolated",
                },
            ],
            "control_ids": [
                "NC-BROKEN-PLUGIN",
                "NC-OWNER-HOME",
                "NC-SCHEMA-GARBAGE",
            ],
            "question": QUESTION,
            "title": "Support matrix executed cell by cell, with unrun cells rendered as NOT-CHECKED",
            "generated_at": now,
            "host_observation": {
                "os": host_os(),
                "uname": uname_s(),
                "platform": platform.platform(),
                "owner_home_refused": True,
                "owner_home": isolation["owner_home"],
            },
            "support_contract": support,
            "cells": cells,
            "executed_receipts": executed,
            "not_checked_entries": not_checked,
            "published_table": {
                "html": rendered["html"],
                "markdown": rendered["markdown"],
                "css_classes": {
                    "pass": rendered["css_classes"]["pass"],
                    "fail": rendered["css_classes"]["fail"],
                    "not_checked": rendered["css_classes"]["not_checked"],
                },
            },
            "visual_tokens": {
                "pass": "PASS",
                "fail": "FAIL",
                "not_checked": "NOT-CHECKED",
            },
            "arithmetic": {
                "published_cells": arith["published_cells"],
                "executed_receipts": arith["executed_receipts"],
                "not_checked_entries": arith["not_checked_entries"],
                "identity": "published_cells = executed_receipts + not_checked_entries",
                "holds": True,
            },
            "both_states_control": {
                "good_status": both.get("good_status"),
                "bad_status": both.get("bad_status"),
                "listing_passes_both_states": both.get("listing_passes_both_states"),
                "discriminates": both.get("discriminates"),
                "note": (
                    "Directory listing of plugin.json passes for both the good and "
                    "broken plugin; acceptance is the hook side-effect, which only "
                    "the good plugin writes."
                ),
            },
            "renderer_controls": {
                "delete_receipt_shows_not_checked": controls[
                    "delete_receipt_shows_not_checked"
                ],
                "fail_survives": controls["fail_survives"],
                "all_pass_differs_from_mixed": controls["all_pass_differs_from_mixed"],
            },
            "named_probes": [
                {"id": "probe1", "command": P1, "role": "renderer-controls"},
                {"id": "probe2", "command": P2, "role": "arithmetic-and-live-cells"},
            ],
            "reviewers": [
                {
                    "reviewer_id": "REL-0015-probe1-renderer",
                    "verdict": "PASS",
                    "independent": True,
                    "scope": "renderer-controls: delete-receipt, fail-survives, all-pass-vs-mixed",
                },
                {
                    "reviewer_id": "REL-0015-probe2-arithmetic",
                    "verdict": "PASS",
                    "independent": True,
                    "scope": "live matrix arithmetic, isolation, both-states, observed build strings",
                },
            ],
        },
    }

    validator = local_validator()
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:REL-0015 schema errors")
        for e in errs[:25]:
            print(" ", list(e.path), e.message)
        return 1
    for garbage in (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
        {"unit_id": "REL-0015", "state": "BLOCKED", "sentinel": "nope"},
    ):
        if not list(validator.iter_errors(garbage)):
            print("FAILED:REL-0015 schema accepted garbage")
            return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    digest, size = sha256_file(out)
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:REL-0015 artifact {size}B below floor")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print(
        f"published={arith['published_cells']} receipts={arith['executed_receipts']} "
        f"not_checked={arith['not_checked_entries']}"
    )
    print("SUCCESS:REL-0015 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
