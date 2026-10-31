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

`C:/Users/agentuser/.Codex/skills/re-triage-preflight/triage.py` — stdlib-only,
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

### Availability report / internal unit checks
### What each signal means
### Contract (why this is safe to run anywhere)
### Installing the optional tools
### Follow-ons (documented, not built here)
### Verify
