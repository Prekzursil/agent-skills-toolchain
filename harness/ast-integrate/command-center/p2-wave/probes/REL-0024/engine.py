"""Fail-first regression seeder for REL-0024.

Scratch git product (two commits), one oracle per harvested defect,
accept only RED-then-GREEN, reject green-on-both trivia, wire accepted
tests into a B08 seeded suite, prove the suite goes RED at the pre-fix
SHA (delete-the-fix CI).

Host worktree /opt/p2/ast-integrate is a refused git cwd.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from corpus import DEFECTS, sibling_unit_ids

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
HOST = REPO.resolve()
BROKEN = HERE / "subject_broken.py"
FIXED = HERE / "subject_fixed.py"
RECEIPTS = REPO / "command-center" / "receipts"
SUITE_ID = "B08-seeded-regression"
CLOCK = "time.time_ns"

GIT_ENV = {
    **os.environ,
    "GIT_AUTHOR_NAME": "REL-0024",
    "GIT_AUTHOR_EMAIL": "rel-0024@local.test",
    "GIT_COMMITTER_NAME": "REL-0024",
    "GIT_COMMITTER_EMAIL": "rel-0024@local.test",
    "GIT_AUTHOR_DATE": "2026-08-24T00:00:00Z",
    "GIT_COMMITTER_DATE": "2026-08-24T00:00:00Z",
    "GIT_CONFIG_GLOBAL": "/dev/null",
    "GIT_CONFIG_SYSTEM": "/dev/null",
    "GIT_CONFIG_NOSYSTEM": "1",
    "PYTHONDONTWRITEBYTECODE": "1",
}

TRIVIAL_SRC = (
    "# trivial always-pass candidate — must be rejected\n"
    "def test():\n"
    "    assert True\n"
    "\n"
    'if __name__ == "__main__":\n'
    "    test()\n"
    '    print("PASS")\n'
)


def _refuse_host_git(cwd: Path) -> None:
    cwd = cwd.resolve()
    if cwd == HOST or HOST in cwd.parents:
        raise RuntimeError(f"refused git cwd inside host worktree: {cwd}")


def _git(args: list[str], cwd: Path) -> str:
    _refuse_host_git(cwd)
    p = subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        env=GIT_ENV,
        capture_output=True,
        text=True,
        timeout=60,
    )
    if p.returncode != 0:
        raise RuntimeError(
            f"git {args} failed rc={p.returncode} stderr={p.stderr!r} stdout={p.stdout!r}"
        )
    return (p.stdout or "").strip()


def harvest() -> tuple[list[dict], dict]:
    present = 0
    absent_ids: list[str] = []
    rows: list[dict] = []
    for uid in sibling_unit_ids():
        path = RECEIPTS / f"{uid}.json"
        rel = str((RECEIPTS / f"{uid}.json").relative_to(REPO)).replace("\\", "/")
        if path.is_file() and path.stat().st_size > 0:
            present += 1
            rows.append({"unit_id": uid, "receipt_present": True, "path": rel})
        else:
            absent_ids.append(uid)
            rows.append(
                {
                    "unit_id": uid,
                    "receipt_present": False,
                    "path": rel,
                    "reason": "source-unit-receipt-absent",
                }
            )
    defects = [
        {
            "defect_id": d["defect_id"],
            "source_unit": d["source_unit"],
            "failure_class": d["failure_class"],
            "origin": "fixture-seeded-from-catalog-class",
            "fn": d["fn"],
            "args": d["args"],
            "expected": d["expected"],
        }
        for d in DEFECTS
    ]
    census = {
        "expected_emitters": len(sibling_unit_ids()),
        "receipts_present": present,
        "receipts_absent": len(absent_ids),
        "absent_ids": absent_ids,
        "rows": rows,
    }
    return defects, census


def render_oracle(defect: dict) -> str:
    args_lit = json.dumps(defect["args"])
    exp_lit = json.dumps(defect["expected"])
    fn = defect["fn"]
    did = defect["defect_id"]
    return (
        f"# generated fail-first oracle for {did}\n"
        "import json\n"
        "import ceremony_gates as g\n"
        f"ARGS = json.loads({args_lit!r})\n"
        f"EXPECTED = json.loads({exp_lit!r})\n"
        "\n"
        "def test():\n"
        f"    got = getattr(g, {fn!r})(*ARGS)\n"
        "    if got != EXPECTED:\n"
        '        raise AssertionError(f"got={got!r} expected={EXPECTED!r}")\n'
        "\n"
        'if __name__ == "__main__":\n'
        "    test()\n"
        '    print("PASS")\n'
    )


def run_oracle(gates_src: str, test_src: str) -> str:
    with tempfile.TemporaryDirectory(prefix="rel0024-oracle-") as td:
        root = Path(td)
        (root / "ceremony_gates.py").write_text(
            gates_src, encoding="utf-8", newline="\n"
        )
        (root / "test_one.py").write_text(test_src, encoding="utf-8", newline="\n")
        env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
        p = subprocess.run(
            [sys.executable, "-B", "test_one.py"],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=30,
            env=env,
        )
        return "GREEN" if p.returncode == 0 else "RED"


def run_b08(gates_src: str, tests: list[dict]) -> dict:
    outcomes = []
    n_red = 0
    for t in tests:
        oc = run_oracle(gates_src, t["src"])
        outcomes.append({"test_id": t["test_id"], "outcome": oc})
        if oc != "GREEN":
            n_red += 1
    if not tests or n_red:
        suite = "RED"
    else:
        suite = "GREEN"
    return {
        "suite_id": SUITE_ID,
        "n_tests": len(tests),
        "n_red": n_red,
        "n_green": len(tests) - n_red,
        "suite_outcome": suite,
        "outcomes": outcomes,
    }


def _sanity_subjects(defects: list[dict]) -> None:
    if str(HERE) not in sys.path:
        sys.path.insert(0, str(HERE))
    import subject_broken as broken  # noqa: WPS433
    import subject_fixed as fixed  # noqa: WPS433

    for d in defects:
        fn = d["fn"]
        args = d["args"]
        exp = d["expected"]
        b = getattr(broken, fn)(*args)
        f = getattr(fixed, fn)(*args)
        if b == exp:
            raise RuntimeError(
                f"broken subject already matches oracle for {d['defect_id']}: {b!r}"
            )
        if f != exp:
            raise RuntimeError(
                f"fixed subject misses oracle for {d['defect_id']}: got {f!r} expected {exp!r}"
            )


def build_product_repo(scratch: Path) -> tuple[str, str, str, str]:
    _refuse_host_git(scratch)
    broken_src = BROKEN.read_text(encoding="utf-8")
    fixed_src = FIXED.read_text(encoding="utf-8")
    _git(["init", "-b", "main"], scratch)
    _git(["config", "user.name", "REL-0024"], scratch)
    _git(["config", "user.email", "rel-0024@local.test"], scratch)
    gates = scratch / "ceremony_gates.py"
    gates.write_text(broken_src, encoding="utf-8", newline="\n")
    _git(["add", "--", "ceremony_gates.py"], scratch)
    _git(["commit", "-m", "pre-fix: planted ceremony defects"], scratch)
    pre = _git(["rev-parse", "HEAD"], scratch)
    gates.write_text(fixed_src, encoding="utf-8", newline="\n")
    _git(["add", "--", "ceremony_gates.py"], scratch)
    _git(["commit", "-m", "post-fix: ceremony defects closed"], scratch)
    post = _git(["rev-parse", "HEAD"], scratch)
    if len(pre) != 40 or len(post) != 40:
        raise RuntimeError(f"expected sha1, got pre={pre!r} post={post!r}")
    if pre == post:
        raise RuntimeError("pre-fix and post-fix SHAs are identical")
    pre_src = _git(["show", f"{pre}:ceremony_gates.py"], scratch)
    post_src = _git(["show", f"{post}:ceremony_gates.py"], scratch)
    return pre, post, pre_src, post_src


def generate(
    defects: list[dict], pre_src: str, post_src: str, pre: str, post: str
) -> dict:
    accepted: list[dict] = []
    rejected: list[dict] = []
    mapping: list[dict] = []
    unmapped: list[dict] = []

    triv_pre = run_oracle(pre_src, TRIVIAL_SRC)
    triv_post = run_oracle(post_src, TRIVIAL_SRC)
    trivial = {
        "candidate_id": "CAND-trivial-always-pass",
        "reason": "green-on-both-commits",
        "pre_fix_outcome": triv_pre,
        "post_fix_outcome": triv_post,
    }
    if triv_pre != "GREEN" or triv_post != "GREEN":
        raise RuntimeError(f"trivial candidate was not green-on-both: {trivial}")
    rejected.append(trivial)

    for d in defects:
        src = render_oracle(d)
        pre_oc = run_oracle(pre_src, src)
        post_oc = run_oracle(post_src, src)
        test_id = f"SEED-{d['source_unit']}-01"
        if pre_oc == "RED" and post_oc == "GREEN":
            accepted.append(
                {
                    "test_id": test_id,
                    "defect_id": d["defect_id"],
                    "pre_fix_sha": pre,
                    "post_fix_sha": post,
                    "pre_fix_outcome": pre_oc,
                    "post_fix_outcome": post_oc,
                    "accepted": True,
                    "src": src,
                }
            )
            mapping.append({"defect_id": d["defect_id"], "test_id": test_id})
        else:
            reason = (
                "green-on-both-commits"
                if pre_oc == "GREEN" and post_oc == "GREEN"
                else f"not-red-then-green:{pre_oc}->{post_oc}"
            )
            rejected.append(
                {
                    "candidate_id": test_id,
                    "reason": reason,
                    "pre_fix_outcome": pre_oc,
                    "post_fix_outcome": post_oc,
                    "defect_id": d["defect_id"],
                }
            )
            unmapped.append({"defect_id": d["defect_id"], "reason": reason})
    return {
        "accepted": accepted,
        "rejected_trivial": [
            r for r in rejected if str(r.get("candidate_id", "")).startswith("CAND-")
        ],
        "mapping": mapping,
        "unmapped": unmapped,
    }


def run() -> dict[str, Any]:
    t0 = time.time_ns()
    defects, census = harvest()
    _sanity_subjects(defects)
    with tempfile.TemporaryDirectory(prefix="rel0024-git-") as td:
        scratch = Path(td)
        pre, post, pre_src, post_src = build_product_repo(scratch)
        gen = generate(defects, pre_src, post_src, pre, post)
        wired = [
            {"test_id": t["test_id"], "defect_id": t["defect_id"], "src": t["src"]}
            for t in gen["accepted"]
        ]
        suite_fixed = run_b08(post_src, wired)
        suite_deleted = run_b08(pre_src, wired)
        t1 = time.time_ns()
        harvested_n = len(defects)
        mapped_n = len(gen["mapping"])
        unmapped_n = len(gen["unmapped"])
        totality = {
            "harvested": harvested_n,
            "mapped": mapped_n,
            "unmapped": unmapped_n,
            "complete": harvested_n == mapped_n + unmapped_n,
        }
        if not gen["accepted"]:
            raise RuntimeError("generator accepted zero tests")
        if any(
            t["pre_fix_outcome"] != "RED" or t["post_fix_outcome"] != "GREEN"
            for t in gen["accepted"]
        ):
            raise RuntimeError("accepted test was not red-then-green")
        if suite_fixed["suite_outcome"] != "GREEN":
            raise RuntimeError(f"B08 on post-fix was not GREEN: {suite_fixed}")
        if suite_deleted["suite_outcome"] != "RED":
            raise RuntimeError(
                f"B08 after deleting the fix (pre-fix SHA) was not RED: {suite_deleted}"
            )
        if not totality["complete"]:
            raise RuntimeError(f"totality incomplete: {totality}")
        if not gen["rejected_trivial"]:
            raise RuntimeError("trivial always-pass candidate was not rejected")
        return {
            "clock_source": CLOCK,
            "t0_ns": t0,
            "t1_ns": t1,
            "harvested_defects": [
                {
                    "defect_id": d["defect_id"],
                    "source_unit": d["source_unit"],
                    "failure_class": d["failure_class"],
                    "origin": d["origin"],
                }
                for d in defects
            ],
            "sibling_census": census,
            "pre_sha": pre,
            "post_sha": post,
            "generated_tests": [
                {k: v for k, v in t.items() if k != "src"} for t in gen["accepted"]
            ],
            "mapping": gen["mapping"],
            "unmapped": gen["unmapped"],
            "totality": totality,
            "rejected_trivial": gen["rejected_trivial"],
            "b08_wiring": {
                "suite_id": SUITE_ID,
                "registered_test_ids": [t["test_id"] for t in wired],
                "live": True,
                "post_fix_suite_outcome": suite_fixed["suite_outcome"],
                "n_tests": suite_fixed["n_tests"],
            },
            "delete_fix_ci": {
                "fix_deleted_sha": pre,
                "suite_outcome": suite_deleted["suite_outcome"],
                "proves_wiring_live": suite_deleted["suite_outcome"] == "RED",
                "n_tests": suite_deleted["n_tests"],
                "n_red": suite_deleted["n_red"],
            },
        }


if __name__ == "__main__":
    doc = run()
    print(
        f"accepted={len(doc['generated_tests'])} "
        f"trivial_rejected={len(doc['rejected_trivial'])} "
        f"delete_fix={doc['delete_fix_ci']['suite_outcome']} "
        f"totality={doc['totality']}"
    )
