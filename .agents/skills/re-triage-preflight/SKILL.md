---
name: re-triage-preflight
description: Run a fast, hash-cached reverse-engineering TRIAGE preflight on an unknown binary BEFORE deep analysis — folds file-format detection, Shannon-entropy packer triage (works with zero external tools), Detect-It-Easy (diec), FLOSS auto string-deobfuscation, and capa capabilities into ONE structured TRIAGE block, cached by SHA-256 so re-runs are instant. Use when you are about to reverse a native binary (PE/ELF/Mach-O/DEX/.so), triage an unknown/suspicious file, check whether a sample is packed/obfuscated, or want a cheap first-pass before opening IDA/Ghidra/radare2. Advisory only — never blocks, degrades gracefully when a tool is missing. Inert until an RE context. Triton dynamic-taint and VulnHuntr/objdiff+m2c are documented opt-in follow-ons; the revula mega-bundle is rejected.
origin: user
---

# re-triage-preflight Skill

A **cheap, deterministic first pass** over an unknown binary that answers the
questions you always ask before opening a disassembler:

- What *is* this file? (PE / ELF / Mach-O / DEX / ZIP-APK / script / raw)
- Is it **packed or obfuscated**? (entropy verdict + Detect-It-Easy, if present)
- What **strings** does it hide? (FLOSS static + auto-deobfuscated stack/decoded)
- What can it **do**? (capa capability rules → ATT&CK, if the CLI is present)

Everything is folded into one `TRIAGE:` block and **cached by SHA-256**, so the
second time you touch the same file the answer is instant.

This rides the existing re-harness bus (same `re-ensure` idiom, same
`SUCCESS:`/`FAILED:` terminal markers). Folding the block into `re_launch.py` as
an auto-inject is a **follow-on** (see *Follow-ons* below) — this skill ships the
standalone script first.

## Script

`C:/Users/Prekzursil/.Codex/skills/re-triage-preflight/triage.py` — stdlib-only,
Python 3.9+. External tools (diec / FLOSS / capa / Triton) are invoked as
**subprocesses only** (never imported), so the script is import-safe even when
they are absent.

```bash
# Fast default (format + entropy packer verdict + DiE if installed). Sub-second.
python triage.py /path/to/sample

# Deep pass: also FLOSS (all string types = deobfuscation) + capa.
python triage.py /path/to/sample --full

# Machine-readable
python triage.py /path/to/sample --json

# Just the FLOSS deobfuscation, longer budget
python triage.py /path/to/sample --tools format,entropy,floss --floss-full --timeout 300

# Availability report / internal unit checks
python triage.py --probe-tools
python triage.py --selftest
```

Key flags: `--full` (add floss+capa) · `--floss-full` (extract the
stack/tight/decoded — i.e. the *deobfuscated* — strings) · `--tools a,b,c`
(explicit set) · `--timeout N` (per-tool bound, default 90s) · `--refresh` /
`--no-cache` · `--minlen N` · `--shadow` / `--quiet`.

## What each signal means

| Signal | Source | Always available? | Reads as |
|---|---|---|---|
| **format** | magic bytes | yes (stdlib) | `PE x86-64`, `ELF64 LE ARM64`, `DEX`, … |
| **entropy / packer** | Shannon, whole-file + 4 KiB windows + PE section names | **yes (stdlib)** | `unlikely` / `possibly` / `likely_packed` + reasons |
| **die** | Detect-It-Easy `diec -j` | if installed | packer / compiler / protector detections |
| **floss** | `python -m floss -j` | if installed | static + **deobfuscated** stack/decoded strings |
| **capa** | `capa -j` | if console CLI present | capability rules → ATT&CK |
| **triton** | import probe only | opt-in | availability of dynamic-taint (not auto-run) |

The **entropy packer verdict is the load-bearing signal** — it needs *no*
external tool, so triage is useful even on a bare box. It flags packing when the
whole-file entropy is high **and** most 4 KiB windows are elevated, or when a PE
carries a packer-style section name (`UPX0`, `.vmp0`, `.themida`, …) or a
high-entropy section. Detect-It-Easy, when installed, corroborates it by name.

## Contract (why this is safe to run anywhere)

- **Never blocks, never nags.** The script only *produces* an advisory block; it
  cannot gate anything. Every external tool is probed, bounded by `--timeout`,
  and degraded to a `unavailable` / `timeout` / `error` status string on failure
  — the run still emits a `TRIAGE:` block and exits `0`. Exit `2` is reserved for
  hard input errors (missing / unreadable file, bad args). This is the
  **ADVISE / shadow-first** posture the council mandates for new signals
  (COUNCIL C5: pure advisory injectors start at ADVISE).
- **`--shadow`** appends a one-line JSON record to a *separate, bounded,
  auto-rotating* sink (`<cache>/../shadow-log/triage-shadow.log`, rotates at
  256 KiB, one backup) and stays silent on stdout — the shape used when this is
  later folded into a cheap lifecycle hook (never the main ledger, never a new
  PreToolUse hot-path).
- **Hash-cached.** Results are keyed by the file's SHA-256 under
  `%LOCALAPPDATA%/re-triage/cache` (Windows) or `~/.cache/re-triage` (POSIX),
  overridable with `RE_TRIAGE_CACHE`. A cache entry is only reused when it covers
  every requested tool; `--refresh` forces recompute; the schema version
  invalidates stale entries automatically.
- **Anti-overfit / cherry-picked.** Only tools that already earn their keep are
  wired. The `revula` RE mega-bundle is **rejected** (it duplicates 8+ MCPs the
  workspace already has). No vector-DB, no trained critic, no second runtime.

## Installing the optional tools

- **FLOSS** — already present here via `python -m floss` (v3.1.x). Elsewhere:
  `pip install flare-floss`. `--full`/`--floss-full` runs the emulation-based
  stack/tight/decoded extraction (the real deobfuscation); it is slower, so it is
  bounded by `--timeout` and off by default.
- **Detect-It-Easy** — install the console build and put `diec` on PATH, or point
  `DIE_PATH` at the executable. Until then the entropy heuristic substitutes.
- **capa** — the analyzer needs its **console entry point + rule pack**
  (`pip install flare-capa`; rules at `~/.capa`). Note the `capa` *library* may
  already be on the box as a FLOSS dependency without the CLI — `--probe-tools`
  reports the truth.
- **Triton** — `pip install triton` (the Triton DBA/taint library, not the
  GPU-kernel `triton`). Dynamic taint is target-specific, so triage only *probes*
  its availability and never auto-runs it.

## Follow-ons (documented, not built here)

- **Fold into `re_launch.py` / the re-autolaunch hook** so opening a binary for
  RE auto-emits a cached `TRIAGE:` block (shadow → advise). This is the RISK-noted
  follow-on; keep it on the cheap lifecycle path, never a new PreToolUse spawn.
- **Triton dynamic taint** — build a per-target taint harness; wire its summary
  as an additional tool once a standard entrypoint exists.
- **VulnHuntr** (Codex-native source-vuln chains for our own Python/MCP surface)
  and **objdiff + m2c** (matching-decomp, two-binary diff) are *conditional* and
  need source / a binary pair — out of scope for a single-file preflight; invoke
  them by hand when the case calls for it.

## Verify

```bash
python triage.py --selftest      # entropy/format/pe/packer/cache/block/shadow units
python triage.py --probe-tools   # which external tools are actually wired
python triage.py C:/Windows/System32/where.exe   # live: real PE, real cache
```
