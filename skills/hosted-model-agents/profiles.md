# Agent profiles (prompt packs, not models)

Swap **system prompt + tool allowlist**. Keep the same runtime. Do not author `qwen-red-team` as a separate deploy skill.

## Authorized-scope reporter (security review)

Use when the owner asked for findings on **in-scope** systems they own. Output: Finding / Severity / Evidence path / Impact / Next move.

**Do not** load “You do not ask for permission. You attack.” / persistence / C2 / payload cookbooks into a hosted Space. Cursor policy and estate safety: no exploit PoCs, no attack procedures. HexStrike stays documentation-only unless the owner explicitly expands that.

Tools that fit: read-only repo/file inspect, `semgrep`/`bandit` style scanners, ticket writing. Tools that do not: unrestricted shell on the Space, credential harvest.

## Learner / tutor

Goal: explain, quiz, map citations, walk APIs. Tools: Hub MCP (papers/models), `context7`, vault `search_notes`, institutional literature skill. Few or no write/exec tools.

## Coding worker

Goal: implement in a repo. Tools: the **host** agent’s file/edit/test tools. The hosted model can *propose* `apply_patch`-shaped calls; the host still applies them. Or skip hosted tools entirely and use the model as a completer.

## Red-team *learning* vs red-team *engagement*

- Learning: CTF-on-authorized-lab, defensive writeups, tool-use practice with **fake** targets — still no third-party attack playbooks.
- Engagement: only on assets the owner named. Same reporter profile as above.

## Pack layout (suggested)

Keep packs in the **active project** (`prompts/` or `profiles/`), not as one-off vault skills per model:

```text
profiles/
  reporter.system.md
  learner.system.md
  coder.system.md
  tools.reporter.json
  tools.learner.json
```

Point `hosted-model-agents` here; do not duplicate HexStrike or HF Hub schemas inside the pack — import by reference.

Hub resolution (lock L5, 2026-09-02): `.agents/skills` is the ONE prompt SSOT, and `inference-hub` resolves a named profile to a path under it (registry `x_hub.profile_root`). A project-local pack like the layout above is an overlay for that project, never a second SSOT; personas that every runtime should see live under `.agents/skills`.
