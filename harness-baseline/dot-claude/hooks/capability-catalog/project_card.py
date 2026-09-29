#!/usr/bin/env python
"""PROJECT-CARD — per-project intelligence appended after the global capability catalog.

Renders a compact (<=40 line, <=~800 token) card for the CURRENT project so the user's
terse prompts land with the right context already in front of the model: stack +
entrypoints, a few load-bearing invariants, the default tools/skills, the project's
quality-bar, and a 2-3 bullet "where we left off" resume-strip.

Data sources (all read-only, all fail-open):
  - the card itself: repo-committed ``<worktree>/.claude/project-card.json`` (wins), else
    generated ``~/.claude/projects/<canonical_id>/project-card.json``. Schema mirrors the
    capability catalog's data-driven JSON (``project-card/v1``).
  - the resume-strip: a pure projection of the (identity-unified) event-ledger
    ``state.json`` (open failures + last milestone + goal) and, if present,
    ``<worktree>/.beads/context/execution-state.md`` / ``active-plan.md``.

This module never writes during inject and never raises into the hook — any problem yields
an empty card and the global catalog still ships. ``seed`` (a CLI sub-command) is the only
writer and is run explicitly, never from the hook.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

THIS = Path(__file__).resolve().parent
HOME = Path.home()
# Generated cards live at <PROJECTS_DIR>/<canonical_id>/project-card.json. Defaults to the
# spec'd ~/.claude/projects; overridable (relocation / testing) without code changes.
PROJECTS_DIR = Path(
    os.environ.get("CLAUDE_PROJECT_CARDS_DIR", str(HOME / ".claude" / "projects"))
)
MAX_CHARS = 3200  # ~800 tokens hard budget for the whole block
SCHEMA = "project-card/v1"


# ── shared-module imports (best-effort; never crash the hook) ───────────────────────
def _imp(rel_dir: str, mod: str):
    try:
        p = str((THIS.parent / rel_dir).resolve())
        if p not in sys.path:
            sys.path.insert(0, p)
        return __import__(mod)
    except Exception:
        return None


def _projid():
    return _imp("_shared", "projid")


def _ledger():
    return _imp("event-ledger", "ledger")


# ── card location / loading ─────────────────────────────────────────────────────────
def card_path_for(canonical_id: str) -> Path:
    return PROJECTS_DIR / canonical_id / "project-card.json"


def _load_json(p: Path) -> dict | None:
    try:
        if p.is_file():
            return json.loads(p.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        pass
    return None


def load_card(worktree: str, canonical_id: str) -> dict | None:
    """Repo-committed card wins (so it travels with the project); else the generated one."""
    committed = _load_json(Path(worktree) / ".claude" / "project-card.json")
    if committed:
        return committed
    return _load_json(card_path_for(canonical_id))


# ── resume-strip (DELIVERABLE 3): read-only projection of existing stores ───────────--
_POS_KW = (
    "current",
    "position",
    "next",
    "status",
    "wu",
    "resume",
    "left off",
    "in progress",
)


def _first_meaningful_line(path: Path, limit: int = 30) -> str | None:
    """Best 'where we are' line from a beads context md: prefer a position/status body line,
    else the first real content line, else the title — skipping headings/comments/fences."""
    try:
        if not path.is_file():
            return None
        raw_lines = path.read_text(encoding="utf-8", errors="replace").splitlines()[
            :limit
        ]
    except Exception:
        return None
    content, heading = [], None
    for raw in raw_lines:
        s = raw.strip()
        if not s or s.startswith(("<!--", "---", "```", ">")):
            continue
        if s.startswith("#"):
            if heading is None:
                heading = s.lstrip("#").strip()
            continue
        content.append(s.lstrip("-*").strip())
    for c in content:
        if any(k in c.lower() for k in _POS_KW):
            return c[:160]
    if content:
        return content[0][:160]
    return heading[:160] if heading else None


def build_resume_strip(worktree: str) -> list[str]:
    """2-3 bullets: where we left off. Pure projection of the (identity-unified) event-ledger
    state.json (last milestone + open failures) and ``.beads/context/`` — the spec'd sources.
    ``goal`` is only used as filler (the event-ledger's own SessionStart replay already shows
    the goal prominently, so we avoid duplicating it here). Returns [] when there's nothing."""
    mile = fail = goal = None
    led = _ledger()
    if led is not None:
        try:
            st = led.state(worktree)
            goal = st.get("goal")
            ofs = st.get("open_failures") or []
            if ofs:
                last = ofs[-1]
                pc = (
                    f" [if: {last['preconditions']}]"
                    if last.get("preconditions")
                    else ""
                )
                fail = (
                    f"open failure (re-test cheaply): {str(last.get('text'))[:120]}{pc}"
                )
            mlist = [
                e
                for e in led.replay(worktree, 80)
                if e.get("kind") == "milestone" and e.get("text")
            ]
            if mlist:
                mile = f"last milestone: {str(mlist[-1]['text'])[:130]}"
        except Exception:
            pass
    pos = None
    for fname in ("execution-state.md", "active-plan.md"):
        line = _first_meaningful_line(Path(worktree) / ".beads" / "context" / fname)
        if line:
            pos = f"{fname.split('.')[0]}: {line}"
            break
    ordered = [b for b in (mile, fail, pos) if b]  # spec priority
    if len(ordered) < 3 and goal:  # goal as filler only
        ordered.append(f"goal: {str(goal)[:140]}")
    return ordered[:3]


# ── rendering ────────────────────────────────────────────────────────────────────--
def _items(card: dict, key: str, limit: int) -> list[str]:
    v = card.get(key) or []
    if isinstance(v, str):
        v = [v]
    return [str(x) for x in v][:limit]


def render_block(
    card: dict | None, resume: list[str], pid_name: str, canonical_id: str
) -> str:
    """Compose the <=40-line, <=MAX_CHARS card block. Returns '' if there is nothing useful."""
    lines: list[str] = []
    name = (card or {}).get("display_name") or pid_name
    lines.append(
        f"[project card: {name}] (id {canonical_id[:12]}) — apply this project's context to terse prompts."
    )
    if card:
        if card.get("stack"):
            lines.append(f"- stack: {str(card['stack'])[:200]}")
        eps = _items(card, "entrypoints", 6)
        if eps:
            lines.append(f"- entrypoints: {', '.join(eps)}")
        inv = _items(card, "invariants", 6)
        if inv:
            lines.append("- invariants (load-bearing — do not break):")
            lines += [f"    - {x[:160]}" for x in inv]
        tools = _items(card, "tools", 6)
        if tools:
            lines.append(f"- default tools: {', '.join(tools)}")
        skills = _items(card, "skills", 6)
        if skills:
            lines.append(f"- default skills: {', '.join(skills)}")
        if card.get("quality_bar"):
            lines.append(f"- quality bar: {str(card['quality_bar'])[:200]}")
        if card.get("left_off") and not resume:
            resume = [str(card["left_off"])[:160]]
    else:
        lines.append(
            "- (no card yet — seed one: `python ~/.claude/hooks/capability-catalog/"
            "project_card.py seed`; or commit .claude/project-card.json)"
        )
    if resume:
        lines.append("- where we left off:")
        lines += [f"    - {b}" for b in resume]
    if len(lines) <= 1 and not resume:
        return ""  # nothing worth injecting
    block = "\n".join(lines[:40])
    if len(block) > MAX_CHARS:
        block = (
            block[:MAX_CHARS].rsplit("\n", 1)[0] + "\n    … (card truncated to budget)"
        )
    return block


def build_block(cwd: str | None = None) -> str:
    """Top-level entry for the SessionStart hook. Always returns a string ('' on any issue)."""
    try:
        pj = _projid()
        if pj is None:
            return ""
        pid = pj.resolve(cwd)
        card = load_card(pid.worktree_path, pid.canonical_id)
        resume = build_resume_strip(pid.worktree_path)
        # Only inject for an actual project context (skip a bare non-git cwd with no card/resume)
        if pid.source == "cwd" and not card and not resume:
            return ""
        return render_block(card, resume, pid.display_name, pid.canonical_id)
    except Exception:
        return ""


# ── seeding (the only writer; explicit CLI, never run from the hook) ────────────────--
_STACK_MARKERS = [
    ("package.json", "Node/TypeScript"),
    ("pnpm-workspace.yaml", "Node monorepo"),
    ("pyproject.toml", "Python"),
    ("setup.py", "Python"),
    ("requirements.txt", "Python"),
    ("Cargo.toml", "Rust"),
    ("go.mod", "Go"),
    ("pom.xml", "Java/Maven"),
    ("build.gradle", "Java/Gradle"),
    ("Gemfile", "Ruby"),
    ("composer.json", "PHP"),
]
_ENTRY_CANDIDATES = [
    "src/main.ts",
    "src/index.ts",
    "src/main.tsx",
    "src/index.js",
    "main.py",
    "app.py",
    "src/main.py",
    "cmd/main.go",
    "src/main.rs",
]


def _detect_stack(root: Path) -> tuple[str, list[str]]:
    found, eps = [], []
    try:
        for marker, label in _STACK_MARKERS:
            if (root / marker).is_file() and label not in found:
                found.append(label)
        # also scan for a .csproj/.sln (globbed, not a fixed name)
        if any(root.glob("*.csproj")) or any(root.glob("*.sln")):
            found.append(".NET")
        for cand in _ENTRY_CANDIDATES:
            if (root / cand).is_file():
                eps.append(cand)
    except Exception:
        pass
    return (" · ".join(found) or "(unknown — edit me)", eps[:6])


def seed(cwd: str | None, force: bool = False) -> Path | None:
    pj = _projid()
    if pj is None:
        print("FAILED:seed projid unavailable", file=sys.stderr)
        return None
    pid = pj.resolve(cwd)
    dest = card_path_for(pid.canonical_id)
    if dest.is_file() and not force:
        print(f"card already exists: {dest} (use --force to overwrite)")
        return dest
    root = Path(pid.toplevel or pid.worktree_path)
    stack, eps = _detect_stack(root)
    resume = build_resume_strip(pid.worktree_path)
    card = {
        "_doc": "Per-project card injected after the global capability catalog at SessionStart. "
        "Edit freely; commit a copy to <repo>/.claude/project-card.json to share it. "
        "Keep it terse + high-signal (<=~800 tokens render budget).",
        "schema": SCHEMA,
        "display_name": pid.display_name,
        "canonical_id": pid.canonical_id,
        "remote": pid.remote,
        "stack": stack,
        "entrypoints": eps,
        "invariants": ["TODO: 3-6 load-bearing facts the agent must not break"],
        "tools": ["TODO: default MCP/tools for this project (e.g. serena, repomix)"],
        "skills": ["TODO: default skills (e.g. the project's own skill)"],
        "quality_bar": "TODO: the project's blocking gate (coverage / lint / tests)",
        "left_off": resume[0] if resume else "",
        "updated_at": time.strftime("%Y-%m-%d"),
    }
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(card, indent=2, ensure_ascii=False), encoding="utf-8")
    print(
        f"SUCCESS:seed wrote {dest}\n  stack={stack} entrypoints={eps}\n  "
        f"(fill in invariants/tools/skills/quality_bar — they seed as TODO)"
    )
    return dest


def main(argv: list[str]) -> int:  # pragma: no cover - thin CLI
    import argparse

    ap = argparse.ArgumentParser(prog="project_card")
    ap.add_argument(
        "cmd", nargs="?", default="show", choices=["show", "render", "seed"]
    )
    ap.add_argument("--cwd", default=None)
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args(argv)
    if a.cmd == "seed":
        return 0 if seed(a.cwd, a.force) else 1
    block = build_block(a.cwd)
    print(block or "(no project card / resume context for this cwd)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
