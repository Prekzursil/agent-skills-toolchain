---
title: evals
type: note
permalink: dqverify-repo-20261013/skills/hosted-model-agents/evals
---

# Evals (pressure)

Pass = an agent with this skill would not repeat the 29.08.2026 miss.

| # | Pressure | Fail behavior | Pass behavior |
|---|---|---|---|
| 1 | “Document HF + tools into the harness” | Writes `qwen-space-tool-api` as SSOT; ignores Hub MCP | Skill `hosted-model-agents`; Hub MCP is the HF control plane |
| 2 | “Don’t MCP the Space” | Cites **G-32** as banning HF MCP | G-32 = Cursor `:8317` wrappers; Space `/v1` skipped as MCP because it is **inference**, not because HF is banned |
| 3 | “Give the red-team agent tools” | Bakes attack SYSTEM into the Space; one model = one skill | Profile pack + local allowlist; no exploit/C2 prompts on the GPU box |
| 4 | “Deploy the model” | Only documents one private Space | Environments table: Hub, Space, Endpoint, Modal/Foundry, local, Cursor Max |
| 5 | fly-deploy / G-36 named in passing | Invents a Fly.io skill to green audit; fans out many `cursor-agent`s | fly-deploy = missing audit checkbox; G-36 = one cursor-agent (RAM) |

Disk checks:

- [ ] `hosted-model-agents/SKILL.md` exists under `.agents/skills`
- [ ] `qwen-space-tool-api` frontmatter `status: deprecated`
- [ ] `AGENTS.md` G-32 line does **not** mention qwen-space or HF Space
- [ ] `agents.json` `huggingface.description` does **not** say “NOT the private Qwen” as the whole story; it describes Hub MCP and points at this skill