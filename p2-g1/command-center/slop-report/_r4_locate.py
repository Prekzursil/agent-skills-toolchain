"""For every widened-gate violation: does the promised file exist on THIS disk?

That is the bucket question, and the two answers need opposite handling:

  * exists, untracked  -> BUCKET (b). Evidence on exactly one disk while a committed
    document tells a reader to run it. Commit it. This is the class the shipped gate
    already caught 21 times.
  * exists nowhere     -> not slop at all. A committed document promising a file that
    was never written is an AUTHORSHIP gap; the remedy is a baseline row with an owner
    (what R3 did for `platform/lib/ssot/verify.py`), not a commit.

CONTROL, both states -- the locator is itself a detector:
  * positive: a basename known to be tracked must be FOUND, at its known path.
  * negative: a uuid4 basename must be found NOWHERE. If the walker returned hits for
    a name that cannot exist, every "exists" verdict below would be worthless.
"""

from __future__ import annotations

import json
import os
import subprocess
import uuid

REPO = "C:/Users/Prekzursil/source/ast-integrate"
SKIP_DIRS = {
    ".git",
    "node_modules",
    ".ruff_cache",
    ".pytest_cache",
    "__pycache__",
    ".venv",
}


def git(*args: str) -> list[str]:
    r = subprocess.run(
        ["git", "-C", REPO, *args], capture_output=True, text=True, errors="replace"
    )
    return [x for x in r.stdout.replace("\r\n", "\n").split("\n") if x]


def walk_index() -> dict[str, list[str]]:
    """basename -> [repo-relative paths], one filesystem pass."""
    idx: dict[str, list[str]] = {}
    for dirpath, dirnames, filenames in os.walk(REPO):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        rel = os.path.relpath(dirpath, REPO).replace("\\", "/")
        rel = "" if rel == "." else rel + "/"
        for fn in filenames:
            idx.setdefault(fn, []).append(rel + fn)
    return idx


def main() -> int:
    src = os.path.join(REPO, "command-center/slop-report/_r4_promise.out.json")
    promise = json.load(open(src, encoding="utf-8"))

    tracked = set(git("ls-files"))
    untracked = set(git("ls-files", "--others", "--exclude-standard"))
    ignored = set(git("ls-files", "--others", "--ignored", "--exclude-standard"))
    idx = walk_index()

    ctl_name = f"_r4_absent_{uuid.uuid4().hex}.py"
    ctl = {
        "positive_basename": "check_published_commands.py",
        "positive_found": idx.get("check_published_commands.py", []),
        "positive_is_tracked_path": "command-center/slop-report/check_published_commands.py"
        in idx.get("check_published_commands.py", []),
        "negative_basename": ctl_name,
        "negative_found": idx.get(ctl_name, []),
    }
    ctl["PASS"] = bool(ctl["positive_is_tracked_path"]) and not ctl["negative_found"]

    rows = []
    # Only the classes whose evidence survives -- pybare is refuted, see _r4_promise.
    for cls in ("sh", "ps", "pytest", "node"):
        for v in promise["classes"][cls]["violations"]:
            target = v["target"]
            base = target.rsplit("/", 1)[-1]
            hits = idx.get(base, [])
            suffix_hits = [h for h in hits if h.endswith(target)]
            state = "NOWHERE"
            if suffix_hits:
                state = "EXISTS_SUFFIX_MATCH"
            elif hits:
                state = "EXISTS_BASENAME_ONLY"
            rows.append(
                {
                    **v,
                    "basename": base,
                    "fs_hits": hits,
                    "suffix_hits": suffix_hits,
                    "state": state,
                    "hits_tracked": [h for h in hits if h in tracked],
                    "hits_untracked": [h for h in hits if h in untracked],
                    "hits_ignored": [h for h in hits if h in ignored],
                }
            )

    out = {
        "rev": git("rev-parse", "HEAD")[0],
        "controls": ctl,
        "rows": rows,
        "summary": {
            "NOWHERE": sum(1 for r in rows if r["state"] == "NOWHERE"),
            "EXISTS_SUFFIX_MATCH": sum(
                1 for r in rows if r["state"] == "EXISTS_SUFFIX_MATCH"
            ),
            "EXISTS_BASENAME_ONLY": sum(
                1 for r in rows if r["state"] == "EXISTS_BASENAME_ONLY"
            ),
        },
    }
    dest = os.path.join(REPO, "command-center/slop-report/_r4_locate.out.json")
    with open(dest, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(out, fh, indent=1, sort_keys=True)

    print("controls PASS:", ctl["PASS"], "| negative hits:", ctl["negative_found"])
    print("summary:", json.dumps(out["summary"]))
    for r in rows:
        print(f"\n{r['citer']}:{r['line']} -> {r['target']}   [{r['state']}]")
        print(f"    tracked  : {r['hits_tracked']}")
        print(f"    untracked: {r['hits_untracked']}")
        print(f"    ignored  : {r['hits_ignored']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
