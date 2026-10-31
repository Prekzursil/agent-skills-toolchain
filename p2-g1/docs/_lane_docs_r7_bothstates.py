"""Round 7: prove the new anchor arm FIRES on the real files, not just in memory.

The in-suite controls mutate a string. This mutates the file on disk and runs the
SHIPPED test, because a gate that has only ever been green is indistinguishable
from a no-op. Both states are executed:

    fixed  state -> exit 0
    broken state -> exit 1, and the failure must NAME the carrier it broke

Every mutation runs inside try/finally with a sha256 restore assertion, so a
crash cannot leave a sibling lane looking at a corrupted shared working tree.

Terminal state: SUCCESS:docs-r7-bothstates / FAILED:docs-r7-bothstates <reason>
"""

from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
TEST = "ci/tests/test_command_doc_promises.py"
NODE = f"{TEST}::test_round5_counts_keep_their_commit_anchors"

CARRIERS = {
    "ci/tests/test_command_doc_promises.py": "67137879",
    "docs/_LANE-DOCS-BUILD-R5.md": "5d573583",
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def run_gate() -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", NODE, "-q", "-p", "no:cacheprovider"],
        cwd=REPO,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return proc.returncode, proc.stdout + proc.stderr


def main() -> int:
    # ---- fixed state --------------------------------------------------------
    rc, out = run_gate()
    if rc != 0:
        print(f"FAILED:docs-r7-bothstates fixed state is already red: {out[-400:]}")
        return 1

    results: list[str] = []
    for rel, anchor in CARRIERS.items():
        path = REPO / rel
        before_bytes = path.read_bytes()
        before = sha(path)

        text = before_bytes.decode("utf-8")
        if anchor not in text:
            print(f"FAILED:docs-r7-bothstates precondition: {anchor} absent from {rel}")
            return 1

        try:
            # Strip the anchor exactly as a careless "tidy the comment" edit would.
            path.write_bytes(text.replace(anchor, "").encode("utf-8"))
            rc_broken, out_broken = run_gate()
        finally:
            path.write_bytes(before_bytes)

        after = sha(path)
        if after != before:
            print(f"FAILED:docs-r7-bothstates {rel} not restored ({before} -> {after})")
            return 1
        if rc_broken == 0:
            print(
                f"FAILED:docs-r7-bothstates gate stayed GREEN with {anchor} stripped from {rel}"
            )
            return 1
        if rel not in out_broken:
            print(f"FAILED:docs-r7-bothstates gate fired but did not name {rel}")
            return 1
        results.append(f"{rel.rsplit('/', 1)[-1]}:fires")

    # ---- fixed state again, to prove the restore really restored ------------
    rc_after, _ = run_gate()
    if rc_after != 0:
        print("FAILED:docs-r7-bothstates gate red after restore")
        return 1

    print(
        "SUCCESS:docs-r7-bothstates fixed=0 broken=1 "
        f"carriers={len(CARRIERS)} {' '.join(results)} restored=True"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
