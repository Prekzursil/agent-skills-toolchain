#!/usr/bin/env python
"""Self-contained tests for project_card + the inject.py extension.
Run: python test_project_card.py  (uses temp dirs only)."""

from __future__ import annotations

import importlib
import io
import json
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "_shared"))
sys.path.insert(0, str(HERE.parent / "event-ledger"))
fails = []


def check(name, cond):
    print(f"  {'OK ' if cond else 'BAD'}  {name}")
    if not cond:
        fails.append(name)


def main():
    tmp = Path(tempfile.mkdtemp(prefix="card-test-"))
    os.environ["EVENT_LEDGER_ROOT"] = str(tmp / "ledger")

    import ledger

    importlib.reload(ledger)  # pick up the temp EVENT_LEDGER_ROOT
    import project_card

    importlib.reload(project_card)
    project_card.PROJECTS_DIR = (
        tmp / "projects"
    )  # never pollute the real ~/.claude/projects

    # a non-git worktree -> projid source==cwd -> deterministic legacy slug
    wt = tmp / "proj_work"
    wt.mkdir()
    wt_s = str(wt)

    print("== resume-strip projects ledger goal/failure/milestone (read-only) ==")
    ledger.append(wt_s, "goal", text="ship per-project intelligence")
    ledger.append(
        wt_s,
        "failure",
        text="catalog re-dumped on compact",
        preconditions="source==compact",
    )
    ledger.append(wt_s, "milestone", text="projid resolver shipped")
    (wt / ".beads" / "context").mkdir(parents=True, exist_ok=True)
    (wt / ".beads" / "context" / "execution-state.md").write_text(
        "# Execution State\n\nCurrent position: WU3 resume-strip\n", encoding="utf-8"
    )
    strip = project_card.build_resume_strip(wt_s)
    joined = " | ".join(strip)
    check("resume includes open failure", "catalog re-dumped" in joined)
    check("resume includes last milestone", "projid resolver shipped" in joined)
    check(
        "resume reads .beads execution-state",
        any("WU3 resume-strip" in b for b in strip),
    )
    check("resume capped at 3 bullets", len(strip) <= 3)
    # goal is filler-only: surfaces when there is no milestone/failure/position signal
    gonly = tmp / "goalonly"
    gonly.mkdir()
    ledger.append(str(gonly), "goal", text="solo objective xyz")
    check(
        "goal surfaces as filler when alone",
        any(
            "solo objective xyz" in b
            for b in project_card.build_resume_strip(str(gonly))
        ),
    )

    print("== load_card: repo-committed wins over generated ==")
    (wt / ".claude").mkdir(parents=True, exist_ok=True)
    (wt / ".claude" / "project-card.json").write_text(
        json.dumps(
            {
                "schema": "project-card/v1",
                "display_name": "CommittedProj",
                "stack": "Electron + TS",
                "invariants": ["never mutate state"],
            }
        ),
        encoding="utf-8",
    )
    pj = importlib.import_module("projid")
    pid = pj.resolve(wt_s)
    gen = project_card.card_path_for(pid.canonical_id)
    gen.parent.mkdir(parents=True, exist_ok=True)
    gen.write_text(json.dumps({"display_name": "GeneratedProj"}), encoding="utf-8")
    card = project_card.load_card(wt_s, pid.canonical_id)
    check("committed card wins", card.get("display_name") == "CommittedProj")

    print("== render_block: budget + content ==")
    big = {
        "display_name": "Reframe",
        "stack": "Electron+Vite+TS",
        "entrypoints": ["frontend/src/main.ts", "sidecar/app.py"],
        "invariants": [
            f"invariant number {i} that is reasonably long " * 4 for i in range(12)
        ],
        "tools": ["serena", "repomix"],
        "skills": ["reframe"],
        "quality_bar": "100% coverage",
    }
    block = project_card.render_block(
        big, ["where we left off bullet"], "Reframe", "6e307b0aaed9"
    )
    check("render <= 40 lines", len(block.splitlines()) <= 40)
    check("render <= char budget", len(block) <= project_card.MAX_CHARS)
    check("render names the project", "Reframe" in block and "project card" in block)
    check("render includes quality bar", "100% coverage" in block)

    print("== build_block end-to-end (card + resume) ==")
    full = project_card.build_block(wt_s)
    check("build_block returns the committed project's card", "CommittedProj" in full)
    check("build_block appends where-we-left-off", "where we left off" in full)

    print("== build_block skips a bare non-git cwd with no card/resume ==")
    bare = tmp / "bare"
    bare.mkdir()
    check("bare cwd -> empty block", project_card.build_block(str(bare)) == "")

    print("== seed: detects stack + writes a card, no overwrite without --force ==")
    seedwt = tmp / "seedproj"
    seedwt.mkdir()
    (seedwt / "package.json").write_text('{"name":"x"}', encoding="utf-8")
    (seedwt / "src").mkdir()
    (seedwt / "src" / "main.ts").write_text("//", encoding="utf-8")
    dest = project_card.seed(str(seedwt))
    seeded = json.loads(Path(dest).read_text(encoding="utf-8"))
    check("seed detected Node/TS stack", "Node/TypeScript" in seeded.get("stack", ""))
    check("seed detected entrypoint", "src/main.ts" in seeded.get("entrypoints", []))
    check("seed schema tagged", seeded.get("schema") == project_card.SCHEMA)

    print("== inject.py extension: catalog + card, dedup, skip-compact ==")
    import inject

    importlib.reload(inject)
    inject.SEEN_DIR = tmp / "seen"  # isolate dedup from the real session store

    def run_inject(stdin_obj):
        old_in, old_out = sys.stdin, sys.stdout
        sys.stdin = io.StringIO(json.dumps(stdin_obj))
        cap = io.StringIO()
        sys.stdout = cap
        try:
            rc = inject.main()
        finally:
            sys.stdin, sys.stdout = old_in, old_out
        return rc, cap.getvalue()

    rc, out = run_inject({"source": "startup", "session_id": "s-card-1", "cwd": wt_s})
    payload = json.loads(out.strip().splitlines()[-1]) if out.strip() else {}
    ctx = payload.get("hookSpecificOutput", {}).get("additionalContext", "")
    check("inject emits global catalog", "[capabilities]" in ctx)
    check("inject appends the project card", "project card: CommittedProj" in ctx)

    rc, out2 = run_inject({"source": "startup", "session_id": "s-card-1", "cwd": wt_s})
    check("inject dedups within a session (2nd call silent)", out2.strip() == "")

    rc, out3 = run_inject({"source": "compact", "session_id": "s-card-2", "cwd": wt_s})
    check("inject skips source==compact", out3.strip() == "")

    print(
        f"\nRESULT: {'PASS' if not fails else 'FAIL: ' + ', '.join(fails)}  ({len(fails)} failures)"
    )
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
