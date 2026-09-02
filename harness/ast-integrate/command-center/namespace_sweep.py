"""Find open register items whose named artifact EXISTS somewhere else in the tree.

WHY. Five of the ten items closed on 2026-08-11 closed for one reason: the deliverable had shipped
under `platform/` while the register's anchor still named a pre-`platform/` path. Nothing was built
to close them -- they were already done and the register could not see it. R-A10's anchor
(`11-COUNCIL-SPECIFICATION.schema.json`) is tracked ZERO times; the successor lives at
`platform/schema/councilspec.schema.json`. R-A12 named a repo-root `install.py`; the lifecycle ships
at `platform/plugin/`.

If that ratio holds across the 59 still open, a meaningful fraction is already delivered and merely
invisible, which is a very different program state from "59 items of work remaining".

THIS IS A DISCOVERY TOOL, NOT A CLOSER. It emits ranked CANDIDATES. Every hit still needs the same
treatment the ten closes got -- re-measure the anchor, run a control, then dispose. A basename match
is a hint, not evidence: `README.md` matches everywhere and means nothing.

WHY AN ALGORITHM AND NOT AGENTS. The fan-out contract records a measured case where six Opus agents
classified 338 files at 86% accuracy with 100% of the errors pointing at data loss, against a 40-line
differ that was exact. "Does this basename exist elsewhere in the tree" is set membership. Set
membership gets code.
"""

from __future__ import annotations

import json
import re
import subprocess
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CATALOG = REPO / "command-center/WORK-UNIT-CATALOG.json"

#: A path-shaped token: at least one dot-suffix, optional directories.
PATHISH = re.compile(
    r"[A-Za-z0-9_./\\-]+\.(?:py|json|md|ps1|sh|toml|ya?ml|jsonl|schema\.json)"
)

#: Basenames too generic for a match to carry any signal.
GENERIC = {
    "README.md",
    "STATUS.md",
    "index.py",
    "cli.py",
    "__init__.py",
    "main.py",
    "conftest.py",
    "settings.json",
    "config.json",
    "package.json",
    "AGENTS.md",
    "CLAUDE.md",
    "manifest.json",
    "schema.json",
    "utils.py",
    "models.py",
    "types.py",
    "test.py",
    "setup.py",
}

#: Fields whose prose names the artifacts an item is about.
TEXT_FIELDS = ("target", "title", "evidence", "next_smallest_action", "output_path")


def tracked_by_basename() -> dict[str, list[str]]:
    out = subprocess.run(
        ["git", "-C", str(REPO), "ls-files"],
        capture_output=True,
        text=True,
        check=False,
    ).stdout.splitlines()
    index: dict[str, list[str]] = defaultdict(list)
    for rel in out:
        rel = rel.strip()
        if rel:
            index[Path(rel).name].append(rel)
    return index


def named_paths(item: dict) -> set[str]:
    blob = " ".join(str(item.get(f) or "") for f in TEXT_FIELDS)
    found = set()
    for raw in PATHISH.findall(blob):
        name = Path(raw.replace("\\", "/")).name
        if name and name not in GENERIC and len(name) > 6:
            found.add(name)
    return found


def sweep() -> dict:
    doc = json.loads(CATALOG.read_text(encoding="utf-8"))
    index = tracked_by_basename()
    if len(index) < 500:
        raise ValueError(
            f"git ls-files indexed only {len(index)} basenames (fail closed)"
        )

    candidates = []
    for item in doc["items"]:
        if item.get("status") != "OPEN":
            continue
        names = named_paths(item)
        if not names:
            continue
        hits = {}
        for name in sorted(names):
            locations = index.get(name, [])
            if not locations:
                continue
            declared = str(item.get("output_path") or "")
            # Only interesting when the artifact is NOT where the item says it is.
            elsewhere = [loc for loc in locations if loc != declared]
            if elsewhere:
                hits[name] = elsewhere[:3]
        if hits:
            candidates.append(
                {
                    "id": item["id"],
                    "program": item.get("program"),
                    "named_but_found_elsewhere": hits,
                    "platform_hits": sum(
                        1
                        for locs in hits.values()
                        for loc in locs
                        if loc.startswith("platform/")
                    ),
                }
            )

    candidates.sort(
        key=lambda c: (-c["platform_hits"], -len(c["named_but_found_elsewhere"]))
    )
    return {
        "basenames_indexed": len(index),
        "open_items_scanned": sum(1 for i in doc["items"] if i.get("status") == "OPEN"),
        "candidates": candidates,
    }


def main() -> int:
    try:
        report = sweep()
    except (OSError, ValueError) as exc:
        print(f"FAILED:namespace-sweep {exc}")
        return 1

    # Detector control: a name that cannot exist must not resolve, and a name that DOES exist must.
    index = tracked_by_basename()
    if "zzz-not-a-real-file.json" in index or "wudeps.py" not in index:
        print("FAILED:namespace-sweep detector control failed")
        return 1

    cands = report["candidates"]
    print(
        f"  indexed {report['basenames_indexed']} basenames; scanned "
        f"{report['open_items_scanned']} OPEN items; {len(cands)} carry a name found elsewhere\n"
    )
    for c in cands[:15]:
        flag = f"  platform:{c['platform_hits']}" if c["platform_hits"] else ""
        print(f"  {c['id']:8} [{c['program']}]{flag}")
        for name, locs in list(c["named_but_found_elsewhere"].items())[:3]:
            print(f"      {name}  ->  {', '.join(locs)}")

    out = REPO / "command-center" / "NAMESPACE-SWEEP.json"
    out.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    strong = [c for c in cands if c["platform_hits"]]
    print(
        f"\nSUCCESS:namespace-sweep {len(cands)} candidate(s), {len(strong)} with a platform/ hit "
        "-- CANDIDATES ONLY, each still needs its anchor re-measured before any disposition"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
