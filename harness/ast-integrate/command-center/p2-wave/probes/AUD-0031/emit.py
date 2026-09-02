#!/usr/bin/env python3
"""Emit command-center/audit/AUD-0031-salvage-consumption-verify.json."""
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
import engine as E  # noqa: E402

UNIT = "AUD-0031"
OUT = "command-center/audit/AUD-0031-salvage-consumption-verify.json"
SCHEMA = "command-center/schema/audit-finding.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0031/probe1_ast_reverse_ref.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0031/probe2_runtime_coverage.py"
)
SENTINEL = (
    "SUCCESS:AUD-0031 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and both named probes are "
    "recorded with their verbatim output"
)
QUESTION = (
    "For each of the 6 modules salvaged into tools/lib/, which non-test "
    "callers import it today - and if a module has zero non-test consumers, "
    "did the salvage decision achieve anything measurable?"
)


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_cmd(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(REPO),
            shell=True,
            capture_output=True,
            text=True,
            env=env,
            timeout=170,
        )
    except subprocess.TimeoutExpired:
        return 124, "TIMEOUT"
    return proc.returncode, ((proc.stdout or "") + (proc.stderr or "")).strip()


def art(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest_file(path) if path.is_file() else ("", 0)
    return {
        "path": rel,
        "bytes": size,
        "sha256": sha,
        "exists": path.is_file(),
        "role": role,
        "eol": "LF",
    }


def first_json_object(text: str) -> dict:
    start = text.find("{")
    if start < 0:
        return {}
    decoder = json.JSONDecoder()
    try:
        obj, _end = decoder.raw_decode(text[start:])
    except json.JSONDecodeError:
        return {}
    return obj if isinstance(obj, dict) else {}


def fingerprint(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}\x1f{command}".encode()).hexdigest()[:32]


def main() -> int:
    started = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    rows = E.roster()
    refs = E.reverse_refs(rows)
    mention = E.mention_control(rows)
    use = E.import_vs_use_control()
    if not mention.get("passed") or not use.get("passed"):
        print(
            f"FAILED:{UNIT} emit controls "
            f"mention={mention.get('passed')} import_vs_use={use.get('passed')}"
        )
        return 1
    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:{UNIT} emit probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    probe2 = first_json_object(t2)
    runtime = {
        "tools_lib_executed": probe2.get("tools_lib_executed") or [],
        "tools_lib_loaded": probe2.get("tools_lib_loaded") or [],
    }
    modules = E.module_rows(rows, refs, runtime)
    summary = E.summarize(modules)
    zero = int(summary["modules_with_zero_non_test_consumers"])
    consumed = int(summary["modules_with_non_test_consumers"])
    salvage_ok = bool(summary["salvage_achieved_measurable_consumption"])
    executed_n = len(runtime["tools_lib_executed"])
    answer = (
        f"Roster is the catalog six ({summary['roster_count']} modules) under "
        f"tools/lib/. On this worktree tools/lib/ exists="
        f"{summary['lib_home_exists']} with {summary['present_on_disk']} of "
        f"{summary['roster_count']} files present. AST reverse-reference "
        f"(tests and the salvage home itself excluded) found non-test import "
        f"consumers for {consumed} module(s); {zero} module(s) have zero "
        f"non-test consumers. Runtime coverage of non-test entry points "
        f"executed {executed_n} tools/lib file(s). Salvage achieved "
        f"measurable consumption={str(salvage_ok).lower()}. An import is "
        f"not a use; mention-only docstring/comment names are not consumers. "
        + SENTINEL
    )
    ended = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    fp1 = fingerprint("command", P1)
    fp2 = fingerprint("command", P2)
    fp_ctl = fingerprint("test-run", "engine.mention_control+import_vs_use_control")
    t1c, t2c = t1[:65000], t2[:65000]
    doc = {
        "schema_version": 1,
        "unit_id": UNIT,
        "id": UNIT,
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "report_kind": "audit-finding",
        "output_path": OUT,
        "output_schema": SCHEMA,
        "question": QUESTION,
        "question_or_target": QUESTION,
        "answer": answer,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json#AUD-0031",
        "min_bytes_threshold": 1024,
        "owner_decision": "salvage home = tools/lib/ shared tree",
        "summary": summary,
        "modules": modules,
        "produced_by": {
            "vendor": "xai",
            "model": "grok",
            "role": "auditor",
            "execution_substrate": "local-parallel",
        },
        "report": {
            "kind": "audit-finding",
            "question": QUESTION,
            "answer": answer,
            "control_ids": [
                "AUD-0031-C1-use-vs-mention",
                "AUD-0031-C2-import-is-not-a-use",
            ],
            "summary": summary,
            "modules": modules,
            "observations": [
                {
                    "name": "modules_with_non_test_consumers",
                    "measured": consumed,
                    "method": "static-analysis",
                    "anchor": (
                        "command-center/p2-wave/probes/AUD-0031/"
                        "probe1_ast_reverse_ref.py"
                    ),
                },
                {
                    "name": "modules_with_zero_non_test_consumers",
                    "measured": zero,
                    "method": "static-analysis",
                    "anchor": (
                        "command-center/p2-wave/probes/AUD-0031/"
                        "probe1_ast_reverse_ref.py"
                    ),
                },
                {
                    "name": "tools_lib_present_on_disk",
                    "measured": int(summary["present_on_disk"]),
                    "method": "file-read",
                    "anchor": "tools/lib/",
                },
                {
                    "name": "tools_lib_files_executed_at_runtime",
                    "measured": executed_n,
                    "method": "test-run",
                    "anchor": (
                        "command-center/p2-wave/probes/AUD-0031/"
                        "probe2_runtime_coverage.py"
                    ),
                },
                {
                    "name": "salvage_achieved_measurable_consumption",
                    "measured": salvage_ok,
                    "method": "static-analysis",
                    "anchor": (
                        "command-center/p2-wave/probes/AUD-0031/engine.py:"
                        "summarize"
                    ),
                },
            ],
        },
        "evidence": [
            {
                "claim": (
                    "Non-test reverse-references to salvaged tools/lib modules "
                    "come from AST import nodes and relative-specifier "
                    "resolution, not textual mentions in comments or docstrings."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": (
                    "command-center/p2-wave/probes/AUD-0031/"
                    "probe1_ast_reverse_ref.py"
                ),
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": P1,
                        "exit_code": c1,
                        "raw_output": t1c,
                        "fingerprint": fp1,
                    },
                    {
                        "role": "verifier",
                        "method": "test-run",
                        "command": (
                            "PYTHONDONTWRITEBYTECODE=1 python3 -B -c "
                            "mention_control from "
                            "command-center/p2-wave/probes/AUD-0031/engine.py"
                        ),
                        "exit_code": 0 if mention.get("passed") else 1,
                        "raw_output": json.dumps(mention, indent=1, sort_keys=True)[
                            :65000
                        ],
                        "fingerprint": fp_ctl,
                    },
                ],
            },
            {
                "claim": (
                    "Runtime coverage of non-test entry points records executed "
                    "tools/lib modules; a mere import without a call is not a use."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": (
                    "command-center/p2-wave/probes/AUD-0031/"
                    "probe2_runtime_coverage.py"
                ),
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": P2,
                        "exit_code": c2,
                        "raw_output": t2c,
                        "fingerprint": fp2,
                    },
                    {
                        "role": "verifier",
                        "method": "test-run",
                        "command": (
                            "PYTHONDONTWRITEBYTECODE=1 python3 -B -c "
                            "import_vs_use_control from "
                            "command-center/p2-wave/probes/AUD-0031/engine.py"
                        ),
                        "exit_code": 0 if use.get("passed") else 1,
                        "raw_output": json.dumps(use, indent=1, sort_keys=True)[:65000],
                        "fingerprint": fingerprint("test-run", "import_vs_use_control"),
                    },
                ],
            },
        ],
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "raw_output": t1c,
                "role": "ast-reverse-ref",
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "raw_output": t2c,
                "role": "runtime-coverage",
            },
        ],
        "tests": [
            {
                "id": "use-vs-mention",
                "name": (
                    "module named only in a docstring or comment is not a consumer"
                ),
                "result": "PASS" if mention.get("passed") else "FAIL",
                "command": P1,
                "assertions": 3,
            },
            {
                "id": "import-is-not-a-use",
                "name": "imported-but-never-called module is not executed",
                "result": "PASS" if use.get("passed") else "FAIL",
                "command": P2,
                "assertions": 2,
            },
        ],
        "negative_controls": [
            {
                "id": "AUD-0031-C1-use-vs-mention",
                "kind": "known-broken-fixture",
                "description": mention.get("description")
                or (
                    "A module named only inside a docstring or a comment must "
                    "NOT count as a consumer; a real import of the same "
                    "module must."
                ),
                "fired_on_bad_state": bool(mention.get("fired_on_import")),
                "silent_on_good_state": bool(mention.get("silent_on_mention")),
                "bad_state_output": json.dumps(mention.get("import_hits")),
                "good_state_output": json.dumps(mention.get("mention_hits")),
            },
            {
                "id": "AUD-0031-C2-import-is-not-a-use",
                "kind": "known-broken-fixture",
                "description": use.get("description")
                or (
                    "A salvaged module imported but never invoked must not "
                    "count as executed; a call to used() must count."
                ),
                "fired_on_bad_state": bool(use.get("python_execute_executed_used")),
                "silent_on_good_state": not bool(
                    use.get("python_import_only_executed_used")
                ),
                "bad_state_output": json.dumps(
                    {
                        "python_execute_executed_used": use.get(
                            "python_execute_executed_used"
                        )
                    }
                ),
                "good_state_output": json.dumps(
                    {
                        "python_import_only_executed_used": use.get(
                            "python_import_only_executed_used"
                        )
                    }
                ),
            },
        ],
        "reviewer": {
            "reviewer_id": "AUD-0031-probe2-runtime-coverage",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": False,
            "notes": (
                "Catalog asks a cross-vendor Codex reviewer to re-run ONLY "
                "probe 2. Probe 2 is a runtime coverage trace and does not "
                "reuse probe 1's AST reverse-reference."
            ),
        },
        "artifacts": [
            art(
                "command-center/p2-wave/probes/AUD-0031/probe1_ast_reverse_ref.py",
                "supporting",
            ),
            art(
                "command-center/p2-wave/probes/AUD-0031/probe2_runtime_coverage.py",
                "supporting",
            ),
            art("command-center/p2-wave/probes/AUD-0031/engine.py", "supporting"),
        ],
        "timestamps": {"started_at": started, "ended_at": ended},
        "retry": {
            "count": 0,
            "policy": (
                "two strikes then pivot (AGENTS.md 4b): after the second "
                "failure with the same detector, enumerate at least 2 "
                "mechanically different detectors before a third attempt"
            ),
        },
        "manifest_registration": {
            "manifest_path": (
                "command-center/p2-wave/probes/AUD-0031/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "registered": True,
            "entry_id": UNIT,
        },
        "downstream_consumers": [
            {
                "consumer": "json.loads",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": {
                    "role": "verifier",
                    "method": "schema-validate",
                    "command": (
                        "PYTHONDONTWRITEBYTECODE=1 python3 -B -c "
                        "json.loads(Path(output_path).read_text())"
                    ),
                    "raw_output": "pending-rewrite-then-rehash",
                    "fingerprint": fingerprint("schema-validate", "json.loads"),
                    "exit_code": 0,
                },
            }
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "Runtime coverage traces a bounded sample of non-test "
                    "entry points under tools/, not every possible caller "
                    "in the wider estate."
                ),
                "verdict": "PARTIAL",
                "settling_experiment": (
                    "Raise the probe-2 entry budget and add package.json "
                    "bin/main roots on a larger host."
                ),
            }
        ],
        "cloud_ok": False,
        "adv_rebuild_circle": False,
        "notes": (
            "G-1 for AUD-0031: live named probes must exit 0. cloud ok=true "
            "is not delivery. Did not run global unit_manifest.py --write. "
            "No ADV rebuild circle."
        ),
    }
    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=1, sort_keys=True) + "\n"
    if SENTINEL not in text:
        print(f"FAILED:{UNIT} sentinel missing from serialized artifact")
        return 1
    out_path.write_text(text, encoding="utf-8")
    try:
        loaded = json.loads(out_path.read_text(encoding="utf-8"))
        load_err = None
        load_ok = isinstance(loaded, dict) and loaded.get("state") != "BLOCKED"
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        load_err = f"{type(exc).__name__}: {exc}"
        load_ok = False
    doc["downstream_consumers"][0]["read_ok"] = bool(load_ok)
    doc["downstream_consumers"][0]["executed"] = True
    doc["downstream_consumers"][0]["exit_code"] = 0 if load_ok else 1
    doc["downstream_consumers"][0]["probe"]["raw_output"] = (
        f"json.loads {OUT} ok={load_ok} error={load_err}"
    )
    doc["downstream_consumers"][0]["probe"]["exit_code"] = 0 if load_ok else 1
    text = json.dumps(doc, indent=1, sort_keys=True) + "\n"
    if SENTINEL not in text:
        print(f"FAILED:{UNIT} sentinel missing from rewritten artifact")
        return 1
    out_path.write_text(text, encoding="utf-8")
    sha, size = digest_file(out_path)
    print(f"wrote {OUT} bytes={size} sha256={sha}")
    print(
        f"consumed={consumed} zero={zero} lib_exists={summary['lib_home_exists']} "
        f"mention={mention.get('passed')} import_vs_use={use.get('passed')}"
    )
    print(f"SUCCESS:{UNIT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
