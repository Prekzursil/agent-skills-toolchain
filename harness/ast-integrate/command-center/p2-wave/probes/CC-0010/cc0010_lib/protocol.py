#!/usr/bin/env python3
"""Hunk-revert causality protocol for CNF-0032.

Copies the fixture subject into an isolated scratch directory (not a git
worktree of the shared checkout), reverse-applies ONE hunk, runs the
associated tests, restores that hunk, and runs the tests again. Never
invokes git add/commit/checkout. Never rewrites the test file.
"""
from __future__ import annotations

import difflib
import hashlib
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SUBJECT = HERE / "fixtures" / "subject"
APP_REL = "app.py"
TEST_REL = "test_app.py"
TEST_CMD = [sys.executable, "-B", TEST_REL]

# Each hunk is unique in app.py. `fixed` is the baseline; `pre` is the
# pre-fix text restored by a reverse apply.
HUNKS = [
    {
        "id": "F1-clamp-ternary",
        "path": APP_REL,
        "expected": "load-bearing",
        "fixed": "    return 0 if n < 0 else n  # CNF-0032-F1\n",
        "pre": "    return n  # CNF-0032-F1-pre\n",
    },
    {
        "id": "F2-tag-comment",
        "path": APP_REL,
        "expected": "non-load-bearing",
        "fixed": "    # tagged for operators  # CNF-0032-F2\n",
        "pre": "    # (no operator tag)  # CNF-0032-F2-pre\n",
    },
    {
        "id": "F3a-div-comment",
        "path": APP_REL,
        "expected": "confounded-change",
        "fixed": "    # handles zero denominator  # CNF-0032-F3a\n",
        "pre": "    # (no zero-denominator note)  # CNF-0032-F3a-pre\n",
    },
    {
        "id": "F3b-div-guard",
        "path": APP_REL,
        "expected": "load-bearing",
        "fixed": "        return None  # CNF-0032-F3b\n",
        "pre": "        return num / den  # CNF-0032-F3b-pre\n",
    },
]


class ProtocolError(RuntimeError):
    pass


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def unified_diff(path: str, old: str, new: str) -> str:
    return "".join(
        difflib.unified_diff(
            old.splitlines(keepends=True),
            new.splitlines(keepends=True),
            fromfile=f"a/{path}",
            tofile=f"b/{path}",
            lineterm="\n",
        )
    )


def _refuse_test_path(rel: str) -> None:
    name = Path(rel).name.lower()
    if name.startswith("test_") or name.endswith("_test.py") or name == TEST_REL:
        raise ProtocolError(f"refused: tests must stay intact ({rel})")


def apply_swap(root: Path, rel: str, src: str, dst: str) -> None:
    _refuse_test_path(rel)
    path = root / rel
    text = path.read_text(encoding="utf-8")
    n = text.count(src)
    if n != 1:
        raise ProtocolError(f"{rel}: hunk anchor matched {n} times, want 1")
    path.write_text(text.replace(src, dst, 1), encoding="utf-8")


def run_tests(root: Path) -> dict:
    p = subprocess.run(
        TEST_CMD,
        cwd=str(root),
        capture_output=True,
        text=True,
        timeout=60,
    )
    tail = ((p.stdout or "") + (p.stderr or "")).strip()[-1500:]
    return {
        "exit_code": int(p.returncode),
        "output_tail": tail,
        "is_red": p.returncode != 0,
        "is_green": p.returncode == 0,
    }


def examine_one(hunk: dict, scratch: Path) -> dict:
    test_before = sha256_file(scratch / TEST_REL)
    app_before = sha256_file(scratch / APP_REL)
    apply_swap(scratch, hunk["path"], hunk["fixed"], hunk["pre"])
    reverted = run_tests(scratch)
    apply_swap(scratch, hunk["path"], hunk["pre"], hunk["fixed"])
    restored = run_tests(scratch)
    test_after = sha256_file(scratch / TEST_REL)
    app_after = sha256_file(scratch / APP_REL)
    if test_before != test_after:
        raise ProtocolError(f"{hunk['id']}: test file mutated")
    if app_before != app_after:
        raise ProtocolError(f"{hunk['id']}: subject not restored")

    if reverted["is_red"] and restored["is_green"]:
        classification = "load-bearing"
    elif (not reverted["is_red"]) and restored["is_green"]:
        classification = (
            "confounded-change"
            if hunk["expected"] == "confounded-change"
            else "non-load-bearing"
        )
    else:
        classification = "repro-not-reproducible"

    return {
        "id": hunk["id"],
        "path": hunk["path"],
        "hunk": {
            "old_text": hunk["pre"],
            "new_text": hunk["fixed"],
            "unified_diff": unified_diff(hunk["path"], hunk["pre"], hunk["fixed"]),
        },
        "test_command": [str(x) for x in TEST_CMD],
        "revert": {
            "exit_code": reverted["exit_code"],
            "is_red": reverted["is_red"],
            "output_tail": reverted["output_tail"],
        },
        "restore": {
            "exit_code": restored["exit_code"],
            "is_green": restored["is_green"],
            "output_tail": restored["output_tail"],
        },
        "classification": classification,
        "expected": hunk["expected"],
        "same_session": True,
        "tests_intact": True,
        "test_sha256": test_before,
        "matched_revert_red_restore_green": bool(
            reverted["is_red"] and restored["is_green"]
        ),
    }


def refuse_test_revert_control(scratch: Path) -> dict:
    raised = False
    message = ""
    try:
        apply_swap(
            scratch,
            TEST_REL,
            "from app import clamp_non_negative, divide_or_none, tag\n",
            "from app import clamp_non_negative\n",
        )
    except ProtocolError as exc:
        raised = True
        message = str(exc)
    return {
        "attempted_path": TEST_REL,
        "refused": raised,
        "message": message,
        "tests_sha256": sha256_file(scratch / TEST_REL),
    }


def run_protocol() -> dict:
    if not (SUBJECT / APP_REL).is_file() or not (SUBJECT / TEST_REL).is_file():
        raise ProtocolError("fixture subject missing")
    fixture_app = sha256_file(SUBJECT / APP_REL)
    fixture_test = sha256_file(SUBJECT / TEST_REL)
    with tempfile.TemporaryDirectory(prefix="cnf0032-scratch-") as tmp:
        scratch = Path(tmp) / "subject"
        shutil.copytree(SUBJECT, scratch)
        baseline = run_tests(scratch)
        if not baseline["is_green"]:
            raise ProtocolError(
                f"baseline tests red in scratch: {baseline['output_tail'][-400:]}"
            )
        rows = [examine_one(h, scratch) for h in HUNKS]
        refuse = refuse_test_revert_control(scratch)
        scratch_was = tmp

    if sha256_file(SUBJECT / APP_REL) != fixture_app:
        raise ProtocolError("shared fixture app.py mutated")
    if sha256_file(SUBJECT / TEST_REL) != fixture_test:
        raise ProtocolError("shared fixture test_app.py mutated")

    load_bearing = [r for r in rows if r["classification"] == "load-bearing"]
    non_lb = [
        r
        for r in rows
        if r["classification"] in {"non-load-bearing", "confounded-change"}
    ]
    matched = [r for r in rows if r["matched_revert_red_restore_green"]]
    return {
        "rows": rows,
        "baseline_green": True,
        "refuse_test_revert": refuse,
        "fixture_app_sha256": fixture_app,
        "fixture_test_sha256": fixture_test,
        "scratch_prefix": "cnf0032-scratch-",
        "scratch_was": scratch_was,
        "counts": {
            "examined": len(rows),
            "load_bearing": len(load_bearing),
            "non_load_bearing": len(non_lb),
            "matched_revert_red_restore_green": len(matched),
        },
        "git_add_commit_checkout_not_used": True,
        "shared_checkout_untouched": True,
    }


def main() -> int:
    try:
        result = run_protocol()
    except ProtocolError as exc:
        print(f"FAILED:CNF-0032-protocol {exc}")
        return 1
    counts = result["counts"]
    print(
        "examined={examined} load_bearing={load_bearing} "
        "non_load_bearing={non_load_bearing} "
        "matched={matched_revert_red_restore_green}".format(**counts)
    )
    print(f"test_revert_refused={result['refuse_test_revert']['refused']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
