---
title: CONTEXT.new
type: note
permalink: dqverify-repo-20261013/cyberstrike/context.new
---

# CONTEXT.md — CyberStrike machine facts (GENERATED — do not hand-edit)

Regen: `python scripts/gen_context.py` (drift check: `--check`). Truth = live config, not prose.

- db (canonical): `C:\Users\Prekzursil\.local\share\cyberstrike\cyberstrike.db` — other cyberstrike.db copies are ghosts
- skills: 44 data roots + 1 repo root (fork lazy-loads both)
- MCP: 35 servers, band 31100-31140, exceptions [9876, 18765]; `bolt-lab` rides the `bolt:` section (:3001), not `mcp:`
- supervisor: `start-cyberstrike-mcp-http.ps1` profiles core,full,heavy · hexstrike-ai :18888
- model: `zai/glm-5.3` / small `zai/glm-5.3-flash` · disabled: ollama,openai · permission `allow`
- kimi-shims (2): `gpt-6.0-astra`/`gpt-5.6-daybreak-blue-latest` -> `moonshotai/kimi-k3` — no OpenAI brain in cockpit; real OpenAI cyber path = external (ChatGPT web)
- local lanes: 127.0.0.1:18318, 127.0.0.1:18319 (dbx needs gateway.py; :18319 rotator, key-state on D:)
- instructions[]: 1 entries; AGENTS.md loads natively (Global.Path.config)