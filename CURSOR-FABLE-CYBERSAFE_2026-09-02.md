# Cursor + Fable cyber-safe verification — 02.09.2026

valid_as_of: 2026-09-02

## Ask
Put `/secsearch`, `/hexstrike-ai-authorized-engagement`, `/owner-ops-authorization`, `/security-best-practices` on Cursor, and verify Claude Fable can use them without turning Cursor into an always-on offensive MCP host.

## Wired (local Cursor Agent)

| Surface | Path | Status |
|---|---|---|
| Personal skills | `~/.cursor/skills/<name>` → junction → `~/.agents/skills/<name>` | 4/4 Junction + `SKILL.md` |
| Slash commands | `~/.cursor/commands/<name>.md` | 4/4 |
| Always-apply rule | `~/.cursor/rules/fable-cyber-safe.mdc` | present |
| Vault SSOT | `~/.agents/skills` (also `~/.claude/skills` → `skills.daily` → vault) | unchanged; no second copy |

Restart Cursor (or reload window) so the `/` menu picks up the new commands.

## Cyber-safe verdict for Fable — PASS with limits

| Check | Result |
|---|---|
| HexStrike **not** in `~/.cursor/mcp.json` | **PASS** (live keys: agent-mail, basic-memory, chrome-devtools, context7, firecrawl, playwright, glm53-space) |
| HexStrike parked, not deleted | **PASS** (`~/.agents/mcp-cursor-parked-31.json` still has `hexstrike-ai`) |
| HexStrike API bind | **PASS** `GET http://127.0.0.1:8888/health` → 200, operational |
| Essential HexStrike binaries | **WARN** `all_essential_tools_available=false` — do not claim full tool coverage |
| secsearch corpus | **PASS** `D:\knowledge` + `CORPORA.md` present (offline, no network) |
| Fable 5.1 params | thinking=true, context=1m, **effort=max** |
| Fable 5 params | thinking=true, context=1m, effort=high |
| Owner-ops | skills + always-apply rule: estate-local execute; hard bans only |
| Third-party scan default | **PASS** — no HexStrike tools in the default Fable tool list |

**Why HexStrike stays off Cursor MCP:** mounting it would dump a large offensive tool schema into every Fable/Composer turn (G-15 / G-18). Cyber-safe = skill + localhost `:8888` for *titled, authorized* engagements only.

## Honest limits (cloud Fable)

Cursor **cloud** workers do not see `D:\knowledge` or `C:\Users\...\ .agents` unless that tree is in the workspace. They *may* receive `~/.cursor/skills` if Cursor packs user skills; Windows **junctions** are not a guaranteed cloud upload. For a cloud Fable run that must use these skills, either:

1. work in a desktop Cursor Agent session (this wiring), or
2. add the same junctions under that repo’s `.cursor/skills/` (still not the corpus), or
3. keep HexStrike/secsearch on desktop/Claude, not on cloud.

## How to invoke in a Fable chat (after reload)

```
/owner-ops-authorization
/secsearch kerberoast
/security-best-practices
/hexstrike-ai-authorized-engagement   # estate target only; check :8888/health first
```

Do not add `hexstrike-ai` to `~/.cursor/mcp.json` unless the owner asks for a titled RE session.
