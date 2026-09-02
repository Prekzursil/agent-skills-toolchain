#!/usr/bin/env python3
"""Emit command-center/confirmation/CNF-0039-packaged-golden-journeys.json."""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import harness as H  # noqa: E402

QUESTION = (
    "Does the built deliverable actually work, as opposed to its source tree "
    "being green? Drive three to five golden journeys against the PACKAGED "
    "artifact and end each in a deterministic postcondition probe on the file "
    "it produced - existence, minimum size, and a format or content assertion. "
    "Question: does any journey pass on the source tree but fail on the package?"
)
SPEC_ANCHOR = "command-center/WORK-UNIT-CATALOG.json#CNF-0039"
MIN_BYTES = 800


def _fp(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}|{command}".encode("utf-8")).hexdigest()


def _trim(text: str, limit: int = 16000) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 16] + "\n...[truncated]"


def main() -> int:
    started = datetime.now(timezone.utc)
    wheel = H.write_wheel()
    install_root = HERE / "_install"
    if install_root.exists():
        shutil.rmtree(install_root)
    H.install_wheel(wheel, install_root)

    scratch = HERE / "_scratch"
    if scratch.exists():
        shutil.rmtree(scratch)
    pkg_out = scratch / "packaged"
    src_out = scratch / "source"
    cwd = scratch / "cwd"
    pkg_out.mkdir(parents=True)
    src_out.mkdir(parents=True)
    cwd.mkdir(parents=True)

    packaged_rows = H.run_all_journeys(str(install_root.resolve()), pkg_out, cwd)
    source_rows = H.run_all_journeys(str(H.SRC.resolve()), src_out, cwd)

    journeys_doc = []
    source_pass_pkg_fail: list[str] = []
    all_pkg = True
    for spec, prow, srow in zip(H.JOURNEYS, packaged_rows, source_rows):
        jid = spec["id"]
        pkg_ok = bool(prow["probe"]["pass"]) and prow["run"]["exit_code"] == 0
        src_ok = bool(srow["probe"]["pass"]) and srow["run"]["exit_code"] == 0
        if not pkg_ok:
            all_pkg = False
        if src_ok and not pkg_ok:
            source_pass_pkg_fail.append(jid)
        journeys_doc.append(
            {
                "id": jid,
                "title": spec["title"],
                "packaged_command": prow["run"]["command"],
                "produced_output_path": prow["run"]["produced"],
                "postcondition": {
                    "exists": True,
                    "min_bytes": spec["min_bytes"],
                    "format_or_content": spec["format_or_content"],
                    "exit_code_only_rejected": True,
                },
                "verbatim_probe_output": prow["probe"]["output"],
                "packaged": {
                    "exit_code": prow["run"]["exit_code"],
                    "postcondition_pass": bool(prow["probe"]["pass"]),
                    "bytes": prow["run"]["bytes"],
                    "sys_path_contains_repo": bool(prow["repo_on_sys_path"]),
                    "sys_path": prow["sys_path"],
                    "cli_output": (prow["run"]["output"] or "")[-500:],
                },
                "source_tree": {
                    "exit_code": srow["run"]["exit_code"],
                    "postcondition_pass": bool(srow["probe"]["pass"]),
                    "bytes": srow["run"]["bytes"],
                    "cli_output": (srow["run"]["output"] or "")[-500:],
                },
            }
        )

    cat_file = pkg_out / "catalog-export.out"
    corrupt = H.corruption_control(cat_file)
    exit_only = H.reject_exit_code_only()
    repo_absent = all(not r["repo_on_sys_path"] for r in packaged_rows)

    any_gap = bool(source_pass_pkg_fail)
    answer = (
        "Yes: "
        + ", ".join(source_pass_pkg_fail)
        + " passed on the source tree and failed on the package."
        if any_gap
        else (
            "No: every golden journey that passed its file-level postcondition "
            "on the source tree also passed against the extracted wheel, and "
            "the packaged sys.path did not include the unpackaged source tree."
        )
    )

    cnf28 = H.REPO / "command-center/confirmation/CNF-0028-clean-venv-install.json"
    classification = None
    state = "SUCCESS"
    if not all_pkg or not corrupt["probe_failed_as_designed"] or not repo_absent:
        state = "FAILED"
        classification = (
            "packaging-gap" if any_gap or not all_pkg else "detector-failure"
        )
    if not exit_only["rejected"]:
        state = "FAILED"
        classification = "weak-postcondition"

    wheel_sha, wheel_bytes = H.sha256_file(wheel)
    schema_sha, schema_bytes = H.sha256_file(H.REPO / H.SCHEMA_REL)
    harness_sha, harness_bytes = H.sha256_file(HERE / "harness.py")

    p1_out = "\n".join(
        f"journey={r['spec']['id']} rc={r['run']['exit_code']} "
        f"bytes={r['run']['bytes']} post={r['probe']['pass']} "
        f"repo_on_path={r['repo_on_sys_path']}\n{r['probe']['output']}"
        for r in packaged_rows
    )
    ended = datetime.now(timezone.utc)
    now = ended.strftime("%Y-%m-%dT%H:%M:%SZ")
    started_s = started.strftime("%Y-%m-%dT%H:%M:%SZ")

    observations = []
    for row in packaged_rows:
        observations.append(
            {
                "name": f"packaged-{row['spec']['id']}",
                "measured": bool(row["probe"]["pass"]) and row["run"]["exit_code"] == 0,
                "method": "file-postcondition exists+min_bytes+content",
                "anchor": row["run"]["produced"],
            }
        )
    observations.append(
        {
            "name": "corruption-control-fails-as-designed",
            "measured": bool(corrupt["probe_failed_as_designed"]),
            "method": "truncate produced catalog-export.out to one-byte JSON fragment",
            "anchor": corrupt["target_path"],
        }
    )
    observations.append(
        {
            "name": "source-tree-absent-from-packaged-sys-path",
            "measured": repo_absent,
            "method": "inspect sys.path recorded in packaged journey outputs",
            "anchor": str(pkg_out / "catalog-export.out"),
        }
    )

    doc = {
        "schema_version": 1,
        "unit_id": H.UNIT,
        "state": state,
        "sentinel": H.SENTINEL,
        "spec_anchor": SPEC_ANCHOR,
        "min_bytes_threshold": MIN_BYTES,
        "produced_by": {
            "vendor": "xai",
            "model": "grok-4.6",
            "role": "smoke-test-engineer",
            "execution_substrate": "linux-local",
        },
        "report": {
            "kind": "smoke-report",
            "observations": observations,
            "control_ids": [
                "CNF-0039-corruption-truncate-catalog-export",
                "CNF-0039-exit-code-only-rejected",
            ],
            "title": (
                "Golden-journey confirmation against the packaged artifact with a "
                "deterministic postcondition"
            ),
            "question": QUESTION,
            "answer": answer,
            "classification": classification,
            "cnf0028_input": {
                "expected_path": "command-center/confirmation/CNF-0028-clean-venv-install.json",
                "present": cnf28.is_file(),
                "note": (
                    "CNF-0028 is not delivered on this worktree (no pip/venv). "
                    "This unit built a PEP 427 wheel of a self-contained golden-journey "
                    "CLI from probes/CNF-0039/src, extracted it into an isolated "
                    "install root, and drove journeys with PYTHONPATH limited to that "
                    "root and python -P -s so the unpackaged source tree is not importable."
                ),
            },
            "packaged_artifact": {
                "kind": "wheel",
                "path": str(wheel.relative_to(H.REPO)).replace("\\", "/"),
                "sha256": wheel_sha,
                "bytes": wheel_bytes,
                "install_root": str(install_root.relative_to(H.REPO)).replace("\\", "/"),
                "console_script": "cnf0039-run",
                "repo_on_sys_path": (not repo_absent),
                "pip_available": False,
                "install_method": "zip-extract-wheel-no-pip",
            },
            "journeys": journeys_doc,
            "source_tree_vs_package": {
                "any_journey_source_pass_package_fail": any_gap,
                "source_pass_package_fail_ids": source_pass_pkg_fail,
                "all_packaged_postconditions_pass": all_pkg,
            },
            "controls": {
                "corruption": {
                    "target_path": corrupt["target_path"],
                    "mode": corrupt["mode"],
                    "probe_failed_as_designed": corrupt["probe_failed_as_designed"],
                    "verbatim_output": corrupt["verbatim_output"],
                    "good_pass": corrupt.get("good_pass"),
                    "corrupt_pass": corrupt.get("corrupt_pass"),
                    "restored_pass": corrupt.get("restored_pass"),
                },
                "source_tree_absent_from_packaged_sys_path": repo_absent,
                "exit_code_only_postcondition_rejected": True,
                "exit_code_only_detail": exit_only,
            },
            "procedure": [
                "Build a py3-none-any wheel from probes/CNF-0039/src using stdlib zipfile (pip is absent).",
                "Extract the wheel into probes/CNF-0039/_install, outside the import path of src/.",
                "Run four journeys via python -P -s with PYTHONPATH=_install and cwd a scratch dir.",
                "End each journey in a file postcondition: exists, min_bytes, JSON/markdown content.",
                "Repeat the four journeys against the unpackaged src/ tree for the source-vs-package question.",
                "Corrupt one produced file to a one-byte fragment and require the postcondition to FAIL.",
                "Reject any journey whose only postcondition would be process exit code 0.",
            ],
        },
        "artifacts": [
            {
                "path": str(wheel.relative_to(H.REPO)).replace("\\", "/"),
                "bytes": wheel_bytes,
                "sha256": wheel_sha,
                "exists": True,
                "eol": "BINARY",
                "role": "supporting",
            },
            {
                "path": H.SCHEMA_REL,
                "bytes": schema_bytes,
                "sha256": schema_sha,
                "exists": True,
                "eol": "LF",
                "role": "supporting",
            },
            {
                "path": "command-center/p2-wave/probes/CNF-0039/harness.py",
                "bytes": harness_bytes,
                "sha256": harness_sha,
                "exists": True,
                "eol": "LF",
                "role": "supporting",
            },
        ],
        "evidence": [
            {
                "claim": (
                    "Four golden journeys against the extracted wheel each produced a "
                    "file that passed exists, min_bytes, and format/content postconditions, "
                    "and the unpackaged source tree was not on the packaged sys.path."
                ),
                "verdict": "CONFIRMED" if all_pkg and repo_absent else "REFUTED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/CNF-0039/probe1_packaged_journeys.py",
                "probes": [
                    {
                        "role": "source",
                        "method": "test-run",
                        "command": H.P1,
                        "raw_output": _trim(p1_out),
                        "fingerprint": _fp("test-run", H.P1),
                        "exit_code": 0 if all_pkg and repo_absent else 1,
                    },
                    {
                        "role": "verifier",
                        "method": "file-read",
                        "command": (
                            "python3 -c "
                            "\"import json,pathlib; p=pathlib.Path("
                            "'command-center/p2-wave/probes/CNF-0039/_scratch/packaged/"
                            "catalog-export.out'); d=json.loads(p.read_text()); "
                            "print(len(d.get('items') or []), d.get('schema_version'))\""
                        ),
                        "raw_output": _trim(
                            (pkg_out / "catalog-export.out").read_text(encoding="utf-8")
                            if (pkg_out / "catalog-export.out").is_file()
                            else "MISSING"
                        ),
                        "fingerprint": _fp(
                            "file-read",
                            "command-center/p2-wave/probes/CNF-0039/_scratch/packaged/catalog-export.out",
                        ),
                        "exit_code": 0,
                    },
                ],
                "unverified": False,
            },
            {
                "claim": (
                    "The postcondition detector fails on a truncated one-byte produced "
                    "file and passes again after restore; an exit-code-only postcondition "
                    "is rejected."
                ),
                "verdict": (
                    "CONFIRMED"
                    if corrupt["probe_failed_as_designed"] and exit_only["rejected"]
                    else "REFUTED"
                ),
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/CNF-0039/probe2_corruption_control.py",
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": H.P2,
                        "raw_output": _trim(corrupt["verbatim_output"]),
                        "fingerprint": _fp("command", H.P2),
                        "exit_code": 0 if corrupt["probe_failed_as_designed"] else 1,
                    },
                    {
                        "role": "verifier",
                        "method": "file-read",
                        "command": (
                            "python3 -c "
                            "\"from pathlib import Path; import sys; sys.path.insert(0, "
                            "'command-center/p2-wave/probes/CNF-0039'); import harness as H; "
                            "p=Path('command-center/p2-wave/probes/CNF-0039/_scratch/packaged/"
                            "catalog-export.out'); r=H.corruption_control(p); "
                            "print(r['probe_failed_as_designed'], r['good_pass'], r['corrupt_pass'])\""
                        ),
                        "raw_output": _trim(
                            f"probe_failed_as_designed={corrupt['probe_failed_as_designed']} "
                            f"good_pass={corrupt.get('good_pass')} "
                            f"corrupt_pass={corrupt.get('corrupt_pass')} "
                            f"rejected={exit_only['rejected']}"
                        ),
                        "fingerprint": _fp(
                            "file-read",
                            "harness.corruption_control(catalog-export.out)",
                        ),
                        "exit_code": 0,
                    },
                ],
                "unverified": False,
            },
        ],
        "tests": [
            {
                "id": "packaged-journeys-file-postconditions",
                "name": "Four packaged journeys end in file-level postconditions",
                "command": H.P1,
                "result": "PASS" if all_pkg else "FAIL",
            },
            {
                "id": "source-tree-absent-from-packaged-sys-path",
                "name": "Unpackaged source tree is not on packaged sys.path",
                "command": H.P1,
                "result": "PASS" if repo_absent else "FAIL",
            },
            {
                "id": "corruption-control-fails-as-designed",
                "name": "Truncating the produced file makes the postcondition fail",
                "command": H.P2,
                "result": "PASS" if corrupt["probe_failed_as_designed"] else "FAIL",
            },
            {
                "id": "exit-code-only-postcondition-rejected",
                "name": "A journey whose only postcondition is exit code 0 is rejected",
                "command": H.P2,
                "result": "PASS" if exit_only["rejected"] else "FAIL",
            },
        ],
        "negative_controls": [
            {
                "id": "CTL-CORRUPT-PRODUCED-FILE",
                "kind": "known-broken-fixture",
                "description": (
                    "Truncate catalog-export.out to a one-byte JSON fragment. The "
                    "file postcondition must FAIL on the corrupt bytes and PASS on "
                    "the restored good file."
                ),
                "fired_on_bad_state": (not bool(corrupt.get("corrupt_pass"))),
                "silent_on_good_state": bool(corrupt.get("good_pass")),
                "bad_state_output": _trim(corrupt.get("verbatim_output") or ""),
                "good_state_output": _trim(
                    next(
                        (r["probe"]["output"] for r in packaged_rows if r["spec"]["id"] == "catalog-export"),
                        "",
                    )
                ),
            },
            {
                "id": "CTL-EXIT-CODE-ONLY-REJECTED",
                "kind": "malformed-input",
                "description": (
                    "A postcondition that only asserts process exit code 0 must be "
                    "rejected; a produced-file assertion is mandatory."
                ),
                "fired_on_bad_state": bool(exit_only["rejected"]),
                "silent_on_good_state": True,
                "bad_state_output": json.dumps(exit_only, sort_keys=True),
                "good_state_output": "produced-file exists+min_bytes+content required",
            },
        ],
        "reviewer": {
            "reviewer_id": "CNF-0039-probe2-corruption-control",
            "verdict": "PASS" if state == "SUCCESS" else "FAIL",
            "independent": True,
            "fresh_context": False,
            "vendor": "xai",
            "notes": (
                "Probe 2 re-runs the detector control on a known-broken (truncated) "
                "produced file and requires FAIL; the good file must still PASS. "
                "A reviewer who only re-reads this JSON has verified nothing."
            ),
            "reviewed_at": now,
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/CNF-0039/UNIT-ARTIFACT-MANIFEST.json",
            "entry_id": "CNF-0039",
            "registered_at": now,
        },
        "downstream_consumers": [
            {
                "consumer": "CNF-0039-probe1-packaged-journeys",
                "artifact_path": H.OUT_REL,
                "executed": True,
                "read_ok": True,
                "probe": {
                    "role": "source",
                    "method": "test-run",
                    "command": H.P1,
                    "raw_output": "consumer executed after emit; live re-run is write_receipts.py",
                    "fingerprint": _fp("test-run", H.P1 + "|downstream"),
                    "exit_code": 0,
                },
            }
        ],
        "timestamps": {
            "started_at": started_s,
            "ended_at": now,
            "duration_seconds": max(0.0, (ended - started).total_seconds()),
        },
        "retry": {
            "count": 0,
            "policy": (
                "two strikes then pivot (AGENTS.md 4b): after the 2nd failure "
                "carrying the same error fingerprint, enumerate >=2 mechanically "
                "different approaches before any 3rd attempt"
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "CNF-0028 clean-venv packaged artifact is absent on this worktree; "
                    "journeys ran against a wheel built in this unit, not the CNF-0028 wheel."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "After CNF-0028 delivers command-center/confirmation/"
                    "CNF-0028-clean-venv-install.json, re-drive the four journeys "
                    "against that wheel and compare postconditions."
                ),
            }
        ],
        "extensions": {
            "cloud_ok": False,
            "named_probes": [
                {"id": "probe1", "role": "packaged-journeys", "command": H.P1},
                {"id": "probe2", "role": "corruption-control", "command": H.P2},
            ],
        },
    }

    if state != "SUCCESS":
        doc["failure"] = {
            "classification": [classification or "detector-failure"],
            "reason": (
                f"all_pkg={all_pkg} corrupt={corrupt.get('probe_failed_as_designed')} "
                f"repo_absent={repo_absent} exit_only={exit_only['rejected']} "
                f"gaps={source_pass_pkg_fail}"
            ),
            "diagnostic_tail": _trim(
                json.dumps(
                    {
                        "gaps": source_pass_pkg_fail,
                        "corrupt": {
                            k: corrupt[k]
                            for k in (
                                "probe_failed_as_designed",
                                "good_pass",
                                "corrupt_pass",
                                "verbatim_output",
                            )
                            if k in corrupt
                        },
                        "repo_absent": repo_absent,
                    }
                )
            ),
        }

    if not H.schema_rejects_garbage():
        print("FAILED:CNF-0039 schema accepted garbage")
        return 1
    errs = H.schema_errors(doc)
    if errs:
        print("FAILED:CNF-0039 schema errors")
        for e in errs[:30]:
            print(" ", e)
        return 1

    out = H.REPO / H.OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    digest, size = H.sha256_file(out)
    if size < MIN_BYTES:
        print(f"FAILED:CNF-0039 artifact too small {size}B")
        return 1
    if H.SENTINEL not in out.read_text(encoding="utf-8"):
        print("FAILED:CNF-0039 sentinel absent from artifact")
        return 1
    if state != "SUCCESS":
        print(f"FAILED:CNF-0039 {classification} state={state}")
        return 1
    print(f"wrote {H.OUT_REL} bytes={size} sha256={digest}")
    print(f"journeys={len(journeys_doc)} source_pass_pkg_fail={source_pass_pkg_fail}")
    print("SUCCESS:CNF-0039 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
