"""B5: reconcile the mechanically-safe LIVE->REPO drift into .agents/skills.

Only two classes are copied, and BOTH are provably non-destructive to repo content:

  LEFT-ONLY-FILE  the repo has no bytes at that path at all -> nothing can be lost.
  LEFT-AHEAD      the live copy's line-set strictly contains the repo copy's -> superset.

Plus ONE hand-audited exception, the six ui-audit entry points.  They are DIVERGED, but the
divergence was read line-by-line (command-center/build/_b4_uiaudit_diff.py) and is exactly:
  * 5 files: repo-unique == the single buggy lexical main-guard line the live fix REPLACES;
             live-unique == that fix (a realpathSync import + an 11-line __isMain block).
             329 - 1 + 12 == 340 etc, so the copy is exact and loses only the defect.
  * critique.mjs: all 19 repo-unique lines have a verified live superseding equivalent
             (nine dimensions not eight, reconcile mode, personas, expanded usage); the one
             dropped import symbol, `basename`, has 0 uses in the live file.

Vendored upstream clones are NEVER copied: crypto-ctf/RsaCtfTool is a 4.97 MB third-party
checkout that .gitignore already excludes under skills/ (line 40-41).

Usage:  python _b5_reconcile.py            # dry run
        python _b5_reconcile.py --apply
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

REPO = Path(r"C:/Users/Prekzursil/source/ast-integrate")
DAILY = Path(r"C:/Users/Prekzursil/.claude/skills.daily")
DEST = REPO / ".agents" / "skills"
BUCKETS = json.loads(
    (REPO / "command-center" / "build" / "B2-reconcile-buckets.json").read_text(encoding="utf-8")
)

# vendored third-party checkouts: present live, deliberately absent from git.
VENDORED_PREFIXES = ("crypto-ctf/RsaCtfTool/",)

# nested self-copy: cv-studio/cv-studio/** is the skill duplicated inside itself.  The prior
# audit says DROP not merge; dropping is destructive to the live tree and this lane defaults
# hard to KEEP, so it is neither copied nor deleted -- it is reported and left alone.
LEAVE_ALONE_PREFIXES = ("cv-studio/cv-studio/",)

# hand-audited DIVERGED exception, see the module docstring.
UI_AUDIT_FIX = [
    "ui-audit/capture.mjs",
    "ui-audit/run_audit.mjs",
    "ui-audit/layout_lint.mjs",
    "ui-audit/visual_diff.mjs",
    "ui-audit/axe_scan.mjs",
    "ui-audit/critique.mjs",
]


def classify(rel: str) -> str | None:
    if any(rel.startswith(p) for p in VENDORED_PREFIXES):
        return None
    if any(rel.startswith(p) for p in LEAVE_ALONE_PREFIXES):
        return None
    return rel


def collect() -> dict[str, list[str]]:
    plan: dict[str, list[str]] = {"LEFT-ONLY-FILE": [], "LEFT-AHEAD": [], "UI-AUDIT-FIX": []}
    for rel in BUCKETS.get("LEFT-ONLY-FILE", []):
        if classify(rel):
            plan["LEFT-ONLY-FILE"].append(rel)
    for rel in BUCKETS.get("LEFT-AHEAD", []):
        if classify(rel):
            plan["LEFT-AHEAD"].append(rel)
    plan["UI-AUDIT-FIX"] = list(UI_AUDIT_FIX)
    return plan


def main() -> int:
    apply = "--apply" in sys.argv
    plan = collect()
    copied: list[str] = []
    for bucket, rels in plan.items():
        print(f"== {bucket}: {len(rels)} files")
        for rel in rels:
            src, dst = DAILY / rel, DEST / rel
            if not src.exists():
                print(f"   SKIP-missing-src {rel}")
                continue
            if bucket == "LEFT-ONLY-FILE" and dst.exists():
                print(f"   SKIP-dst-exists  {rel}")
                continue
            print(f"   {'COPY' if apply else 'WOULD-COPY'} {rel}")
            if apply:
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
            copied.append(rel)
    print(f"\ntotal {'copied' if apply else 'would copy'}: {len(copied)}")
    excluded = [r for r in BUCKETS.get("LEFT-ONLY-FILE", []) if not classify(r)]
    print(f"deliberately NOT copied (vendored clone / nested self-copy): {len(excluded)}")
    (REPO / "command-center" / "build" / "B5-reconcile-applied.json").write_text(
        json.dumps({"applied": apply, "copied": sorted(copied),
                    "excluded": sorted(excluded)}, indent=1),
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
