---
name: fabric-patterns
description: Use Fabric (danielmiessler) patterns and strategies from the CLI - summarize,
  extract_wisdom, create_summary, raw_query and 250+ more - on OpenRouter (plain fabric)
  or Cursor quota (fabric-cursor). Consumer of the .agents/skills SSOT; patterns stay
  private. Use when a pipeline-style text transform beats writing a prompt.
permalink: dqverify-repo-20261013/skills/fabric-patterns/skill
---

# Fabric patterns (estate wiring)

Fabric is wired on this box as a **consumer/cherry-pick donor** of the `.agents/skills` SSOT
(G-79). It is not an MCP server; it is a CLI you pipe text through.

## Measured state (02.09.2026)

| item | value |
|---|---|
| binary | `~\.local\bin\fabric.exe` v1.4.470 |
| config | `~\.config\fabric\.env` (vendor keys by NAME only), `patterns/` (256, upstream loader), `strategies/` (9), `contexts/` (3) |
| plain `fabric` | PowerShell profile function; Gemini-isolated; default vendor OpenRouter, model `nvidia/nemotron-3.5-lightning:free`; `'…' \| fabric -p raw_query` -> `OK` in 12.7 s |
| `fabric-cursor` | `~\.local\bin\fabric-cursor.ps1/.cmd`; process-local `OPENAI_API_BASE_URL=http://127.0.0.1:8317/v1` (auth2api, the ONLY Cursor quota bridge, G-23/G-34); default `-m cursor-gpt-5-mini`; `fabric-cursor -m cursor-grok-4.6 -p raw_query` -> `OK` in 8.4 s |

## Commands

```powershell
fabric -l                                   # list patterns (256)
Get-Content notes.md | fabric -p create_summary
Get-Content talk.txt | fabric -p extract_wisdom -o wisdom.md
fabric -L                                   # models on the native vendors
fabric-cursor -L                            # models on Cursor quota (36 ids: cursor-claude-fable-5-1, cursor-grok-4.6, ...)
Get-Content spec.md | fabric-cursor -m cursor-claude-fable-5-1 -p summarize
fabric --strategy cot -p analyze_claims     # strategies live in ~/.config/fabric/strategies
```

Pipeline input is preserved by both entry points (the profile function collects `$input`; the
wrapper forwards redirected stdin). `fabric-cursor` needs `--raw` (already set in the wrapper):
pattern mode sends a system-only message that the Cursor upstream rejects.

## Rules

- **Patterns are private-only (G-58).** Never upstream an estate pattern without scrub + explicit
  owner review. Custom patterns go under `~\.config\fabric\patterns\<name>\system.md` and are
  listed in `~\.config\fabric\unique_patterns.txt`.
- **SSOT direction (G-79/G-80).** `.agents\skills` is the prompt SSOT. A Fabric pattern that
  proves useful is cherry-picked INTO a skill (hand-edited, attributed); skills are never bulk-
  exported into Fabric, and Fabric output is never injected wholesale into a prompt.
- **Quota.** `fabric-cursor` spends Cursor quota; plain `fabric` spends OpenRouter (spend-capped
  sidecar, T0/T1 grunt per `openrouter-routing`). Prefer plain `fabric` for bulk transforms.
- **Secrets.** Keys live in `~\.config\fabric\.env` (gitignored) - never in a skill, never in
  `agents.json`. The wrapper's `cursor-local-key` is a placeholder the local proxy expects.

## Troubleshooting

- `Gemini Error 404` printed before the answer: the estate-wide `GOOGLE_*` override leaked into
  the process. Both entry points unset it process-locally (fixed 02.09.2026); if it reappears,
  run through the profile function or the wrapper, not `fabric.exe` directly.
- `Conversation length is 0` on Cursor quota: `--raw` missing (call `fabric-cursor`, not
  `fabric --vendor OpenAI`).
- Empty output on free OpenRouter models: shared-capacity endpoint; retry or pass `-m` with a paid
  model, never persist a key change to `.env` from a script.