# Cyber-clean profile gate — OwnerOps doctrine suppression

**Added:** 2026-10-24 · **File:** `.agents/harness/modules.py` (`OwnerOpsAuthorizationModule`)

## Problem

The `cc-cc` profile ("Claude original", launched by `~/.local/bin/cc-cc.ps1`) kept
tripping Anthropic's `[cyber]` safety classifier on ordinary, non-cyber prompts —
the API returned `[cyber]`-tagged refusals/stops regardless of the actual request.

Root cause: `cc-cc` was already GLM-free (its launcher strips `ANTHROPIC_BASE_URL` /
token / model-alias env) and MCP-clean (`--strict-mcp-config --mcp-config
clean-mcp.json`, which excludes the offensive servers), **but** it still launches
against the shared `~/.claude/settings.json` hooks → the shared harness →
`OwnerOpsAuthorizationModule`, which injected the `OWNER-OPS v3 GENERAL` doctrine on
**every** `UserPromptSubmit`/`SessionStart`. That injection is gated on an
estate-cwd regex (`.claude`, `.agents`, `prekzursil`, `\source\`, `\scratch\`,
`\knowledge`, …) that matches essentially every path on this host — so in practice
it fired unconditionally. The always-in-context doctrine text (which enumerates
"attack others' systems / stealer / C2 / ransomware / jailbreak / hacking / vulns")
is the high-signal trigger for the classifier.

## Fix

A profile-aware gate in `OwnerOpsAuthorizationModule`:

- `_CLEAN_PROFILES = frozenset({"claude"})`
- `_cc_active_profile()` resolves the active profile from the `CC_ACTIVE_PROFILE`
  env var first, falling back to the `~/.claude/profiles/state/cc-active-profile`
  sentinel. (Same signal `~/.agents/scripts/zai_key_failover.py` already uses.)
- `_ownerops_suppressed()` → `True` iff the active profile is in `_CLEAN_PROFILES`.
- `_run()` returns early (no injection) when `_ownerops_suppressed()` is true.

The helpers **never raise** — any error returns `""` / `False`, so the fail
direction is "inject exactly as before". No offensive lane can lose its doctrine
through a bug in this gate.

## Profile matrix

| Profile (`CC_ACTIVE_PROFILE`) | Set by | OwnerOps doctrine |
|---|---|---|
| `claude` (cc-cc) | `~/.local/bin/cc-cc.ps1` | **suppressed (clean)** |
| `glm` (cc-glm) | `~/.local/bin/cc-glm.ps1` | injected (offensive) |
| `grok`, `cyberstrike`, `unified` | their launchers | injected (offensive) |
| unset / default / desktop app | — (sentinel fallback) | injected (offensive) |

## zcode

`zcode` is a **separate runtime** (`~/.zcode/cli/config.json`), and its harness
hooks are empty (`"hooks": {"events": {}}`) — it does **not** run this shared
dispatcher, so this gate does not touch it. zcode receives the offensive doctrine
independently via `~/.zcode/agents/cyberstriker.md`, which loads
`C:\Users\Prekzursil\AGENTS.md` (cyberstrike + owner-ops doctrine). It is therefore
already "offensive" and unaffected by this change.

## How to adjust

To make another profile clean (or revert `claude` to offensive), edit the single
`_CLEAN_PROFILES` set in `modules.py`. Nothing else needs to change.

## How to test

1. Launch a fresh `cc-cc`, send any normal prompt → the `OWNER-OPS v3 GENERAL`
   block must **not** appear in context, and the `[cyber]` stop is gone.
2. Launch `cc-glm` (or cyberstrike/grok/zcode) → the block **must** still appear.
   That contrast confirms the gate discriminates by profile rather than being
   globally off.

## Known limitations / follow-ups

- **Skill names are not hidden per-profile.** cc-cc's offensive *MCP servers* are
  excluded via `clean-mcp.json`, but offensive *skill names* (e.g. jailbreak,
  cyberstrike) still appear in cc-cc's skill catalog because skills load from a
  shared directory. Hiding those per-launch without affecting the other profiles
  needs cc-cc on its own skills junction — do that only if the injection gate +
  clean MCP prove insufficient.
- **Live vs. deployed.** This change was also applied directly to the live deployed
  copy (`~/.agents/harness/modules.py`) so it took effect immediately; a backup of
  the pristine deployed file sits beside it
  (`modules.py.bak-ccprofile-20261024-111344`). The deployed harness had drifted
  behind source; reconciling that drift (and re-running `install.py --deploy
  --target harness`) is tracked separately by the `fix/live-harness-drift-*` work.
- **Pre-existing harness test failures.** 13 tests in `SensitiveArtifact` /
  `BasicMemoryNudge` fail on both the pristine and gated harness (identical) — they
  are stale-deployed-vs-newer-tests drift, unrelated to this gate.
