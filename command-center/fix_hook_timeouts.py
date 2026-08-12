r"""Union-merge the three drifted Stop-hook timeouts, and size git-hygiene to its MEASURED cost.

MEASURED 2026-08-12, which is the whole justification:
  git-hygiene full scan        28,275 ms   against a live budget of 30,000 ms -> 1.7s of headroom
  git-hygiene throttled run       314 ms   (it self-throttles to one full scan per 15 min)
  repo-declared budget         12,000 ms   -> would fail EVERY full scan, 100% of the time

The dispatcher disarmed this guard twice in consecutive turns with "still running past their own
budget ... their silence is NOT a pass". A guard that cannot finish inside its budget is not a slow
guard, it is an ABSENT one, and this one reports live-authored harness files that never reached
version control -- precisely the drift class this session has been fixing all night.

WHY 90s AND NOT 35s: the measured 28.3s was taken while a six-lane wave is writing the tree. The
budget has to cover the bad case, not the quiet one, and the cost of a generous ceiling is zero
because the common path is 314 ms -- the ceiling is only reached once per 15 minutes. A 35s budget
would re-fail the first time the box is busier than it is right now.

THE OTHER TWO ARE A UNION-MERGE, NOT A CHANGE. HOOK-MANIFEST-DRIFT.md recorded that three Stop hooks
carry LIVE timeouts 2-2.5x their repo values. Live is ahead because someone raised them when they
timed out; a naive repo->live deploy would revert that and reintroduce the failure. So the repo takes
the live value. That direction is deliberate: it is the only one that destroys nothing.

Both manifests are written because the repo is the source of truth AND the live tree is what runs
today. Editing only the deployed copy is the anti-pattern this repo documents; editing only the repo
leaves the guard unarmed until the next deploy.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
LIVE = Path("C:/Users/Prekzursil/.claude/hooks/_dispatch/manifest.json")
REPO_MANIFEST = REPO / "hooks" / "_dispatch" / "manifest.json"

#: name -> new timeout. git-hygiene is sized to measurement; the other two adopt the live value.
TARGETS = {
    "git-hygiene": 90,
    "forge/todo-surfacer": 18,
    "stub-ledger/report": 25,
}
MEASURED_FULL_SCAN_MS = 28_275


def patch(path: Path, tag: str) -> tuple[bool, list[str]]:
    """Edit ONLY the timeout lines, textually. Never round-trip the document through json.dumps.

    The first version of this did round-trip, and reformatted the ENTIRE file: 296 insertions /
    296 deletions for a three-value change. The indent heuristic tested `raw.startswith('{\\n  ')`
    while the file begins `{\\r\\n  `, so CRLF defeated the check and it fell through to indent=1,
    rewriting every line from 10 spaces to 5. Values were correct and the JSON was valid -- and the
    diff was unreviewable, which is its own kind of wrong in a repo where the next person has to
    audit what changed. A surgical edit cannot have that failure mode at all.
    """
    raw = path.read_text(encoding="utf-8", newline="")
    doc = json.loads(raw)  # parse only to VALIDATE and to read current values, never to write
    checks = ((doc.get("events") or {}).get("Stop") or {}).get("checks") or []
    if not checks:
        return False, [f"{tag}: no Stop.checks found -- manifest shape changed"]
    current = {c.get("name"): c.get("timeout") for c in checks if c.get("name") in TARGETS}
    missing = set(TARGETS) - set(current)
    if missing:
        return False, [f"{tag}: MISSING hooks {sorted(missing)} -- refusing to write"]

    eol = "\r\n" if "\r\n" in raw else "\n"
    lines = raw.split(eol)
    notes, edits = [], 0
    for name, new in TARGETS.items():
        old = current[name]
        if old == new:
            notes.append(f"{tag}: {name} already {new}s")
            continue
        # Find this hook's own object: its "name" line, then the FIRST "timeout" line after it and
        # before the next "name" line. Anchoring on the following "name" is what stops the edit
        # leaking into a sibling hook when a block has no timeout of its own.
        anchor = next((i for i, ln in enumerate(lines) if f'"name": "{name}"' in ln), None)
        if anchor is None:
            return False, notes + [f"{tag}: no line carries the name {name!r}"]
        end = next((j for j in range(anchor + 1, len(lines)) if '"name":' in lines[j]), len(lines))
        tline = next((j for j in range(anchor, end) if '"timeout":' in lines[j]), None)
        if tline is None:
            return False, notes + [f"{tag}: {name} has no timeout line in its own block"]
        before = lines[tline]
        lines[tline] = re.sub(r'("timeout":\s*)\d+', lambda m: f"{m.group(1)}{new}", before, count=1)
        if lines[tline] == before:
            return False, notes + [f"{tag}: {name} timeout line did not change: {before.strip()!r}"]
        notes.append(f"{tag}: {name} {old}s -> {new}s")
        edits += 1

    if edits:
        out = eol.join(lines)
        changed = sum(1 for a, b in zip(raw.split(eol), lines) if a != b)
        if changed != edits:
            return False, notes + [f"{tag}: {changed} lines differ but only {edits} edits intended"]
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write(out)
        json.loads(path.read_text(encoding="utf-8"))  # still parses after a textual edit
    return True, notes


def main() -> int:
    print(f"  measured git-hygiene full scan: {MEASURED_FULL_SCAN_MS:,}ms -> budget {TARGETS['git-hygiene']}s")
    allnotes = []
    for path, tag in ((REPO_MANIFEST, "repo"), (LIVE, "live")):
        if not path.is_file():
            print(f"FAILED:hook-timeouts missing {path}")
            return 1
        ok, notes = patch(path, tag)
        allnotes += notes
        if not ok:
            for n in notes:
                print(f"  {n}")
            print("FAILED:hook-timeouts refused to write")
            return 1
    for n in allnotes:
        print(f"  {n}")

    # Verify by re-reading BOTH files -- a write that silently no-ops would look identical here.
    for path, tag in ((REPO_MANIFEST, "repo"), (LIVE, "live")):
        doc = json.loads(path.read_text(encoding="utf-8"))
        got = {
            c["name"]: c.get("timeout")
            for c in doc["events"]["Stop"]["checks"]
            if c.get("name") in TARGETS
        }
        if got != TARGETS:
            print(f"FAILED:hook-timeouts {tag} read back {got}, expected {TARGETS}")
            return 1
        print(f"  {tag} verified: {got}")
    print("\nSUCCESS:fix-hook-timeouts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
