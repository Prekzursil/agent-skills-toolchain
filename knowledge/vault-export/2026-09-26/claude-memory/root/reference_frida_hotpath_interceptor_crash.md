---
name: reference_frida_hotpath_interceptor_crash
description: Frida crash lesson — a high-frequency Interceptor.attach on a hot-path/render-thread
  function (e.g. getGlobal) crashes during scene transitions; use a periodic JS write
  or one-shot patchCode instead
metadata:
  node_type: memory
  type: reference
  originSessionId: 3cd9445a-ab17-4eec-ad05-c1d1bf411c40
permalink: main/claude-memory/root/reference-frida-hotpath-interceptor-crash
---

A high-frequency `Interceptor.attach(fn, ...)` on a function called per-frame on a
render/GL thread (e.g. Battle Cats `getGlobal` @ RVA 0x653C80, ~175k calls/sec) **crashes
the process during scene transitions** — Frida's interceptor trampoline races thread
create/destroy and jumps to a freed/unmapped code page.

**Diagnose:** `adb logcat -d -b crash`. The signature is a CONTROL-FLOW fault, not a data
deref: `rip == fault_addr` (SEGV_MAPERR fetching an instruction) with
`/memfd:frida-agent-64.so` on the backtrace, on a `GLThread NNN` during a menu→battle
transition. If your hook's data-write guard never even fired (`armed`/flag never set) yet it
still crashed, the **interceptor itself** is the culprit, NOT your deref.

**Fix:** remove the interceptor. Do the work on a JS `setInterval` (the JS thread, not the
render thread): call the target as a `NativeFunction`, validate state under try/catch, and
write via Frida Memory-API (`.readU32()/.writeU32()` are CATCHABLE — a bad pointer throws and
is caught, never crashes). For a value the game reads each frame but writes only on config
change, a ~60Hz periodic write wins without any per-frame hook. A one-shot `Memory.patchCode`
is the deterministic backstop. **Invariant:** every deref of a possibly-transient game
pointer MUST be a Frida Memory-API call, never a raw/native deref (those faults are
UNCATCHABLE).

**Why:** I lost a full cycle on Battle Cats because the first fix blamed a CModule C deref of
`gs+0x37A508` and hardened THAT while keeping the getGlobal interceptor — so it didn't fix the
crash. The live tombstone proved the interceptor was it. Fix = ralph-hardening `f4ddd5e`
(bc_battle_trainer_agent.js / bc_speed_force.py periodic write + tests/live_speed_crash_soak.py).

**How to apply:** when a Frida hook crashes a game "randomly" (esp. on screen/scene changes),
suspect the hook FREQUENCY + thread, not your logic. Prefer poll-on-JS-thread or static patch
over a per-frame native interceptor. Supersedes the narrower lesson in
[[battlecats_companion_launcher]] (frida session must be held open) and relates to
[[feedback_bc_live_game_modding_care]] and [[feedback_bc_re_dont_overcomplicate]].