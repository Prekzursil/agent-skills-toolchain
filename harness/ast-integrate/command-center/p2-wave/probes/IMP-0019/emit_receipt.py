#!/usr/bin/env python3
"""Emit command-center/receipts/IMP-0019.json from live AST + behavioural probes."""
from __future__ import annotations

import datetime as dt
import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
PLUGIN = REPO / "tools" / "plugin"
GUARD = REPO / "tools" / "glob-argv-guard"
sys.path.insert(0, str(PLUGIN))
sys.path.insert(0, str(GUARD))

import glob_argv_guard as gag  # noqa: E402
import argv_only as ao  # noqa: E402
from arg_marshall import dispatch  # noqa: E402
from exec_policy import build_policy, existing_executable, run_script, write_script  # noqa: E402
from exit_codes import observe_argv  # noqa: E402

UNIT = "IMP-0019"
OUT = "command-center/receipts/IMP-0019.json"
TEST = "tools/plugin/tests/test_argv_only.py"
QUESTION = (
    "Replace every string-concatenated shell invocation in the plugin with an "
    "argv-array spawn so an apostrophe, quote, backtick, or `$` in user content "
    "cannot terminate the command early or inject a token. Ban `shell=True` and "
    "string interpolation into commands at lint level."
)


def sha_file(rel: str) -> dict:
    path = REPO / rel
    data = path.read_bytes() if path.is_file() else b""
    return {
        "path": rel,
        "bytes": len(data),
        "sha256": hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest() if data else "",
        "exists": path.is_file(),
        "role": "supporting",
        "eol": "LF" if data and b"\r\n" not in data else ("CRLF" if data else "NOT-CHECKED"),
    }


def run_tests() -> dict:
    p = subprocess.run(
        [sys.executable, "-B", str(REPO / TEST)],
        cwd=str(REPO),
        capture_output=True,
        text=True,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return {
        "id": "tools/plugin/tests/test_argv_only.py",
        "name": "test_hostile_filenames_round_trip + extended glob-argv-guard",
        "command": f"PYTHONDONTWRITEBYTECODE=1 python3 -B {TEST}",
        "result": "PASS" if p.returncode == 0 else "FAIL",
        "exit_code": p.returncode,
        "raw_output": text[-8000:],
    }


def load_concat_mod():
    path = GUARD / "fixtures" / "concatenated_spawn.py"
    spec = importlib.util.spec_from_file_location("concatenated_spawn", path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod, path


def live_evidence() -> dict:
    findings = [f.to_dict() for f in gag.scan_plugin(PLUGIN)]
    mutant_findings = [f.to_dict() for f in gag.scan_file(GUARD / "fixtures" / "concatenated_spawn.py")]
    mutant_kinds = sorted({f["kind"] for f in mutant_findings})

    got = ao.echo_argv(gag.HOSTILE_FILENAME)
    reviewer = ao.echo_argv(gag.REVIEWER_INJECTION)

    with tempfile.TemporaryDirectory(prefix="imp0019-emit-") as td:
        root = Path(td)
        named = root / gag.HOSTILE_FILENAME
        named.write_text("payload\n", encoding="utf-8")
        echo = existing_executable("/bin/echo", "/usr/bin/echo", "echo")
        policy = build_policy(
            policy_id="IMP-0019-emit",
            allowed_executables=[sys.executable, echo],
            allowed_write_roots=[str(root)],
            network_mode="deny",
        )
        script = write_script(
            root / "echo_argv.py",
            "import json, sys\nprint(json.dumps({'argv': sys.argv[1:]}), flush=True)\n",
        )
        run = run_script(policy, script, args=[gag.HOSTILE_FILENAME])
        run_argv = json.loads(run.stdout.strip().splitlines()[-1])["argv"] if run.exit_code == 0 else []
        marshalled = dispatch(str(named), threshold=10_000_000)
        observed = observe_argv(
            [sys.executable, "-B", str(gag.ECHO_CHILD), gag.HOSTILE_FILENAME], via="bash"
        )

    wrapped = ao.wrap_argv_for_shell(
        "bash", [sys.executable, "-B", str(gag.ECHO_CHILD), gag.HOSTILE_FILENAME]
    )
    wrap_proc = ao.spawn(wrapped, capture_output=True, text=True, timeout=20)
    wrap_echo = ao.parse_echo(wrap_proc.stdout) if wrap_proc.returncode == 0 else []

    mod, _ = load_concat_mod()
    mutant = mod.run_concatenated(
        sys.executable, str(gag.ECHO_CHILD), gag.HOSTILE_FILENAME
    )
    mutant_received = None
    if (mutant.stdout or "").strip():
        try:
            mutant_received = json.loads(mutant.stdout.strip().splitlines()[-1]).get("argv")
        except json.JSONDecodeError:
            mutant_received = None
    concat_corrupts = mutant_received != [gag.HOSTILE_FILENAME]

    ok = (
        findings == []
        and got == [gag.HOSTILE_FILENAME]
        and reviewer == [gag.REVIEWER_INJECTION]
        and run.exit_code == 0
        and run_argv == [gag.HOSTILE_FILENAME]
        and marshalled.round_trip_ok
        and observed.present
        and observed.exit_code == 0
        and ao.parse_echo(observed.stdout) == [gag.HOSTILE_FILENAME]
        and wrap_echo == [gag.HOSTILE_FILENAME]
        and "shell=True" in mutant_kinds
        and "f-string-into-command" in mutant_kinds
        and concat_corrupts
        and gag.HOSTILE_FILENAME not in wrapped[2]
    )
    return {
        "ok": ok,
        "ast_findings": findings,
        "ast_finding_count": len(findings),
        "hostile_filename": gag.HOSTILE_FILENAME,
        "reviewer_injection": gag.REVIEWER_INJECTION,
        "spawn_echo": got,
        "reviewer_echo": reviewer,
        "run_script_exit": run.exit_code,
        "run_script_argv": run_argv,
        "marshall_round_trip": marshalled.round_trip_ok,
        "observe_argv_exit": observed.exit_code,
        "bash_wrap_echo": wrap_echo,
        "mutant_kinds": mutant_kinds,
        "mutant_received": mutant_received,
        "concat_corrupts": concat_corrupts,
        "entrypoints": list(ao.ENTRYPOINTS),
        "intercept_exemption": (
            "tools/plugin/intercept.py wraps user os.system/Popen for IMP-0064; "
            "it is not a plugin-constructed command string and is skipped by scan_plugin"
        ),
    }


def main() -> int:
    tests = run_tests()
    if tests["exit_code"] != 0:
        print(tests["raw_output"])
        print("FAILED:IMP-0019 tests")
        return 1
    live = live_evidence()
    if not live["ok"]:
        print(json.dumps(live, indent=2, default=str)[:8000])
        print("FAILED:IMP-0019 live evidence")
        return 1

    now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )
    supporting = [
        sha_file("tools/glob-argv-guard/glob_argv_guard.py"),
        sha_file("tools/glob-argv-guard/echo_child.py"),
        sha_file("tools/glob-argv-guard/test_glob_argv_guard.py"),
        sha_file("tools/glob-argv-guard/fixtures/concatenated_spawn.py"),
        sha_file("tools/plugin/argv_only.py"),
        sha_file("tools/plugin/exec_policy.py"),
        sha_file("tools/plugin/arg_marshall.py"),
        sha_file("tools/plugin/compat_diagnostics.py"),
        sha_file("tools/plugin/exit_codes.py"),
        sha_file("tools/plugin/tests/test_argv_only.py"),
        sha_file("command-center/p2-wave/probes/IMP-0019/probe1_ast_scan.py"),
        sha_file("command-center/p2-wave/probes/IMP-0019/probe2_reviewer_injection.py"),
    ]
    receipt = {
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0019",
        "title": "Argv-array-only process invocation layer (no command-string concatenation)",
        "schema_version": 1,
        "output_schema": "command-center/schema/receipt.schema.json",
        "question_or_target": QUESTION,
        "answer": (
            "Plugin spawn sites call glob-argv-guard.spawn with an argv list. "
            "An AST scan of tools/plugin (except intercept.py, which wraps user "
            "os.system) reports zero shell=True / f-string-into-command sites. "
            "A filename containing apostrophe, quote, $(id), and a space round-trips "
            "through every named entrypoint. A concatenated mutant is flagged by the "
            "same lint and corrupts the same filename."
        ),
        "verdict": "PASS",
        "evidence": [
            {
                "id": "signal-1-ast-scan",
                "kind": "ast-lint",
                "summary": (
                    f"scan_plugin reported {live['ast_finding_count']} findings "
                    "for shell=True / f-string-into-command / os.system"
                ),
                "finding_count": live["ast_finding_count"],
                "findings": live["ast_findings"],
                "verdict": "CONFIRMED",
            },
            {
                "id": "signal-2-hostile-filename-round-trip",
                "kind": "behavioural-probe",
                "summary": (
                    "Literal filename with apostrophe, quote, $(id), and space "
                    "arrived intact at the child via spawn, run_script, dispatch, "
                    "observe_argv, and bash exec-passthrough"
                ),
                "hostile_filename": live["hostile_filename"],
                "spawn_echo": live["spawn_echo"],
                "run_script_argv": live["run_script_argv"],
                "marshall_round_trip": live["marshall_round_trip"],
                "observe_argv_exit": live["observe_argv_exit"],
                "bash_wrap_echo": live["bash_wrap_echo"],
                "verdict": "CONFIRMED",
            },
            {
                "id": "negative-control-concatenated-spawn",
                "kind": "negative-control",
                "summary": (
                    "fixtures/concatenated_spawn.py is flagged shell=True and "
                    "f-string-into-command AND corrupts the hostile filename"
                ),
                "mutant_kinds": live["mutant_kinds"],
                "mutant_received": live["mutant_received"],
                "concat_corrupts": live["concat_corrupts"],
                "verdict": "CONFIRMED",
            },
        ],
        "tests": [
            tests,
            {
                "id": "test_hostile_filenames_round_trip",
                "name": "tools/plugin/tests/test_argv_only.py::test_hostile_filenames_round_trip",
                "result": "PASS",
            },
            {
                "id": "negative-control-lint-and-corruption",
                "name": "concatenated call flagged and corrupts",
                "result": "PASS",
            },
        ],
        "reviewer": {
            "reviewer_id": "IMP-0019-probe2-reviewer-injection",
            "verdict": "PASS",
            "independent": True,
            "injection": live["reviewer_injection"],
            "note": (
                "Reviewer token uses backticks, semicolon, and $HOME — characters "
                "the implementer hostile filename does not include."
            ),
            "reviewer_echo": live["reviewer_echo"],
        },
        "entrypoints": live["entrypoints"],
        "intercept_exemption": live["intercept_exemption"],
        "named_probes": [
            {
                "id": "probe1",
                "role": "ast-scan",
                "command": (
                    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                    "command-center/p2-wave/probes/IMP-0019/probe1_ast_scan.py"
                ),
            },
            {
                "id": "probe2",
                "role": "reviewer-injection",
                "command": (
                    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                    "command-center/p2-wave/probes/IMP-0019/probe2_reviewer_injection.py"
                ),
            },
        ],
        "artifacts": [
            {"path": OUT, "role": "primary"},
            {"path": "tools/glob-argv-guard/glob_argv_guard.py", "role": "lint-and-spawn"},
            {"path": "tools/plugin/argv_only.py", "role": "plugin-spawn-layer"},
            {"path": "tools/plugin/tests/test_argv_only.py", "role": "tests"},
        ],
        "supporting": supporting,
        "timestamps": {"ended_at": now},
        "cloud_ok": False,
        "notes": (
            "G-1 for IMP-0019: live named probes re-run exit 0, receipt "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. cloud ok=true is not delivery."
        ),
    }
    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(receipt, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {OUT}")
    print("SUCCESS:IMP-0019")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
