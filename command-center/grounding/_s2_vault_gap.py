"""LANE SKILLS2 / item 2 -- does the EXISTING tool's vault plan actually close the ui-audit no-op?

The dry run offers 12 ui-audit files. That is a count, not an answer. The question is the
INTERSECTION: are the SIX vault files that still carry the old lexical main-guard among the
files the tool would copy, or are they refused as DIVERGED (in which case pointing the tool
at the vault does NOT close the defect and something else is needed)?

use-vs-mention control: `_fix_main_guard.py` is the REPAIR SCRIPT -- it contains the old
guard string as its search pattern. Counting it as "a file carrying the defect" is the exact
mislabelling that the ground floor warns about, so USE and MENTION are counted separately:
a USE is the guard string inside an `if (...)` main-guard line; a MENTION is anywhere else.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

REPO = Path(r"C:/Users/Prekzursil/source/ast-integrate/.agents/skills/ui-audit")
DAILY = Path(r"C:/Users/Prekzursil/.claude/skills.daily/ui-audit")
VAULT = Path(r"C:/Users/Prekzursil/.agents/skills/ui-audit")
PLAN = Path(
    r"C:/Users/Prekzursil/source/ast-integrate/command-center/grounding/S2-VAULT-DRYRUN.out.txt"
)

OLD = re.compile(r"resolve\(\s*process\.argv\[1\]\s*\)")
NEW = re.compile(r"__isMain")
GUARDLINE = re.compile(r"^\s*(if\s*\(|const\s+__isMain)")


def classify(root: Path) -> dict[str, dict]:
    out = {}
    if not root.exists():
        return out
    for f in sorted(root.rglob("*")):
        if not f.is_file() or f.suffix not in (".mjs", ".cjs", ".js", ".py"):
            continue
        try:
            txt = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        rel = f.relative_to(root).as_posix()
        uses, mentions = [], []
        for i, line in enumerate(txt.splitlines(), 1):
            if OLD.search(line):
                (uses if GUARDLINE.match(line) else mentions).append(i)
        out[rel] = {
            "old_use": uses,
            "old_mention": mentions,
            "has_new": bool(NEW.search(txt)),
        }
    return out


repo, daily, vault = classify(REPO), classify(DAILY), classify(VAULT)

plan_files = set()
for line in PLAN.read_text(encoding="utf-8").splitlines():
    if "WOULD-COPY ui-audit/" in line:
        plan_files.add(line.split("WOULD-COPY ui-audit/", 1)[1].strip())

print("=" * 78)
print("0. USE-vs-MENTION control -- the repair script MENTIONS the pattern it removes")
for label, tree in (("repo", repo), ("daily", daily), ("vault", vault)):
    u = sorted(k for k, v in tree.items() if v["old_use"])
    m = sorted(k for k, v in tree.items() if v["old_mention"] and not v["old_use"])
    n = sorted(k for k, v in tree.items() if v["has_new"])
    print(f"  {label:6s} scanned={len(tree):3d}  USES-old={len(u)}  mentions-only={len(m)}  has-__isMain={len(n)}")
    print(f"         USES-old : {u}")
    print(f"         mentions : {m}")
if not any(v["old_mention"] for v in repo.values()):
    print("  ! control inert: no MENTION found anywhere, so the split proves nothing")

print()
print("=" * 78)
print("1. THE INTERSECTION -- are the defective vault files in the deploy plan?")
defective = sorted(k for k, v in vault.items() if v["old_use"])
print(f"  vault files USING the old guard (n={len(defective)}):")
covered, missed = [], []
for rel in defective:
    inplan = rel in plan_files
    repo_fixed = repo.get(rel, {}).get("has_new") and not repo.get(rel, {}).get("old_use")
    print(
        f"    {rel:36s} in-plan={'YES' if inplan else 'NO ':3s} "
        f"repo-copy-fixed={'YES' if repo_fixed else 'NO'}"
    )
    (covered if inplan else missed).append(rel)
print()
print(f"  CLOSED by one dry-run --apply : {len(covered)}/{len(defective)}  {covered}")
print(f"  STILL OPEN (refused/absent)   : {len(missed)}/{len(defective)}  {missed}")
print(f"  plan offers {len(plan_files)} ui-audit files total; "
      f"{len(plan_files - set(defective))} of them are unrelated to this defect")

out = {
    "vault_defective_uses": defective,
    "plan_ui_audit_files": sorted(plan_files),
    "closed_by_plan": covered,
    "still_open": missed,
    "counts": {
        "repo_uses_old": sorted(k for k, v in repo.items() if v["old_use"]),
        "repo_mentions_only": sorted(
            k for k, v in repo.items() if v["old_mention"] and not v["old_use"]
        ),
        "daily_uses_old": sorted(k for k, v in daily.items() if v["old_use"]),
    },
}
Path(
    r"C:/Users/Prekzursil/source/ast-integrate/command-center/grounding/S2-VAULT-GAP.json"
).write_text(json.dumps(out, indent=1), encoding="utf-8")
print("\nwrote S2-VAULT-GAP.json")
