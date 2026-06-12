---
name: fresh-context-verify
description: Use when a value, address, offset, or assumption has become load-bearing and you have relied on it for many steps without an independent check — especially in long reverse-engineering or autonomous-loop work that keeps hitting inconsistencies. Re-derive the value in a FRESH context that cannot inherit your current reasoning, and halt if it disagrees. The structural fix for sunk-cost grinding on a wrong-but-consistent anchor.
---

# Fresh-Context Verify

Same-context self-checking ("am I sure?") is proven unreliable — a wrong anchor stays wrong because the reasoning that produced it is still in the window (intrinsic self-correction degrades reasoning; Huang et al., ICLR 2024). The only fix is an EXTERNAL oracle: re-derive the value in a clean context that never saw your assumption.

## When to run
- A periodic FALSIFY-CHECK prompt told you to (you have made many edits on one assumption).
- You keep hitting inconsistencies / contradictions and the work is not converging.
- A single number / address / offset / field is load-bearing for a long chain of work.
- Before committing days more effort to a path built on one unverified value.

## Protocol
1. **Name the anchor.** State the exact value or assumption and the ONE claim everything downstream depends on (e.g. "the date gate is checked at sub_X" or "field +Y holds the timestamp").
2. **Spawn a clean re-derivation.** Use the `Agent` tool (`Explore` or general-purpose) with a prompt containing ONLY the raw evidence (the binary / file / data + the question) and NOT your reasoning or your current answer: *"Independently determine X from this evidence. Do not assume any prior value."* The fresh agent cannot inherit your wrong anchor.
3. **Compare.** Match → the anchor survives; continue with higher confidence. Differs, or the fresh agent cannot reproduce it → **STOP.** The anchor is suspect — that is your 2-day-waste early-warning.
4. **On mismatch:** do not patch around it. Re-derive from the disagreement; if the two derivations still conflict, surface both to the user.

## Why a subagent, not "re-check yourself"
The subagent runs in a separate context window — it is the *independent sample / fresh reviewer* the evidence demands. Re-reading your own chat is not independent; it re-confirms the bias. Keep the fresh agent's input minimal and bias-free, and never tell it your current answer.
