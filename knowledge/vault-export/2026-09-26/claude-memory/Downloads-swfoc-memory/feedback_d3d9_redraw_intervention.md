---
name: D3D9 redraw intervention is dangerous
description: Don't post WM_DISPLAYCHANGE / RedrawWindow spam to a D3D9 game window
  in a device-lost / black-screen state — it promotes soft-failure to hard crash
type: feedback
originSessionId: 7139727b-6316-4a4b-ba33-8787be5a31fc
permalink: main/claude-memory/downloads-swfoc-memory/feedback-d3d9-redraw-intervention
---

When a D3D9 game (e.g. SWFOC's `StarWarsG.exe`, 2006 Petroglyph engine) shows symptoms of device-lost recovery cycles — flashing, occasional black frames, content visible only when window is moved/resized — DO NOT try to "help" by sending Win32 redraw messages to it.

Specifically:
- **`PostMessageW(hwnd, WM_DISPLAYCHANGE, ...)`** can take a half-functional D3D9 device and push it into a hard crash. Lost two attached `StarWarsG.exe` PIDs to this in tonight's operator-support session (2026-05-08).
- **`RedrawWindow(hwnd, ..., RDW_INVALIDATE | RDW_UPDATENOW)` in a tight loop** (e.g. 50 Hz pump) at the same time the engine's own device-lost handler is running creates a race that the engine almost always loses.
- **Toggling z-order via `SetWindowPos(HWND_TOPMOST, ..., SWP_FRAMECHANGED)` then back to NOTOPMOST** triggers internal D3D9 mode-change paths that compound with whatever caused the original device-lost.

**Why:** D3D9 fullscreen-exclusive devices on modern Windows (DWM compositor + HDR-capable displays + fullscreen optimization) already have fragile lost-device recovery. The engine's own `IDirect3DDevice9::TestCooperativeLevel` / `Reset` cycle is the only thing that can legitimately heal the device. Anything else just adds noise.

**How to apply:**
- For old D3D9 game graphics issues, the FIX is environmental: disable Fullscreen Optimization, run as Administrator, switch to windowed mode, disable HDR, force discrete GPU. Apply BEFORE relaunch.
- Never use Frida (or any other injector) to spray graphics-related Win32 messages at a wounded D3D9 game in hopes of "kickstarting" the renderer. Best case: nothing happens. Worst case: hard crash, lose attached process.
- If the game is genuinely stuck and you need to recover state, prefer **clean kill + relaunch with compatibility fixes** over live intervention.
- Live intervention is only safe BEFORE the device-lost cycle starts (e.g., to break a CPU-side soft-lock that hasn't yet starved the renderer enough to trigger TDR).

**Adjacent lesson:** Frida MCP's `execute_in_session` runs each script in an isolated context. Globals don't persist between calls; `setInterval` callbacks die when the script returns. For monitoring loops, do the work inside ONE long-running call with `Thread.sleep` between samples, OR write progress to a file from inside a hook (no setInterval). Don't try to set up a hook in one call and read its state in a later call — both will fail silently.

Captured: 2026-05-08, after `swfoc_memory` operator-support session.