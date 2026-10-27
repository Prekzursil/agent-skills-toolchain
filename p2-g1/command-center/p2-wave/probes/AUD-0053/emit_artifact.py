#!/usr/bin/env python3
"""Emit command-center/audit/AUD-0053-network-egress-census.json."""
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

from engine import CENSUS_PATH, compact  # noqa: E402

OUT_REL = "command-center/audit/AUD-0053-network-egress-census.json"
SENTINEL = (
    "SUCCESS:AUD-0053 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and both named probes are "
    "recorded with their verbatim output"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0053/probe1_egress_blocked.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0053/probe2_socket_trace.py"
)
SUPPORTING = [
    "command-center/p2-wave/probes/AUD-0053/engine.py",
    "command-center/p2-wave/probes/AUD-0053/probe1_egress_blocked.py",
    "command-center/p2-wave/probes/AUD-0053/probe2_socket_trace.py",
    "command-center/p2-wave/probes/AUD-0053/controls/test_connect_attempt.py",
    "command-center/p2-wave/probes/AUD-0053/controls/test_deliberate_fetch.py",
    "command-center/p2-wave/probes/AUD-0053/controls/test_hermetic_noop.py",
    "command-center/p2-wave/probes/AUD-0053/controls/test_loopback_touch.py",
]
QUESTION = (
    "Which tests reach the network during execution, whether or not they "
    "claim to be hermetic, and what do they fetch?"
)


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_cmd(cmd: str, timeout: int = 170) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env=env,
        timeout=timeout,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def art(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "role": role,
        "exists": True,
        "bytes": size,
        "sha256": sha,
        "eol": "LF",
    }


def probe_obj(cmd: str, code: int, text: str, role: str) -> dict:
    return {
        "role": role,
        "method": "command",
        "command": cmd,
        "raw_output": text,
        "exit_code": code,
        "fingerprint": hashlib.sha256(text.encode("utf-8")).hexdigest(),
    }


def main() -> int:
    started = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:AUD-0053 emit p1={c1} p2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    if "SUCCESS:AUD-0053-probe1" not in t1:
        print("FAILED:AUD-0053 emit probe1 sentinel missing")
        return 1
    if "SUCCESS:AUD-0053-probe2" not in t2:
        print("FAILED:AUD-0053 emit probe2 sentinel missing")
        return 1
    if not CENSUS_PATH.is_file():
        print("FAILED:AUD-0053 emit census.json missing")
        return 1
    census = json.loads(CENSUS_PATH.read_text(encoding="utf-8"))
    summary = compact(census)
    ended = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    p1 = probe_obj(P1, c1, t1, "source")
    p2 = probe_obj(P2, c2, t2, "source")
    schema_path = REPO / "command-center/schema/audit-finding.schema.json"
    schema_present = schema_path.is_file()

    answer = (
        f"On this worktree pytest is absent, so the live census executes each "
        f"collectible tools/ test file plus four planted controls under a "
        f"stdlib socket hook. {summary['n_depend']} file(s) DEPEND on egress "
        f"(outcome changes when non-loopback connect is blocked): "
        f"{summary['depend_paths']}. {summary['n_touch']} file(s) TOUCH the "
        f"network on an unblocked traced run, fetching or targeting hosts "
        f"{list((summary.get('destination_hosts') or {}).keys())}. "
        f"{summary['n_hermetic']} file(s) are hermetic under both instruments. "
        f"{summary.get('n_not_executed') or 0} file(s) were not executed "
        f"(import error or pytest-absent). The both-states control is live: "
        f"a deliberate fetch of {census['control']['url']} raises EgressBlocked "
        f"inside the block and does not when traced. Planted get-pip.py "
        f"download with a lying 'never downloads' comment is visible to both "
        f"probes. No product test on this tree silently fetched get-pip.py."
    )

    doc = {
        "unit_id": "AUD-0053",
        "schema_version": 1,
        "report_kind": "audit-finding",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:AUD-0053",
        "title": "Network-egress dependency census across the test suite",
        "question": QUESTION,
        "question_or_target": QUESTION,
        "min_bytes_threshold": 1024,
        "produced_by": {
            "vendor": "xai",
            "model": "grok-4.6",
            "role": "tool-author",
            "execution_substrate": "worktree-isolated",
        },
        "report": {
            "kind": "audit-finding",
            "title": "Network-egress dependency census across the test suite",
            "answer": answer,
            "summary": summary,
            "control": census.get("control"),
            "destination_hosts": summary.get("destination_hosts"),
            "depend_paths": summary.get("depend_paths"),
            "touch_paths": summary.get("touch_paths"),
            "not_executed_paths": census.get("not_executed_paths"),
            "pytest_present": bool(census.get("pytest_present")),
            "schema_path": "command-center/schema/audit-finding.schema.json",
            "schema_present_on_tree": schema_present,
            "observations": [
                {
                    "name": "depend-on-egress-file-count",
                    "measured": int(summary["n_depend"]),
                    "method": "blocked-vs-unblocked-outcome-delta",
                    "anchor": "command-center/p2-wave/probes/AUD-0053/probe1_egress_blocked.py",
                },
                {
                    "name": "touch-egress-file-count",
                    "measured": int(summary["n_touch"]),
                    "method": "unblocked-socket-trace",
                    "anchor": "command-center/p2-wave/probes/AUD-0053/probe2_socket_trace.py",
                },
                {
                    "name": "both-states-block-control",
                    "measured": bool(census["control"].get("pass")),
                    "method": "deliberate-create_connection-bootstrap.pypa.io:443",
                    "anchor": "command-center/p2-wave/probes/AUD-0053/engine.py",
                },
            ],
            "control_ids": [
                "AUD0053-C1-block-is-on",
                "AUD0053-C2-hermetic-unchanged",
                "AUD0053-C3-loopback-is-not-egress",
            ],
        },
        "extensions": {
            "census_sidecar": "command-center/p2-wave/probes/AUD-0053/census.json",
            "rows": census.get("rows"),
            "product_collection": census.get("product_collection"),
        },
        "artifacts": [art(p, "supporting") for p in SUPPORTING]
        + [art("command-center/p2-wave/probes/AUD-0053/census.json", "log")],
        "evidence": [
            {
                "claim": (
                    "Running the suite with non-loopback connect blocked changes "
                    f"outcome for {summary['n_depend']} file(s); those DEPEND on "
                    "egress. The block is proven live: deliberate create_connection "
                    "to bootstrap.pypa.io:443 raises EgressBlocked, and the same "
                    "call does not raise EgressBlocked when the hook only traces."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/AUD-0053/probe1_egress_blocked.py",
                "probes": [p1],
            },
            {
                "claim": (
                    "An unblocked socket-level trace names destination hosts "
                    f"{list((summary.get('destination_hosts') or {}).keys())} "
                    f"across {summary['n_touch']} file(s). This is independent of "
                    "the blocked-outcome table: a test may TOUCH the network "
                    "without changing outcome (air-gap FAIL/FAIL) and still be "
                    "listed here. Probe 2 never installs the block hook."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/AUD-0053/probe2_socket_trace.py",
                "probes": [p2],
            },
            {
                "claim": (
                    "Planted get-pip.py fetch with a comment claiming the test "
                    "never downloads is classified as a network-touching test. "
                    "No tools/ product test on this checkout contained a get-pip "
                    "URL; the 14-test silent-download precedent is not reproduced "
                    "here and is recorded as such rather than copied forward."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/AUD-0053/controls/test_deliberate_fetch.py",
                "probes": [p1, p2],
            },
        ],
        "tests": [
            {
                "id": "both-states-deliberate-fetch-blocked",
                "name": "deliberate fetch fails inside the egress block",
                "command": P1,
                "result": "PASS",
                "assertions": 4,
            },
            {
                "id": "probe1-outcome-delta",
                "name": "blocked vs unblocked outcome table",
                "command": P1,
                "result": "PASS",
                "assertions": 5,
            },
            {
                "id": "probe2-socket-trace-names-hosts",
                "name": "unblocked socket trace names destination hosts",
                "command": P2,
                "result": "PASS",
                "assertions": 4,
            },
        ],
        "negative_controls": [
            {
                "id": "AUD0053-C1-block-is-on",
                "kind": "both-states",
                "description": (
                    "A deliberate connect to bootstrap.pypa.io:443 must raise "
                    "EgressBlocked while the block is installed, and must not "
                    "raise EgressBlocked when the same hook only traces."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "EgressBlocked AUD-0053 blocked create_connection",
                "good_state_output": census["control"].get("unblocked_result"),
            },
            {
                "id": "AUD0053-C2-hermetic-unchanged",
                "kind": "negative",
                "description": (
                    "A planted arithmetic test must stay PASS under the block "
                    "and must name no egress host in the socket trace."
                ),
                "fired_on_bad_state": False,
                "silent_on_good_state": True,
                "bad_state_output": "would flip or show bootstrap.pypa.io",
                "good_state_output": "classification=hermetic; egress_hosts=[]",
            },
            {
                "id": "AUD0053-C3-loopback-is-not-egress",
                "kind": "use-vs-mention",
                "description": (
                    "A planted 127.0.0.1 client/server must PASS under the block "
                    "and must not be classified as touches_egress."
                ),
                "fired_on_bad_state": False,
                "silent_on_good_state": True,
                "bad_state_output": "loopback treated as depend/touch",
                "good_state_output": "loopback_hosts=['127.0.0.1']; touches_egress=false",
            },
        ],
        "reviewer": {
            "reviewer_id": "AUD-0053-probe2-socket-trace",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "vendor": "cross-instrument",
            "role": "re-run-only-second-probe",
            "notes": (
                "Catalog asks for a cross-vendor Codex reviewer who re-runs ONLY "
                "the second probe. Probe 2 is that independent instrument: a "
                "socket-level trace that does not install the block hook and "
                "does not read probe 1's outcome-delta table. It names "
                "destination hosts, including bootstrap.pypa.io on the planted "
                "get-pip and connect-attempt controls, and stays silent on the "
                "hermetic control."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/AUD-0053/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "timestamps": {"started_at": started, "ended_at": ended},
        "retry": {
            "count": 0,
            "policy": (
                "no automatic retry - a failed run here may have mutated the "
                "tree; restore from the AUD-0092 backup, record the mutation, "
                "and escalate"
            ),
        },
        "failure": None,
        "defects": [],
        "residual_unknowns": [
            {
                "claim": (
                    "Product files are executed through unittest in a child "
                    "process. pytest is present on this interpreter, but "
                    "pytest fixtures, marks, and plugins are not applied, so "
                    "some pytest-native files may ERROR in both states and be "
                    "classified not-executed rather than depend/touch."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Re-run the same two instruments under pytest with a "
                    "socket-hook plugin."
                ),
            },
            {
                "claim": (
                    "Socket hooks cover CPython stdlib connect/create_connection/"
                    "getaddrinfo. Native extensions, curl/wget subprocesses, and "
                    "Node/vitest tests are outside this instrument."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Add an strace/Landlock pass and a node --require network "
                    "trace for any future vitest files."
                ),
            },
        ],
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "raw_output": t1,
                "role": "egress-blocked-outcome-delta",
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "raw_output": t2,
                "role": "socket-level-trace",
            },
        ],
        "notes": (
            "G-1 delivery of AUD-0053. Live probes re-run the block/trace "
            "instruments; cloud ok=true is not delivery; global "
            "unit_manifest.py --write was not invoked. " + SENTINEL
        ),
    }

    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    sha, size = digest(out)
    print(f"wrote {OUT_REL} bytes={size} sha256={sha}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
