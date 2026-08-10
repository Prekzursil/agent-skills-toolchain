---
name: bc-drive
description: Deterministic ON-DEMAND driver for a LIVE Battle Cats (jp.co.ponos.battlecatsen, EN 15.4.1) instance on rooted BlueStacks. Reads engine state (scene/metrics) via crash-safe one-shot Frida NativeFunction calls (NO per-frame Interceptor) and actuates via OS-level `adb shell input tap` in device px. BC is a CUSTOM PONOS C++/GLES engine (not cocos2d-x). Use to script/inspect BC menu navigation, resolve its device-to-drawable coordinate space, or read its scene state. Requires adb + frida-server up.
---

# bc-drive — on-demand Battle Cats canvas driver

Control a **live** Battle Cats instance deterministically: read engine state on demand
and actuate with OS-level taps. Built and validated against EN **15.4.1**, x86_64
`libnative-lib.so`, on BlueStacks (`adb 127.0.0.1:5555`, frida 17.11.0).

## CRITICAL CONSTRAINT — no per-frame Interceptor

A hook on the render/update path (`appUpdateDraw` @0x33F7E0 or any per-frame fn)
**crashes BC on scene transitions** (the hot-path lesson). This driver therefore uses
ONLY: (a) one-shot `NativeFunction` calls and (b) pure memory reads, invoked per
request (attach → call → detach). The optional `capture` mode hooks a *constructor*
(fires on scene-build, not per-frame) briefly. Actuation is OS-side `adb input tap`
(no game-thread race).

## Files
- `bc_agent.js` — Frida agent (rpc.exports: `scene`, `metrics`, `touchInfo`, `info`,
  `startCapture`/`stopCapture`).
- `bc_drive.py` — Python driver/CLI (attach-on-demand; tap via adb; screenshot;
  objective pixel-diff demo).

## Verified offsets (RVA in `libnative-lib.so`; runtime = base + RVA)
| RVA | meaning | verified |
|---|---|---|
| `0x65D900` | `getGlobal() -> MyApplication*` | ✅ returns valid non-null ptr |
| `0x668910` | `getScene(app) -> int` = `*(int*)(app+0x2F24)` | ✅ disassembled + called |
| `0x1098C10` | metrics struct | ✅ decoded (below) |
| `0x668C70` | touch dispatch = `vtable[+0x40]` (vtable RVA `0xBED598`) | ✅ resolved read-only |
| `0x65DD0F` | scene SETTER (writes +0x2F20 & +0x2F24) | ✅ disassembled |

### Coordinate space (the key result — SOLVED)
### Scene / state model (honest)
### Widgets (best-effort)
### Usage
### Safety
### What works vs what's inferred
