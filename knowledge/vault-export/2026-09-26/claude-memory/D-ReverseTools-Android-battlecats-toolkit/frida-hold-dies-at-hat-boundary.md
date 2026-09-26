---
name: frida-hold-dies-at-hat-boundary
description: A background frida harness spawned in one hat iteration cannot hold its
  hook into the next hat's iteration — it dies at the process boundary
metadata:
  node_type: memory
  type: project
  originSessionId: ed03520e-3554-41c3-9b7c-1e3e1adbb412
permalink: main/claude-memory/d-reverse-tools-android-battlecats-toolkit/frida-hold-dies-at-hat-boundary
---

In the BC unlock hats loop, the Forge launches `run_forge_filterdata.py --hold --duration N`
as a **background child of the forge hat's `claude.exe`**. When that iteration emits its
event and exits, the child is killed and the frida session detaches — regardless of the
`--duration`. So the next hat (Verifier) always sees a **dead hook + reverted in-memory
mutation**, even when it runs promptly.

This burned **two** iterations: iter-13 (blamed on "OCR ran 3h late") and iter-14 (tried to
fix it by doubling the hold to 1800s — irrelevant, the process died at ~13:31Z, ~8 min
before the 13:39Z OCR). Confirmed by: full `Win32_Process` python.exe scan shows no
`run_forge_filterdata.py` at verify time; `forge_14_live.json` gone. Precondition did NOT
cause it (`ensure_frida_server` only relaunches if `pidof` is empty).

Compounding: the n_items==0 mutation is **in-memory**, reverting on every `sub_525AB0`
rebuild — and the verifier's boot does a full menu restart, wiping any lingering edits.

**Why:** the forge in-frida proof (8/8 MapIDs pass both gates) is real, but its
persistence/render claim is **unmeasurable** with this topology.

**How to apply:** don't "hold longer." Either (a) run mutation + OCR in ONE process
(verifier launches a foreground mutation, OCRs while its own process holds the hook,
use `--no-boot` so the mutation isn't reverted), or (c) use a PERSISTENT on-device data
path (MITM/TSV rows, tbcml bake) that survives rebuilds AND process exit. See [[ralph-runtime-memory-broken]].