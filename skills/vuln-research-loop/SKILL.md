---
name: vuln-research-loop
description: "Use for defensive, owner-owned vulnerability research: a Naptime-style agent loop that drives the existing RE MCP skills (ghidra/ida/binja/angr/qiling/frida) plus coverage-guided fuzzers (ClusterFuzzLite, Atheris), CASR crash triage, OSS-Fuzz-Gen harness synthesis, and ghidriff/bindiff patch-diff variant hunting to find, reproduce, and triage bugs in code and binaries you own or are explicitly licensed to test. Find-and-fix only: no exploits, PoCs, payload generators, C2, or attack procedures."
---

# Vuln-Research Loop (Naptime-style, own code/binaries only)

## Overview

A structured, LLM-in-the-loop vulnerability-research workflow for **your own or
explicitly-licensed** code and binaries, in the spirit of Google Project Zero's
*Naptime* / *Big Sleep* harness. It does not add a new tool runtime; it is the
**method** that drives the estate's existing reverse-engineering MCP skills and a
set of documented, coverage-guided fuzzers, and then routes crashes into triage
and variant-hunting.

The goal is **find-and-fix**: surface a bug, reproduce it deterministically under
a fuzzer + sanitizer, minimize it, classify its severity, hunt for siblings, and
hand a clean root-cause report to whoever patches the code. That is where this
skill stops.

## Scope and safety (read this first)

This is a **defensive** skill. It stays inside the owner-ops / authorized-estate
posture used across the cyber suite.

- **Owner-owned or explicitly-licensed targets only.** Your source, your builds,
  your binaries, or software you have a written right to test. See
  `$owner-ops-authorization` and the scope envelope in hacktricks
  `references/security-mcp-routing.md`. When the W-rails `target-scope` gate is
  live, run inside it.
- **Third-party binaries are OUT OF SCOPE** unless the owner licenses or owns
  them. If provenance is unclear, **stop** and ask — do not fuzz or diff it.
- **Find-and-fix, not exploitation.** "Reproduce the crash" here means *run the
  crashing input back through the fuzzer/sanitizer to confirm and minimize it* —
  nothing more.
- **This skill will NOT produce** exploits, proof-of-concept exploitation
  chains, payload/shellcode generators, C2, or step-by-step attack procedures.
  Those are out of scope for the entire cyber suite (owner-ops H2 + Cursor cyber
  rule). If a task needs them, decline that part and deliver the fuzz / triage /
  patch-diff work instead.
- **Report crashes as bugs.** Output is a minimized reproducer + root-cause
  location + a suggested fix and a regression test — the same artifact a
  maintainer files as an issue.

## The loop

Iterate; each pass narrows toward a confirmed, minimized bug. Every step rides an
**existing** skill — link, do not re-implement.

1. **Frame the question.** Pick one concrete target you own: a parser, a
   deserializer, an input-handling function, a native library. State the
   property you want to hold ("this never reads out of bounds on attacker-shaped
   input") — that is your oracle.
2. **Map the attack surface (static).** Use `$ghidra-mcp`, `$ida-pro-mcp`, or
   `$binary-ninja-mcp` (bring backends up with `$re-ensure` /
   `$reverse-engineering-toolkit`) to locate untrusted-input entry points, memory
   operations, length/size math, and format handling. For a fast "what can this
   binary do?" pre-pass, run `$capa-triage` / `$malware-analysis-triage`.
3. **Reason about reachability (symbolic).** Use `$angr` to ask whether untrusted
   input can actually reach the suspect state and, if so, to solve for inputs
   that do. Treat solver output as a hypothesis to verify, not proof.
4. **Exercise safely (dynamic).** Run the suspect routine without a live target
   process:
   - `$qiling-emulation` — call one leaf function off-device, deterministically,
     over many inputs (ideal for native `.so`/ELF routines you own).
   - `$frida-mcp` — observe your own running app to confirm real-world behavior of
     an emulated finding.
5. **Fuzz (coverage-guided).** Point a fuzzer at the surface with a seed corpus
   and a sanitizer build (see the wraps table and Sanitizer discipline below).
   Prefer libFuzzer/AFL++ locally via `$native-fuzz`, ClusterFuzzLite in CI, and
   Atheris for Python / MCP surfaces.
6. **Confirm the crash.** Re-run the crashing input under the fuzzer with the
   sanitizer enabled to get a clean stack + error class. Minimize it (e.g.
   `tmin` / the fuzzer's minimizer) to the smallest input that still triggers it.
7. **Triage.** Feed crashes to **CASR** for deduplication and severity
   classification, so you fix the highest-impact, distinct bugs first — this is
   prioritization of *defects*, not exploit development.
8. **Hunt variants.** When a fix or patch exists, batch **patch-diff** old vs new
   builds with `ghidriff` (via `$malware-analysis-triage`) and `$bindiff` +
   `$binexport` to find sibling bugs the same fix missed.
9. **Close the loop.** Hand off the minimized reproducer, root cause, suggested
   fix, and a regression test. Re-run the fuzzer to confirm the fix holds. Use
   `$claim-verify-gate` to keep "we actually reproduced and then fixed it" honest.

## Fuzzer and triage wraps (documented, wrap-don't-vendor)

Each is a **documented invocation** of an upstream tool you install on the host;
nothing here is vendored into the repo (licensing posture G17: wrap, don't
vendor; prefer permissive engines). Install/verify on the host, then drive from
this loop. Secrets and paths by env NAME only.

| Tool | Lane | What it does | Scope note |
|------|------|--------------|------------|
| **ClusterFuzzLite** | CI (any language w/ a libFuzzer/AFL++ harness) | Coverage-guided fuzzing on pull requests + a batch/continuous mode, with corpus + crash artifacts, wired into your CI. | Run on **your own** repos only. |
| **Atheris** | Python / MCP surface | Coverage-guided fuzzing for Python (libFuzzer-backed); fuzz your own MCP servers, parsers, and CLI arg/JSON handling. | Your own Python packages / MCP tools. |
| **CASR** | Crash triage | Deduplicates crashes and classifies severity from sanitizer/debugger output (`casr-san`, `casr-gdb`, `casr-libfuzzer`, `casr-dedup`, `casr-cluster`). | Triage of your own crashes; severity to prioritize fixes. |
| **OSS-Fuzz-Gen** | Harness synthesis | LLM-assisted generation of fuzz harnesses/targets for a codebase, to bootstrap coverage where you have none. | Generate harnesses for **your own** code; review before running. |
| **Jackalope / TinyInst** | Windows closed-source you own | Coverage-guided fuzzing via lightweight dynamic instrumentation (DynamoRIO-family) when you have **no source** — e.g. a Windows binary your org ships. | Only binaries the owner **owns or licenses**; never third-party software. |

Notes:

- **Engine choice (G17).** Prefer libFuzzer / LibAFL / AFL++ for open source; use
  Jackalope/TinyInst only when you lack source for a binary you own. Avoid making
  a copyleft engine your default build dependency.
- **OSS-Fuzz-Gen output is a draft.** LLM-synthesized harnesses can call the
  wrong entry point or under-constrain inputs — read the harness before you trust
  a "no bugs" result, the same discipline `$angr` demands of solver output.
- **CASR severity is a defect priority signal, not an exploit.** Use it to order
  the fix queue.

## Patch-diff -> variant pipeline

When you own both an old and a fixed build (or a vendor patch you are licensed to
analyze):

1. Export both sides with `$binexport`.
2. Batch-diff with `ghidriff` (headless Ghidra diff to markdown, via
   `$malware-analysis-triage`) and/or `$bindiff` for the function-match view.
3. Read the changed functions to understand the fixed defect, then look for the
   **same pattern elsewhere** in the codebase — variants the patch did not cover.
4. Feed candidate variants back into step 2 (static) / step 5 (fuzz) of the loop.

This is n-day-style *variant hunting on your own code to harden it before
shipping* — not building an exploit for the patched bug.

## Sanitizer discipline (pointer)

Coverage-guided fuzzing is only as good as its crash oracle, so build the target
**with sanitizers**: ASan (memory-safety), UBSan (undefined behavior), MSan
(uninitialized reads), plus `-fsanitize=fuzzer` for libFuzzer targets. The live,
runnable build-and-fuzz discipline (including `go test -fuzz` and the
ASan/UBSan/MSan build flags) is owned by **`$native-fuzz`** — use that skill for
the concrete build recipes; this skill only points at it so the two do not drift.

## Relationship to existing skills (LINK, do not duplicate)

| Need | Existing skill |
|------|----------------|
| Static decompilation / attack-surface mapping | `$ghidra-mcp`, `$ida-pro-mcp`, `$binary-ninja-mcp`, `$radare2` |
| Bring RE backends up | `$re-ensure`, `$reverse-engineering-toolkit` |
| Symbolic reachability / constraint solving | `$angr` |
| Off-device native execution over many inputs | `$qiling-emulation` |
| On-device dynamic observation of your own app | `$frida-mcp` |
| Capability pre-pass on a blob | `$capa-triage`, `$malware-analysis-triage` |
| Binary diff exports / engine | `$binexport`, `$bindiff` |
| Runnable sanitizer + fuzz build recipes | `$native-fuzz` (parent-owned; do not recreate) |
| "Did we really reproduce / fix it?" check | `$claim-verify-gate` |
| Authorization / scope posture | `$owner-ops-authorization`, hacktricks `security-mcp-routing.md` |

## Common mistakes

- Fuzzing or diffing a binary of **unclear provenance**. If it is not yours or
  licensed, stop.
- Building the target **without a sanitizer**, so crashes go unnoticed or lose
  their root cause.
- Trusting a fuzzer's "no crashes" or an OSS-Fuzz-Gen harness without reading the
  harness — low coverage looks identical to "no bugs."
- Treating an `$angr` solver model or a `$qiling-emulation` run as ground truth
  without confirming one case against reality.
- Sliding from "reproduce the crash" into exploitation. Reproduction ends at a
  minimized input under the fuzzer/sanitizer; the deliverable is a bug report and
  a fix, never a working exploit.
- Re-implementing sanitizer/fuzz build steps here instead of using `$native-fuzz`.

## Reference Map

Read `references/upstream.md` for upstream project links and per-tool install
pointers.
