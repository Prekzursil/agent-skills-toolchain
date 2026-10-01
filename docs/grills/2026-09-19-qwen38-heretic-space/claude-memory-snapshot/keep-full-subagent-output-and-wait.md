---
name: keep-full-subagent-output-and-wait
description: "Save every subagent's full report verbatim the moment it returns, retry failed ones, and never wrap up while background agents or workflows are still running"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: ca9aa7a4-16ad-4e9d-bafe-00eed0171063
  modified: 2026-09-19T00:41:37.657Z
---

When subagents, lenses, scouts or workflows return, write their FULL final output to a durable file immediately (not just a digest in
a summary doc), retry any that failed, and do not converge, summarize-and-move-on, or start the next phase while background work is
still running.

**Why:** on 2026-09-19 the user interrupted twice — "hope you are remembering what the subagents told you and didnt dismiss and lose
what they did… there is an ongoing workflow that might also still yield good results before going", then "retry this one as well" for
a lens that had been killed by a platform safeguard. Claude had only stored compressed digests and was about to write the final log
while a verification workflow was unfinished.
**How to apply:** extract final reports from the task transcript with a script (last assistant text part of
`tasks/<id>.output`) into an `evidence/reports/` folder next to the working doc; for workflows copy `journal.jsonl` and render
findings + verdicts to markdown, re-exporting at completion. Tell the user where everything is saved. For a retry, pass
`model: "fable"` to the Agent tool — the general-purpose agent otherwise runs on its own default model, not the session model the user
asked for.

Related: [[qwen38-heretic-space-grill]], [[user-prefers-grill-before-build]]
