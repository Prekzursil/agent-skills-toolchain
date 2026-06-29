#!/usr/bin/env python3
"""bc_drive.py -- on-demand Battle Cats driver (jp.co.ponos.battlecatsen, EN 15.4.1).

Deterministic, request-driven control of a LIVE Battle Cats instance on BlueStacks.
BC is a CUSTOM PONOS C++/GLES engine (NOT cocos2d-x).

State model (all reads are single NativeFunction calls / memory reads -- NEVER a
hook; a per-frame Interceptor on the render path crashes BC on scene changes):
  * scene  = app+0x2F24 (getScene): COARSE macro-state. ~100 for ALL out-of-battle
             menus; enum cluster 0x61..0x65 (97..101) per static analysis; flips on
             major transitions (e.g. entering battle -- not exercised here for safety).
  * prev   = app+0x2F20: secondary/previous state (written with scene by setter @0x65DD0F).
  * view   = app+0x2F08: an app UI field that VARIES over time/path (animation/scroll/
             transient). NOT a reliable screen id NOR a dependable change-signal -- the
             same screen yields different values over time, and 242 was observed on BOTH
             Title and Cat Base. -> identify screens by SCREENSHOT (the only ground truth).

Primitives:
  * metrics(): OS window px + BC drawable units + scale (BC-drawable -> device/adb px).
  * widgets(): tappable-rect map for a NAMED screen (device px + drawable back-proj).
  * tap(x,y) : OS-level `adb shell input tap` in DEVICE px (1920x1080 here).
  * screenshot: `adb exec-out screencap -p` (pick/verify tap targets visually).

Usage:
  python bc_drive.py scene
  python bc_drive.py view
  python bc_drive.py metrics
  python bc_drive.py touchinfo
  python bc_drive.py screenshot [out.png]
  python bc_drive.py tap  <devX> <devY>          # device px
  python bc_drive.py tapw <drawX> <drawY>        # BC drawable units -> device px
  python bc_drive.py widgets [ScreenName]        # Title|ChapterSelect|CatBase
  python bc_drive.py demo [ScreenName]           # tap forward -> prove view changed
  python bc_drive.py capture <ctorRVAhex> <ms>    # native NewButton-ctor capture (advanced)
"""
import json
import os
import struct
import subprocess
import sys
import time

import frida

ADB = os.environ.get("BC_ADB", "adb")
SERIAL = os.environ.get("BC_SERIAL", "127.0.0.1:5555")
PKG = "jp.co.ponos.battlecatsen"
AGENT_JS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bc_agent.js")

# Tappable widgets per screen, in DEVICE px @ 1920x1080. Screenshot-derived (visual
# inspection), NOT from the native node tree. (V) = confirmed to actuate live.
# `forward` = a safe forward-navigation button used by `demo`.
SCREENS = {
    "Title": {"forward": "Play", "widgets": {
        "Play":     {"cx": 955,  "cy": 665},   # (V) -> ChapterSelect
        "Settings": {"cx": 955,  "cy": 815},
        "ShowCode": {"cx": 120,  "cy": 40},
        "Mailbox":  {"cx": 1815, "cy": 1010},
    }},
    "ChapterSelect": {"forward": "ChapterCenter", "widgets": {
        "Close":         {"cx": 1815, "cy": 410},   # (V) -> Title
        "ChapterCenter": {"cx": 960,  "cy": 665},   # (V) -> CatBase (selected chapter)
        "ChapterLeft":   {"cx": 420,  "cy": 690},
        "ChapterRight":  {"cx": 1480, "cy": 690},
    }},
    "CatBase": {"forward": "Start", "widgets": {
        "Start":   {"cx": 355,  "cy": 315},   # (V) -> stage list
        "Upgrade": {"cx": 355,  "cy": 470},
        "Equip":   {"cx": 355,  "cy": 625},
        "Menu":    {"cx": 170,  "cy": 800},
        "Back":    {"cx": 75,   "cy": 930},   # (V) -> ChapterSelect
        "Store":   {"cx": 1190, "cy": 1035},
    }},
}
# The `view` field (app+0x2F08) is NOT a reliable screen id: it varies on the same
# screen over time and collides across screens (242 seen on BOTH Title and Cat Base),
# so there is no view->screen mapping. Identify the current screen by SCREENSHOT and
# pass the name explicitly to `widgets`/`demo` (e.g. `widgets CatBase`).
VIEW_TO_SCREEN = {}


def adb(*args, binary=False):
    cmd = [ADB, "-s", SERIAL] + list(args)
    if binary:
        return subprocess.run(cmd, stdout=subprocess.PIPE, check=True).stdout
    return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          text=True, check=True).stdout.strip()


def get_pid():
    out = adb("shell", "pidof", PKG)
    if not out:
        raise RuntimeError(f"{PKG} not running (pidof empty). Launch BC first.")
    return int(out.split()[0])


def get_device():
    try:
        return frida.get_usb_device(timeout=8)
    except Exception:
        return frida.get_device_manager().add_remote_device("127.0.0.1:27042")


class BCDriver:
    """On-demand session: attach, run rpc, detach. No persistent hook in the game."""

    def __init__(self):
        self.pid = get_pid()
        self.dev = get_device()
        self.session = None
        self.script = None

    def __enter__(self):
        self.session = self.dev.attach(self.pid)
        with open(AGENT_JS, "r", encoding="utf-8") as f:
            self.script = self.session.create_script(f.read())
        self.script.load()
        return self

    def __exit__(self, *exc):
        try:
            if self.session:
                self.session.detach()
        except Exception:
            pass

    @property
    def rpc(self):
        return self.script.exports_sync


def tap(dev_x, dev_y):
    """OS-level tap in device px. Reliable regardless of engine internals."""
    adb("shell", "input", "tap", str(int(dev_x)), str(int(dev_y)))
    return {"tapped_device_px": [int(dev_x), int(dev_y)]}


def screenshot(out_path):
    with open(out_path, "wb") as f:
        f.write(adb("exec-out", "screencap", "-p", binary=True))
    return out_path


def screencap_raw():
    """Raw framebuffer (no PNG): (w, h, pixel_bytes). Pixels are the trailing w*h*4
    bytes -- robust to header-size differences across Android versions."""
    data = adb("exec-out", "screencap", binary=True)
    w, h = struct.unpack("<II", data[:8])
    return w, h, data[len(data) - w * h * 4:]


def frame_diff(a, b, step=4001, tol=24):
    """Fraction of sampled pixels differing beyond `tol` per channel -- an OBJECTIVE
    'the screen changed' signal independent of any engine state field."""
    pa, pb = a[2], b[2]
    n = min(len(pa), len(pb))
    diff = total = 0
    for i in range(0, n, step):
        total += 1
        if abs(pa[i] - pb[i]) > tol:
            diff += 1
    return diff / total if total else 0.0


def infer_screen(view):
    return VIEW_TO_SCREEN.get(view)


def cmd_scene():
    with BCDriver() as d:
        print(json.dumps(d.rpc.scene(), indent=2))


def cmd_view():
    with BCDriver() as d:
        s = d.rpc.scene()
    print(json.dumps({"view": s.get("view"), "scene_macro": s.get("scene"),
                      "inferred_screen": infer_screen(s.get("view")),
                      "note": "view is path-dependent; confirm screen via screenshot"}, indent=2))


def cmd_metrics():
    with BCDriver() as d:
        print(json.dumps(d.rpc.metrics(), indent=2))


def cmd_touchinfo():
    with BCDriver() as d:
        print(json.dumps(d.rpc.touch_info(), indent=2))


def cmd_info():
    with BCDriver() as d:
        print(json.dumps(d.rpc.info(), indent=2))


def cmd_screenshot(out):
    out = out or os.path.join(os.path.dirname(AGENT_JS), "bc_screen.png")
    print(f"saved {screenshot(out)}")


def cmd_tap(x, y):
    print(json.dumps(tap(x, y), indent=2))


def cmd_tapw(dx, dy):
    """Tap using BC drawable-unit coordinates, converted to device px via metrics."""
    with BCDriver() as d:
        m = d.rpc.metrics()
    px, py = round(dx * m["scaleX"]), round(dy * m["scaleY"])
    print(json.dumps({"drawable": [dx, dy], "scale": [m["scaleX"], m["scaleY"]], **tap(px, py)}, indent=2))


def cmd_widgets(screen):
    with BCDriver() as d:
        s = d.rpc.scene()
        m = d.rpc.metrics()
    if not screen:
        screen = infer_screen(s.get("view"))
    out = {"requested_screen": screen, "scene_macro": s.get("scene"), "view": s.get("view"),
           "device_px": [m["windowW"], m["windowH"]], "drawable_units": [m["drawableW"], m["drawableH"]],
           "scale_drawable_to_device": [m["scaleX"], m["scaleY"]],
           "source": "screenshot-derived (device px); validated by live taps"}
    if screen and screen in SCREENS:
        out["widgets"] = {
            name: {"device_px": [r["cx"], r["cy"]],
                   "drawable": [round(r["cx"] / m["scaleX"]), round(r["cy"] / m["scaleY"])]}
            for name, r in SCREENS[screen]["widgets"].items()}
    else:
        out["widgets"] = None
        out["available_screens"] = list(SCREENS)
        out["note"] = "screen not identified; `screenshot` then pass a name, e.g. `widgets Title`"
    print(json.dumps(out, indent=2))


def cmd_demo(screen):
    """End-to-end proof: read state -> screenshot -> tap forward -> screenshot ->
    OBJECTIVELY confirm the screen changed via framebuffer pixel-diff (the reliable
    signal), and report scene/view (view labeled unreliable)."""
    t = {"steps": []}
    out_dir = os.path.dirname(AGENT_JS)
    before_png = os.path.join(out_dir, "bc_demo_before.png")
    after_png = os.path.join(out_dir, "bc_demo_after.png")
    with BCDriver() as d:
        t["metrics"] = d.rpc.metrics()
        before = d.rpc.scene()
        t["state_before"] = before
        if not screen:
            screen = infer_screen(before.get("view"))
        if not screen or screen not in SCREENS:
            t["error"] = (f"screen unknown (view={before.get('view')}); run `screenshot`, "
                          f"then `demo <ScreenName>` from {list(SCREENS)}")
            print(json.dumps(t, indent=2))
            return
        btn = SCREENS[screen]["forward"]
        r = SCREENS[screen]["widgets"][btn]
        fb = screencap_raw()
        screenshot(before_png)
        t["steps"].append(f"screen={screen} scene={before.get('scene')} view={before.get('view')}")
        t["steps"].append(f"tap {btn} @ device ({r['cx']},{r['cy']})")
        tap(r["cx"], r["cy"])
        frac = 0.0
        for _ in range(15):
            time.sleep(0.3)
            frac = frame_diff(fb, screencap_raw())
            if frac > 0.10:
                break
        after = d.rpc.scene()
        screenshot(after_png)
        t["state_after"] = after
        t["screen_changed"] = frac > 0.10
        t["screen_changed_pixel_frac"] = round(frac, 3)
        t["view_changed_unreliable"] = after.get("view") != before.get("view")
        t["screenshots"] = {"before": before_png, "after": after_png}
        t["result"] = ("SUCCESS:bc-drive-demo screen changed via tap"
                       if t["screen_changed"] else "FAILED:bc-drive-demo no screen change detected")
        t["steps"].append(f"{t['result']} pixel_diff={round(frac, 3)} "
                          f"scene {before.get('scene')}->{after.get('scene')} "
                          f"view {before.get('view')}->{after.get('view')}")
    print(json.dumps(t, indent=2))


def cmd_capture(ctor_rva_hex, ms):
    """Advanced/best-effort: briefly hook a NewButton-ctor RVA, navigate, then dump.
    Trigger navigation (a tap) during the window. The NewButton ctor RVA is not yet
    resolved (game C++ symbols are stripped; RTTI in .rodata names the class
    `NewButton` + createXxxButton factories). Pass the RVA once resolved via xref RE."""
    rva = int(ctor_rva_hex, 16)
    with BCDriver() as d:
        start = d.rpc.start_capture(rva, 0x80)
        print(json.dumps({"start": start}, indent=2))
        if not start.get("ok"):
            return
        print(f"[*] capturing {ms} ms -- navigate now ...", file=sys.stderr)
        time.sleep(int(ms) / 1000.0)
        print(json.dumps(d.rpc.stop_capture(), indent=2))


CMDS = {
    "scene": lambda a: cmd_scene(), "view": lambda a: cmd_view(),
    "metrics": lambda a: cmd_metrics(), "touchinfo": lambda a: cmd_touchinfo(),
    "info": lambda a: cmd_info(),
    "screenshot": lambda a: cmd_screenshot(a[0] if a else None),
    "tap": lambda a: cmd_tap(int(a[0]), int(a[1])),
    "tapw": lambda a: cmd_tapw(float(a[0]), float(a[1])),
    "widgets": lambda a: cmd_widgets(a[0] if a else None),
    "demo": lambda a: cmd_demo(a[0] if a else None),
    "capture": lambda a: cmd_capture(a[0], a[1]),
}


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in CMDS:
        print(__doc__)
        return
    CMDS[sys.argv[1]](sys.argv[2:])


if __name__ == "__main__":
    main()
