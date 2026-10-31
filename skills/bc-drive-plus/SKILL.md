---
name: bc-drive-plus
description: Use when driving a LIVE Battle Cats (jp.co.ponos.battlecatsen, EN 15.4.1)
  on rooted BlueStacks beyond bc-drive. Adds bounded one-shot touch-dispatch capture
  to resolve the stripped NewButton ctor RVA, OmniParser V2 set-of-mark grounding
  for the DOM-less GLES canvas, minitouch/evdev low-latency input, and a save-snapshot
  ring with auto-rollback. Needs adb + frida-server; builds on bc-drive and bcsfe-save-roundtrip.
license: MIT
permalink: dqverify-repo-20261013/skills/bc-drive-plus/skill
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

---

## 1 · Bounded one-shot dispatch-capture (`dispatch_capture.py`)

**Closes bc-drive open gap #1.** bc-drive documented that the `NewButton` class is
known from RTTI in `.rodata` (callback `void(NewButton*, NewButtonChangeState)`,
vtable RVA `0xBED598`) but its **constructor RVA is unresolved** because the game's
own C++ symbols are stripped. This module recovers the runtime evidence to resolve
it, **without** a per-frame hook.

### Mechanism
The touch-dispatch function is already resolved read-only by bc-drive:
`0x668C70 == getGlobal()->vtable[+0x40]`. It fires **only on touch events** (not per
frame). We attach a **single-shot** `Interceptor` to it; on the **first** tap we
capture — minimally — `(phase, x, y, pid)`, the return address (caller RVA), and a
short **accurate backtrace** (module-relative RVAs), emit them **asynchronously**,
then **detach**. With the known NewButton vtable RVA and (optionally) the touched
node's own vtable, an **offline xref pass** localizes the ctor.

Honest boundary: the module yields the **evidence** (caller RVAs ranked by
frequency + any hit-node vtable RVA + a match flag against `0xBED598`); the final
ctor RVA is **confirmed** by the documented offline step below — it is not
hallucinated as a printed number.

### Offline follow-up to confirm the ctor RVA
1. In Ghidra/IDA on the pinned 15.4.1 `libnative-lib.so`, go to the NewButton
   vtable RVA `0xBED598` (from RTTI).
2. Find the function that **stores** that vtable into a fresh object
   (`mov [obj], <vtable_addr>`) — that is the `NewButton` constructor.
3. Cross-check it against the `caller_rvas_ranked` list from the capture (the live
   `dispatch → widget callback` path). If `hit_node_matches_newbutton_vtable` is
   true, `node_ptr` is a **live** NewButton and its ctor is the storer of its vtable.
4. Feed the confirmed ctor RVA back into bc-drive's `capture <ctorRVA> <ms>` to dump
   live button objects + candidate rect floats (its infra was built and ready).

### THREAD-SELECTION SAFETY (the flagged live-frida risk — how it is honored)
The touch dispatcher runs on the game's **UI/input thread**. An `Interceptor`
callback runs **on that same thread**. The safety rules baked in:
- **No synchronous host RPC inside `onEnter`.** A blocking `recv()`/RPC would stall
  the input thread → ANR/crash. The agent uses **only async `send()`**. *This is the
  thread-selection flag.*
- **Single-shot.** The agent self-limits to `max_hits` (default **1**); the driver
  detaches the instant the cap is hit.
- **Scene-guarded.** `arm_and_capture` **refuses** to arm unless `scene` is in the
  out-of-battle menu cluster (`97..101`). It will **never** hook the input path
  mid-battle (hot, timing-sensitive). Scene is read via bc-drive's on-demand
  `scene` — if it can't be read, the guard **refuses** (fail-safe).
- **Hard timeout.** The driver auto-detaches after `timeout_ms` even if no touch
  arrives, so a hook is never left live.
- **Not a per-frame hook.** `0x668C70` ≠ the render path `appUpdateDraw @0x33F7E0`.

### Usage
```
python dispatch_capture.py show               # print the generated single-shot agent JS
python dispatch_capture.py capture 6000        # SHADOW: arm 1-shot, YOU tap once (6 s window)
python dispatch_capture.py capture 6000 955 665 # ARMED: arm + drive ONE safe menu tap as trigger
```
Shadow (`capture <ms>`) hooks + records and waits for **your** manual tap — it never
actuates. Passing `<x> <y>` is an explicit operator-armed run that drives one safe
menu tap. Output includes `ctor_evidence` (ranked caller RVAs + node-vtable match +
the exact offline follow-up). Env: `BC_ADB`, `BC_SERIAL`, `BC_DC_SINK` (bounded
rotating shadow log). Optional `node_field_off` (Python API) reads a candidate
hit-node pointer off arg0 and reports its vtable RVA directly.

---

## 2 · OmniParser V2 set-of-mark grounding (ADOPT recipe)

BC's canvas is a **DOM-less custom GLES surface** — there is no accessibility tree to
query, so bc-drive identifies screens by **screenshot + vision** and carries a
hand-curated per-screen widget-rect map. **Set-of-Mark (SoM)** grounding upgrades
this: overlay **numbered marks** on detected interactive regions so the model refers
to "tap **7**" instead of guessing pixel coordinates (the technique that lifts GUI
grounding accuracy on canvas UIs).

Rides the existing bus — the input is bc-drive's `adb exec-out screencap`; the output
maps mark-number → **device-px rect** (1920×1080), reusing bc-drive's `metrics`
device↔drawable scale (×1.6875) for drawable back-projection.

**Adopt (local, GPU-optional):**
```bash
# OmniParser V2 (MIT) = YOLO icon/box detector + a caption model. Run on cloud-hub
# GPU or locally; feed it the bc-drive screenshot, get boxes back, number them.
pip install ultralytics  # icon detector backbone
# weights: microsoft/OmniParser-v2.0 (HF)  ->  hf_hub_download
```
Pipeline: `bc_drive.py screenshot` → OmniParser detect → number boxes top-left→
bottom-right → build `{mark: {device_px:[cx,cy], rect:[...], drawable:[...]}}` → the
operator/model picks a mark → `bc_drive.py tap <cx> <cy>`. Status: **documented ADOPT,
not yet wired to a live model here** (honest — grounding accuracy must be validated
against real BC screens before it supersedes the curated `SCREENS` map). Until then
bc-drive's screenshot-derived map remains the source of truth; SoM is the roadmap to
generalize beyond the three hand-mapped screens.

---

## 3 · minitouch / evdev low-latency input (ADOPT recipe)

bc-drive actuates with `adb shell input tap`, which **spawns a process per tap**
(~tens–hundreds of ms). For faster/smoother sequences (swipes, multi-tap), a
persistent low-latency channel helps:
- **minitouch** — a tiny daemon writing directly to the touch `evdev` node; open one
  socket and stream `d`/`m`/`u` commands (down/move/up) with sub-ms dispatch.
- **raw evdev** — `su -c` write `EV_ABS`/`EV_KEY` events to `/dev/input/eventX`.

**Adopt:**
```bash
# push a prebuilt minitouch matching the emulator ABI (x86_64), then:
adb -s 127.0.0.1:5555 push minitouch /data/local/tmp/ && adb shell chmod 755 /data/local/tmp/minitouch
adb shell "/data/local/tmp/minitouch -i"     # prints max-contacts + coordinate bounds
# stream: printf 'd 0 <x> <y> 50\nc\nu 0\nc\n' | nc <minitouch socket>
```
Coordinate space: minitouch/evdev use the **touch device's** ABS range, which may
differ from the 1920×1080 display px — read the bounds from `minitouch -i` and scale
bc-drive's device-px targets into that range. Status: **documented ADOPT with an
`adb tap` fallback** — the safety envelope is unchanged (taps only on safe menu
navigation; never gacha "Draw", stage "Start" confirm, or anything spending
currency). Latency is an optimization, not a correctness requirement, so `adb tap`
stays the default until minitouch is bound for the specific BlueStacks build.

---

## 4 · Save-snapshot ring + auto-rollback (`snapshot_ring.py`)

Encodes the **HGT-safe-restore** discipline from `bcsfe-save-roundtrip` as
automation: keep a **bounded rotating ring** of known-good pre-edit `SAVE_DATA`
snapshots so **any** broken/suspect state can be rolled back to the last verified
save. ("HGT" = the anti-cheat ban trap; the guard is: always be able to restore a
clean, pre-edit save.)

Rides the bcsfe bus exactly (do not reinvent):
- **Pull** after a `KEYCODE_HOME` flush (backgrounding flushes RAM→disk; `force-stop`
  does **not** flush).
- **Restore** in place via `cat >` so the **inode + owner (uid 10065) + SELinux
  `app_data_file` context** survive; **`am force-stop` FIRST** so autosave can't race;
  **`md5sum` verify** device == snapshot after.
- **Empty-wipe trap:** a 0-byte/short read is **never** stored as good and **never**
  pushed back (the MSYS `d41d8cd9…` wipe class). `MIN_SAVE_BYTES` gates both ends; a
  backup whose on-disk md5 ≠ recorded md5 is refused before any push.

### Shadow vs enforce (council C5)
- `snapshot` (read-only pull) and an **explicit** `rollback` are always **real**.
- **Automatic** rollback (`auto_rollback(is_broken)`) defaults to **SHADOW**: if the
  health probe says broken, it **logs** which snapshot it *would* restore and mutates
  nothing. Only `enforce=True` actually restores. A flaky probe that raises is treated
  as **not broken** (never triggers a destructive restore on its own error).

### Usage
```
python snapshot_ring.py snap [label]      # flush+pull a byte-exact snapshot into the ring
python snapshot_ring.py list              # ring contents, newest first
python snapshot_ring.py rollback [index]  # EXPLICIT restore (index from `list`; default newest good)
python snapshot_ring.py verify            # md5 device vs newest snapshot
python snapshot_ring.py prune             # enforce capacity + drop orphan files
```
Env: `BC_ADB`, `BC_SERIAL`, `BC_RING_DIR` (default `<skill>/.save-ring`),
`BC_RING_CAP` (default 10). Python API: `SnapshotRing(io, ring_dir).auto_rollback(
probe, enforce=False)` for a shadow health-guard loop; inject a custom `SaveIO` for
testing or a non-adb transport.

> **Live-game care (inherited):** read-only discovery is safe; prefer reversible
> save-edits over forcing unverified in-memory fields. On a broken state: **kill all
> hooks + restart BC first**, *then* `rollback` to the newest verified snapshot.

---

## What works vs what's inferred (honesty ledger)

| Capability | Status |
|---|---|
| `dispatch_capture` agent-JS generation (valid JS, single-shot, no sync RPC) | ✅ unit-tested (`node --check` clean) |
| Scene guard refuses to arm outside menu cluster | ✅ unit-tested |
| Single-shot detach + hard-timeout detach (hook never left live) | ✅ unit-tested (fake device) |
| Shadow = no auto-tap; explicit arm fires exactly one tap | ✅ unit-tested |
| `resolve_ctor_candidates` ranks caller RVAs + flags vtable match | ✅ unit-tested |
| **Live** dispatch-capture on a running BC + actual ctor RVA | ⚠️ needs a device run + the offline xref step (documented) |
| Snapshot ring rotation, corruption guard, integrity-gated rollback | ✅ unit-tested (fake SaveIO) |
| Shadow auto-rollback logs-not-mutates; flaky probe is safe | ✅ unit-tested |
| **Live** pull/restore round-trip (inode/uid/SELinux preserved) | ⚠️ needs a device run (rides proven bcsfe recipe) |
| OmniParser V2 set-of-mark grounding | 📋 documented ADOPT recipe; not yet wired to a live model |
| minitouch/evdev low-latency input | 📋 documented ADOPT recipe; `adb tap` remains default |

## Files
- `dispatch_capture.py` — bounded single-shot touch-dispatch capture + ctor-evidence resolver + CLI.
- `snapshot_ring.py` — save-snapshot ring + HGT-safe auto-rollback + CLI.
- (grounding + input are ADOPT recipes above; they ride bc-drive's screenshot/adb bus.)

## Safety summary
Read-mostly. Zero per-frame hooks. The one input-path hook is single-shot,
scene-guarded, hard-timeout-bounded, and async-only (thread-selection safe). Save
writes are inode/context-preserving, force-stop-guarded, md5-verified, and
empty-wipe-guarded; automated rollback is shadow-by-default. Taps only on safe menu
navigation — never gacha "Draw", stage "Start" confirm, or anything that spends
currency or alters the save.