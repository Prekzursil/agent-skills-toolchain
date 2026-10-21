"""ADV-0019 Probe 1 (Windows full checkout, 2026-10-21): extract every tool/command
token from instruction artifacts (AGENTS.md, skills/**/SKILL.md, .agents/rules) and
emit the candidate set for the live-inventory difference. Includes the retired-budget
calibration reach control."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent

MCP_RE = re.compile(r"\bmcp__[a-z0-9][a-z0-9_-]*__[a-z0-9][a-z0-9_-]*\b")
MCP_STAR_RE = re.compile(r"\bmcp__[a-z0-9][a-z0-9_-]*__\*")
CMD_RE = re.compile(r"`([a-z][a-z0-9_-]{1,38})`")
RETIRE_WORDS = ("gone", "retired", "removed", "no longer", "do not follow", "not a valid")


def instruction_files() -> list[Path]:
    files: list[Path] = []
    ag = REPO / "AGENTS.md"
    if ag.is_file():
        files.append(ag)
    for pat in ("skills/*/SKILL.md", "skills-*/*/SKILL.md"):
        files.extend(sorted(REPO.glob(pat)))
    rules = REPO / ".agents/rules"
    if rules.is_dir():
        files.extend(sorted(rules.rglob("*.md")))
    return files


def main() -> int:
    files = instruction_files()
    mcp_tokens: dict[str, list[str]] = {}
    cmd_tokens: dict[str, set[str]] = {}
    budget_reach: list[str] = []
    for f in files:
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        rel = str(f.relative_to(REPO)).replace("\\", "/")
        for m in MCP_RE.finditer(text):
            mcp_tokens.setdefault(m.group(0), []).append(rel)
        for m in MCP_STAR_RE.finditer(text):
            mcp_tokens.setdefault(m.group(0), []).append(rel)
        for m in CMD_RE.finditer(text):
            tok = m.group(1)
            # context: is this inside a retirement notice?
            line_start = text.rfind("\n", 0, m.start()) + 1
            line = text[line_start:text.find("\n", m.start())]
            ctx = "MENTION-RETIRED" if any(w in line.lower() for w in RETIRE_WORDS) else "USE"
            cmd_tokens.setdefault(tok, set()).add(ctx)
            if tok in ("get_budget", "check_budget"):
                budget_reach.append(f"{rel}: {ctx}")
    present_control = [t for t in ("git", "python") if t in cmd_tokens]

    payload = {
        "probe": "probe1-extract",
        "files_walked": len(files),
        "total_bytes": sum(f.stat().st_size for f in files if f.is_file()),
        "mcp_tokens": {k: sorted(set(v)) for k, v in sorted(mcp_tokens.items())},
        "cmd_token_count": len(cmd_tokens),
        "cmd_tokens_sample": {k: sorted(v) for k, v in sorted(cmd_tokens.items())[:400]},
        "budget_token_reach": budget_reach,
        "controls": {
            "CTRL-LSFILES-ALIVE": len(files) > 100,          # harness walked a real estate
            "CTRL-ABSENT-BUDGET-TOKEN-REACH": len(budget_reach) > 0,  # retired tokens reached
            "CTRL-PRESENT-TOKEN-EXTRACTED": len(present_control) > 0,  # live tools in corpus
        },
    }
    out = [
        f"SUCCESS:adv0019-probe1 {len(files)} instruction files walked "
        f"({payload['total_bytes']} bytes); {len(mcp_tokens)} distinct mcp__ tokens; "
        f"{len(cmd_tokens)} distinct backticked command tokens; budget-token reach: "
        f"{len(budget_reach)} sites",
    ]
    for k, v in payload["controls"].items():
        out.append(f"  {k}: {'PASS' if v else 'FAIL'}")
    out.append(f"  present-control tokens found: {present_control}")
    text_out = "\n".join(out) + "\n"
    print(text_out, end="")
    (OUT / "probe1-extract.json").write_text(json.dumps(payload, indent=1) + "\n", encoding="utf-8")
    (OUT / "probe1-extract.raw.txt").write_text(text_out, encoding="utf-8")
    ok = all(payload["controls"].values())
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
