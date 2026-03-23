---
name: format-codex-sessions
description: Use when Codex rollout JSONL files need to be turned into readable Markdown conversations, transcripts, or chat logs without dumping raw event noise, prompt bulk, or secrets.
---

# Format Codex Sessions

## Overview

Render Codex rollout JSONL files into readable Markdown transcripts. Keep the human conversation, summarize tool chatter, and suppress prompt bulk plus token-like data by default.

## Reference Map

- Run [scripts/render_codex_session.mjs](scripts/render_codex_session.mjs) to generate the transcript.
- Use `readable` mode for shareable conversation output.
- Use `audit` mode when the user needs more operational detail without a raw event dump.
- Use `dialogue` mode when tool activity should disappear from the final transcript.

## Required Discovery

1. Confirm the input is a Codex rollout JSONL rather than a generic chat export.
2. Decide whether the user wants a readable transcript, an audit-style view, or dialogue-only output.
3. Keep the rendered output outside the repo unless the artifact is derived documentation that belongs in a repo doc.

## Workflow

1. Run the renderer against the target session file.
2. Review the transcript for duplicated turns or weak tool summaries.
3. Lightly polish wording only if the user asks for more human-friendly phrasing.
4. Keep raw session exports and machine-specific artifacts out of the repo.

## Output Contract

The transcript should:

- preserve chronology
- keep user and assistant turns readable
- summarize tool calls instead of dumping raw argument blobs
- redact or suppress prompt bulk, tokens, cookies, and auth headers

## Stop Rules

- Do not commit raw rollout JSONL files into the repo.
- Do not emit `session_meta.base_instructions` into the readable transcript.
- Do not keep token-like fields or auth material in the rendered output.
- Stop and switch to `audit` mode only when the user explicitly needs more internal detail.

## Common Mistakes

- Treating duplicated `event_msg` commentary as separate assistant turns
- Copying giant developer or system prompt blocks into the transcript
- Keeping raw tool output that overwhelms the conversation
- Forgetting that readable transcripts are derived artifacts, not raw logs
