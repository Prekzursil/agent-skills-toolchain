'use strict';
/*
 * bc_agent.js  --  On-demand Battle Cats (jp.co.ponos.battlecatsen, EN 15.4.1) driver agent.
 *
 * CRITICAL CONSTRAINT: NO per-frame Interceptor. A hook on appUpdateDraw / render
 * functions crashes BC on scene transitions (the hot-path lesson). Everything here is
 * either a pure memory READ or a single NativeFunction CALL, invoked once per request.
 * The optional captureCtor() hook is short-lived (attach -> navigate -> detach) and is
 * NOT a render-path hook.
 *
 * Confirmed offsets (RVA in libnative-lib.so, x86_64 build):
 *   getGlobal()  -> MyApplication*   @ 0x65D900
 *   getScene(g)  -> int (scene/state) @ 0x668910   (arg0 = MyApplication*)
 *   metrics struct                    @ 0x1098C10
 *     +0x00 MyApplication*   (== getGlobal())
 *     +0x08 windowW   +0x0C windowH   (OS window px; == `wm size`; == adb-tap space)
 *     +0x10 sizeW     +0x14 sizeH     (logical size px)
 *     +0x18 drawableW +0x1C drawableH (BC internal canvas units)
 */

const M = 'libnative-lib.so';
const RVA = { getGlobal: 0x65D900, getScene: 0x668910, metrics: 0x1098C10 };
// MyApplication field offsets (verified live via disasm of getScene + state diffing):
//   +0x2F24 = coarse scene/state (getScene reads this; enum cluster 0x61..0x65 = 97..101)
//   +0x2F20 = secondary/previous state (written alongside +0x2F24 by setter @0x65DD0F)
//   +0x2F08 = per-screen view fingerprint (stable per screen, differs across screens;
//             title=242, chapter-select=551, Cat Base=370 in EN 15.4.1)
const APP = { scene: 0x2F24, prevScene: 0x2F20, view: 0x2F08, touchVtblOff: 0x40 };

let _base = null;
function base() {
  if (_base) return _base;
  const m = Process.findModuleByName(M);
  if (!m) throw new Error('module ' + M + ' not found');
  _base = m.base;
  return _base;
}
function fnGetGlobal() { return new NativeFunction(base().add(RVA.getGlobal), 'pointer', []); }
function fnGetScene() { return new NativeFunction(base().add(RVA.getScene), 'int', ['pointer']); }

// short-lived button-constructor capture state (best-effort widget enumeration)
let _cap = null; // { listener, rva, rows: [] }

rpc.exports = {
  // module info / sanity
  info: function () {
    const m = Process.findModuleByName(M);
    if (!m) return { ok: false, error: 'module not found', mods: Process.enumerateModules().slice(0, 8).map(x => x.name) };
    return { ok: true, module: M, base: m.base.toString(), size: m.size };
  },

  // scene/state id  (getScene(getGlobal())) -- single NativeFunction call, never hooked.
  // Returns BOTH the coarse macro-state (getScene == app+0x2F24, ~100 for all
  // out-of-battle menus) and the finer per-screen view fingerprint (app+0x2F08),
  // which DOES change as you navigate menus (title=242, chapter-select=551,
  // Cat Base=370 in EN 15.4.1).
  scene: function () {
    const g = fnGetGlobal()();
    if (g.isNull()) return { ok: false, error: 'global null' };
    return {
      ok: true,
      scene: fnGetScene()(g),                 // coarse macro-state (app+0x2F24)
      prev: g.add(APP.prevScene).readS32(),   // app+0x2F20 (secondary/prev)
      view: g.add(APP.view).readS32(),        // app+0x2F08 per-screen fingerprint
      global: g.toString()
    };
  },

  // Read-only inspection of the touch-dispatch path:
  //   touch = getGlobal()->vtable[+0x40](g, phase{0,1,2}, (int)x, (int)y, pid)
  // We resolve (never call) the fn pointer so it is documented/portable. Actuation
  // is done OS-side via `adb shell input tap` (safer; no game-thread race).
  touchInfo: function () {
    const g = fnGetGlobal()();
    if (g.isNull()) return { ok: false, error: 'global null' };
    const b = base();
    const vt = g.readPointer();                       // *MyApplication == vtable
    const fn = vt.add(APP.touchVtblOff).readPointer(); // vtable[+0x40]
    return { ok: true, vtable_rva: vt.sub(b).toString(16), touch_fn_rva: fn.sub(b).toString(16) };
  },

  // metrics struct read + derived device<->drawable scale
  metrics: function () {
    const ma = base().add(RVA.metrics);
    const windowW = ma.add(0x08).readU32();
    const windowH = ma.add(0x0c).readU32();
    const sizeW = ma.add(0x10).readU32();
    const sizeH = ma.add(0x14).readU32();
    const drawableW = ma.add(0x18).readU32();
    const drawableH = ma.add(0x1c).readU32();
    return {
      ok: true,
      addr: ma.toString(),
      app_ptr: ma.readPointer().toString(),
      windowW: windowW, windowH: windowH,
      sizeW: sizeW, sizeH: sizeH,
      drawableW: drawableW, drawableH: drawableH,
      // multiply a BC-drawable coordinate by these to get device/adb-tap px
      scaleX: drawableW ? windowW / drawableW : null,
      scaleY: drawableH ? windowH / drawableH : null
    };
  },

  // --- best-effort native widget enumeration -------------------------------
  // Briefly hooks a button/widget constructor at the given RVA, records arg0
  // (the new object pointer) plus a window of candidate float fields so a rect
  // can be located post-hoc. NOT a render hook: it fires only while widgets are
  // built. Always paired with stopCapture() to detach quickly.
  startCapture: function (rva, floatWindow) {
    if (_cap) return { ok: false, error: 'capture already running; call stopCapture first' };
    const fw = floatWindow || 0x80; // bytes of object to sample
    const addr = base().add(rva);
    const rows = [];
    let listener;
    try {
      listener = Interceptor.attach(addr, {
        onEnter: function (args) {
          try {
            const self = args[0];
            const floats = [];
            for (let i = 0; i < fw; i += 4) {
              const f = self.add(i).readFloat();
              floats.push(Number.isFinite(f) ? Number(f.toFixed(2)) : null);
            }
            rows.push({ self: self.toString(), floats: floats });
          } catch (e) { rows.push({ err: String(e) }); }
        }
      });
    } catch (e) {
      return { ok: false, error: 'attach failed: ' + String(e) };
    }
    _cap = { listener: listener, rva: rva, rows: rows };
    return { ok: true, rva: '0x' + rva.toString(16), floatWindow: fw };
  },
  stopCapture: function () {
    if (!_cap) return { ok: false, error: 'no capture running' };
    try { _cap.listener.detach(); } catch (e) {}
    const rows = _cap.rows;
    const rva = _cap.rva;
    _cap = null;
    return { ok: true, rva: '0x' + rva.toString(16), count: rows.length, rows: rows };
  }
};
