# Gem-hunt 2026-09-02 - hosted models - lens 12: peers and parallelism

**Lens id:** `12-peers-and-parallelism`
**Mode:** discovery only (research + findings). No code changed. No PR.
**Question:** how can a hosted (HF Router / Endpoint / Modal / Azure Foundry) or local (llama.cpp, Ollama, LM Studio) model participate as a *first-class worker* in this estate - registered on agent-mail (`mcp_agent_mail` on `127.0.0.1:8812`), fanned out beside Codex `mcp-server` threads, driven like an agent through an ACP adapter, and run in parallel panes on a RAM-starved Windows 11 box without tmux.

## Evidence discipline

Every claim below carries a source URL, a **tier** (A = primary spec / vendor doc / repo source; B = maintainer blog, release notes, well-known secondary; C = community post, forum, inference from partial evidence), a **corroboration** flag (corroborated = 2+ independent sources or source + local repo evidence; UNVERIFIED = single source, not reproduced here), and a **date** (source publication or last-checked). Claims are labelled **[FACT]** (sourced), **[INFERENCE]** (my reasoning from facts), or **[RECOMMENDATION]** (what I would do). Local-repo evidence is cited as `repo:<path>@<branch>`.

Estate locks (hard constraints, cited verbatim from the brief, never proposed against): OpenRouter is a spend-capped CLI/Codex sidecar only (never a Cursor BYOK key, never Claude `ANTHROPIC_BASE_URL`, never a new OpenRouter MCP); no LiteLLM, no LangGraph, no second orchestration runtime, no vector-DB memory; auth2api `:8317` stays the only Cursor bridge and retires within 7 days of an official Cursor `/v1` GA; ports 8765/8812/8317 are owned; `.agents/skills` is the ONE prompt SSOT (Fabric/Goose consume it); never rotate credentials; never remove a feature to buy reliability.

Dedup-set (exists, not re-proposed): `.agents/skills/hosted-model-agents` (live-capture/2026-09-02), `tools/mcp/glm53-space` (main; owner has decided to deprecate), auth2api `:8317`, `.agents/agents.json` registry + `.agents/local.json` secrets-by-name, the installed runtime list on the Windows box.

---

## 0. Status of this document

| Section | State |
|---|---|
| 1. What the estate already has (local evidence) | pending |
| 2. agent-mail as the peer bus: registration, contact gating, leases | pending |
| 3. Codex `mcp-server` fan-out and where a hosted model slots in | pending |
| 4. ACP (Agent Client Protocol): v1 today, v2 draft, adapters | pending |
| 5. Parallel panes: dmux / superset / tmux / Windows reality | pending |
| 6. Design: one hosted-model-agent adapter (agent-mail + ACP) | pending |
| 7. Parallelism pattern that fits this box | pending |
| 8. Reuse from `multi-ai-mingle` | pending |
| 9. Rubric table | pending |
| 10. Ten-line summary | pending |

(Sections are filled and pushed incrementally; a section marked `pending` means the run has not reached it yet.)
