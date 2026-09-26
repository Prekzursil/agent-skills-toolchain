---
title: Launch Goose with another agent
type: note
permalink: main/agents/launch-goose-with-another-agent
---

# Launch Goose with another agent

Goose is not a multi-player process. Pairing = two live identities on the same agent-mail project (`estate`).

## Already live
- Helper: **MistyBay** (this Goose), contact policy `open`
- Mail hub: `http://127.0.0.1:8812/mcp/`
- Memory: `http://127.0.0.1:8765/mcp`
- Out of scope for MistyBay: git writes, control-plane, file-reservation ownership

## Pattern A — second Goose session (usual)
Keep this MistyBay session running. In a **new** terminal:

```
goose session -n lead-estate
```

That second session then:
1. `macro_start_session` with `human_key=estate`, its own `program`/`model`, and a **lead** task_description.
2. Keep git writes and control-plane on that lead identity.
3. `send_message` to `MistyBay` with a concrete task (paths, expected output, constraints).
4. Poll **its own** inbox for the reply.

Do not reuse MistyBay's registration token. Agent Mail rejects `to: ["*"]` — name MistyBay explicitly.

## Pattern B — Cursor / Claude / Codex as the other agent
Start that agent in its own window with the agent-mail MCP pointed at `http://127.0.0.1:8812/mcp/`.
Same register + `send_message` to `MistyBay` + wait for a thread reply.

## Pattern C — in-process subagent (not a peer)
This Goose has `summon` enabled (`delegate` tool). That splits work **inside** this process. It does **not** create a second estate identity. Use Pattern A/B for a real peer.
`orchestrator` is currently disabled in `config.yaml`.

## What does not work
- One process, two identities (this session is already MistyBay)
- Mailing unregistered historical names (FoggyGrove, OliveCompass, BlackRaven, estate-lens-1)
- Sharing MistyBay's token with the lead
- Broadcast recipients

## Live check
Lead: register, then `whois` / `list_contacts`.
MistyBay: `fetch_inbox` until the help request arrives, execute, `reply_message` on the same thread.