#!/usr/bin/env python3
"""dispatch_capture.py -- bounded one-shot touch-dispatch capture for LIVE Battle
Cats EN (jp.co.ponos.battlecatsen 15.4.1) on rooted BlueStacks.

WHY: recover the runtime evidence needed to resolve the STRIPPED ``NewButton``
constructor RVA -- bc-drive's #1 documented open gap. BC's own C++ symbols are
stripped; only RTTI in .rodata names the class ``NewButton`` + createXxxButton
factories. The touch-dispatch fn is already resolved:
    RVA 0x668C70  ==  getGlobal()->vtable[+0x40]   (vtable RVA 0xBED598)

MECHANISM (bounded, single-shot, thread-safe):
  Attach a ONE-SHOT Interceptor to 0x668C70. On the FIRST real touch it fires,
  capture MINIMALLY: the args (phase{0,1,2}, x, y, pid), the return address (caller
  RVA), and a short ACCURATE backtrace (module-relative RVAs). Emit asynchronously
  via send(), then DETACH. Combined with the known NewButton vtable RVA (0xBED598),
  the caller RVAs -- and, if a hit-node field offset is supplied, the touched node's
  own vtable RVA -- localize the ctor via an offline xref pass (documented follow-up
  in SKILL.md). This yields the evidence; the final ctor RVA is confirmed by the
  xref-to-vtable step in Ghidra/IDA (honest: not magically printed here).

THREAD-SELECTION SAFETY (the flagged live-frida risk -- honored):
  * The touch dispatcher runs on the game's UI/input thread. The onEnter callback
    does the MINIMUM and NEVER makes a synchronous host RPC -- a blocking recv()
    inside onEnter would stall the input thread and ANR/crash BC. It reads registers
    and calls ONLY async send(). *This is the thread-selection safety flag.*
  * SINGLE-SHOT: the agent self-limits to ``max_hits`` (default 1); after the cap it
    stops recording and the driver detaches immediately.
  * SCENE-GUARDED: refuses to arm unless ``scene`` is in the out-of-battle menu
    cluster (97..101). NEVER hooks the input path during a battle.
  * HARD TIMEOUT: the driver auto-detaches after ``timeout_ms`` even if no touch
    arrives, so a hook is never left live.
  * NOT a per-frame hook: 0x668C70 fires only on touch events (unlike the render
    path appUpdateDraw @0x33F7E0, which crashes BC on scene transitions).

SHADOW-MODE (council C5): default is OBSERVE-only. The module hooks + records and
the OPERATOR performs the single tap manually; it never auto-navigates, never spends
currency, never blocks/nags. Passing an explicit ``auto_tap=(x, y)`` with
``shadow=False`` drives ONE safe menu tap as the trigger.

CLI:
  python dispatch_capture.py show                 # print the generated agent JS
  python dispatch_capture.py capture <ms>         # arm 1-shot; operator taps once
  python dispatch_capture.py capture <ms> <x> <y> # arm + drive ONE safe menu tap
Env: BC_ADB, BC_SERIAL, BC_DC_SINK (bounded log sink; default <skill>/.dc-shadow.log).
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import time
from collections import Counter
from dataclasses import dataclass, field
from typing import Callable, Optional

MODULE = "libnative-lib.so"
PKG = "jp.co.ponos.battlecatsen"
RVA_TOUCH_DISPATCH = 0x668C70  # getGlobal()->vtable[+0x40] (resolved, read-only)
VTABLE_NEWBUTTON = 0xBED598  # NewButton vtable RVA (from RTTI in .rodata)
# Out-of-battle macro-state cluster (getScene == app+0x2F24). ~100 across all menus;
# static analysis of the setter @0x65DD0F gives the enum cluster 0x61..0x65 = 97..101.
MENU_SCENE_MIN, MENU_SCENE_MAX = 97, 101
DEFAULT_TIMEOUT_MS = 6000
DEFAULT_BACKTRACE_DEPTH = 8
SHADOW_SINK_MAX_BYTES = 256 * 1024  # bounded, rotating shadow log

log = logging.getLogger("bc.dispatch_capture")


def is_menu_scene(scene: Optional[int]) -> bool:
    """True only for the out-of-battle menu cluster. Arming the input-path hook
    outside this range (e.g. mid-battle) is refused -- the thread-selection guard."""
    return scene is not None and MENU_SCENE_MIN <= int(scene) <= MENU_SCENE_MAX


def rva_hex(ptr: int, base: int) -> str:
    """Module-relative RVA (``0x...``) for an absolute pointer, or ``None`` if the
    pointer is outside the module (a caller in libc/another module)."""
    off = ptr - base
    if off < 0:
        return None
    return f"0x{off:x}"


def build_agent_js(
    rva: int = RVA_TOUCH_DISPATCH,
    *,
    max_hits: int = 1,
    backtrace_depth: int = DEFAULT_BACKTRACE_DEPTH,
    node_field_off: Optional[int] = None,
    module: str = MODULE,
) -> str:
    """Generate the Frida agent for a BOUNDED single-shot capture.

    The agent is deliberately tiny and does NO synchronous host RPC inside onEnter
    (thread-selection safety). It self-limits to ``max_hits`` and sends rows async.
    ``node_field_off`` (optional) reads a candidate hit-node pointer off arg0 and
    reports its vtable RVA directly.
    """
    node_read = ""
    if node_field_off is not None:
        node_read = f"""
          try {{
            var nodePtr = self.add({int(node_field_off)}).readPointer();
            if (!nodePtr.isNull()) {{
              var nvt = nodePtr.readPointer();
              row.node_ptr = nodePtr.toString();
              row.node_vtable_rva = '0x' + nvt.sub(base).toString(16);
            }}
          }} catch (e) {{ row.node_err = String(e); }}"""
    return f"""'use strict';
// BOUNDED single-shot touch-dispatch capture. NOT a per-frame hook: {hex(rva)}
// (getGlobal()->vtable[+0x40]) fires only on touch events. onEnter does the MINIMUM
// and NEVER blocks the game/input thread (async send() only). Self-limits to
// max_hits then stops; the Python driver detaches immediately after.
var MODULE = {json.dumps(module)};
var m = Process.findModuleByName(MODULE);
if (!m) {{ send({{ ok: false, error: 'module not found: ' + MODULE }}); }}
var base = m ? m.base : ptr(0);
var HITS = 0, MAX = {int(max_hits)}, DEPTH = {int(backtrace_depth)};
var listener = null;
try {{
  listener = Interceptor.attach(base.add({hex(rva)}), {{
    onEnter: function (args) {{
      if (HITS >= MAX) return;          // single-shot cap
      HITS++;
      var self = args[0];
      var row = {{
        hit: HITS,
        arg0: self.toString(),
        phase: args[1].toInt32 ? args[1].toInt32() : null,
        x: args[2].toInt32 ? args[2].toInt32() : null,
        y: args[3].toInt32 ? args[3].toInt32() : null,
        pid: args[4] ? args[4].toString() : null,
        ret_rva: '0x' + this.returnAddress.sub(base).toString(16),
        base: base.toString()
      }};
      try {{
        row.backtrace = Thread.backtrace(this.context, Backtracer.ACCURATE)
          .slice(0, DEPTH)
          .map(function (a) {{ var o = a.sub(base); return o.compare(0) >= 0
            ? '0x' + o.toString(16) : a.toString(); }});
      }} catch (e) {{ row.bt_err = String(e); }}{node_read}
      send({{ ok: true, row: row }});     // async -- never blocks the input thread
      if (HITS >= MAX && listener) {{ try {{ listener.detach(); }} catch (e) {{}} }}
    }}
  }});
  send({{ ok: true, armed: true, rva: '{hex(rva)}', max_hits: MAX }});
}} catch (e) {{
  send({{ ok: false, error: 'attach failed: ' + String(e) }});
}}
rpc.exports = {{
  disarm: function () {{ if (listener) {{ try {{ listener.detach(); }} catch (e) {{}} }} return {{ ok: true, hits: HITS }}; }}
}};
"""


@dataclass
class CaptureResult:
    """Terminal-state receipt for a bounded capture run."""

    result: str
    armed: bool = False
    rows: list = field(default_factory=list)
    error: Optional[str] = None
    scene: Optional[int] = None
    shadow: bool = True

    def to_json(self) -> dict:
        return {
            "result": self.result,
            "armed": self.armed,
            "scene": self.scene,
            "shadow": self.shadow,
            "rows": self.rows,
            "error": self.error,
        }


def parse_rows(messages: list) -> list:
    """Extract capture rows from a list of frida ``send()`` payloads (dicts with a
    ``row`` key or already-unwrapped rows)."""
    rows = []
    for msg in messages:
        payload = msg.get("payload", msg) if isinstance(msg, dict) else msg
        if isinstance(payload, dict) and payload.get("ok") and "row" in payload:
            rows.append(payload["row"])
    return rows


def resolve_ctor_candidates(
    rows: list, known_vtable_rva: int = VTABLE_NEWBUTTON
) -> dict:
    """From captured rows, aggregate the runtime evidence that localizes the stripped
    NewButton ctor. Returns caller/backtrace RVAs ranked by frequency, any hit-node
    vtable RVA and whether it matches the known NewButton vtable, plus the exact
    offline follow-up. Honest: the ctor RVA is CONFIRMED by the documented xref step,
    not asserted here."""
    caller_freq: Counter = Counter()
    node_vtables: list = []
    node_match = False
    known_hex = f"0x{known_vtable_rva:x}"
    for row in rows:
        if row.get("ret_rva"):
            caller_freq[row["ret_rva"]] += 1
        for frame in row.get("backtrace", []) or []:
            caller_freq[frame] += 1
        nvt = row.get("node_vtable_rva")
        if nvt:
            node_vtables.append(nvt)
            if nvt.lower() == known_hex.lower():
                node_match = True
    ranked = [{"rva": rva, "count": c} for rva, c in caller_freq.most_common()]
    return {
        "known_newbutton_vtable_rva": known_hex,
        "hit_node_vtable_rvas": node_vtables,
        "hit_node_matches_newbutton_vtable": node_match,
        "caller_rvas_ranked": ranked,
        "followup": (
            "Offline: in Ghidra/IDA, xref the NewButton vtable RVA "
            f"{known_hex} (from RTTI); the function that STORES this vtable into a "
            "fresh object (mov [obj], vtable) is the NewButton ctor. Cross-check "
            "against the ranked caller RVAs above (the dispatch->callback path). If "
            "hit_node_matches_newbutton_vtable is true, node_ptr is a live NewButton "
            "-- its ctor is the storer of its vtable."
        ),
    }


class _AdbTap:
    """Minimal adb tap seam (device px). Only used for the explicit auto_tap trigger."""

    def __init__(self, adb: Optional[str] = None, serial: Optional[str] = None) -> None:
        self.adb = adb or os.environ.get("BC_ADB", "adb")
        self.serial = serial or os.environ.get("BC_SERIAL", "127.0.0.1:5555")

    def __call__(self, x: int, y: int) -> None:
        subprocess.run(
            [
                self.adb,
                "-s",
                self.serial,
                "shell",
                "input",
                "tap",
                str(int(x)),
                str(int(y)),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=True,
        )


def _shadow_log(sink_path: str, record: dict) -> None:
    """Append to a bounded, rotating shadow sink (council C5 (iii): shadow logs go to
    a separate, size-capped sink -- never the main ledger)."""
    try:
        if (
            os.path.exists(sink_path)
            and os.path.getsize(sink_path) > SHADOW_SINK_MAX_BYTES
        ):
            os.replace(sink_path, sink_path + ".1")
        with open(sink_path, "a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": time.time(), **record}) + "\n")
    except OSError:
        pass


class BoundedDispatchCapture:
    """Orchestrates a bounded, single-shot, thread-safe touch-dispatch capture.

    Device coupling is injected (``device`` = frida device-like, ``tapper`` = tap
    callable, ``sleep``/``now`` = clock) so the arm/timeout/scene-guard/shadow state
    machine is unit-testable without a live device or frida socket.
    """

    def __init__(
        self,
        device=None,
        *,
        shadow: bool = True,
        tapper: Optional[Callable[[int, int], None]] = None,
        sleep: Callable[[float], None] = time.sleep,
        now: Callable[[], float] = time.monotonic,
        sink_path: Optional[str] = None,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self._device = device
        self.shadow = shadow
        self.tapper = tapper
        self.sleep = sleep
        self.now = now
        self.sink_path = sink_path or os.environ.get(
            "BC_DC_SINK",
            os.path.join(os.path.dirname(os.path.abspath(__file__)), ".dc-shadow.log"),
        )
        self.log = logger or log

    def _get_device(self):
        if self._device is not None:
            return self._device
        import frida  # lazy: only needed for a real attach

        try:
            return frida.get_usb_device(timeout=8)
        except Exception:
            return frida.get_device_manager().add_remote_device("127.0.0.1:27042")

    def _get_pid(self) -> int:
        adb = os.environ.get("BC_ADB", "adb")
        serial = os.environ.get("BC_SERIAL", "127.0.0.1:5555")
        out = subprocess.run(
            [adb, "-s", serial, "shell", "pidof", PKG],
            stdout=subprocess.PIPE,
            text=True,
            check=True,
        ).stdout.strip()
        if not out:
            raise RuntimeError(f"{PKG} not running (pidof empty)")
        return int(out.split()[0])

    def arm_and_capture(
        self,
        scene: Optional[int],
        *,
        pid: Optional[int] = None,
        timeout_ms: int = DEFAULT_TIMEOUT_MS,
        max_hits: int = 1,
        backtrace_depth: int = DEFAULT_BACKTRACE_DEPTH,
        node_field_off: Optional[int] = None,
        auto_tap: Optional[tuple] = None,
    ) -> CaptureResult:
        """Arm the one-shot hook, wait (bounded) for ``max_hits`` touches, detach.

        Refuses to arm outside the menu cluster (thread-selection safety). In shadow
        mode it will NOT auto-tap (operator taps); an explicit ``auto_tap`` with
        ``shadow=False`` drives one safe menu tap as the trigger.
        """
        if not is_menu_scene(scene):
            return CaptureResult(
                result="FAILED:dispatch-capture refused: scene not in menu cluster "
                f"({scene}); will not hook the input path outside a menu",
                scene=scene,
                shadow=self.shadow,
            )
        device = self._get_device()
        pid = pid if pid is not None else self._get_pid()
        js = build_agent_js(
            max_hits=max_hits,
            backtrace_depth=backtrace_depth,
            node_field_off=node_field_off,
        )
        session = device.attach(pid)
        messages: list = []
        script = session.create_script(js)
        script.on("message", lambda message, data: messages.append(message))
        script.load()

        # Trigger: shadow = operator taps manually; explicit auto_tap only when armed.
        if auto_tap is not None:
            if self.shadow:
                _shadow_log(
                    self.sink_path,
                    {"event": "would_auto_tap", "xy": list(auto_tap), "scene": scene},
                )
                self.log.info(
                    "SHADOW: would auto-tap %s (operator taps manually)", auto_tap
                )
            else:
                tap = self.tapper or _AdbTap()
                tap(int(auto_tap[0]), int(auto_tap[1]))

        # Bounded wait: poll until max_hits rows captured OR the hard timeout elapses.
        deadline = self.now() + timeout_ms / 1000.0
        armed = False
        while self.now() < deadline:
            rows = parse_rows(messages)
            if any(
                isinstance(m, dict) and m.get("payload", {}).get("armed")
                for m in messages
            ):
                armed = True
            if len(rows) >= max_hits:
                break
            self.sleep(0.05)

        # Always detach -- a hook is never left live.
        try:
            script.exports_sync.disarm()
        except Exception:
            pass
        try:
            session.detach()
        except Exception:
            pass

        rows = parse_rows(messages)
        errs = [
            m.get("payload", {}).get("error")
            for m in messages
            if isinstance(m, dict)
            and isinstance(m.get("payload"), dict)
            and m["payload"].get("error")
        ]
        if rows:
            result = f"SUCCESS:dispatch-capture {len(rows)} hit(s)"
        elif errs:
            result = f"FAILED:dispatch-capture {errs[0]}"
        else:
            result = "FAILED:dispatch-capture no touch captured within timeout"
        if self.shadow:
            _shadow_log(
                self.sink_path,
                {
                    "event": "capture",
                    "result": result,
                    "hits": len(rows),
                    "scene": scene,
                },
            )
        return CaptureResult(
            result=result,
            armed=armed,
            rows=rows,
            error=(errs[0] if errs else None),
            scene=scene,
            shadow=self.shadow,
        )


# -- CLI -------------------------------------------------------------------
def _emit(obj: object) -> None:
    sys.stdout.write(json.dumps(obj, indent=2, default=str) + "\n")


def main(argv: Optional[list[str]] = None) -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s %(name)s: %(message)s"
    )
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        sys.stdout.write(__doc__ or "")
        return 0
    cmd, rest = args[0], args[1:]
    if cmd == "show":
        sys.stdout.write(build_agent_js() + "\n")
        return 0
    if cmd == "capture":
        # Read live scene via the sibling bc-drive agent so the guard is real.
        scene = _read_scene_via_bc_drive()
        timeout_ms = int(rest[0]) if rest else DEFAULT_TIMEOUT_MS
        auto_tap = (int(rest[1]), int(rest[2])) if len(rest) >= 3 else None
        shadow = auto_tap is None  # an explicit tap target = operator-armed run
        cap = BoundedDispatchCapture(shadow=shadow)
        res = cap.arm_and_capture(scene, timeout_ms=timeout_ms, auto_tap=auto_tap)
        out = res.to_json()
        out["ctor_evidence"] = resolve_ctor_candidates(res.rows)
        _emit(out)
        return 0 if res.result.startswith("SUCCESS") else 1
    sys.stdout.write(__doc__ or "")
    return 2


def _read_scene_via_bc_drive() -> Optional[int]:
    """Best-effort: reuse bc-drive's on-demand ``scene`` read for the menu guard."""
    try:
        bc_drive = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "bc-drive",
            "bc_drive.py",
        )
        out = subprocess.run(
            [sys.executable, bc_drive, "scene"],
            stdout=subprocess.PIPE,
            text=True,
            timeout=30,
            check=True,
        ).stdout
        return int(json.loads(out).get("scene"))
    except Exception as e:  # noqa: BLE001 -- guard degrades to "unknown" (refuses to arm)
        log.warning(
            "could not read scene via bc-drive (%s); guard will refuse to arm", e
        )
        return None


if __name__ == "__main__":
    raise SystemExit(main())
