---
name: llm-decompile-verify
description: Use when recovering readable, COMPILABLE C from a stripped binary or
  a decompiler's pseudo-C and you refuse to trust the model's own claim that the decompilation
  is correct. The decompilation is only "done" when the regenerated source RECOMPILES
  and RE-EXECUTES identically to the original on the same inputs (the recompile-verify
  round-trip). The model runs on HF Inference or cloud-hub GPU; the compile-and-run
  oracle runs in a cloud-hub Modal sandbox or locally. NOT for the table-stakes "LLM
  reads Ghidra/IDA pseudo-C" flow (Claude+ghidra-mcp already do that) and NOT for
  pure static mapping (use game-re-binary) - the gem here is the anti-faking round-trip
  gate, not the reading. Cite SK2Decompile (arXiv 2509.22114) and LLM4Decompile.
origin: user
permalink: dqverify-repo-20261013/skills/llm-decompile-verify/skill
---

# LLM-Decompile + Recompile-Verify Loop

## The one idea

Neural decompilers (LLM4Decompile, Nova, SK2Decompile) turn a decompiler's pseudo-C
into clean, human-readable C. The failure mode of every one of them - and of a naive
"ask Claude to clean up the Ghidra output" flow - is **plausible-but-wrong C**: the
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
| A neural decompiler / LLM produced C and you must prove it is faithful | You have no way to obtain or drive the target toolchain (no oracle -> gate cannot exist) |
| Matching-decompilation / recompile-to-verify an offset or algorithm port | Pure static surface mapping (imports/strings/xrefs) |

## Rides the existing bus (anti-overfit)

No new runtime, **no vector-DB, no trained critic, no guardrail framework.** Every stage
is an existing tool + the compiler as a deterministic external oracle:

| Stage | Rides |
|---|---|
| Get the binary / baseline pseudo-C | `re-ensure` -> `mcp__ghidra-mcp__decompile_function` / `mcp__ida-pro-mcp` / `re_launch.py` |
| Run the decompiler model (GPU) | `mcp__huggingface__*` (HF Inference) **or** cloud-hub GPU (`mcp__cloud-hub__compute_provision` / `modal_run`) |
| Compile + execute oracle (sandboxed) | `mcp__cloud-hub__modal_sandbox_exec` (isolated gcc/clang) **or** a local `gcc`/`clang` |
| Terminal receipt | AGENTS.md 4: `SUCCESS:<id>` / `FAILED:<id> reason` |

## Pipeline

```
[1] EXTRACT      re-ensure; decompile_function(addr) -> pseudo-C scaffold + signature
                 objcopy/extract the target function's reference object where possible
[2] REFINE (GPU) feed the pseudo-C to the decompiler model (skeleton-then-detail,
                 per SK2Decompile: recover STRUCTURE first, then fill DETAIL) -> candidate C
[3] RECOMPILE    compile candidate C with the target toolchain + flags
                 FAIL -> capture compiler stderr, feed the errors back to [2], retry
                 (bounded: N<=4 iterations) -- a compiler diagnostic is a free critic
[4] RE-EXECUTE   link candidate + a driver harness that calls the function over a fixed
                 input set; diff stdout vs the ORIGINAL's output on the same inputs
                 MISMATCH -> report first differing input, feed back to [2], retry
[5] RECEIPT      all inputs match -> SUCCESS:<id>; otherwise FAILED:<id> reason
```

Stage 3 is a *free* iterative critic: compiler errors are precise, deterministic, and
cheap - they carry the model most of the way before an execution test is even run. Stage
4 is the faking-proof gate: a candidate that compiles but changed behavior dies here.

### Skeleton-then-detail (SK2Decompile)

Do not ask for the whole function in one shot. First recover the **skeleton** (types,
signature, control-flow shape, called-symbol names); verify it compiles as a stub; then
fill the **detail** (expressions, constants). Structural errors surface early and cheaply,
and the detail pass is conditioned on an already-compiling skeleton. This is the two-stage
recipe SK2Decompile trains with a re-compilability + re-executability reward.

## GPU execution (HF + cloud-hub)

The decompiler model is 6.7B-33B class; run it on GPU, not locally:

- **HF Inference:** resolve a model (`mcp__huggingface__hub_repo_search "LLM4Decompile"` /
  `"SK2Decompile"`), call its inference endpoint. Good for one-off refines.
- **cloud-hub GPU:** for batch or when you also want the compile/run oracle co-located,
  provision a GPU pod (`compute_provision` / `modal_run`) and run model + toolchain in the
  same sandbox so the round-trip has no data shuffling.
- **Compile/run oracle:** prefer a **Modal sandbox** (`modal_sandbox_create` ->
  `modal_sandbox_exec` gcc) so untrusted reconstructed C compiles and executes **isolated**
  from the host. A local `gcc`/`clang` is the fast path when the source is trusted.

## Verified recipe (the recompile-verify oracle)

This is the smallest faithful implementation of stages 3-5. It is **executable and was
run for real** (see Evidence). Drop the model's candidate C in place of `CANDIDATES`.

```python
import subprocess, tempfile
from pathlib import Path
CC = "gcc"                                    # or clang; or run inside a Modal sandbox
WORK = Path(tempfile.mkdtemp(prefix="lldv_"))
DRIVER = ('#include <stdio.h>\n int target(int);\n'
          'int main(void){ for(int i=-5;i<15;i++) printf("%d\\n", target(i)); return 0; }\n')
ORIGINAL = "int target(int x){ int a=x*x; a+=3*x; a+=7; return a; }\n"   # ground truth

def build(src, tag):                          # returns (compiled_ok, binary, stderr)
    d=WORK/f"drv_{tag}.c"; t=WORK/f"tgt_{tag}.c"; b=WORK/f"b_{tag}.exe"
    d.write_text(DRIVER); t.write_text(src)
    p=subprocess.run([CC,str(d),str(t),"-O0","-o",str(b)],capture_output=True,text=True)
    return p.returncode==0, b, p.stderr.strip()

def run(b): return subprocess.run([str(b)],capture_output=True,text=True,timeout=10).stdout

ok, refbin, err = build(ORIGINAL, "ref")
assert ok, f"reference did not compile: {err}"
ref_io = run(refbin)                          # the behavioral oracle

def verify(candidate_src, cid):               # <- the anti-faking done-gate
    ok, b, cerr = build(candidate_src, cid)
    if not ok:
        return f"FAILED:{cid} does-not-recompile :: {(cerr.splitlines() or ['?'])[-1]}"
    got = run(b)
    if got == ref_io:
        return f"SUCCESS:{cid} recompiles + re-executes == reference"
    rl, cl = ref_io.splitlines(), got.splitlines()
    diff = next((f"input#{i} ref={r} got={c}" for i,(r,c) in enumerate(zip(rl,cl)) if r!=c), "len-mismatch")
    return f"FAILED:{cid} re-execution-mismatch :: {diff}"
```

The full probe (with three candidates - one equivalent, two fakes) lives with this build;
re-run it as the skill's self-test whenever you touch the recipe.

## The done-gate contract (advisory / shadow - council C5)

- The verdict is **external executable evidence** (compiler exit code + a byte-diff of
  program output), never a model's self-assessment. That is the whole point.
- It ships **advisory / shadow**: the skill *emits* the `SUCCESS:`/`FAILED:` receipt and
  logs it; it **does not auto-block a commit and does not nag.** The agent or owner decides
  what to do with a FAILED verdict. (Per COUNCIL-VERDICT C5: this is a pure advisory
  executable oracle, not a safety-invariant enforce-gate.)
- Never emit `SUCCESS` without a real compile + a real execution match. If no oracle is
  available (cannot build/run the target), say so and return `FAILED:<id> no-oracle` -
  an unverifiable decompilation is not "done."

## Metrics (report these, per SK2Decompile / LLM4Decompile)

- **re-compilability rate** = fraction of candidates that compile (stage 3 pass).
- **re-executability rate** = fraction that also match reference I/O (stage 4 pass) - the
  headline correctness number. Report it, not "looks correct."
- **iterations-to-pass** = feedback loops [2]<-[3]/[4] consumed (bounded at N<=4).

## Pitfalls / honest limits

- **Oracle coverage is only as good as the inputs.** Byte-identical output on a weak input
  set can still miss a divergence. Widen inputs (boundaries, negatives, overflow) and,
  when available, diff against the original object via `objdiff`/normalized IR similarity
  as a second axis. Re-executability is necessary, not a total proof.
- **Reference I/O requires a driveable original.** If you cannot execute the original
  function (no harness, side effects, hardware deps), you have no behavioral oracle -
  fall back to re-compilability + structural/objdiff similarity and label the verdict
  accordingly. Do not upgrade it to `SUCCESS`.
- **Untrusted reconstructed C executes** - compile/run it in a **Modal sandbox**, never
  blindly on the host.
- **Toolchain must match** the original's compiler/flags for objdiff-style comparison;
  for pure I/O equivalence any conforming toolchain is fine.
- Low-novelty siblings to avoid re-building: GhidrOllama, aidapal, Gepetto, JADX-AI-MCP
  ("LLM reads decompiler output") - already covered by Claude + `ghidra-mcp`.

## References

- **SK2Decompile** - arXiv **2509.22114** (skeleton-then-detail neural decompilation with a
  re-compilability + re-executability reward). Primary evidence for this skill.
- **LLM4Decompile** - re-executability as the correctness metric for neural decompilation.
- MASTER-DECISION-QUEUE **E.1** (line 153): "only 'done' when it round-trips the compiler;
  runs on HF+cloud-hub GPU"; E.5 flags the LLM-reads-pseudo-C tools as low-novelty.