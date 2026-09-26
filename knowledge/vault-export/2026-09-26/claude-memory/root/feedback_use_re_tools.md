---
name: Use RE tools for static analysis before runtime
description: Use Ghidra/IDA/BinaryNinja MCPs for static binary analysis. Do NOT attempt
  runtime testing until static analysis is complete.
type: feedback
permalink: main/claude-memory/root/feedback-use-re-tools
---

When doing reverse engineering / game modding work, ALWAYS use the RE tool MCPs (ghidra-mcp, ida-pro-mcp, binary-ninja-mcp) for static analysis FIRST. Do NOT jump to runtime testing, value scanning, or breakpoints until the static analysis is fully complete and the solution is designed.

**Why:** Runtime approaches waste the user's time with repetitive unpause/pause cycles. Static analysis on the dump/binary is faster, more thorough, and doesn't require the game to be running. The user has these tools installed and configured specifically for this purpose.

**How to apply:** Spawn the `re-analyst` subagent profile from `~/.agents/subagent-profiles.md` which attaches Ghidra, IDA, Binary Ninja, Frida, CheatEngine, and HexStrike MCP servers. Have the subagent do ALL analysis before presenting results. Only go to runtime for final verification.

Also: the user wants per-unit and per-faction targeting, not blanket all-units invulnerability. Always find the faction/owner field in the object struct during static analysis.