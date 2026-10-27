"""Is AUD-0030's 692-vs-679 module delta explained by .py files created after the unit ran?

H1 = the unit's walk lost 13 modules (a defect in the unit).
H2 = the tree GREW after the unit's ended_at (time-indexed, same class as the AUD-0041 CI drift).

Two mechanically independent signals, because neither alone is sufficient:
  (a) git add-time -- exact, but the unit walked the DISK, so a file that existed UNTRACKED at
      measurement time and was committed later is wrongly subtracted by this signal;
  (b) filesystem mtime -- covers untracked-at-the-time files, but is only trustworthy here
      because these paths were authored in this worktree and never re-checked-out. Stated as a
      limitation, not treated as proof on its own.
"""

import json
import pathlib
import subprocess
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parents[2]


def git(*a):
    return subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True).stdout


a30 = json.loads(
    (ROOT / "command-center/audit/AUD-0030-import-graph-cycles.json").read_text(
        encoding="utf-8"
    )
)
ts = a30["timestamps"]
ENDED = datetime.fromisoformat(ts["ended_at"].replace("Z", "+00:00"))
print(f"AUD-0030 ended_at = {ENDED.isoformat()}  (claim: module_count=679)")

tracked = [
    f
    for f in git("ls-files", "tools").splitlines()
    if f.endswith(".py") and not ({"node_modules", "vendor"} & set(f.split("/")))
]
print(f"tracked non-vendored .py under tools/ TODAY: {len(tracked)}")

raw = git("log", "--diff-filter=A", "--format=%H|%cI", "--name-only", "--", "tools")
added_first, cur = {}, None
for ln in raw.splitlines():
    if "|" in ln and len(ln.split("|")[0]) == 40:
        cur = ln.split("|")[1]
    elif ln.strip() and cur:
        added_first[ln.strip()] = (
            cur  # log is newest-first, so the last write is the earliest add
        )

sig_a, sig_b, both = [], [], []
for f in tracked:
    g = added_first.get(f)
    git_after = bool(g) and datetime.fromisoformat(g) > ENDED
    p = ROOT / f
    mt = (
        datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc)
        if p.exists()
        else None
    )
    mt_after = bool(mt) and mt > ENDED
    if git_after:
        sig_a.append(f)
    if mt_after:
        sig_b.append(f)
    if git_after and mt_after:
        both.append(f)

print(f"signal (a) git-added after ended_at      : {len(sig_a)}")
print(f"signal (b) file mtime after ended_at     : {len(sig_b)}")
print(f"both signals agree                       : {len(both)}")
lo, hi = len(tracked) - len(sig_a), len(tracked) - len(both)
print(f"reconstructed module set at ended_at, bracketed: [{lo} .. {hi}]")
inside = lo <= 679 <= hi
print(f"unit's 679 inside the bracket: {inside}")
verdict = (
    "TIME-INDEXED (H2) -- 679 lies inside the reconstructed bracket; the count was correct "
    "at its own timestamp and the tree has grown since"
    if inside
    else f"UNRESOLVED -- 679 outside [{lo}..{hi}]"
)
print(f"\nVERDICT: {verdict}")
(ROOT / "command-center/p2-next/REVIEW-AUD0030-TIMEINDEX.json").write_text(
    json.dumps(
        {
            "unit_ended_at": ts["ended_at"],
            "tracked_now": len(tracked),
            "added_after_by_git": len(sig_a),
            "mtime_after": len(sig_b),
            "both": len(both),
            "reconstructed_bracket": [lo, hi],
            "unit_claim": 679,
            "claim_inside_bracket": inside,
            "verdict": verdict,
            "limitation": "the unit walked the DISK; git add-time under-counts files that were untracked "
            "at measurement time, and mtime is only usable here because these paths were "
            "authored in this worktree and never re-checked-out",
        },
        indent=2,
    ),
    encoding="utf-8",
)
print("SUCCESS:timeindex")
