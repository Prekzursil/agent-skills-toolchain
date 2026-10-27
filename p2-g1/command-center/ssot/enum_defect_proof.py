"""Both-states proof of the enumeration defect, on named cases.

The claim: `sweep_all_checkouts.py`'s identity test is a test for the repo's NAME appearing
in a remote URL or an object-store path, and it therefore MISSES working copies of this repo
that have no remote and a directory named something else.

A claim like that is only worth anything if the detector is shown to answer BOTH ways in BOTH
directions, so this runs four cases chosen to make each failure mode visible:

  canonical            OLD must fire  (else OLD is simply broken and proves nothing)
  _advver_M14/chk      OLD must MISS, NEW must fire   <- the defect, 1 commit, no remote
  _advver_M14/scratch  OLD must MISS, NEW must fire   <- 0 commits: ONLY content can see it
  ToolUniverse-secfix  BOTH must miss (else NEW fires on everything and is vacuous)

Read-only.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

CANONICAL = Path("C:/Users/Prekzursil/source/agent-skills-toolchain")
ROOT_COMMIT = "66e383dd97e4e53bd34085636f9b2a2f83efce02"
TARGET = "agent-skills-toolchain"
OUT = Path(__file__).resolve().parent / "enum-defect-proof.json"

CASES = [
    ("canonical", "C:/Users/Prekzursil/source/agent-skills-toolchain", "OLD-FIRES"),
    (
        "chk (1 commit, no remote)",
        "C:/Users/Prekzursil/source/_advver_M14/chk",
        "OLD-MISSES",
    ),
    (
        "scratch (0 commits, no remote)",
        "C:/Users/Prekzursil/source/_advver_M14/scratch",
        "OLD-MISSES",
    ),
    (
        "ToolUniverse-secfix (unrelated)",
        "C:/Users/Prekzursil/source/ToolUniverse-secfix",
        "BOTH-MISS",
    ),
]

SENTINELS = ["AGENTS.md", "README.md", "package.json", "ruff.toml", "CLAUDE.md"]


def git(repo, *a):
    p = subprocess.run(
        ["git", "-C", str(repo), *a],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return p.stdout.strip() if p.returncode == 0 else ""


def git_hash(b: bytes) -> str:
    h = hashlib.sha1()
    h.update(b"blob %d\0" % len(b))
    h.update(b)
    return h.hexdigest()


def hashes(b: bytes) -> list[str]:
    out = [git_hash(b)]
    lf = b.replace(b"\r\n", b"\n")
    if lf != b:
        out.append(git_hash(lf))
    return out


def main() -> int:
    p = subprocess.run(
        ["git", "rev-list", "--objects", "--all"],
        cwd=str(CANONICAL),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    reach = {
        ln.split(" ", 1)[0].strip()
        for ln in p.stdout.splitlines()
        if len(ln.split(" ", 1)[0].strip()) == 40
    }
    print(f"canonical reachable objects: {len(reach)}\n")

    rows = []
    print(
        f"{'case':<34}{'OLD(name)':<11}{'history':<9}{'content':<9}{'NEW':<6}expected"
    )
    print("-" * 88)
    for label, path, expected in CASES:
        if not Path(path).exists():
            print(f"{label:<34}{'ABSENT':<11}")
            continue
        origin = git(path, "config", "--get", "remote.origin.url")
        common = git(path, "rev-parse", "--path-format=absolute", "--git-common-dir")
        old = TARGET in origin.lower() or TARGET in common.lower()
        hist = (
            subprocess.run(
                ["git", "-C", path, "cat-file", "-e", ROOT_COMMIT], capture_output=True
            ).returncode
            == 0
        )
        hits = []
        for s in SENTINELS:
            f = Path(path) / s
            try:
                if f.is_file() and any(h in reach for h in hashes(f.read_bytes())):
                    hits.append(s)
            except OSError:
                pass
        new = hist or bool(hits)
        rows.append(
            {
                "case": label,
                "path": path,
                "origin": origin,
                "commits": git(path, "rev-list", "--count", "HEAD") or "0",
                "old_name_signal": old,
                "history_signal": hist,
                "content_signal": bool(hits),
                "content_hits": hits,
                "new_verdict": new,
                "expected": expected,
            }
        )
        print(
            f"{label:<34}{str(old):<11}{str(hist):<9}{str(bool(hits)):<9}{str(new):<6}{expected}"
        )

    def find(sub):
        return next((r for r in rows if sub in r["case"]), None)

    canon, chk, scratch, unrel = (
        find("canonical"),
        find("chk"),
        find("scratch"),
        find("unrelated"),
    )
    checks = {
        "OLD fires on canonical (old test is not simply broken)": bool(
            canon and canon["old_name_signal"]
        ),
        "OLD misses chk": bool(chk and not chk["old_name_signal"]),
        "OLD misses scratch": bool(scratch and not scratch["old_name_signal"]),
        "NEW finds chk": bool(chk and chk["new_verdict"]),
        "NEW finds scratch": bool(scratch and scratch["new_verdict"]),
        "scratch findable ONLY by content (0 commits)": bool(
            scratch and not scratch["history_signal"] and scratch["content_signal"]
        ),
        "NEW does not fire on an unrelated repo (not vacuous)": bool(
            unrel and not unrel["new_verdict"]
        ),
    }
    print()
    for k, v in checks.items():
        print(f"  [{'PASS' if v else 'FAIL'}] {k}")

    OUT.write_text(
        json.dumps({"rows": rows, "checks": checks}, indent=2), encoding="utf-8"
    )
    print(f"\nwrote {OUT}")
    if all(checks.values()):
        print(
            "SUCCESS:enum-defect-proof the NAME test misses real checkouts; identity finds them"
        )
        return 0
    print("FAILED:enum-defect-proof expected discrimination not observed")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
