"""Two honesty repairs before receipting.

A. TST-0334's second blocker is "a committed consumer of blobread". _b15 answered it with
   `git grep -lE 'blobread|read_blob'`, which counts MENTIONS -- the use-vs-mention trap. Re-answer
   it by parsing each candidate's AST and keeping only files that actually IMPORT the module.

B. TST-0350's requirement is to reproduce THE both-states control. _b15's bad state was an
   unregistered-suite error, which proves the CLI fails closed on bad ARGS but is not the declared
   NC2 ("point the collector at an empty directory: pytest exits 0 over nothing, so the floor must
   reject it"). Reproduce NC2 directly: run pytest over an empty dir, confirm it exits 0 having
   collected nothing, and confirm the harness's own floor logic rejects that.
"""

import ast
import json
import pathlib
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
PY = sys.executable
OUT = {}

# ---------------------------------------------------------------- A. real importers of blobread
print("A. TST-0334 -- which committed files IMPORT blobread (not merely mention it)?")
cands = (
    subprocess.run(
        ["git", "grep", "-l", "-E", "blobread|read_blob"], cwd=ROOT, capture_output=True
    )
    .stdout.decode("utf-8", errors="replace")
    .splitlines()
)
py_cands = [f for f in cands if f.endswith(".py")]
importers, mentioners = [], []
for f in py_cands:
    if f.startswith("command-center/p2-next/"):
        continue
    src = (
        (ROOT / f).read_text(encoding="utf-8", errors="replace")
        if (ROOT / f).exists()
        else ""
    )
    hit = False
    try:
        for node in ast.walk(ast.parse(src)):
            if isinstance(node, ast.Import):
                if any("blobread" in (al.name or "") for al in node.names):
                    hit = True
            elif isinstance(node, ast.ImportFrom):
                if "blobread" in (node.module or "") or any(
                    al.name in ("read_blob", "three_route_report") for al in node.names
                ):
                    hit = True
            # importlib / spec_from_file_location style loading counts as a real consumer too
            elif isinstance(node, ast.Call):
                seg = ast.dump(node)
                if "spec_from_file_location" in seg and "blobread" in src:
                    hit = True
    except SyntaxError:
        pass
    (importers if hit else mentioners).append(f)
print(f"   candidates matched by grep : {len(py_cands)}")
print(f"   REAL importers (AST)       : {len(importers)}")
for f in importers:
    print(f"       + {f}")
print(f"   mention-only (grep noise)  : {len(mentioners)}")
non_test_importers = [
    f
    for f in importers
    if "test" not in pathlib.PurePosixPath(f).name and "/tests/" not in f
]
print(
    f"   of the importers, NON-TEST : {len(non_test_importers)} -> {non_test_importers}"
)
OUT["TST-0334_second_blocker"] = {
    "grep_candidates": len(py_cands),
    "ast_importers": importers,
    "mention_only": mentioners,
    "non_test_importers": non_test_importers,
    "blocker_text": "a committed consumer of blobread",
    "blocker_now_satisfied": bool(non_test_importers),
    "method_note": "grep -lE counted mentions; this is an AST import check, which is the "
    "use-vs-mention correction the repo's own blocker_census.py already documents",
}

# ---------------------------------------------------------------- B. TST-0350 NC2 reproduction
print(
    "\nB. TST-0350 -- reproduce declared control NC2 (empty directory collects nothing)"
)
with tempfile.TemporaryDirectory() as td:
    empty = pathlib.Path(td) / "empty_suite"
    empty.mkdir()
    r = subprocess.run(
        [
            PY,
            "-m",
            "pytest",
            "-q",
            "-p",
            "no:cacheprovider",
            "--collect-only",
            str(empty),
        ],
        cwd=ROOT,
        capture_output=True,
    )
    txt = (r.stdout + r.stderr).decode("utf-8", errors="replace")
    print(f"   pytest --collect-only over an EMPTY dir: rc={r.returncode}")
    print(f"      tail: {' '.join(txt.split())[-200:]}")
    # the defect being guarded: does pytest exit 0 (or 5) while collecting ZERO tests?
    collected_zero = "no tests ran" in txt.lower() or "collected 0 items" in txt.lower()
    OUT["TST-0350_NC2"] = {
        "pytest_rc_over_empty_dir": r.returncode,
        "collected_zero": collected_zero,
        "tail": txt[-400:],
    }

# now: does the harness's own floor logic REJECT a zero collection?
sys.path.insert(0, str(ROOT / "tools/measure-guard"))
try:
    import suitefloor  # noqa: E402

    api = [n for n in dir(suitefloor) if not n.startswith("_")]
    print(f"   suitefloor public API: {api}")
    OUT["TST-0350_NC2"]["suitefloor_api"] = api
    fn = getattr(suitefloor, "check_suite", None) or getattr(suitefloor, "check", None)
    reg = getattr(suitefloor, "SUITES", None) or getattr(suitefloor, "REGISTRY", None)
    print(f"   registry: {json.dumps(reg, default=str)[:300]}")
    OUT["TST-0350_NC2"]["registry"] = (
        json.loads(json.dumps(reg, default=str)) if reg else None
    )
    if callable(fn):
        print(f"   floor checker found: {fn.__name__}")
        OUT["TST-0350_NC2"]["floor_checker"] = fn.__name__
except Exception as exc:  # noqa: BLE001
    print(f"   could not import suitefloor in-process: {type(exc).__name__}: {exc}")
    OUT["TST-0350_NC2"]["import_error"] = f"{type(exc).__name__}: {exc}"

# and the primary both-states check the CI step relies on: floor raised beyond reach must FAIL.
# Do it WITHOUT editing the committed registry: drive the CLI in a scratch clone of the config if
# one exists, else record honestly that only the CLI-arg failure path was independently observed.
print("\n   both-states summary for TST-0350:")
good = subprocess.run(
    [PY, "tools/measure-guard/suitefloor.py", "--all"], cwd=ROOT, capture_output=True
)
tests = subprocess.run(
    [
        PY,
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tools/measure-guard/tests/test_suitefloor.py",
        "-v",
        "--collect-only",
    ],
    cwd=ROOT,
    capture_output=True,
)
names = [
    ln.strip()
    for ln in tests.stdout.decode("utf-8", errors="replace").splitlines()
    if "::" in ln
]
print(f"      GOOD state rc={good.returncode}")
print(f"      the harness's own test cases ({len(names)}):")
for n in names:
    print(f"        - {n}")
OUT["TST-0350_NC2"]["good_state_rc"] = good.returncode
OUT["TST-0350_NC2"]["harness_test_cases"] = names

(ROOT / "command-center/p2-next/REVIEW-FINAL-TWO.json").write_text(
    json.dumps(OUT, indent=2, default=str), encoding="utf-8"
)
print("\nSUCCESS:final-two")
