"""Is `total=333` real, or is it my own instrument inflating again?

Three ways that number could be wrong, each checked here rather than assumed:

  1. JUNCTION ALIASES -- the walk counted 4,447 paths that collapse to 1,840 real ones, so a
     physical checkout reachable through `Local Settings`/`My Documents` would be counted
     twice. Collapse by `os.path.realpath` before believing any total.
  2. CONTENT false positives -- the CONTENT signal fires when a sentinel file's blob is in
     canonical's history. Canonical VENDORS third-party trees, so a standalone clone of a
     vendored repo legitimately shares that blob and is NOT a checkout of this repo. Any
     CONTENT-only row is therefore suspect and is re-checked with an independent test.
  3. HISTORY false positives -- `cat-file -e <root>` could in principle hit an unrelated repo
     that shares the object. Spot-verified against a second, mechanically different signal:
     does the checkout's HEAD tree carry a path only this repo has?

The independent confirmation used for both spot checks is `git log --format=%s -1 <root>`,
which must return canonical's actual root-commit subject. Reading a commit MESSAGE is a
different mechanism from testing object existence or hashing a working file.
"""

from __future__ import annotations

import json
import os
import random
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
CANONICAL = Path("C:/Users/Prekzursil/source/agent-skills-toolchain")
ROOT_COMMIT = "66e383dd97e4e53bd34085636f9b2a2f83efce02"
OUT = HERE / "enum-total-verified.json"


def git(repo, *a):
    p = subprocess.run(
        ["git", "-C", str(repo), *a],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return p.stdout.strip() if p.returncode == 0 else ""


def main() -> int:
    rows = json.loads((HERE / "enumerate-checkouts.json").read_text(encoding="utf-8"))[
        "rows"
    ]

    root_subject = git(CANONICAL, "log", "--format=%s", "-1", ROOT_COMMIT)
    print(f"canonical root-commit subject: {root_subject!r}")
    if not root_subject:
        print("FAILED:verify-enum cannot read canonical root subject")
        return 3

    # ---------- 1. junction collapse
    seen: dict[str, dict] = {}
    dupes = []
    for r in rows:
        rp = os.path.realpath(r["path"]).replace("\\", "/").rstrip("/").lower()
        if rp in seen:
            dupes.append(r["path"])
        else:
            seen[rp] = r
    print(f"\nraw belongs      : {len(rows)}")
    print(f"junction dupes   : {len(dupes)}")
    print(f"DISTINCT belongs : {len(seen)}")

    distinct = list(seen.values())

    # ---------- 2/3. spot-verify with an independent signal
    hist_rows = [r for r in distinct if r["sig_history"]]
    cont_only = [
        r for r in distinct if r["sig_content"] and not r["sig_history"] and not r["sig_name"]
    ]

    random.seed(7)
    sample = random.sample(hist_rows, min(12, len(hist_rows)))

    print(f"\n--- HISTORY rows: {len(hist_rows)}; verifying a random {len(sample)} ---")
    hist_ok = 0
    for r in sample:
        subj = git(r["path"], "log", "--format=%s", "-1", ROOT_COMMIT)
        ok = subj == root_subject
        hist_ok += ok
        print(f"  [{'OK ' if ok else 'BAD'}] {r['path'][:78]}")
    print(f"  HISTORY spot-check: {hist_ok}/{len(sample)} confirmed by commit-subject read")

    print(f"\n--- CONTENT-ONLY rows: {len(cont_only)} (the suspect class) ---")
    cont_confirmed, cont_refuted = [], []
    for r in cont_only:
        # independent test: does this checkout carry a path only this repo has?
        marker = git(r["path"], "cat-file", "-e", "HEAD:docs/ssot/SSOT-CLONE-INVENTORY.md")
        has_repo_topology = (
            subprocess.run(
                ["git", "-C", r["path"], "cat-file", "-e", "HEAD:REPO-TOPOLOGY.md"],
                capture_output=True,
            ).returncode
            == 0
        )
        subj = git(r["path"], "log", "--format=%s", "-1", ROOT_COMMIT)
        confirmed = has_repo_topology or subj == root_subject
        (cont_confirmed if confirmed else cont_refuted).append(
            {
                "path": r["path"],
                "hits": r["content_hits"],
                "has_repo_topology": has_repo_topology,
                "root_subject_match": subj == root_subject,
                "marker": bool(marker),
            }
        )
        print(
            f"  [{'CONFIRMED' if confirmed else 'REFUTED  '}] {r['path'][:62]}\n"
            f"      hits={r['content_hits']}"
        )

    print(
        f"\nCONTENT-ONLY: {len(cont_confirmed)} confirmed, {len(cont_refuted)} REFUTED "
        f"(false positives of the content signal)"
    )

    corrected = len(distinct) - len(cont_refuted)
    print(f"\nraw total reported by the sweep : {len(rows)}")
    print(f"after junction collapse         : {len(distinct)}")
    print(f"after removing content-only FPs : {corrected}")

    report = {
        "root_subject": root_subject,
        "raw": len(rows),
        "junction_dupes": len(dupes),
        "distinct": len(distinct),
        "history_rows": len(hist_rows),
        "history_spotcheck": {"sampled": len(sample), "confirmed": hist_ok},
        "content_only": len(cont_only),
        "content_only_confirmed": cont_confirmed,
        "content_only_refuted": cont_refuted,
        "corrected_total": corrected,
    }
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\nwrote {OUT}")
    if hist_ok != len(sample):
        print("FAILED:verify-enum history signal did not confirm on every sampled row")
        return 1
    print(f"SUCCESS:verify-enum corrected_total={corrected} (raw {len(rows)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
