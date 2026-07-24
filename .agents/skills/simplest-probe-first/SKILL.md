---
name: simplest-probe-first
description: Use BEFORE committing to any expensive or multi-step approach (vision/OCR pipeline, multi-agent fan-out, live RE, big rewrite, long orchestration). Run the cheapest deterministic diagnostic FIRST to check whether a simpler path works. Prevents the waste where hours go into a heavy pipeline a one-command check would have ruled out (e.g. a 10-hour vision run on a PDF with no text layer).
---

# Simplest-Probe-First

A tunnel-visioned agent commits to the first (often heaviest) approach and never checks the cheap one. Same-context self-talk ("maybe consider a simpler option") is unreliable (intrinsic self-correction degrades reasoning — Huang et al., ICLR 2024). The reliable fix is a **deterministic probe**: run a one-command external check whose *result* picks the path for you.

## The rule
Before any approach that costs more than a few minutes or spawns agents: name the cheapest falsifiable probe, **RUN it**, and let its result choose the path. If the probe says the simple path works, take it. Never skip the probe because the hard path "feels right."

## Probe table (extend it as you learn)
| Situation | Cheap probe to run FIRST | If the probe says… |
|---|---|---|
| PDF / scanned doc → extract text | `pdffonts file.pdf` or `pdftotext file.pdf -` | empty / no fonts = no text layer → use OCR (ABBYY, the `ocr` MCP, tesseract), NOT a vision-LLM pipeline |
| Office / HTML doc → text | check for a text layer / try `markitdown` | has text → parse directly, skip OCR and vision |
| Reverse-engineer a function | static decompile (IDA / Ghidra / Binary Ninja) + xrefs first | static answers it → done; only go live-hook / Frida if static is genuinely insufficient |
| "Make X faster" | profile it once | the profile names the hot path → fix that; do not rewrite blindly |
| "Build utility Y" | `gh search code` + search npm / PyPI / crates | it exists → fork / port / wrap (see the `development-workflow` rule), do not hand-roll |
| "Have I solved this before?" | `mcp__basic-memory__search_notes` + grep `~/.claude/*.md` + project docs | found → reuse the documented approach, do not re-crack it |
| Big new abstraction / orchestration | state the complexity tier and why a simpler tier fails | can't justify it → use the simpler tier (anti-over-engineering) |

## Output
State, in one or two lines: the probe you ran, its result, and the path you chose *because of* that result. Then proceed.
