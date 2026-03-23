# Multi-Agent Quickstart

This is the shortest mental model for using the system without getting lost.

## First rule

Start simple. Do not jump straight to the most complicated tool.

## Which tool do I use?

- `codex_consult`
  - Use when you want one strong answer.
- `codex_brainstorm`
  - Use when you want multiple ideas before deciding.
- `codex_review`
  - Use when you already have a plan or implementation and want a critic.
- `codex_discuss`
  - Use when you want two Codex peers to argue through tradeoffs before synthesis.
- `codex_coordinate`
  - Use when work should be split into roles and then consolidated.
- `codex_curate`
  - Use when you already have options and want the best one selected.

## When does PromptBridge join?

PromptBridge is optional and talk-only.

Use it when:

- you want a second opinion in plain language
- you want a curator to compare options
- the profile or tool mode explicitly asks for a curator

Do not use PromptBridge as the execution authority.

## Beginner path

1. Start with `multi-agent-quickstart`.
2. Use `codex_consult` first.
3. Move to `codex_brainstorm` if you need alternatives.
4. Use `codex_review` before risky implementation.
5. Use `codex_curate` when choosing among options.

## After planning

If the work is ready to execute, choose the execution path explicitly:

- subagent-driven execution for complex work, which is the recommended path
- inline execution when the task is small or subagents would be overhead

This keeps the handoff visible instead of silently forcing a single route.

## Advanced path

If you already know what you want, call the raw orchestration tools directly and pass profile overrides instead of relying on wrapper skills.

## Failure behavior

If the sidecar is unavailable, keep going in the Codex lane and mark:

```text
fallback_to_lane_a = true
```
