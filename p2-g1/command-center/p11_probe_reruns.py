"""P11 - re-run the executable Wave-1/Wave-2 claims and complete the W1-06 both-states control.

Arms:
  A  Wave-1 module set (wfdsl + councilspec + council_protocols + completion-predicate +
     receipt-schema-gate) -> Wave 1 claimed 444 passed, Wave 2 re-confirmed 444.
  B  the 65 flagship blueprint test files -> Wave 2 claimed `1111 passed`.
  C  forge: `tournament` must show BOTH CERTIFIED and REJECTED; `fuse --strategy union` must
     REJECT. Both-states, not a single direction.
  D  W1-06 baseline reproduction: run the HEAD bytes of _mutation_selfcheck.py against a
     RECONSTRUCTED Wave-1 platform/{lib,schema} (from commit edcf9f5b). If that scores 12/12 while
     the same tool scores 0/12 against today's tree, the regression is located in the tree, not the
     tool - which is the control that makes the W1-06 verdict non-circular.
"""

from __future__ import annotations

import io
import json
import re
import subprocess
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path

REPO = Path("C:/Users/Prekzursil/source/ast-integrate")
LIB = REPO / "platform" / "lib"
W1_END = "edcf9f5b"
W3_END = "04e4736c"
OUT: dict[str, object] = {}
SUMMARY = re.compile(r"(\d+) passed(?:, (\d+) skipped)?(?:, (\d+) failed)?")


def run(args: list[str], cwd: Path, timeout: int = 1500) -> dict[str, object]:
    p = subprocess.run(
        args, cwd=str(cwd), capture_output=True, text=True, check=False, timeout=timeout
    )
    tail = (p.stdout + p.stderr).strip().splitlines()
    return {
        "cmd": " ".join(args[-6:]),
        "exit": p.returncode,
        "last_lines": tail[-4:] if tail else [],
        "stdout": p.stdout,
    }


# ---- A: Wave-1 module set ----------------------------------------------------------------------
WAVE1_SET = [
    "wfdsl",
    "councilspec",
    "council_protocols",
    "test_completion_predicate.py",
    "test_receipt_schema_gate.py",
]
a = run(
    [
        sys.executable,
        "-m",
        "pytest",
        *WAVE1_SET,
        "-q",
        "--no-header",
        "-p",
        "no:cacheprovider",
    ],
    LIB,
)
m = SUMMARY.search(a["stdout"] or "")
OUT["A_wave1_module_set"] = {
    "claim": "Wave 1: 444 passed (Wave 2 re-confirmed 444)",
    "exit": a["exit"],
    "measured_passed": int(m.group(1)) if m else None,
    "measured_failed": int(m.group(3)) if m and m.group(3) else 0,
    "tail": a["last_lines"],
}

# ---- B: 65 flagship blueprint tests -------------------------------------------------------------
flagship_ids = []
for p in sorted((REPO / "platform/workflows").glob("*.json")):
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        continue
    if isinstance(d, dict) and d.get("flagship") is True:
        flagship_ids.append(p.stem)
tests_dir = REPO / "platform/lib/workflows"
present = {p.name for p in tests_dir.glob("test_*.py")}
matched, unmatched = [], []
for bid in flagship_ids:
    exact = "test_" + bid.replace("-", "_").replace(".", "_") + ".py"
    if exact in present:
        matched.append(exact)
        continue
    # short-name convention the repo actually uses (bp-arc-01.foo -> test_bp_arc_01.py)
    head = bid.split(".")[0].replace("-", "_")
    cands = [n for n in present if n.startswith("test_" + head)]
    if cands:
        matched.append(sorted(cands)[0])
    else:
        unmatched.append(bid)
uniq = sorted(set(matched))
b = run(
    [
        sys.executable,
        "-m",
        "pytest",
        *[f"workflows/{n}" for n in uniq],
        "-q",
        "--no-header",
        "-p",
        "no:cacheprovider",
    ],
    LIB,
)
mb = SUMMARY.search(b["stdout"] or "")
OUT["B_flagship"] = {
    "claim": "Wave 2: 65 flagship, 65/65 have a test file, `1111 passed`",
    "flagship_blueprints_found": len(flagship_ids),
    "test_files_resolved": len(uniq),
    "flagship_with_no_test_file": unmatched,
    "exit": b["exit"],
    "measured_passed": int(mb.group(1)) if mb else None,
    "measured_failed": int(mb.group(3)) if mb and mb.group(3) else 0,
    "tail": b["last_lines"],
}

# ---- C: forge both-states -----------------------------------------------------------------------
c1 = run([sys.executable, "-m", "foundry.forge", "tournament"], LIB)
c2 = run([sys.executable, "-m", "foundry.forge", "fuse", "--strategy", "union"], LIB)
t = c1["stdout"] or ""
OUT["C_forge_both_states"] = {
    "claim": "Wave 2: forge reaches BOTH CERTIFIED and REJECTED on the same input pair",
    "tournament_exit": c1["exit"],
    "tournament_certified_lines": t.count("CERTIFIED"),
    "tournament_rejected_lines": t.count("REJECTED"),
    "tournament_tail": c1["last_lines"],
    "union_exit": c2["exit"],
    "union_says_rejected": "REJECTED" in (c2["stdout"] or ""),
    "union_tail": c2["last_lines"],
}


# ---- D: W1-06 baseline reproduction against a reconstructed Wave-1 tree --------------------------
def cat(rev: str, rel: str) -> bytes | None:
    r = subprocess.run(
        ["git", "cat-file", "-p", f"{rev}:{rel}"],
        cwd=str(REPO),
        capture_output=True,
        check=False,
    )
    return None if r.returncode else r.stdout


def tree(rev: str, prefix: str) -> list[str]:
    r = subprocess.run(
        ["git", "ls-tree", "-r", "--name-only", rev, "--", prefix],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        check=False,
    )
    return [x for x in r.stdout.split("\n") if x.strip()]


d_result: dict[str, object] = {
    "claim": "W1-06 baseline: the SAME tool bytes score 12/12 against the Wave-1 tree",
}
with tempfile.TemporaryDirectory() as td:
    root = Path(td) / "recon"
    (root / "platform" / "lib").mkdir(parents=True)
    (root / "platform" / "schema").mkdir(parents=True)
    for rel in (
        "platform/lib/completion_predicate.py",
        "platform/lib/test_completion_predicate.py",
    ):
        blob = cat(W1_END, rel)
        if blob is None:
            d_result["setup_error"] = f"missing at {W1_END}: {rel}"
            break
        (root / rel).write_bytes(blob)
    for rel in tree(W1_END, "platform/schema"):
        if rel.endswith(".schema.json"):
            blob = cat(W1_END, rel)
            if blob:
                (root / "platform" / "schema" / rel.rsplit("/", 1)[-1]).write_bytes(
                    blob
                )
    tool_src = (cat(W3_END, "platform/lib/_mutation_selfcheck.py") or b"").decode(
        "utf-8"
    )
    ns: dict[str, object] = {
        "__name__": "p11_recon",
        "__file__": str(root / "platform" / "lib" / "_mutation_selfcheck.py"),
    }
    buf = io.StringIO()
    try:
        with redirect_stdout(buf):
            # `tool_src` is HEAD's own committed platform/lib/_mutation_selfcheck.py, executed
            # against an older checkout of the tree to reconstruct that wave's mutation baseline.
            # Running the CURRENT tool over an OLD tree is the entire point -- it isolates
            # tool-vs-tree as the cause of a baseline disagreement -- and no explicit dispatch
            # can substitute for executing the tool's source. Repo-committed bytes only.
            # semgrep honours a suppression only inline or on the line DIRECTLY above.
            # nosemgrep: quality.opengrep.python-exec-use
            exec(compile(tool_src, "<HEAD tool vs W1 tree>", "exec"), ns)  # noqa: S102
            rc = ns["main"]()  # type: ignore[operator]
        text = buf.getvalue()
        rep = json.loads(text[text.find("{") : text.rfind("}") + 1])
        d_result.update(
            {
                "exit": rc,
                "killed_count": rep.get("killed_count"),
                "survived": rep.get("survived"),
                "mutants_importable": sum(
                    1 for r in rep.get("rows", []) if r.get("mutant_importable")
                ),
            }
        )
    except Exception as exc:
        d_result["exception"] = f"{type(exc).__name__}: {exc}"
        d_result["raw_tail"] = buf.getvalue()[-1500:]
OUT["D_mutation_baseline_reconstruction"] = d_result

dest = REPO / "command-center" / "P11-RERUNS.json"
clean = json.loads(json.dumps(OUT, default=str))
for k in ("A_wave1_module_set", "B_flagship", "C_forge_both_states"):
    if isinstance(clean.get(k), dict):
        clean[k].pop("stdout", None)
dest.write_text(json.dumps(clean, indent=2), encoding="utf-8")
print(json.dumps(clean, indent=2))
print(f"SUCCESS:p11-reruns {dest}")
