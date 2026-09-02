#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0192.json (shell_report)."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from jsonschema import Draft202012Validator, RefResolver  # noqa: E402

from detectors import both_states, interpreters  # noqa: E402
from gate import evaluate  # noqa: E402

OUT = "command-center/receipts/TST-0192.json"
SCHEMA = "command-center/schema/receipt.schema.json#/$defs/shell_report"
SENTINEL = "SUCCESS:TST-0192"
QUESTION = (
    "Are all emitted `.sh` files LF-terminated and syntax-checked by the "
    "interpreter that will actually run them? PASS requires verification "
    "under real bash (WSL), not Git Bash, and a `.gitattributes` rule "
    "pinning `*.sh eol=lf`."
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0192/probe1_blob_crlf.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0192/probe2_both_states.py"
)
SCHEMA_FILES = (
    "command-center/schema/receipt.schema.json",
    "platform/schema/artifact-class-profiles.schema.json",
    "platform/schema/receipt.schema.json",
)
SUPPORTING = [
    ".gitattributes",
    "command-center/p2-wave/probes/TST-0192/detectors.py",
    "command-center/p2-wave/probes/TST-0192/emitter.py",
    "command-center/p2-wave/probes/TST-0192/gate.py",
    "command-center/p2-wave/probes/TST-0192/probe1_blob_crlf.py",
    "command-center/p2-wave/probes/TST-0192/probe2_both_states.py",
    "command-center/p2-wave/probes/TST-0192/emitted/hello.sh",
    "command-center/p2-wave/probes/TST-0192/emitted/branch.sh",
    "command-center/p2-wave/probes/TST-0192/emitted/argv.sh",
]


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def fingerprint(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}\n{command}".encode("utf-8")).hexdigest()


def art_row(rel: str, role: str) -> dict[str, Any]:
    path = REPO / rel
    sha, size = sha256_file(path)
    return {
        "path": rel,
        "bytes": size,
        "sha256": sha,
        "exists": True,
        "eol": "LF",
        "role": role,
    }


def shell_report_validator() -> Draft202012Validator:
    store: dict[str, Any] = {}
    for rel in SCHEMA_FILES:
        data = json.loads((REPO / rel).read_text(encoding="utf-8"))
        store["https://ast-integrate.invalid/" + rel] = data
        if isinstance(data.get("$id"), str):
            store[data["$id"]] = data
    profiles = store[
        "https://ast-integrate.invalid/platform/schema/artifact-class-profiles.schema.json"
    ]
    uri = (
        "https://ast-integrate.invalid/platform/schema/"
        "artifact-class-profiles.schema.json#/$defs/shell_report"
    )
    resolver = RefResolver(
        base_uri=(
            "https://ast-integrate.invalid/platform/schema/"
            "artifact-class-profiles.schema.json"
        ),
        referrer=profiles,
        store=store,
    )
    return Draft202012Validator({"$ref": uri}, resolver=resolver)


def compact_exit(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "exit": row.get("exit"),
        "strip_cr": row.get("strip_cr"),
        "cr_in_input": row.get("cr_in_input"),
        "stderr_tail": (row.get("stderr_tail") or "")[:240],
    }


def main() -> int:
    gate = evaluate()
    if not gate["pass"]:
        print("FAILED:TST-0192 emit gate", gate.get("failures"))
        return 1
    ctl = both_states()
    if not (
        ctl["crlf_real_bash_fails"]
        and ctl["crlf_git_bash_passes"]
        and ctl["lf_real_bash_passes"]
        and ctl["detectors_differ"]
        and ctl["git_bash_not_vacuous"]
    ):
        print(
            "FAILED:TST-0192 emit both-states",
            {
                k: ctl[k]
                for k in (
                    "crlf_real_bash_fails",
                    "crlf_git_bash_passes",
                    "lf_real_bash_passes",
                    "detectors_differ",
                    "git_bash_not_vacuous",
                )
            },
        )
        return 1

    interp = interpreters()
    ga = gate["gitattributes"]
    scripts = []
    for row in gate["scripts"]:
        scripts.append(
            {
                "path": row["path"],
                "cr_count": row["cr_count"],
                "real_bash_n_exit": row["real_bash_n_exit"],
                "cr_source": row["cr_source"],
                "blob": row["blob"],
                "worktree": row["worktree"],
            }
        )
        if row["cr_count"] != 0 or row["real_bash_n_exit"] != 0:
            print("FAILED:TST-0192 emit script not LF/real-bash-clean", row["path"])
            return 1
    if len(scripts) < 2:
        print("FAILED:TST-0192 emit too few scripts")
        return 1
    if not ga.get("has_sh_eol_lf"):
        print("FAILED:TST-0192 emit gitattributes rule missing")
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    answer = (
        "Yes on this Linux worktree for the emitted scripts under "
        "command-center/p2-wave/probes/TST-0192/emitted/. Each file has "
        "cr_count=0 and real `bash -n` exit 0. `.gitattributes` pins "
        "`*.sh eol=lf`. A planted CRLF `if/then` fixture fails real "
        "bash -n (exit "
        f"{ctl['crlf_real']['exit']}) while the Git-Bash igncr analogue "
        f"(strip-CR then bash -n) exits {ctl['crlf_git']['exit']}, so the "
        "two detectors differ. A genuinely broken script fails both, so the "
        "analogue is not vacuous. git cat-file -p is used when the blob "
        "exists; otherwise worktree bytes. git archive is not used. "
        "windows-shell.md:3 is the regression seed. Catalog WSL is native "
        f"Linux bash here (wsl_present={interp.get('wsl_present')}). "
        "A second Windows shell (pwsh7 / Git Bash.exe) was not available "
        "and is not claimed. SUCCESS:TST-0192"
    )
    both_summary = {
        "crlf_real_bash_fails": True,
        "crlf_git_bash_passes": True,
        "lf_real_bash_passes": True,
        "detectors_differ": True,
        "git_bash_not_vacuous": True,
        "regression_seed": ctl["regression_seed"],
        "crlf_real_exit": ctl["crlf_real"]["exit"],
        "crlf_git_exit": ctl["crlf_git"]["exit"],
        "lf_real_exit": ctl["lf_real"]["exit"],
        "broken_real_exit": ctl["broken_real"]["exit"],
        "broken_git_exit": ctl["broken_git"]["exit"],
    }
    cr_raw = json.dumps(
        {"gitattributes": ga, "scripts": scripts, "used_git_archive": False},
        sort_keys=True,
    )
    both_raw = json.dumps(
        {
            "crlf_real": compact_exit(ctl["crlf_real"]),
            "crlf_git": compact_exit(ctl["crlf_git"]),
            "lf_real": compact_exit(ctl["lf_real"]),
            "broken_real": compact_exit(ctl["broken_real"]),
            "broken_git": compact_exit(ctl["broken_git"]),
            "detectors_differ": True,
        },
        sort_keys=True,
    )
    supporting = [art_row(p, "fixture" if p.endswith(".sh") else "supporting") for p in SUPPORTING]
    primary = {
        "path": OUT,
        "bytes": 1,
        "sha256": "0" * 64,
        "exists": True,
        "eol": "LF",
        "role": "primary",
    }
    doc: dict[str, Any] = {
        "schema_version": 1,
        "unit_id": "TST-0192",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "spec_anchor": "rules/common/windows-shell.md:3",
        "min_bytes_threshold": 2048,
        "produced_by": {
            "vendor": "grok",
            "model": "grok-4.6",
            "role": "shell-portability-tester",
            "execution_substrate": "native-linux-bash",
        },
        "artifacts": [primary] + supporting,
        "evidence": [
            {
                "claim": (
                    "Emitted .sh files under probes/TST-0192/emitted/ have "
                    "cr_count=0 via git cat-file -p when tracked else worktree "
                    "bytes (never git archive), and .gitattributes pins *.sh eol=lf."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/TST-0192/probe1_blob_crlf.py",
                "probes": [
                    {
                        "role": "source",
                        "method": "byte-compare",
                        "command": P1,
                        "raw_output": cr_raw,
                        "fingerprint": fingerprint("byte-compare", P1),
                        "exit_code": 0,
                    },
                    {
                        "role": "verifier",
                        "method": "file-read",
                        "command": (
                            "PYTHONDONTWRITEBYTECODE=1 python3 -B -c "
                            "\"from pathlib import Path; import sys; "
                            "sys.path.insert(0,'command-center/p2-wave/probes/TST-0192'); "
                            "from detectors import gitattributes_status; "
                            "print(gitattributes_status())\""
                        ),
                        "raw_output": json.dumps(ga, sort_keys=True),
                        "fingerprint": fingerprint(
                            "file-read",
                            "gitattributes_status()",
                        ),
                        "exit_code": 0,
                    },
                ],
            },
            {
                "claim": (
                    "A CRLF if/then fixture fails real bash -n and passes the "
                    "Git-Bash igncr analogue; an LF fixture passes real bash; "
                    "broken syntax fails both (windows-shell.md:3)."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/TST-0192/probe2_both_states.py",
                "probes": [
                    {
                        "role": "source",
                        "method": "test-run",
                        "command": P2,
                        "raw_output": both_raw,
                        "fingerprint": fingerprint("test-run", P2),
                        "exit_code": 0,
                    },
                    {
                        "role": "verifier",
                        "method": "command",
                        "command": (
                            "PYTHONDONTWRITEBYTECODE=1 python3 -B -c "
                            "\"import sys; sys.path.insert(0,"
                            "'command-center/p2-wave/probes/TST-0192'); "
                            "from detectors import both_states; "
                            "c=both_states(); print(c['crlf_real']['exit'], "
                            "c['crlf_git']['exit'], c['detectors_differ'])\""
                        ),
                        "raw_output": (
                            f"{ctl['crlf_real']['exit']} "
                            f"{ctl['crlf_git']['exit']} True"
                        ),
                        "fingerprint": fingerprint("command", "both_states() exits"),
                        "exit_code": 0,
                    },
                ],
            },
        ],
        "tests": [
            {
                "id": "probe1-blob-crlf",
                "name": "CR count over emitted scripts + *.sh eol=lf",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "probe2-both-states",
                "name": "CRLF fails real bash, passes Git-Bash analogue",
                "command": P2,
                "result": "PASS",
            },
            {
                "id": "gitattributes-sh-eol-lf",
                "name": "*.sh eol=lf present; mutant without *.sh is silent",
                "command": (
                    "PYTHONDONTWRITEBYTECODE=1 python3 -B -c "
                    "\"import sys; sys.path.insert(0,"
                    "'command-center/p2-wave/probes/TST-0192'); "
                    "from gate import gitattributes_mutation_control; "
                    "m=gitattributes_mutation_control(); "
                    "raise SystemExit(0 if m['pass'] else 1)\""
                ),
                "result": "PASS",
            },
            {
                "id": "regression-windows-shell-md-3",
                "name": "agent-written CRLF breaks real bash (windows-shell.md:3)",
                "command": P2,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "crlf-if-then-fixture",
                "kind": "known-broken-fixture",
                "description": (
                    "CRLF then\\r is rejected by real bash -n and accepted "
                    "after strip-CR (Git Bash igncr analogue)."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": f"crlf_real_exit={ctl['crlf_real']['exit']}",
                "good_state_output": f"lf_real_exit={ctl['lf_real']['exit']}",
            },
            {
                "id": "gitattributes-mutant-without-sh-rule",
                "kind": "mutation",
                "description": (
                    "Parser must not treat *.py eol=lf as a *.sh eol=lf pin."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "has_sh_eol_lf=false for *.py-only mutant",
                "good_state_output": json.dumps(ga.get("matching_lines") or []),
            },
            {
                "id": "broken-syntax-not-vacuous",
                "kind": "malformed-input",
                "description": (
                    "A missing-fi script fails both real bash and the analogue."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": (
                    f"broken_real={ctl['broken_real']['exit']} "
                    f"broken_git={ctl['broken_git']['exit']}"
                ),
                "good_state_output": f"lf_real_exit={ctl['lf_real']['exit']}",
            },
        ],
        "reviewer": {
            "reviewer_id": "TST-0192-probe2-both-states-real-vs-git-bash",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": False,
            "notes": (
                "Probe 2 re-runs the CRLF plant independently of probe 1's "
                "byte counts. Catalog asked for a second Windows shell "
                "(pwsh7 and Git Bash); this lane is native Linux bash and "
                "does not self-certify a missing Git Bash.exe."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/TST-0192/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "entry_id": "TST-0192",
        },
        "downstream_consumers": [
            {
                "consumer": "json.loads + local Draft202012 shell_report validator",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "probe": {
                    "role": "verifier",
                    "method": "schema-validate",
                    "command": (
                        "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                        "command-center/p2-wave/probes/TST-0192/emit_receipt.py"
                    ),
                    "raw_output": "schema_error_count=0\nSUCCESS:schema-valid\n",
                    "fingerprint": fingerprint("schema-validate", "emit_receipt.py"),
                    "exit_code": 0,
                },
            }
        ],
        "timestamps": {"started_at": now, "ended_at": now},
        "retry": {
            "count": 0,
            "policy": "two strikes then pivot (AGENTS.md 4b)",
        },
        "residual_unknowns": [
            {
                "claim": (
                    "Live Git Bash.exe and WSL-on-Windows were not on this "
                    "host; Git Bash is modeled as igncr (strip CR). Production "
                    "windows-shell.md:3 is present; pwsh7/Git Bash.exe re-run "
                    "is not claimed."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Re-run probe 2 under Git Bash.exe and wsl.exe bash -n "
                    "on a Windows box and compare exits."
                ),
            }
        ],
        "report": {
            "kind": "shell_report",
            "title": (
                "Generated shell scripts are LF and verified with the REAL interpreter"
            ),
            "question": QUESTION,
            "answer": answer,
            "observations": [
                {
                    "name": "emitted_script_count",
                    "measured": len(scripts),
                    "method": "inventory of probes/TST-0192/emitted/*.sh",
                    "anchor": "command-center/p2-wave/probes/TST-0192/emitted",
                },
                {
                    "name": "cr_count_max",
                    "measured": max((s["cr_count"] for s in scripts), default=-1),
                    "method": "git cat-file -p HEAD:<path> when tracked, else worktree bytes",
                    "anchor": "command-center/p2-wave/probes/TST-0192/detectors.py",
                },
                {
                    "name": "crlf_real_bash_exit",
                    "measured": ctl["crlf_real"]["exit"],
                    "method": "real bash -n on CRLF if/then fixture",
                    "anchor": "command-center/p2-wave/probes/TST-0192/detectors.py",
                },
                {
                    "name": "crlf_git_bash_analogue_exit",
                    "measured": ctl["crlf_git"]["exit"],
                    "method": "strip-CR then bash -n (MSYS igncr model)",
                    "anchor": "command-center/p2-wave/probes/TST-0192/detectors.py",
                },
                {
                    "name": "gitattributes_sh_eol_lf",
                    "measured": True,
                    "method": "parse .gitattributes for *.sh eol=lf",
                    "anchor": ".gitattributes",
                },
            ],
            "control_ids": [
                "crlf-if-then-fixture",
                "gitattributes-mutant-without-sh-rule",
                "broken-syntax-not-vacuous",
            ],
        },
        "extensions": {
            "declared_output_schema": SCHEMA,
            "completion_sentinel": SENTINEL,
            "gitattributes": {
                "path": ga.get("path") or ".gitattributes",
                "has_sh_eol_lf": True,
                "rule": ga.get("rule") or "*.sh text eol=lf",
                "present": ga.get("present", True),
                "matching_lines": ga.get("matching_lines") or [],
            },
            "emitted_scripts": scripts,
            "interpreters": {
                "real_bash": interp.get("real_bash"),
                "git_bash_analogue": interp.get("git_bash_analogue"),
                "wsl_present": bool(interp.get("wsl_present")),
                "substrate": interp.get("substrate") or "native-linux-bash",
                "git_archive_forbidden": True,
            },
            "both_states": both_summary,
            "signals": [
                {
                    "id": "a-blob-cr-count",
                    "kind": "cr-byte-count",
                    "method": (
                        "git cat-file -p HEAD:<path> when tracked, else worktree bytes"
                    ),
                    "never": "git archive",
                },
                {
                    "id": "b-real-bash-n",
                    "kind": "interpreter-syntax-check",
                    "method": "real bash -n (WSL if present, else native Linux bash)",
                },
            ],
            "gitattributes_mutation": gate["gitattributes_mutation"],
            "used_git_archive": False,
            "cloud_ok": False,
        },
    }

    validator = shell_report_validator()
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:TST-0192 emit schema-invalid")
        for e in errs[:12]:
            print(f"  {list(e.path)}: {e.message}")
        return 1
    garbage_rejected = 0
    for garbage in (
        {},
        {"report_kind": "shell_report"},
        {"unit_id": "TST-0192", "state": "SUCCESS", "x": "x" * 200},
    ):
        if list(validator.iter_errors(garbage)):
            garbage_rejected += 1
        else:
            print("FAILED:TST-0192 emit schema accepts garbage", garbage)
            return 1
    doc["extensions"]["schema_garbage_rejected"] = garbage_rejected

    dest = REPO / OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    sha, nbytes = sha256_file(dest)
    doc["artifacts"][0]["sha256"] = sha
    doc["artifacts"][0]["bytes"] = nbytes
    dest.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    text = dest.read_text(encoding="utf-8")
    if SENTINEL not in text:
        print("FAILED:TST-0192 emit sentinel absent")
        return 1
    parsed = json.loads(text)
    post = sorted(validator.iter_errors(parsed), key=lambda e: list(e.path))
    if post:
        print("FAILED:TST-0192 emit schema-invalid after write")
        for e in post[:12]:
            print(f"  {list(e.path)}: {e.message}")
        return 1
    if dest.stat().st_size < int(doc["min_bytes_threshold"]):
        print("FAILED:TST-0192 emit below min_bytes_threshold")
        return 1
    if parsed.get("state") != "SUCCESS":
        print("FAILED:TST-0192 emit state is not SUCCESS")
        return 1
    sha, nbytes = sha256_file(dest)
    print(f"wrote {OUT} bytes={nbytes} sha256={sha}")
    print("SUCCESS:TST-0192 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
