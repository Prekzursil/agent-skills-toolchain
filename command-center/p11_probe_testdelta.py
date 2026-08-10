"""P11 - "no unrelated regression" (spec :11150) done as a SET difference, not a count comparison.

A pass count rising 444 -> 515 does not prove nothing was removed: an addition of 80 and a deletion
of 9 also rises. So diff the actual test-function NAMES defined in the Wave-1 module set, AST-parsed
from committed blobs at edcf9f5b versus the working tree. Any name present then and absent now is a
candidate silent regression and is listed by file.
"""

from __future__ import annotations

import ast
import json
import subprocess
from pathlib import Path

REPO = Path("C:/Users/Prekzursil/source/ast-integrate")
W1_END = "edcf9f5b"
PREFIXES = (
    "platform/lib/wfdsl",
    "platform/lib/councilspec",
    "platform/lib/council_protocols",
    "platform/lib/test_completion_predicate.py",
    "platform/lib/test_receipt_gate.py",
    "platform/lib/test_receipt_schema_gate.py",
)


def ls(rev: str) -> list[str]:
    r = subprocess.run(
        ["git", "ls-tree", "-r", "--name-only", rev, "--", *PREFIXES],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        check=False,
    )
    return [
        x
        for x in r.stdout.split("\n")
        if x.endswith(".py")
        and "/test_" in x
        or x.endswith(".py")
        and x.rsplit("/", 1)[-1].startswith("test_")
    ]


def blob(rev: str, rel: str) -> str | None:
    r = subprocess.run(
        ["git", "cat-file", "-p", f"{rev}:{rel}"],
        cwd=str(REPO),
        capture_output=True,
        check=False,
    )
    return None if r.returncode else r.stdout.decode("utf-8", errors="replace")


def testnames(src: str) -> set[str]:
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return set()
    out: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(
            node, (ast.FunctionDef, ast.AsyncFunctionDef)
        ) and node.name.startswith("test_"):
            out.add(node.name)
        if isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
            for sub in node.body:
                if isinstance(
                    sub, (ast.FunctionDef, ast.AsyncFunctionDef)
                ) and sub.name.startswith("test_"):
                    out.add(f"{node.name}::{sub.name}")
    return out


old_files = sorted(set(ls(W1_END)))
old: dict[str, set[str]] = {}
for f in old_files:
    s = blob(W1_END, f)
    if s is not None:
        old[f] = testnames(s)

new: dict[str, set[str]] = {}
for f in old_files:
    p = REPO / f
    if p.is_file():
        new[f] = testnames(p.read_text(encoding="utf-8", errors="replace"))
    else:
        new[f] = set()

# a renamed file still counts as present if its tests moved anywhere in platform/lib
all_now: set[str] = set()
for p in (REPO / "platform" / "lib").rglob("test_*.py"):
    all_now |= testnames(p.read_text(encoding="utf-8", errors="replace"))

removed_per_file, truly_gone, moved = {}, [], {}
for f, names in old.items():
    gone = sorted(names - new.get(f, set()))
    if gone:
        removed_per_file[f] = gone
        for g in gone:
            if g in all_now:
                moved.setdefault(f, []).append(g)
            else:
                truly_gone.append({"file": f, "test": g})

added = {
    f: sorted(new.get(f, set()) - names)
    for f, names in old.items()
    if new.get(f, set()) - names
}

OUT = {
    "anchor": W1_END,
    "wave1_test_files_examined": len(old_files),
    "wave1_test_functions_total": sum(len(v) for v in old.values()),
    "now_test_functions_in_same_files": sum(len(v) for v in new.values()),
    "file_missing_now": [f for f in old_files if not (REPO / f).is_file()],
    "removed_from_their_original_file": removed_per_file,
    "removed_but_FOUND_elsewhere_in_platform_lib": moved,
    "REMOVED_AND_NOWHERE_IN_PLATFORM_LIB": truly_gone,
    "added_since_wave1_per_file_counts": {f: len(v) for f, v in added.items()},
    "verdict": (
        "NO SILENT REMOVAL - every Wave-1 test function is still defined somewhere in platform/lib"
        if not truly_gone
        else f"{len(truly_gone)} Wave-1 test function(s) no longer exist anywhere"
    ),
}
dest = REPO / "command-center" / "P11-TEST-DELTA.json"
dest.write_text(json.dumps(OUT, indent=2), encoding="utf-8")
print(json.dumps(OUT, indent=2)[:4000])
print(f"SUCCESS:p11-testdelta {dest}")
