#!/usr/bin/env python3
"""lint-frontmatter-keys - validate agent/skill/command frontmatter against the
frontmatter key vocabulary EXTRACTED FROM THE INSTALLED claude binary.

WHY THIS EXISTS
---------------
An unsupported frontmatter key is silently DROPPED by Claude Code. The author sees
no error and believes the behaviour is configured. Measured 2026-09-25 on this estate:
`~/.claude/agents/security-reviewer.md` shipped

    fallbacks: [claude-opus-4-8]
    server-side-fallback: true

Neither key exists anywhere in claude.exe's frontmatter vocabulary (`server-side-fallback`
and `serverSideFallback` are byte-absent from the 245 MB binary), so the intended
server-side model fallback was never in force. A doc-derived allowlist cannot catch this,
because the product's real vocabulary is not fully documented.

DESIGN: NO HARDCODED ALLOWLIST
------------------------------
The vocabulary is scanned out of the installed binary on every run, anchored on a literal
array prefix rather than a byte offset, so it survives a version bump instead of going
stale the way a pinned list would. If the anchor stops matching (product refactor), the
lint reports FAILED rather than silently passing everything -- fail closed on the
instrument, never a green from a broken detector.

SEVERITIES
----------
  ERROR  key absent from the binary's vocabulary entirely  -> the key is dead
  WARN   key known to the parser but not in the agent-config projection list
         (agent files only; e.g. `color`, which several working agents use)

EXIT CODES
----------
  0  no ERRORs (WARNs may be present)
  1  at least one ERROR
  2  instrument failure (binary not found / anchor not matched / no files scanned)

USAGE
    python lint-frontmatter-keys.py                     # default estate scan
    python lint-frontmatter-keys.py <path> [<path> ...] # explicit files or dirs
    python lint-frontmatter-keys.py --selftest          # both-states proof
    python lint-frontmatter-keys.py --print-vocab       # show extracted vocabulary
"""

from __future__ import annotations

import os
import re
import sys
import tempfile
from pathlib import Path

# ---------------------------------------------------------------- binary location

def find_binary() -> Path | None:
    """Locate the installed claude binary. Env override wins, then known layouts."""
    env = os.environ.get("CLAUDE_BINARY")
    if env and Path(env).is_file():
        return Path(env)
    home = Path(os.path.expanduser("~"))
    candidates = [
        home / "AppData/Roaming/npm/node_modules/@anthropic-ai/claude-code/bin/claude.exe",
        home / ".local/share/claude/bin/claude.exe",
        home / ".local/bin/claude.exe",
        Path("/usr/local/lib/node_modules/@anthropic-ai/claude-code/bin/claude"),
    ]
    for c in candidates:
        if c.is_file():
            return c
    # last resort: any claude.exe under a versions dir
    vdir = home / ".local/share/claude/versions"
    if vdir.is_dir():
        for p in sorted(vdir.rglob("claude*"), reverse=True):
            if p.is_file() and p.stat().st_size > 10_000_000:
                return p
    return None


# ---------------------------------------------------------------- vocabulary extraction

# Anchored on the array's opening literals, not a byte offset, so a relinked/rebuilt
# binary keeps resolving. Both arrays are emitted by the frontmatter layer.
PARSER_ANCHOR = b'["name","description","model","allowed-tools"'
AGENT_ANCHOR = b'["name","description","prompt","tools","disallowedTools"'

_ITEM = re.compile(rb'"([^"\\]{1,64})"')


def _read_array(data: bytes, anchor: bytes) -> list[str] | None:
    i = data.find(anchor)
    if i < 0:
        return None
    end = data.find(b"]", i)
    if end < 0 or end - i > 8192:
        return None
    return [m.group(1).decode("ascii", "replace") for m in _ITEM.finditer(data[i:end])]


def extract_vocab(binary: Path) -> tuple[set[str], set[str]]:
    """Return (parser_vocabulary, agent_projection_keys) read out of the binary."""
    data = binary.read_bytes()
    parser = _read_array(data, PARSER_ANCHOR)
    agent = _read_array(data, AGENT_ANCHOR)
    if not parser:
        raise RuntimeError(
            f"frontmatter vocabulary anchor not found in {binary} -- the product layout "
            "changed; update PARSER_ANCHOR before trusting this lint"
        )
    return set(parser), set(agent or ())


# ---------------------------------------------------------------- frontmatter parsing

# Top-level YAML mapping keys only: no leading whitespace, key then colon.
_KEY = re.compile(r"^([A-Za-z_][A-Za-z0-9_.-]*)\s*:")


def frontmatter_keys(path: Path) -> list[tuple[int, str]]:
    """Top-level frontmatter keys as (1-indexed line number, key). [] if no frontmatter."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return []
    out: list[tuple[int, str]] = []
    for n, raw in enumerate(lines[1:], start=2):
        if raw.strip() == "---":
            break
        m = _KEY.match(raw)
        if m:
            out.append((n, m.group(1)))
    return out


# ---------------------------------------------------------------- scanning

def default_targets() -> list[Path]:
    home = Path(os.path.expanduser("~"))
    return [home / ".claude/agents", home / ".claude/skills", home / ".claude/commands"]


def is_config_entrypoint(path: Path) -> bool:
    """True only for files Claude Code actually parses as frontmatter config.

    A skill directory routinely holds reference/data .md files with their OWN
    domain schema -- e.g. skills/code-security/rules/*.md use title/impact/
    impactDescription/tags. Those are data, not config, and linting them produced
    a wall of false positives on the first run. Only SKILL.md is the skill's
    entry point; agents/ and commands/ files are entry points directly.
    """
    if ".bak" in path.name:  # archived snapshots, not live config
        return False
    parts = path.parts
    if "skills" in parts:
        return path.name == "SKILL.md"
    return True  # agents/, commands/ (incl. namespaced subdirs)


def collect(targets: list[Path]) -> list[Path]:
    files: list[Path] = []
    for t in targets:
        if t.is_file():
            files.append(t)  # explicit file: always honour the caller
        elif t.is_dir():
            files.extend(p for p in sorted(t.rglob("*.md")) if is_config_entrypoint(p))
    return files


# Keys the ESTATE deliberately writes as its own provenance metadata. The product
# parses none of them (they are silently dropped), but dropping them costs nothing --
# they are read by estate tooling, not by Claude Code. Measured 2026-09-25: `origin`
# appears in 59 of 468 local SKILL.md files. Listed here so the gate stays ACTIONABLE:
# a permanently-red gate gets ignored, which is the same failure as a never-red one.
# Anything NOT in this set and not in the product vocabulary is a real ERROR.
ESTATE_METADATA = {"origin"}


def lint(files: list[Path], parser_vocab: set[str], agent_keys: set[str]):
    errors: list[str] = []
    warns: list[str] = []
    for path in files:
        is_agent = path.parent.name == "agents"
        for line, key in frontmatter_keys(path):
            if key in ESTATE_METADATA and key not in parser_vocab:
                warns.append(f"{path}:{line}: WARN '{key}' is estate provenance metadata - "
                             f"not parsed by the product (harmless, dropped)")
            elif key not in parser_vocab:
                errors.append(f"{path}:{line}: ERROR unknown frontmatter key '{key}' "
                              f"(absent from the installed binary's vocabulary - silently dropped)")
            elif is_agent and agent_keys and key not in agent_keys:
                warns.append(f"{path}:{line}: WARN '{key}' is parsed but not in the "
                             f"agent-config projection list")
    return errors, warns


# ---------------------------------------------------------------- self-test (both states)

_GOOD = """---
name: probe-good
description: control file using only supported keys
tools: ["Read"]
model: haiku
effort: low
maxTurns: 5
omitClaudeMd: true
---
body
"""

_BAD = """---
name: probe-bad
description: broken file carrying the real measured defect keys
tools: ["Read"]
fallbacks: [claude-opus-4-8]
server-side-fallback: true
---
body
"""


def selftest(parser_vocab: set[str], agent_keys: set[str]) -> int:
    """Both-states proof: must FAIL on the broken input and PASS on the good one."""
    with tempfile.TemporaryDirectory() as td:
        agents = Path(td) / "agents"
        agents.mkdir()
        good = agents / "probe-good.md"
        bad = agents / "probe-bad.md"
        good.write_text(_GOOD, encoding="utf-8")
        bad.write_text(_BAD, encoding="utf-8")

        ge, _ = lint([good], parser_vocab, agent_keys)
        be, _ = lint([bad], parser_vocab, agent_keys)

        ok = True
        print("--- both-states self-test ---")
        print(f"GOOD state (only supported keys): {len(ge)} error(s) -- "
              f"{'PASS (expected 0)' if not ge else 'FAIL'}")
        for e in ge:
            print("   unexpected: " + e)
        if ge:
            ok = False

        want = {"fallbacks", "server-side-fallback"}
        got = {e.split("'")[1] for e in be if "'" in e}
        print(f"BROKEN state (real defect keys): {len(be)} error(s) -- "
              f"{'PASS (fires)' if be else 'FAIL (silent in broken state = measures nothing)'}")
        for e in be:
            print("   " + e.split(": ", 1)[1])
        if not be or not want.issubset(got):
            print(f"   expected to flag {sorted(want)}, flagged {sorted(got)}")
            ok = False

        print()
        if ok:
            print("SUCCESS:lint-frontmatter-keys-selftest both states proven "
                  "(fires on broken, silent on good)")
            return 0
        print("FAILED:lint-frontmatter-keys-selftest both-states proof did not hold")
        return 1


# ---------------------------------------------------------------- main

def main(argv: list[str]) -> int:
    args = argv[1:]
    binary = find_binary()
    if binary is None:
        print("FAILED:lint-frontmatter-keys no installed claude binary found "
              "(set CLAUDE_BINARY to override)")
        return 2
    try:
        parser_vocab, agent_keys = extract_vocab(binary)
    except RuntimeError as exc:
        print(f"FAILED:lint-frontmatter-keys {exc}")
        return 2

    print(f"binary: {binary}")
    print(f"vocabulary: {len(parser_vocab)} parser keys, {len(agent_keys)} agent-projection keys")

    if "--print-vocab" in args:
        print("\nPARSER VOCABULARY:\n  " + "\n  ".join(sorted(parser_vocab)))
        print("\nAGENT PROJECTION KEYS:\n  " + "\n  ".join(sorted(agent_keys)))
        return 0

    if "--selftest" in args:
        return selftest(parser_vocab, agent_keys)

    targets = [Path(a) for a in args if not a.startswith("-")] or default_targets()
    files = collect(targets)
    if not files:
        print("FAILED:lint-frontmatter-keys no .md files scanned (bad target?)")
        return 2

    errors, warns = lint(files, parser_vocab, agent_keys)
    print(f"scanned: {len(files)} file(s)\n")
    for w in warns:
        print(w)
    for e in errors:
        print(e)
    print()
    if errors:
        print(f"FAILED:lint-frontmatter-keys {len(errors)} unsupported key(s), "
              f"{len(warns)} warning(s)")
        return 1
    print(f"SUCCESS:lint-frontmatter-keys 0 unsupported keys, {len(warns)} warning(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
