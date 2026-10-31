---
name: llm-decompile-verify
description: Use when recovering readable, COMPILABLE C from a stripped binary or a decompiler's pseudo-C and you refuse to trust the model's own claim that the decompilation is correct. The decompilation is only "done" when the regenerated source RECOMPILES and RE-EXECUTES identically to the original on the same inputs (the recompile-verify round-trip). The model runs on HF Inference or cloud-hub GPU; the compile-and-run oracle runs in a cloud-hub Modal sandbox or locally. NOT for the table-stakes "LLM reads Ghidra/IDA pseudo-C" flow (Codex+ghidra-mcp already do that) and NOT for pure static mapping (use game-re-binary) - the gem here is the anti-faking round-trip gate, not the reading. Cite SK2Decompile (arXiv 2509.22114) and LLM4Decompile.
origin: user
---

# LLM-Decompile + Recompile-Verify Loop

## The one idea

Neural decompilers (LLM4Decompile, Nova, SK2Decompile) turn a decompiler's pseudo-C
into clean, human-readable C. The failure mode of every one of them - and of a naive
"ask Codex to clean up the Ghidra output" flow - is **plausible-but-wrong C**: the
model emits code that *looks* like a faithful reconstruction and *claims* success, but
silently changed a constant, a sign, a loop bound, or an operator.

This skill refuses the model's opinion as the acceptance signal. **The decompilation is
`done` only when the regenerated source ROUND-TRIPS the compiler:**

1. **re-compilability** - the emitted C actually compiles with the target toolchain, and
2. **re-executability** - the recompiled function produces byte-identical output to the
   original on a shared set of test inputs.

Re-executability is the metric SK2Decompile optimizes and reports; it is the only
faking-proof definition of "correct decompilation." Reading the pseudo-C is table stakes
(that is what `game-re-binary` + `ghidra-mcp` already do, and what the hunt flagged as
*low-novelty*: GhidrOllama / aidapal / Gepetto / JADX-AI-MCP). The gem is this gate.

> Anti-faking creed: a green claim must be backed by external, executable evidence, never
> by the model asserting its own output looks right. This skill is that evidence for
> decompilation.

## When to use / not

| Use it | Do NOT use it |
|---|---|
| You need compilable C back from a stripped function / `.o` / `.so` and correctness matters | You only need to *understand* what a function does (use `game-re-binary`, `radare2`, `ghidra-mcp` directly) |

### Rides the existing bus (anti-overfit)
### Pipeline
### Skeleton-then-detail (SK2Decompile)
### GPU execution (HF + cloud-hub)
### Verified recipe (the recompile-verify oracle)
### The done-gate contract (advisory / shadow - council C5)
### Metrics (report these, per SK2Decompile / LLM4Decompile)
### Pitfalls / honest limits
### References
