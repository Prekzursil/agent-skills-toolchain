"""INTEGRATE / step I7 -- what would widening the gate's corpus cost?

The shipped gate covers tracked .md under command-center/ and docs/ (255 files). The repo
has ~4,900 tracked .md. Leaving the rest ungated is a real residual, and a residual is only
honest if it carries a number, so this pre-runs the settling experiment by IMPORTING the
shipped resolver rather than reimplementing it -- a second implementation would measure my
copy of the rule, not the rule.

Reported per scope: commands found, distinct targets, unresolved targets, and how the
unresolved ones break down, so the next lane can triage instead of re-measuring.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
from collections import Counter
from pathlib import Path

ROOT = Path("C:/Users/Prekzursil/source/ast-integrate")
GATE = ROOT / "command-center/slop-report/check_published_commands.py"
OUT = ROOT / "command-center/slop-report/_i7_scope_cost.out.json"

spec = importlib.util.spec_from_file_location("cpc", GATE)
assert spec and spec.loader
cpc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cpc)


def git(*args):
    return subprocess.run(
        ["git", "-C", str(ROOT), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    ).stdout


def main() -> int:
    tracked = {p for p in git("ls-files").splitlines() if p}
    all_md = sorted(p for p in tracked if p.endswith(".md"))

    scopes = {
        "shipped (command-center/ + docs/, minus harvest)": [
            p for p in all_md if cpc.in_corpus(p)
        ],
        "harvested transcripts (deliberately excluded)": [
            p
            for p in all_md
            if p.startswith(cpc.INCLUDE_PREFIXES) and p.startswith(cpc.EXCLUDE_PREFIXES)
        ],
        "every tracked .md in the repo": all_md,
    }

    out: dict = {"rev": git("rev-parse", "HEAD").strip(), "scopes": {}}
    for label, corpus in scopes.items():
        total = 0
        unresolved: list[dict] = []
        targets: set[str] = set()
        for path in corpus:
            for lineno, line in enumerate(cpc.blob(str(ROOT), path).splitlines(), 1):
                for m in cpc.CMD.finditer(line):
                    total += 1
                    tgt = m.group(1)
                    targets.add(tgt)
                    ok, _ = cpc.resolve(tgt, path, tracked)
                    if not ok:
                        unresolved.append(
                            {"citer": path, "line": lineno, "target": tgt}
                        )
        top = Counter(u["target"].split("/")[0] for u in unresolved)
        out["scopes"][label] = {
            "corpus_files": len(corpus),
            "commands_found": total,
            "distinct_targets": len(targets),
            "unresolved_commands": len(unresolved),
            "unresolved_distinct_targets": len({u["target"] for u in unresolved}),
            "unresolved_by_leading_segment": dict(top.most_common()),
            "unresolved_citer_trees": dict(
                Counter(u["citer"].split("/")[0] for u in unresolved).most_common()
            ),
        }

    OUT.write_text(
        json.dumps(out, indent=1, sort_keys=True), encoding="utf-8", newline="\n"
    )
    for label, s in out["scopes"].items():
        print(
            f"{label}\n   files={s['corpus_files']:5d} cmds={s['commands_found']:5d} "
            f"targets={s['distinct_targets']:4d} UNRESOLVED={s['unresolved_commands']:4d} "
            f"({s['unresolved_distinct_targets']} distinct)"
        )
        if s["unresolved_commands"]:
            print(f"   by leading segment: {s['unresolved_by_leading_segment']}")
            print(f"   citer trees:        {s['unresolved_citer_trees']}")
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
