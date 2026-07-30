"""Two-directional reconcile map: databricks-fanout-harness  <->  toolchain skill copy.

Corrects a briefed fact that was wrong twice: the toolchain does NOT carry "only a SKILL.md with
zero implementation". `.agents/skills/codex-databricks-fanout/scripts/` already holds 31 files
including a full harness/ (contract, submit, poll, harvest, gate, preflight, lanes/). So the task
the owner actually set - "reunite them and keep the best version variant" - is a RECONCILE, not a
port.

Direction is the whole point. Two lanes today nearly destroyed data by reading one direction only:
a skills sync was measured vault-ahead when it was actually 34-files DIVERGED (a blind sync would
have clobbered unique content in 42 of 79), and 130 of 338 drift rows compared the wrong pair. So
every file here gets classified by comparing BOTH sides, with line endings normalised first
(CRLF-vs-LF alone manufactures hundreds of phantom differences).

Verdicts:
  DBX_ONLY     - exists only in the databricks repo  -> pure addition, safe to bring over
  TOOLCHAIN_ONLY - exists only in the toolchain       -> must NOT be deleted by the merge
  IDENTICAL    - byte-identical after EOL normalisation -> no action
  DBX_AHEAD    - toolchain content is a strict subset  -> take dbx
  TOOLCHAIN_AHEAD - dbx content is a strict subset     -> keep toolchain
  DIVERGED     - both sides hold unique lines          -> needs a real human/agent merge
Read-only: prints a map, changes nothing.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

DBX = Path("C:/Users/Prekzursil/source/databricks-fanout-harness")
TC = Path("C:/Users/Prekzursil/source/ast-patch167")
DBX_REV = "origin/feat/csie-foundation"
TC_REV = "origin/main"
TC_PREFIX = ".agents/skills/codex-databricks-fanout/scripts/"
ENV = {**os.environ, "MSYS_NO_PATHCONV": "1"}


def g(repo: Path, *a: str) -> tuple[int, str]:
    r = subprocess.run(
        ["git", "-C", str(repo), *a],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=ENV,
        check=False,
    )
    return r.returncode, r.stdout


def listing(repo: Path, rev: str, prefix: str = "") -> set[str]:
    args = ["ls-tree", "-r", "--name-only", rev]
    if prefix:
        args += ["--", prefix]
    _, out = g(repo, *args)
    files = {ln.strip() for ln in out.splitlines() if ln.strip()}
    if prefix:
        files = {f[len(prefix) :] for f in files if f.startswith(prefix)}
    return files


def body(repo: Path, rev: str, path: str) -> list[str] | None:
    rc, out = g(repo, "show", f"{rev}:{path}")
    if rc != 0:
        return None
    # Normalise EOL before ANY comparison - otherwise CRLF vs LF alone reports every file as
    # different, which is the phantom-drift trap recorded in the ledger.
    return [ln.rstrip("\r") for ln in out.split("\n")]


def main() -> int:
    dbx_files = listing(DBX, DBX_REV)
    tc_files = listing(TC, TC_REV, TC_PREFIX)
    # The dbx repo has no scripts/ prefix; harness/ e2e/ tests/ map 1:1 by relative path.
    interesting = {
        f
        for f in dbx_files
        if f.split("/")[0] in {"harness", "e2e", "tests", "engine", "backends"}
        or f in {"conftest.py", "batch_runner.py"}
    }

    buckets: dict[str, list[str]] = {
        k: []
        for k in (
            "DBX_ONLY",
            "TOOLCHAIN_ONLY",
            "IDENTICAL",
            "DBX_AHEAD",
            "TOOLCHAIN_AHEAD",
            "DIVERGED",
        )
    }

    for f in sorted(interesting | tc_files):
        d = body(DBX, DBX_REV, f) if f in dbx_files else None
        t = body(TC, TC_REV, TC_PREFIX + f) if f in tc_files else None
        if d is not None and t is None:
            buckets["DBX_ONLY"].append(f)
        elif d is None and t is not None:
            buckets["TOOLCHAIN_ONLY"].append(f)
        elif d is None and t is None:
            continue
        elif d == t:
            buckets["IDENTICAL"].append(f)
        else:
            ds, ts = set(d), set(t)
            d_uniq, t_uniq = ds - ts, ts - ds
            if d_uniq and t_uniq:
                buckets["DIVERGED"].append(
                    f"{f}  (+{len(d_uniq)} dbx / +{len(t_uniq)} tc)"
                )
            elif d_uniq:
                buckets["DBX_AHEAD"].append(f"{f}  (+{len(d_uniq)})")
            else:
                buckets["TOOLCHAIN_AHEAD"].append(f"{f}  (+{len(t_uniq)})")

    print(
        f"  dbx files (interesting): {len(interesting)}   toolchain skill files: {len(tc_files)}\n"
    )
    for k in (
        "DIVERGED",
        "TOOLCHAIN_AHEAD",
        "DBX_AHEAD",
        "DBX_ONLY",
        "TOOLCHAIN_ONLY",
        "IDENTICAL",
    ):
        rows = buckets[k]
        print(f"  {k}: {len(rows)}")
        for r in rows[:18]:
            print(f"      {r}")
        if len(rows) > 18:
            print(f"      ... and {len(rows) - 18} more")
        print()
    print("  ACTION SHAPE:")
    print(f"    pure additions to bring over : {len(buckets['DBX_ONLY'])}")
    print(f"    must NOT be deleted          : {len(buckets['TOOLCHAIN_ONLY'])}")
    print(f"    need a real merge            : {len(buckets['DIVERGED'])}")

    # Emit the map so merge agents consume a measured artifact rather than a prose summary.
    # Pair each module with its own test file: a module and its test must move together or the
    # suite validates the wrong variant.
    import json
    import re

    def bare(rows: list[str]) -> list[str]:
        return [re.sub(r"\s+\(.*$", "", r) for r in rows]

    diverged = bare(buckets["DIVERGED"])
    groups: dict[str, list[str]] = {}
    for f in diverged:
        stem = Path(f).stem
        key = stem[5:] if stem.startswith("test_") else stem
        groups.setdefault(key, []).append(f)

    out = {
        "dbx_repo": str(DBX),
        "dbx_rev": DBX_REV,
        "toolchain_repo": str(TC),
        "toolchain_rev": TC_REV,
        "toolchain_prefix": TC_PREFIX,
        "diverged": diverged,
        "diverged_detail": buckets["DIVERGED"],
        "dbx_only": bare(buckets["DBX_ONLY"]),
        "toolchain_only_NEVER_DELETE": bare(buckets["TOOLCHAIN_ONLY"]),
        "identical": bare(buckets["IDENTICAL"]),
        "merge_groups": [
            {"id": f"M{i:02d}", "name": k, "files": v}
            for i, (k, v) in enumerate(sorted(groups.items()))
        ],
    }
    dest = Path(__file__).resolve().parent / "_merge_map.json"
    dest.write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(f"\n  merge groups: {len(out['merge_groups'])}  ->  wrote {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
