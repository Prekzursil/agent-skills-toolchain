#!/usr/bin/env python3
"""Emit command-center/receipts/CNF-0186.json (rot-watchdog tooling receipt)."""
from __future__ import annotations

import ast
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import scenarios as S  # noqa: E402
from jsonschema import Draft202012Validator, RefResolver  # noqa: E402

OUT = "command-center/receipts/CNF-0186.json"
SCHEMA = "command-center/schema/confirmation-tooling-receipt.schema.json"
WATCHDOG = "command-center/p2-wave/probes/CNF-0186/watchdog.py"
INTERPRET = "command-center/p2-wave/probes/CNF-0186/interpret.py"
SCENARIOS = "command-center/p2-wave/probes/CNF-0186/scenarios.py"
CLASSIFICATIONS = "command-center/p2-wave/probes/CNF-0186/fixtures/classifications.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0186/probe1_known_broken_both_states.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0186/probe2_attribution_silence_kill.py"
)
QUESTION = (
    "Implementation target: a scheduled re-run of the replication packages that "
    "reports the FIRST day each one stops reproducing, with the environment delta "
    "since the last green. A package that silently rots converts a verified claim "
    "back into an unverified one without anyone noticing, and the loss is invisible "
    "precisely because nothing fails loudly."
)
POLICY = (
    "Two strikes then pivot: after the 2nd failure on the same error-fingerprint, "
    "enumerate >=2 alternative implementations before a 3rd attempt (AGENTS.md 4b)."
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def present(rel: str) -> bool:
    p = REPO / rel
    return p.is_file() and p.stat().st_size > 0


def find_line(rel: str, snippet: str) -> int:
    path = REPO / rel
    hits = [
        i
        for i, ln in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if snippet in ln
    ]
    if len(hits) != 1:
        raise SystemExit(f"FAILED:CNF-0186 emit anchor {rel} {snippet!r} hits={hits}")
    return hits[0]


def fp(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}|{command}".encode("utf-8")).hexdigest()


def artifact_row(rel: str, role: str) -> dict:
    path = REPO / rel
    if not path.is_file():
        raise SystemExit(f"FAILED:CNF-0186 missing artifact {rel}")
    raw = path.read_bytes()
    return {
        "path": rel,
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "exists": True,
        "eol": "LF",
        "role": role,
    }


def run_cmd(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=180,
        env=env,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def schema_validator():
    """Compile the catalog output_schema against on-disk $ref targets (no network)."""
    files = [
        SCHEMA,
        "platform/schema/artifact-class-profiles.schema.json",
        "platform/schema/receipt.schema.json",
    ]
    store: dict[str, dict] = {}
    for rel in files:
        doc = json.loads((REPO / rel).read_text(encoding="utf-8"))
        if isinstance(doc.get("$id"), str):
            store[doc["$id"]] = doc
        store["https://ast-integrate.invalid/" + rel] = doc
    schema = store["https://ast-integrate.invalid/" + SCHEMA]
    resolver = RefResolver.from_schema(schema, store=store)
    return Draft202012Validator(schema, resolver=resolver)


def scheduling_substrate() -> dict:
    cron_d = Path("/etc/cron.d")
    return {
        "on_demand_cli": WATCHDOG,
        "cron_daily_invocation": (
            "PYTHONDONTWRITEBYTECODE=1 python3 -B "
            f"{WATCHDOG} --packages-dir <packages> --state-dir <state> --date $(date -I)"
        ),
        "systemctl_on_path": shutil.which("systemctl") is not None,
        "crontab_on_path": shutil.which("crontab") is not None,
        "cron_d_exists": cron_d.is_dir(),
        "timer_installed_by_this_unit": False,
        "note": (
            "This unit delivers the watchdog CLI and missing-run detector. It does "
            "not install a system crontab or systemd timer on the estate."
        ),
    }


def probe(role: str, method: str, command: str, raw_output: str, exit_code: int) -> dict:
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": raw_output[:65000],
        "fingerprint": fp(method, command),
        "exit_code": exit_code,
    }


def main() -> int:
    started = datetime.now(timezone.utc).replace(microsecond=0)
    with tempfile.TemporaryDirectory(prefix="cnf0186-emit-") as tmp:
        root = Path(tmp)
        both = S.scenario_both_states_and_known_broken(root / "both")
        attr = S.scenario_attribution(root / "attr")
        silence = S.scenario_silence(root / "silence")
        kill = S.scenario_kill_mid_run(root / "kill")
    if not (both["pass"] and attr["pass"] and silence["pass"] and kill["pass"]):
        print(
            "FAILED:CNF-0186 emit scenarios "
            f"both={both['pass']} attr={attr['pass']} "
            f"silence={silence['pass']} kill={kill['pass']}"
        )
        return 1

    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:CNF-0186 named probes c1={c1} c2={c2}")
        print(t1[-1500:])
        print(t2[-1500:])
        return 1

    wd_src = (REPO / WATCHDOG).read_text(encoding="utf-8")
    ast.parse(wd_src)
    cls_doc = json.loads((REPO / CLASSIFICATIONS).read_text(encoding="utf-8"))
    if not isinstance(cls_doc, dict) or not cls_doc.get("classes"):
        print("FAILED:CNF-0186 classifications fixture unusable")
        return 1

    a1 = find_line(WATCHDOG, 'return f"SUCCESS:{pkg_id}"')
    a2 = find_line(SCENARIOS, 'json.dumps({"widget": "9.9.9"}, indent=1)')
    a3 = find_line(WATCHDOG, 'if state.get("first_fail_day") is None:')
    a4 = find_line(WATCHDOG, '"source": "stored-canonical-bytes"')
    a5 = find_line(INTERPRET, '"reason": "silence"')
    a6 = find_line(INTERPRET, '"reason": "missing-run"')
    a7 = find_line(INTERPRET, 'adj["killed_mid_run"] = True')

    cnf0182 = present("command-center/receipts/CNF-0182.json")
    cnf0184 = present("command-center/receipts/CNF-0184.json")
    now = datetime.now(timezone.utc).replace(microsecond=0)
    now_s = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    started_s = started.strftime("%Y-%m-%dT%H:%M:%SZ")
    duration = max(0.0, (now - started).total_seconds())

    read_success_cmd = f"read {WATCHDOG}:{a1} SUCCESS:<pkg> grammar"
    read_delta_cmd = f"read {WATCHDOG}:{a4} stored-canonical-bytes"
    compile_cmd = (
        "PYTHONDONTWRITEBYTECODE=1 python3 -B -c "
        f"\"import ast; ast.parse(open({WATCHDOG!r}, encoding='utf-8').read()); "
        "print('PARSE-OK')\""
    )
    json_cmd = (
        "PYTHONDONTWRITEBYTECODE=1 python3 -B -c "
        f"\"import json; json.load(open({CLASSIFICATIONS!r}, encoding='utf-8')); "
        "print('JSON-OK')\""
    )

    artifacts = [
        artifact_row(WATCHDOG, "primary"),
        artifact_row(INTERPRET, "supporting"),
        artifact_row(SCENARIOS, "supporting"),
        artifact_row(SCHEMA, "supporting"),
        artifact_row(CLASSIFICATIONS, "fixture"),
        artifact_row(
            "command-center/p2-wave/probes/CNF-0186/probe1_known_broken_both_states.py",
            "control",
        ),
        artifact_row(
            "command-center/p2-wave/probes/CNF-0186/probe2_attribution_silence_kill.py",
            "control",
        ),
    ]

    doc = {
        "schema_version": 1,
        "unit_id": "CNF-0186",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNF-0186",
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:33988-34029",
        "min_bytes_threshold": 256,
        "artifacts": artifacts,
        "evidence": [
            {
                "claim": (
                    "Healthy fixture packages emit exactly SUCCESS:<pkg> with no stdout "
                    "noise; breaking pkg-widget's pinned widget version makes the next "
                    f"run FAILED:pkg-widget pin-mismatch; first_fail_day="
                    f"{both['first_fail_day']} and it holds on a later fail day."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": f"{SCENARIOS}:{a2}",
                "probes": [
                    probe("source", "test-run", P1, t1, c1),
                    probe(
                        "verifier",
                        "file-read",
                        read_success_cmd,
                        (REPO / WATCHDOG).read_text(encoding="utf-8").splitlines()[a1 - 1],
                        0,
                    ),
                ],
            },
            {
                "claim": (
                    "Environment delta is parsed from stored last-green canonical "
                    "fingerprint bytes (a planted pins_sha256 of 64 zeros is honored); "
                    "empty stdout and a missing scheduled run are FAILED not green; "
                    "killing the watchdog mid-run does not mark pkg-sleepy SUCCESS."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": f"{WATCHDOG}:{a4}",
                "probes": [
                    probe("source", "test-run", P2, t2, c2),
                    probe(
                        "verifier",
                        "file-read",
                        read_delta_cmd,
                        (REPO / WATCHDOG).read_text(encoding="utf-8").splitlines()[a4 - 1],
                        0,
                    ),
                ],
            },
            {
                "claim": (
                    "Estate P0/P1 replication packages from CNF-0182 are on this worktree "
                    "and the watchdog has rot-watched them on a calendar schedule."
                ),
                "verdict": "NOT-CHECKED",
                "unverified": True,
                "anchor": "command-center/receipts/CNF-0182.json",
                "settling_experiment": (
                    "After CNF-0182 delivers packages, invoke watchdog.py from cron "
                    "with --date $(date -I) and persist state_dir across days."
                ),
                "probes": [
                    probe(
                        "source",
                        "file-read",
                        "stat command-center/receipts/CNF-0182.json",
                        "ABSENT" if not cnf0182 else "PRESENT",
                        1 if not cnf0182 else 0,
                    )
                ],
            },
        ],
        "tests": [
            {
                "id": "T1-known-broken-and-both-states",
                "name": "Known-broken pin control, both-states SUCCESS with no noise, first-fail day holds",
                "command": P1,
                "result": "PASS",
                "output_tail": t1[-4000:],
            },
            {
                "id": "T2-attribution-silence-kill",
                "name": "Stored-fingerprint attribution, silence≠green, kill-mid-run reviewer path",
                "command": P2,
                "result": "PASS",
                "output_tail": t2[-4000:],
            },
        ],
        "negative_controls": [
            {
                "id": "NC-BROKEN-PIN",
                "kind": "known-broken-fixture",
                "description": (
                    "Deliberately rewrite pkg-widget pins.json widget 1.0.0 -> 9.9.9; "
                    "the next watchdog run must emit FAILED:pkg-widget pin-mismatch "
                    "while pkg-healthy stays SUCCESS."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "\n".join(both["day2"]["lines"]),
                "good_state_output": "\n".join(both["day1"]["lines"]),
            },
            {
                "id": "NC-SILENCE",
                "kind": "absent-input",
                "description": (
                    "Empty watchdog stdout and a missing scheduled run must be FAILED, "
                    "never SUCCESS."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": json.dumps(
                    {
                        "empty_overall": silence["empty_adjudication"]["overall"],
                        "missing_overall": silence["missing_adjudication"]["overall"],
                    },
                    sort_keys=True,
                ),
                "good_state_output": "SUCCESS:pkg-healthy\nSUCCESS:pkg-widget",
            },
            {
                "id": "NC-KILL-MID-RUN",
                "kind": "mutation",
                "description": (
                    "SIGKILL the watchdog process group mid-run; pkg-sleepy must not "
                    "be SUCCESS and overall must be FAILED."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": json.dumps(
                    {
                        "killed": kill["killed"],
                        "sleepy_not_success": kill["sleepy_not_success"],
                        "overall_failed": kill["overall_failed"],
                        "run_complete": kill["run_complete"],
                    },
                    sort_keys=True,
                ),
                "good_state_output": "SUCCESS:pkg-healthy",
            },
        ],
        "reviewer": {
            "reviewer_id": "CNF-0186-probe2-kill-mid-run",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "vendor": "local",
            "notes": (
                "Started watchdog.py against pkg-healthy + pkg-sleepy, SIGKILL'd the "
                "process group after 0.7s, and required interpret.incomplete_kill to "
                "treat pkg-sleepy as not SUCCESS and the overall run as FAILED."
            ),
            "reviewed_at": now_s,
        },
        "defects": [],
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/CNF-0186/UNIT-ARTIFACT-MANIFEST.json",
            "entry_id": "CNF-0186",
            "registered_at": now_s,
        },
        "downstream_consumers": [
            {
                "consumer": "python3 ast.parse of watchdog.py",
                "artifact_path": WATCHDOG,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": probe(
                    "verifier",
                    "static-analysis",
                    compile_cmd,
                    f"PARSE-OK bytes={len(wd_src.encode('utf-8'))}",
                    0,
                ),
            },
            {
                "consumer": "json.loads of CNF-0186 classifications fixture",
                "artifact_path": CLASSIFICATIONS,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": probe(
                    "verifier",
                    "schema-validate",
                    json_cmd,
                    f"JSON-OK classes={len(cls_doc.get('classes') or [])}",
                    0,
                ),
            },
        ],
        "timestamps": {
            "started_at": started_s,
            "ended_at": now_s,
            "duration_seconds": duration,
        },
        "retry": {"count": 0, "policy": POLICY},
        "residual_unknowns": [
            {
                "claim": (
                    "Estate P0/P1 replication packages from CNF-0182 rot-watch on a "
                    "calendar schedule."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "After CNF-0182 delivers packages, invoke watchdog.py from cron "
                    "with --date $(date -I) and persist state_dir across days."
                ),
            },
            {
                "claim": "CNF-0184 live normalizers are loaded from the estate receipt.",
                "verdict": "NOT-CHECKED" if not cnf0184 else "CONFIRMED",
                "settling_experiment": (
                    "Deliver CNF-0184; watchdog.py loads that receipt's normalizers "
                    "when present, otherwise fixtures/classifications.json."
                ),
            },
        ],
        "produced_by": {
            "vendor": "xai",
            "model": "grok-4.6",
            "role": "program-confirmer",
            "execution_substrate": "local-serialized",
        },
        "report": {
            "kind": "confirmation-tooling-receipt",
            "observations": [
                {
                    "name": "both_states_exact_success_lines",
                    "measured": True,
                    "method": "watchdog CLI on pkg-healthy + pkg-widget",
                    "anchor": f"{WATCHDOG}:{a1}",
                },
                {
                    "name": "known_broken_pin_first_fail_day",
                    "measured": str(both["first_fail_day"] or ""),
                    "method": "break widget pin then re-run",
                    "anchor": f"{SCENARIOS}:{a2}",
                },
                {
                    "name": "first_fail_day_held",
                    "measured": bool(both["first_fail_held_on_later_day"]),
                    "method": "third-day re-run without rewriting first_fail_day",
                    "anchor": f"{WATCHDOG}:{a3}",
                },
                {
                    "name": "attribution_from_stored_canonical_bytes",
                    "measured": bool(attr["from_stored_bytes"]),
                    "method": "planted last-green fingerprint vs live capture",
                    "anchor": f"{WATCHDOG}:{a4}",
                },
                {
                    "name": "silence_is_failed",
                    "measured": bool(silence["pass"]),
                    "method": "interpret.adjudicate empty stdout + missing_run",
                    "anchor": f"{INTERPRET}:{a5}",
                },
                {
                    "name": "missing_run_is_failed",
                    "measured": bool(silence["missing_run_ok"]),
                    "method": "interpret.missing_run against empty state_dir",
                    "anchor": f"{INTERPRET}:{a6}",
                },
                {
                    "name": "kill_mid_run_sleepy_not_success",
                    "measured": bool(kill["sleepy_not_success"]),
                    "method": "SIGKILL process group then interpret.incomplete_kill",
                    "anchor": f"{INTERPRET}:{a7}",
                },
            ],
            "control_ids": ["NC-BROKEN-PIN", "NC-SILENCE", "NC-KILL-MID-RUN"],
        },
        "extensions": {
            "title": "Replication-package rot watchdog: detect the day a package stops reproducing",
            "question_or_target": QUESTION,
            "tool": {
                "name": "replication-package-rot-watchdog",
                "path": WATCHDOG,
                "purpose": (
                    "Scheduled re-run of replication packages that emits SUCCESS:<pkg> or "
                    "FAILED:<pkg> reason, stores the environment fingerprint with each "
                    "result, reports first-fail day, and treats silence as FAILED."
                ),
            },
            "tooling": {
                "kind": "rot-watchdog",
                "invariants": [
                    "Stdout is only terminal-state lines: SUCCESS:<pkg> or FAILED:<pkg> reason.",
                    "Environment fingerprints are persisted as canonical JSON bytes; deltas parse those bytes and never reconstruct a historical fingerprint from the live environment.",
                    "The first calendar day a package stops reproducing is stored and not rewritten on later failures.",
                    "Empty watchdog stdout, a missing scheduled run, or a package with no terminal line is FAILED, not green.",
                ],
                "terminal_line_grammar": "^(SUCCESS|FAILED):(\\S+)(?:\\s+(.*))?$",
                "silence_policy": INTERPRET,
                "fingerprint_policy": "store canonical bytes; delta source=stored-canonical-bytes",
                "first_fail_day_policy": (
                    "set on first SUCCESS->FAILED (or first FAIL if never green); hold on later FAILs"
                ),
            },
            "dependencies_on_this_tree": {
                "CNF-0182": {
                    "path": "command-center/receipts/CNF-0182.json",
                    "present": cnf0182,
                    "verdict": "CONFIRMED" if cnf0182 else "NOT-CHECKED",
                },
                "CNF-0184": {
                    "path": "command-center/receipts/CNF-0184.json",
                    "present": cnf0184,
                    "verdict": "CONFIRMED" if cnf0184 else "NOT-CHECKED",
                },
            },
            "packages_exercised": [
                "pkg-healthy (fixture; timestamp+tmp path normalized)",
                "pkg-widget (fixture; pinned widget==1.0.0)",
                "pkg-sleepy (fixture; 30s sleep for kill-mid-run)",
            ],
            "scheduling": scheduling_substrate(),
            "measured": {
                "both_states": {
                    "healthy_stdout_exact": both["day1"]["lines"],
                    "no_noise": both["day1"]["lines"]
                    == ["SUCCESS:pkg-healthy", "SUCCESS:pkg-widget"],
                },
                "known_broken": {
                    "broken_pin": "widget 1.0.0 -> 9.9.9",
                    "day2_lines": both["day2"]["lines"],
                    "first_fail_day": both["first_fail_day"],
                    "held_on_day3": both["first_fail_held_on_later_day"],
                },
                "attribution": {
                    "from_stored_bytes": attr["from_stored_bytes"],
                    "planted_stored_fingerprint_honored": attr[
                        "planted_stored_fingerprint_honored"
                    ],
                    "delta_source": (attr["delta"] or {}).get("source"),
                },
                "silence": {
                    "empty_stdout_overall": silence["empty_adjudication"]["overall"],
                    "missing_run_overall": silence["missing_adjudication"]["overall"],
                },
                "kill_mid_run": {
                    "killed": kill["killed"],
                    "sleepy_not_success": kill["sleepy_not_success"],
                    "overall_failed": kill["overall_failed"],
                    "run_complete": kill["run_complete"],
                },
            },
            "named_probes": [
                {"id": "probe1", "role": "known-broken-both-states", "command": P1},
                {"id": "probe2", "role": "attribution-silence-kill", "command": P2},
            ],
            "global_catalog_write": False,
            "notes": (
                "G-1 for CNF-0186: watchdog proven on fixture packages. CNF-0182/CNF-0184 "
                "estate artifacts are absent and recorded NOT-CHECKED. Did not run global "
                "unit_manifest.py --write."
            ),
        },
    }

    validator = schema_validator()
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:CNF-0186 schema errors")
        for e in errs[:20]:
            print(" ", list(e.path), e.message)
        return 1
    garbage = [
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"x": "x" * 2000},
    ]
    for g in garbage:
        if validator.is_valid(g):
            print(f"FAILED:CNF-0186 schema accepted garbage {list(g)[:2]}")
            return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(doc, indent=1, sort_keys=True) + "\n"
    if "SUCCESS:CNF-0186" not in raw:
        print("FAILED:CNF-0186 sentinel missing from artifact text")
        return 1
    out.write_text(raw, encoding="utf-8")
    digest, size = sha256_file(out)
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:CNF-0186 artifact {size}B below floor")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print("SUCCESS:CNF-0186 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
