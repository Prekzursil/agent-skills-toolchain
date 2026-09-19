---
name: dangling-reference-means-dropped-paste
description: "If the user's answer says \"these\"/\"this\" with no referent, a paste was probably dropped — ask them to resend instead of investigating"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: ca9aa7a4-16ad-4e9d-bafe-00eed0171063
  modified: 2026-09-19T00:22:22.592Z
---

When a user reply contains a dangling reference ("add these", "as well as this") and nothing it could point to, assume pasted content
did not arrive (it was stripped from an AskUserQuestion free-text answer on 2026-09-19) and immediately ask the user to resend it in a
normal message. Do not go off investigating what "these" might be.

**Why:** the user had pasted two model repo ids into an AskUserQuestion "Other" answer; the text arrived with gaps, Claude started
researching the user's account to guess, and the user interrupted twice, frustrated: "as i kept saying".
**How to apply:** one short line — "your paste didn't come through, please resend it as a normal message" — then wait. Also: this
user adds requirements in rapid bursts and interrupts long tool runs; keep investigation steps short and acknowledge each new
requirement on arrival before continuing.

Related: [[user-prefers-grill-before-build]], [[qwen38-heretic-space-grill]]
