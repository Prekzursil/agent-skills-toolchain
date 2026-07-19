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

MyApplication fields: `+0x2F24` scene (getScene), `+0x2F20` prev/secondary scene,
`+0x2F08` a UI field (unreliable, see below).

## Coordinate space (the key result — SOLVED)
metrics struct @ `base+0x1098C10`:
```
+0x00 MyApplication*  (== getGlobal())
+0x08 windowW=1920   +0x0C windowH=1080   <- OS window px (== `wm size`, == adb-tap space)
+0x10 sizeW=1920     +0x14 sizeH=1080     <- logical size px
+0x18 drawableW=1138 +0x1C drawableH=640  <- BC internal canvas units
```
- **`adb shell input tap` operates in DEVICE px = 1920x1080** (== windowW/H, == screencap
  pixels). Confirmed: taps reliably actuate BC (drove Title→ChapterSelect→CatBase→stage
  list; objective framebuffer pixel-diff = 0.20 on a forward tap).
- **BC internal drawable space = 1138x640.** Uniform scale **device = drawable × 1.6875**
  (exactly 1080/640; 1138×1.6875 ≈ 1920). `tapw` converts drawable→device with this.

## Scene / state model (honest)
- `scene` (`+0x2F24`, via getScene): **COARSE macro-state.** Reads **100** across the
  ENTIRE out-of-battle menu system (Title, chapter-select, Cat Base, stage list, Equip).
  Static analysis (setter @0x65DD0F: `lea eax,[rsi-0x61]; cmp 4; bt 0x13`) shows the
  enum cluster is **0x61..0x65 (97..101)**; it flips on major transitions (e.g. entering
  a battle — deliberately NOT exercised: that spends energy / alters the save). Use it
  only as a **battle-vs-menu guard**, not to tell menu screens apart.
- `+0x2F08` (`view`): an app UI field that **VARIES on the same screen over time** and
  **collides across screens** (242 seen on BOTH Title and Cat Base). NOT a screen id and
  NOT a dependable change-signal. Reported for transparency; do not depend on it.
- **Screen identity → SCREENSHOT.** The only ground truth for "which menu am I on" is
  `adb exec-out screencap` + vision. `demo` proves navigation via an objective
  framebuffer **pixel-diff**, not via any state field.

## Widgets (best-effort)
- `widgets <ScreenName>` returns a **screenshot-derived** tappable-rect map (device px +
  drawable back-projection) for `Title`, `ChapterSelect`, `CatBase`. Several rects are
  tap-validated this session (Play, chapter-center, Start, Back, Close).
- **Native node-tree extraction is NOT done.** RTTI in `.rodata` reveals the architecture
  — button class **`NewButton`** (callback `void(NewButton*, NewButtonChangeState)`) and
  many `createXxxButton` factories (`MyApplication::battle_createButton`,
  `RankingView::createButton`, `MainMenuLevelSelect::createStageSelectButton`,
  `UIComponent::createBackButton`, `FilterMenu::createOK/Close Button`, …). But the game's
  own C++ **function symbols are stripped** (only third-party firebase/Botan/libc++
  exports survive), so the `NewButton` constructor RVA is unresolved. Once resolved (via
  RTTI→vtable→ctor xref RE), `capture <ctorRVA> <ms>` hooks it briefly during a navigation
  to dump live button objects + candidate rect floats. Infra is built and ready.

## Usage
```
python bc_drive.py scene                 # {scene, prev, view, global}
python bc_drive.py metrics               # window/size/drawable px + scale
python bc_drive.py touchinfo             # vtable + touch-fn RVAs (read-only)
python bc_drive.py screenshot [out.png]
python bc_drive.py tap  <devX> <devY>    # device px (1920x1080)
python bc_drive.py tapw <drawX> <drawY>  # BC drawable units -> device px
python bc_drive.py widgets <ScreenName>  # Title | ChapterSelect | CatBase
python bc_drive.py demo <ScreenName>     # tap forward -> objective pixel-diff proof
python bc_drive.py capture <ctorRVAhex> <ms>   # native NewButton capture (needs ctor RVA)
```
Env: `BC_SERIAL` (default 127.0.0.1:5555), `BC_ADB` (default adb). Requires BC running
(`adb shell pidof jp.co.ponos.battlecatsen`) and frida-server up.

## Safety
Read-mostly. Taps only on safe menu navigation. NEVER taps gacha "Draw", stage "Start"
confirmation, or anything that spends currency / alters the save. Zero per-frame hooks.

## What works vs what's inferred
| Capability | Status |
|---|---|
| `getGlobal`, `metrics`, `getScene` offsets | ✅ verified live (called/disassembled) |
| Coordinate space (device 1920x1080 ↔ drawable 1138x640, ×1.6875) | ✅ verified |
| `adb input tap` actuates BC in device px | ✅ verified (multi-screen + pixel-diff) |
| `scene()` = coarse macro-state (100 in menus) | ✅ verified; granularity is a finding |
| touch dispatch `vtable[+0x40]` @0x668C70 | ✅ resolved read-only (not called) |
| Widget rects (Title/ChapterSelect/CatBase) | ✅ screenshot-derived; key ones tap-validated |
| `scene` enum value-space {97..101}, battle value | ⚠️ inferred from static analysis (not run live) |
| `+0x2F08` as a screen signal | ❌ disproven (unreliable) — use screenshots |
| Native `NewButton` node-tree / rects | ⚠️ architecture known (RTTI); ctor RVA unresolved (symbols stripped) |
