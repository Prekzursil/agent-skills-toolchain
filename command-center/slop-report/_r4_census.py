"""Round-4 census: the CURRENT untracked/ignored surface, rev-anchored.

Disjointness control: tracked / untracked / ignored must not overlap, and a freshly
generated uuid4 name must appear in none of them (proves the reader is not matching
everything).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import uuid

REPO = "C:/Users/Prekzursil/source/ast-integrate"


def git(*args: str) -> str:
    out = subprocess.run(
        ["git", *args], cwd=REPO, capture_output=True, text=True, check=False
    )
    if out.returncode != 0:
        sys.stderr.write(f"git {' '.join(args)} -> rc={out.returncode}\n{out.stderr}\n")
    return out.stdout


def lines(s: str) -> list[str]:
    return [x for x in s.replace("\r\n", "\n").split("\n") if x]


def main() -> int:
    rev = git("rev-parse", "HEAD").strip()
    tracked = set(lines(git("ls-files")))
    untracked = set(lines(git("ls-files", "--others", "--exclude-standard")))
    ignored = set(lines(git("ls-files", "--others", "--ignored", "--exclude-standard")))
    modified = set(lines(git("diff", "--name-only")))
    staged = set(lines(git("diff", "--cached", "--name-only")))

    control_name = f"_r4_control_{uuid.uuid4().hex}.py"
    controls = {
        "tracked_x_untracked": sorted(tracked & untracked)[:5],
        "tracked_x_ignored": sorted(tracked & ignored)[:5],
        "untracked_x_ignored": sorted(untracked & ignored)[:5],
        "uuid_in_tracked": control_name in tracked,
        "uuid_in_untracked": control_name in untracked,
        "uuid_in_ignored": control_name in ignored,
        # positive control: a known-present tracked file MUST be seen
        "known_tracked_seen": "command-center/slop-report/check_published_commands.py"
        in tracked,
    }

    now = time.time()

    def bucket_by_tree(paths: set[str]) -> dict[str, int]:
        d: dict[str, int] = {}
        for p in paths:
            top = p.split("/", 1)[0] if "/" in p else "<root>"
            d[top] = d.get(top, 0) + 1
        return dict(sorted(d.items(), key=lambda kv: -kv[1]))

    def age_min(p: str) -> float | None:
        fp = os.path.join(REPO, p)
        try:
            return round((now - os.path.getmtime(fp)) / 60.0, 1)
        except OSError:
            return None

    untracked_detail = []
    for p in sorted(untracked):
        fp = os.path.join(REPO, p)
        try:
            size = os.path.getsize(fp)
        except OSError:
            size = -1
        untracked_detail.append({"path": p, "bytes": size, "age_min": age_min(p)})

    out = {
        "rev": rev,
        "counts": {
            "tracked": len(tracked),
            "untracked": len(untracked),
            "ignored": len(ignored),
            "modified_tracked": len(modified),
            "staged": len(staged),
        },
        "controls": controls,
        "untracked_by_tree": bucket_by_tree(untracked),
        "ignored_by_tree": bucket_by_tree(ignored),
        "modified_tracked_paths": sorted(modified),
        "staged_paths": sorted(staged),
        "untracked_detail": untracked_detail,
    }
    dest = os.path.join(REPO, "command-center/slop-report/_r4_census.out.json")
    with open(dest, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(out, fh, indent=1, sort_keys=True)
    print(json.dumps({k: out[k] for k in ("rev", "counts", "controls")}, indent=1))
    print("untracked_by_tree:", json.dumps(out["untracked_by_tree"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
