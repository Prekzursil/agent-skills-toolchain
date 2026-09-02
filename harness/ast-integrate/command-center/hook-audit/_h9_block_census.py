r"""H9 — BLOCK vs INJECT census across all three hook planes.

AGENTS.md §6: exit 2 (block) is for irreversible/dangerous ops ONLY; everything
else must be exit 0 + additionalContext (inject).

Claude Code has three distinct block channels, and counting only one undercounts:
  1. process exit code 2                       (PreToolUse/PostToolUse deny)
  2. {"decision": "block", ...}                (Stop / PreToolUse legacy shape)
  3. hookSpecificOutput.permissionDecision = "deny"   (current PreToolUse shape)

USE-vs-MENTION: a docstring or a comment SAYING "never blocks" is not a block, and
a rule file quoting `exit 2` is not a hook. Every hit is therefore classified by
whether it sits in CODE or in a STRING/COMMENT, using tokenize -- not a regex over
prose. Control: a file known to block (deny-credential-reads) must come back
BLOCKS, and a file whose docstring says "NEVER blocks" while containing no code
hit must come back INJECT.
"""

from __future__ import annotations

import io
import json
import re
import tokenize
from pathlib import Path

REPO = Path("C:/Users/Prekzursil/source/ast-integrate")
LIVE = Path.home() / ".claude" / "hooks"
OUT = REPO / "command-center" / "hook-audit"

EXIT2 = re.compile(r"(?:sys\.)?exit\(\s*2\s*\)|return\s+2\b|SystemExit\(\s*2\s*\)")
DENY = re.compile(
    r"permissionDecision|\"decision\"\s*:\s*\"block\"|'decision'\s*:\s*'block'"
)


def code_only(src: str) -> str:
    """Strip comments and string literals so a MENTION cannot count as a USE."""
    out = []
    try:
        for tok in tokenize.generate_tokens(io.StringIO(src).readline):
            if tok.type in (tokenize.COMMENT, tokenize.STRING):
                continue
            out.append(tok.string)
    except (tokenize.TokenError, IndentationError, SyntaxError):
        return src  # fail loud-ish: keep everything rather than silently under-count
    return " ".join(out)


def strings_only(src: str) -> str:
    out = []
    try:
        for tok in tokenize.generate_tokens(io.StringIO(src).readline):
            if tok.type == tokenize.STRING:
                out.append(tok.string)
    except (tokenize.TokenError, IndentationError, SyntaxError):
        return ""
    return " ".join(out)


def classify(p: Path) -> dict:
    src = p.read_text(encoding="utf-8", errors="replace")
    c, s = code_only(src), strings_only(src)
    # permissionDecision is emitted as a JSON KEY, i.e. inside a string literal or a
    # dict key -- so for DENY the string surface is the real one. exit 2 is code.
    return {
        "exit2_code": bool(EXIT2.search(c)),
        "exit2_mention_only": bool(EXIT2.search(s)) and not bool(EXIT2.search(c)),
        "deny_shape": bool(DENY.search(src)),
        "deny_value_deny": bool(
            re.search(r'permissionDecision["\']?\s*[:=]\s*["\']deny', src)
        ),
        "docstring_says_never_blocks": bool(
            re.search(r"never blocks|inject-only|NEVER blocks", src, re.I)
        ),
    }


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    rows = {}
    for p in sorted(LIVE.rglob("*.py")):
        if "__pycache__" in str(p) or p.name.startswith("test_"):
            continue
        rel = str(p.relative_to(LIVE)).replace("\\", "/")
        rows[rel] = classify(p)

    # --- controls -------------------------------------------------------
    ctl_block = next((k for k in rows if k.startswith("deny-credential-reads/")), None)
    if not ctl_block or not (
        rows[ctl_block]["exit2_code"] or rows[ctl_block]["deny_value_deny"]
    ):
        print(f"FAILED:h9 block-control {ctl_block} did not register as blocking")
        return 1
    ctl_inject = next(
        (
            k
            for k, v in rows.items()
            if v["docstring_says_never_blocks"]
            and not v["exit2_code"]
            and not v["deny_value_deny"]
        ),
        None,
    )
    if not ctl_inject:
        print(
            "FAILED:h9 no inject-control found -- detector cannot distinguish the two"
        )
        return 1
    print(f"  control BLOCK : {ctl_block} -> {rows[ctl_block]}")
    print(f"  control INJECT: {ctl_inject}")

    blockers = sorted(
        k for k, v in rows.items() if v["exit2_code"] or v["deny_value_deny"]
    )
    mention_only = sorted(k for k, v in rows.items() if v["exit2_mention_only"])
    contradictions = sorted(
        k
        for k, v in rows.items()
        if v["docstring_says_never_blocks"]
        and (v["exit2_code"] or v["deny_value_deny"])
    )

    # which of the blockers are actually WIRED on plane P1/P2?
    man = json.loads((LIVE / "_dispatch/manifest.json").read_text(encoding="utf-8"))
    wired_p1 = {
        (c.get("script") or "").replace("\\", "/")
        for blob in (man.get("events") or {}).values()
        for c in (blob or {}).get("checks") or []
    }
    st = json.dumps(
        json.loads(
            (Path.home() / ".claude/settings.json").read_text(encoding="utf-8")
        ).get("hooks")
        or {}
    ).replace("\\\\", "/")

    print(f"\n== BLOCK-CAPABLE hook scripts ({len(blockers)})")
    for b in blockers:
        p1 = b in wired_p1
        p2 = b in st
        where = "P1-dispatcher" if p1 else ("P2-settings" if p2 else "DARK")
        note = " <-- BLOCK inside the inject-only dispatcher" if p1 else ""
        print(f"   {where:14s} {b}{note}")

    print(
        f"\n== exit-2 MENTIONED in a string but never in code ({len(mention_only)}): {mention_only}"
    )
    print(
        f"== docstring says never-blocks BUT code can block ({len(contradictions)}): {contradictions}"
    )

    (OUT / "H9-BLOCK-CENSUS.json").write_text(
        json.dumps(
            {
                "controls": {"block": ctl_block, "inject": ctl_inject},
                "rows": rows,
                "blockers": blockers,
                "mention_only": mention_only,
                "contradictions": contradictions,
                "blockers_in_dispatcher": sorted(b for b in blockers if b in wired_p1),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print("SUCCESS:h9-block-census")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
