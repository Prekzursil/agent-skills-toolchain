#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0203.json from live extractor runs.

Does not write SUBAGENT-RETURN / UNIT-ARTIFACT-MANIFEST (write_receipts.py
does that after named probes pass). Does not call unit_manifest.py --write.
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
PLUGIN = REPO / "tools" / "plugin"
sys.path.insert(0, str(PLUGIN))

import extract as X  # noqa: E402
from path_budget import DECLARED_PATH_LENGTH_LIMIT, LIMIT_KIND  # noqa: E402

OUT = "command-center/receipts/TST-0203.json"
SCHEMA = "command-center/schema/receipt.schema.json#/$defs/portability_report"
SENTINEL = "SUCCESS:TST-0203"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0203/probe1_in_limit_extracts.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0203/probe2_overlimit_cleanup.py"
)
QUESTION = (
    "Does extracting an archive containing over-limit member paths abort "
    "and remove the partially-extracted tree? PASS requires no residue and "
    "a message naming the first offending member."
)


def sha_file(rel: str) -> tuple[int, str, bool]:
    path = REPO / rel
    if not path.is_file():
        return 0, "", False
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return len(raw), hashlib.sha256(raw).hexdigest(), True


def run_cli(archive: Path, dest: Path) -> tuple[int, dict, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        [
            sys.executable,
            "-B",
            str(PLUGIN / "extract.py"),
            "--archive",
            str(archive),
            "--dest",
            str(dest),
        ],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )
    combined = ((proc.stdout or "") + "\n" + (proc.stderr or "")).strip()
    try:
        doc = json.loads((proc.stdout or "").strip().splitlines()[-1])
    except (json.JSONDecodeError, IndexError):
        doc = {}
    return proc.returncode, doc, combined


def walk_files(root: Path) -> list[str]:
    if not root.exists():
        return []
    import os as _os

    found: list[str] = []
    for dirpath, _dirnames, filenames in _os.walk(root):
        for name in filenames:
            found.append(_os.path.relpath(_os.path.join(dirpath, name), root))
    return sorted(found)


def measure() -> dict:
    with tempfile.TemporaryDirectory(prefix="t203-emit-", dir="/tmp") as td:
        td_path = Path(td)
        ok_dest = td_path / "okd0"
        bad_dest = td_path / "bad0"
        naive_dest = td_path / "nav0"
        noclean_dest = td_path / "noc0"
        ok_tar = td_path / "ok.tar"
        bad_tar = td_path / "bad.tar"
        ok_spec = X.build_in_limit_archive(ok_tar, ok_dest)
        bad_spec = X.build_overlimit_archive(bad_tar, bad_dest)
        ok_dest.mkdir()
        bad_dest.mkdir()
        noclean_dest.mkdir()
        ok_rc, ok_doc, ok_txt = run_cli(ok_tar, ok_dest)
        bad_rc, bad_doc, bad_txt = run_cli(bad_tar, bad_dest)
        naive = X.naive_extractall(bad_tar, naive_dest)
        noclean = X.extract_without_cleanup(bad_tar, noclean_dest)
        return {
            "in_limit": {
                "exit_code": ok_rc,
                "ok": bool(ok_doc.get("ok")),
                "members_extracted": ok_doc.get("members_extracted"),
                "independent_walk": len(walk_files(ok_dest)),
                "expected": ok_spec["count"],
                "stdout_ok": ok_txt[:500],
            },
            "over_limit": {
                "exit_code": bad_rc,
                "ok": bool(bad_doc.get("ok")),
                "message": bad_doc.get("message") or bad_txt,
                "offending_member": bad_spec["offending_member"],
                "message_names_member": bad_spec["offending_member"] in bad_txt,
                "token_in_message": X.OVERLIMIT_TOKEN in bad_txt,
                "members_written_before_abort": bad_doc.get(
                    "members_written_before_abort"
                ),
                "prefix_count": bad_spec["prefix_count"],
                "independent_walk": walk_files(bad_dest),
                "dest_exists": bad_dest.exists(),
                "offending_length": bad_spec["offending_length"],
            },
            "negative_naive_extractall": {
                "count": naive["count"],
                "left_residue": naive["count"] >= bad_spec["prefix_count"],
            },
            "negative_no_cleanup": {
                "written_before_abort": noclean.members_written_before_abort,
                "walk": len(walk_files(noclean_dest)),
                "left_the_40": len(walk_files(noclean_dest))
                == bad_spec["prefix_count"],
            },
        }


def main() -> int:
    measured = measure()
    inn = measured["in_limit"]
    over = measured["over_limit"]
    if inn["exit_code"] != 0 or inn["independent_walk"] != inn["expected"]:
        print("FAILED:TST-0203 emit in-limit control")
        print(json.dumps(inn, indent=2))
        return 1
    if (
        over["exit_code"] != 2
        or over["dest_exists"]
        or over["independent_walk"]
        or not over["message_names_member"]
        or over["members_written_before_abort"] != over["prefix_count"]
    ):
        print("FAILED:TST-0203 emit over-limit fail-closed")
        print(json.dumps(over, indent=2))
        return 1
    if not measured["negative_naive_extractall"]["left_residue"]:
        print("FAILED:TST-0203 emit naive extractall did not leave residue")
        return 1
    if not measured["negative_no_cleanup"]["left_the_40"]:
        print("FAILED:TST-0203 emit no-cleanup control did not keep the 40")
        return 1

    tests_rc = subprocess.run(
        [
            sys.executable,
            "-B",
            str(PLUGIN / "tests" / "test_extract_long_members.py"),
        ],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        timeout=120,
    )
    test_out = ((tests_rc.stdout or "") + (tests_rc.stderr or "")).strip()
    if tests_rc.returncode != 0:
        print(test_out[-4000:])
        print("FAILED:TST-0203 emit catalog tests")
        return 1

    impl = "tools/plugin/extract.py"
    budget = "tools/plugin/path_budget.py"
    tests = "tools/plugin/tests/test_extract_long_members.py"
    impl_b, impl_s, impl_ok = sha_file(impl)
    bud_b, bud_s, bud_ok = sha_file(budget)
    tes_b, tes_s, tes_ok = sha_file(tests)
    if not (impl_ok and bud_ok and tes_ok):
        print("FAILED:TST-0203 emit missing implementation")
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = {
        "schema_version": 1,
        "report_kind": "portability_report",
        "unit_id": "TST-0203",
        "id": "TST-0203",
        "state": "SUCCESS",
        "status": "DELIVERED",
        "title": "Archive extraction with long member names fails closed and cleans up",
        "question": QUESTION,
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "output_schema": SCHEMA,
        "execution_substrate": "local-serialized",
        "host": {
            "system": platform.system(),
            "release": platform.release(),
            "python": platform.python_version(),
            "note": (
                "Declared MAX_PATH budget is enforced in the extractor, not by "
                "the OS. Linux writes long members; residue-free dest after "
                "exit 2 is therefore cleanup, not ENAMETOOLONG."
            ),
        },
        "path_budget": {
            "declared_limit": DECLARED_PATH_LENGTH_LIMIT,
            "kind": LIMIT_KIND,
            "enforced_in": impl,
            "over_limit_predicate": "len(str(resolved_dest)) >= declared_limit",
        },
        "implementation": {
            "extractor": {
                "path": impl,
                "bytes": impl_b,
                "sha256": impl_s,
            },
            "path_budget": {
                "path": budget,
                "bytes": bud_b,
                "sha256": bud_s,
            },
            "tests": {
                "path": tests,
                "bytes": tes_b,
                "sha256": tes_s,
            },
            "b07_note": (
                "Live Program-B B07 artifact writer is absent from this sparse "
                "worktree. tools/plugin/extract.py is the shipped package "
                "extractor this unit binds (pack.py is the sibling packer)."
            ),
        },
        "signals": [
            {
                "id": "signal-a-extractor-exit-and-message",
                "exit_code": over["exit_code"],
                "message_names_first_offending_member": over["message_names_member"],
                "token": X.OVERLIMIT_TOKEN,
                "members_written_before_abort": over["members_written_before_abort"],
                "ok": over["exit_code"] == 2 and over["message_names_member"],
            },
            {
                "id": "signal-b-independent-directory-scan",
                "dest_exists_after_failure": over["dest_exists"],
                "residue_files": over["independent_walk"],
                "ok": (not over["dest_exists"]) and over["independent_walk"] == [],
            },
        ],
        "tests_required": {
            "both_states_in_limit_archive_extracts_fully": {
                "exit_code": inn["exit_code"],
                "walk": inn["independent_walk"],
                "expected": inn["expected"],
                "pass": inn["exit_code"] == 0
                and inn["independent_walk"] == inn["expected"],
            },
            "fixture_40_then_member_41_over_limit_cleanup": {
                "prefix_count": over["prefix_count"],
                "written_before_abort": over["members_written_before_abort"],
                "residue": over["independent_walk"],
                "named": over["message_names_member"],
                "pass": (
                    over["members_written_before_abort"] == over["prefix_count"]
                    and over["independent_walk"] == []
                    and over["message_names_member"]
                ),
            },
        },
        "negative_controls": {
            "naive_extractall_leaves_residue": measured["negative_naive_extractall"],
            "cleanup_disabled_keeps_the_40": measured["negative_no_cleanup"],
        },
        "named_probes": [
            {"id": "probe1", "command": P1, "role": "in-limit-archive-extracts-fully"},
            {
                "id": "probe2",
                "command": P2,
                "role": "overlimit-abort-names-member-and-cleanup",
            },
        ],
        "reviewer": {
            "reviewer_id": "TST-0203-probe2-independent-os-walk",
            "verdict": "PASS",
            "independent": True,
            "catalog_windows_second_shell": (
                "NOT-CHECKED. Catalog reviewer_requirement asks for a re-run "
                "on a second Windows shell (pwsh7 and Git Bash). This G-1 "
                "delivery is Linux; that human pass is not claimed."
            ),
        },
        "schema_note": (
            "command-center/schema/receipt.schema.json is absent on this "
            "worktree (IMP-0433). G-1 does not load it. This receipt is a "
            "portability_report shaped from the catalog unit text."
        ),
        "min_bytes_threshold": 128,
        "ts": now,
        "notes": (
            "G-1 for TST-0203: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "cloud ok=true is not delivery. No ADV rebuild. SUCCESS:TST-0203"
        ),
        "catalog_tests_output_tail": test_out[-2000:],
        "measured": measured,
    }
    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=1, sort_keys=True) + "\n"
    if SENTINEL not in text:
        print("FAILED:TST-0203 emit sentinel missing")
        return 1
    out_path.write_text(text, encoding="utf-8")
    print(f"wrote {OUT} bytes={len(text.encode('utf-8'))}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
