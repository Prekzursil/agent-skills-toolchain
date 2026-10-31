---
name: bc-drive-plus
description: Additive enhancements to the bc-drive Battle Cats (jp.co.ponos.battlecatsen, EN 15.4.1) canvas driver on rooted BlueStacks. Adds (1) a BOUNDED one-shot touch-dispatch capture that hooks the already-resolved dispatch fn 0x668C70 for a SINGLE tap then detaches, recovering the runtime evidence to resolve the stripped NewButton ctor RVA (closes bc-drive's #1 open gap) with thread-selection safety honored; (2) OmniParser V2 set-of-mark numbered grounding for the DOM-less GLES canvas; (3) minitouch/evdev low-latency input vs per-process adb tap; (4) a save-snapshot ring + auto-rollback encoding the HGT-safe-restore discipline. Use for advanced BC UI-driving, native widget-tree recovery, or automated save protection. Requires adb + frida-server; builds on bc-drive and bcsfe-save-roundtrip.
license: MIT
---

# bc-drive-plus — advanced Battle Cats driving (dispatch-capture · grounding · input · snapshot-ring)

> Additive layer over **`bc-drive`** (read the base skill first). Same target: a
> **live** Battle Cats EN **15.4.1**, x86_64 `libnative-lib.so`, on BlueStacks
> (`adb 127.0.0.1:5555`, frida 17.11.0). Every enhancement rides the existing
> bus — the one-shot-NativeFunction / OS-tap / screenshot discipline — and **never**
> reintroduces a per-frame render hook (which crashes BC on scene transitions).

## The four enhancements

| # | Capability | File / status | Risk |
|---|---|---|---|
| 1 | Bounded one-shot **dispatch-capture** (recover stripped `NewButton` ctor RVA) | `dispatch_capture.py` ✅ built + unit-tested; live run needs device | live-frida input-path hook — **thread-selection safety honored** |
| 2 | **OmniParser V2 set-of-mark** grounding for the GLES canvas | recipe below (ADOPT) — rides `adb screencap` bus | read-only (screenshot) |
| 3 | **minitouch/evdev** low-latency input | recipe below (ADOPT) — falls back to `adb tap` | actuation only on safe menu nav |
| 4 | Save-**snapshot ring** + auto-rollback (HGT-safe-restore) | `snapshot_ring.py` ✅ built + unit-tested; live run needs device | stateful save write — **auto-rollback shadow-by-default** |

Shadow-mode is the universal discipline (council C5): any **automated / stateful**
action defaults to OBSERVE-only (log "would do X", mutate nothing); only an
**explicit operator command** actuates. Nothing here blocks or nags.

### 1 · Bounded one-shot dispatch-capture (`dispatch_capture.py`)
### Mechanism
### Offline follow-up to confirm the ctor RVA
### THREAD-SELECTION SAFETY (the flagged live-frida risk — how it is honored)
### Usage
### 2 · OmniParser V2 set-of-mark grounding (ADOPT recipe)
### OmniParser V2 (MIT) = YOLO icon/box detector + a caption model. Run on cloud-hub
### GPU or locally; feed it the bc-drive screenshot, get boxes back, number them.
### weights: microsoft/OmniParser-v2.0 (HF)  ->  hf_hub_download
### 3 · minitouch / evdev low-latency input (ADOPT recipe)
### push a prebuilt minitouch matching the emulator ABI (x86_64), then:
### stream: printf 'd 0 <x> <y> 50\nc\nu 0\nc\n' | nc <minitouch socket>
### 4 · Save-snapshot ring + auto-rollback (`snapshot_ring.py`)
