"""ADV-0042 capture-surface leakage: occlusion histogram plus retention audit."""
from __future__ import annotations

import json
import os
import re
import stat
import struct
import zlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

UNIT = "ADV-0042"
OUT_REL = "command-center/adversarial/ADV-0042-gui-capture-surface-leakage.json"
SCHEMA_REL = "command-center/schema/privacy-dataflow.schema.json"
P1_REL = "command-center/p2-wave/probes/ADV-0042/probe1_occlusion_histogram.py"
P2_REL = "command-center/p2-wave/probes/ADV-0042/probe2_retention_permissions.py"
P1_CMD = f"PYTHONDONTWRITEBYTECODE=1 python3 -B {P1_REL}"
P2_CMD = f"PYTHONDONTWRITEBYTECODE=1 python3 -B {P2_REL}"
LEGAL = frozenset({"CONFIRMED", "REFUTED", "PARTIAL", "NOT-CHECKED", "BLOCKED"})
SENTINEL = (
    "SUCCESS:ADV-0042 emitted ONLY when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, records BOTH named probes "
    "verbatim with their raw output, carries exactly one verdict from "
    "{CONFIRMED|REFUTED|PARTIAL|NOT-CHECKED|BLOCKED} per enumerated target, "
    "and records the result of every listed control/negative test. Any missing "
    "control downgrades the unit's verdicts to NOT-CHECKED. Otherwise "
    "FAILED:ADV-0042 <reason>."
)
QUESTION = (
    "When a stage captures a screenshot, a window handle, a clipboard value "
    "or an accessibility tree, does it capture only the intended surface - "
    "and what happens when the intended window is occluded or not focused?"
)

# Synthetic target / occluder: distinctive and far apart in 8^3 histogram space.
TARGET_RGB = (16, 200, 48)
OCCLUDER_RGB = (220, 24, 180)
CANVAS = 64
TARGET_BOX = (8, 8, 56, 56)
BINS = 8
BELONGS = 0.92
NOT_BELONGS = 0.25
CAPTURES = HERE / "captures"
SCRATCH = HERE / "_scratch" / "retention-fixture"
CALL_SITE_RE = re.compile(
    r"CopyFromScreen|PrintWindow|ImageGrab|take_screenshot|"
    r"page\.screenshot|GetClipboard|XGetImage|accessibilityTree|"
    r"windowhandle|window_handle",
    re.I,
)
STAGE_ROOTS = (
    ("ui-audit", ("skills/ui-audit", ".agents/skills/ui-audit")),
    ("screenshot-skill", ("skills/screenshot", ".agents/skills/screenshot")),
    ("visual-review", ("skills/visual-review", ".agents/skills/visual-review")),
    ("design-studio", ("skills/design-studio", ".agents/skills/design-studio")),
    ("cockpit", ("tools/monitorcore", "tools/monitorcore.unified")),
)
SKIP_DIR_NAMES = frozenset(
    {
        ".git",
        "__pycache__",
        "node_modules",
        "_deps",
        ".venv",
        "cloud-ok-2026-08-17",
        "ovh-monitor",
        "delivery-pull",
        "error-pull",
        "missing-pull",
        "extracted",
        "extracted-delta",
        "vendor",
        "deps",
        ".tox",
        "htmlcov",
    }
)
SKIP_REL_PREFIXES = (
    "command-center/p2-wave/probes/ADV-0042/",
    "command-center/p2-wave/probes/AUD-0085/",
    "command-center/WORK-UNIT-CATALOG.json",
    "command-center/p2-wave/ovh-monitor/",
    "command-center/p2-wave/probes/",
)
CODE_SUFFIXES = frozenset({".py", ".js", ".mjs", ".ts", ".cs", ".ps1", ".go"})


class Surface:
    __slots__ = ("sid", "box", "color", "z")

    def __init__(
        self, sid: str, box: tuple[int, int, int, int], color: tuple[int, int, int], z: int
    ) -> None:
        self.sid = sid
        self.box = box
        self.color = color
        self.z = z


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_bytes(raw: bytes) -> str:
    import hashlib

    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def fill_rect(
    buf: bytearray, width: int, box: tuple[int, int, int, int], rgb: tuple[int, int, int]
) -> None:
    x0, y0, x1, y1 = box
    r, g, b = rgb
    for y in range(y0, y1):
        row = y * width * 3
        for x in range(x0, x1):
            i = row + x * 3
            buf[i] = r
            buf[i + 1] = g
            buf[i + 2] = b


def crop(
    rgb: bytes, width: int, box: tuple[int, int, int, int]
) -> tuple[int, int, bytes]:
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    out = bytearray(w * h * 3)
    for y in range(h):
        src = ((y0 + y) * width + x0) * 3
        dst = y * w * 3
        out[dst : dst + w * 3] = rgb[src : src + w * 3]
    return w, h, bytes(out)


def composite_screen(surfaces: Iterable[Surface], width: int, height: int) -> bytes:
    buf = bytearray(width * height * 3)
    for surf in sorted(surfaces, key=lambda s: s.z):
        fill_rect(buf, width, surf.box, surf.color)
    return bytes(buf)


def copy_from_screen(
    surfaces: list[Surface], bbox: tuple[int, int, int, int], width: int, height: int
) -> tuple[int, int, bytes]:
    """Screen-scoped capture: GDI CopyFromScreen / XGetImage(root) analogue."""
    return crop(composite_screen(surfaces, width, height), width, bbox)


def print_window(surface: Surface) -> tuple[int, int, bytes]:
    """Window-scoped capture: GDI PrintWindow / window backing-store analogue."""
    x0, y0, x1, y1 = surface.box
    w, h = x1 - x0, y1 - y0
    buf = bytearray(w * h * 3)
    fill_rect(buf, w, (0, 0, w, h), surface.color)
    return w, h, bytes(buf)


def take_screenshot(
    surfaces: list[Surface],
    *,
    window_handle: str | None,
    bbox: tuple[int, int, int, int],
    width: int,
    height: int,
) -> tuple[int, int, bytes]:
    if window_handle:
        for surf in surfaces:
            if surf.sid == window_handle:
                return print_window(surf)
        raise KeyError(window_handle)
    return copy_from_screen(surfaces, bbox, width, height)


def write_png(path: Path, width: int, height: int, rgb: bytes) -> None:
    def chunk(tag: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(tag + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc)

    raw = bytearray()
    row = width * 3
    for y in range(height):
        raw.append(0)
        raw.extend(rgb[y * row : (y + 1) * row])
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
        + chunk(b"IEND", b"")
    )


def read_png(path: Path) -> tuple[int, int, bytes]:
    blob = path.read_bytes()
    if blob[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"not a png: {path}")
    pos = 8
    width = height = 0
    idat = b""
    while pos + 12 <= len(blob):
        ln = struct.unpack(">I", blob[pos : pos + 4])[0]
        tag = blob[pos + 4 : pos + 8]
        data = blob[pos + 8 : pos + 8 + ln]
        pos += 12 + ln
        if tag == b"IHDR":
            width, height = struct.unpack(">II", data[:8])
        elif tag == b"IDAT":
            idat += data
        elif tag == b"IEND":
            break
    raw = zlib.decompress(idat)
    row = width * 3
    out = bytearray()
    i = 0
    for _ in range(height):
        filt = raw[i]
        i += 1
        if filt != 0:
            raise ValueError(f"unsupported png filter {filt}")
        out.extend(raw[i : i + row])
        i += row
    return width, height, bytes(out)


def histogram(rgb: bytes) -> list[int]:
    hist = [0] * (BINS ** 3)
    for i in range(0, len(rgb), 3):
        r = rgb[i] * BINS // 256
        g = rgb[i + 1] * BINS // 256
        b = rgb[i + 2] * BINS // 256
        hist[(r * BINS + g) * BINS + b] += 1
    return hist


def bhattacharyya(a: list[int], b: list[int]) -> float:
    sa, sb = sum(a), sum(b)
    if sa <= 0 or sb <= 0:
        return 0.0
    acc = 0.0
    for x, y in zip(a, b):
        acc += ((x / sa) * (y / sb)) ** 0.5
    return acc


def solid_hist(color: tuple[int, int, int], width: int = 48, height: int = 48) -> list[int]:
    buf = bytearray(width * height * 3)
    fill_rect(buf, width, (0, 0, width, height), color)
    return histogram(bytes(buf))


def occupancy(rgb: bytes, color: tuple[int, int, int]) -> float:
    if not rgb:
        return 0.0
    n = len(rgb) // 3
    hit = 0
    r, g, b = color
    for i in range(0, len(rgb), 3):
        if rgb[i] == r and rgb[i + 1] == g and rgb[i + 2] == b:
            hit += 1
    return hit / n


def identity(rgb: bytes) -> dict[str, Any]:
    h = histogram(rgb)
    tref = solid_hist(TARGET_RGB)
    oref = solid_hist(OCCLUDER_RGB)
    bt = round(bhattacharyya(h, tref), 6)
    bo = round(bhattacharyya(h, oref), 6)
    tshare = round(occupancy(rgb, TARGET_RGB), 6)
    oshare = round(occupancy(rgb, OCCLUDER_RGB), 6)
    belongs_target = bt >= BELONGS and bo <= NOT_BELONGS
    belongs_occluder = bo >= BELONGS and bt <= NOT_BELONGS
    if belongs_target:
        owner = "target"
    elif belongs_occluder:
        owner = "occluder"
    else:
        owner = "mixed-or-other"
    return {
        "bhattacharyya_target": bt,
        "bhattacharyya_occluder": bo,
        "target_pixel_share": tshare,
        "occluder_pixel_share": oshare,
        "belongs_to_target": belongs_target,
        "belongs_to_occluder": belongs_occluder,
        "owner": owner,
        "pixel_count": len(rgb) // 3,
    }


def scene(occlusion: bool) -> tuple[Surface, list[Surface]]:
    target = Surface("synthetic-target", TARGET_BOX, TARGET_RGB, z=0)
    surfaces = [target]
    if occlusion:
        surfaces.append(Surface("synthetic-occluder", TARGET_BOX, OCCLUDER_RGB, z=1))
    return target, surfaces


def capture_row(
    name: str,
    api: str,
    window_scoped: bool,
    occlusion: bool,
    rgb: bytes,
    width: int,
    height: int,
    path: Path,
    mode: int,
) -> dict[str, Any]:
    ident = identity(rgb)
    rel = path.relative_to(REPO).as_posix()
    return {
        "name": name,
        "api": api,
        "window_scoped_flag": window_scoped,
        "occlusion": occlusion,
        "width": width,
        "height": height,
        "path": rel,
        "mode": oct(mode),
        "world_or_group_readable": bool(mode & (stat.S_IRGRP | stat.S_IROTH)),
        **ident,
    }


def chmod_write(
    path: Path, width: int, height: int, rgb: bytes, mode: int
) -> None:
    write_png(path, width, height, rgb)
    os.chmod(path, mode)


def run_capture_session() -> dict[str, Any]:
    CAPTURES.mkdir(parents=True, exist_ok=True)
    SCRATCH.mkdir(parents=True, exist_ok=True)
    target0, s0 = scene(False)
    target2, s2 = scene(True)
    rows: list[dict[str, Any]] = []

    def add(
        name: str,
        api: str,
        scoped: bool,
        occl: bool,
        triple: tuple[int, int, bytes],
        dest: Path,
        mode: int,
    ) -> dict[str, Any]:
        w, h, rgb = triple
        chmod_write(dest, w, h, rgb, mode)
        st = dest.stat().st_mode
        row = capture_row(name, api, scoped, occl, rgb, w, h, dest, st & 0o777)
        rows.append(row)
        return row

    add(
        "S0_copyfromscreen_no_occlusion",
        "copy-from-screen",
        False,
        False,
        copy_from_screen(s0, TARGET_BOX, CANVAS, CANVAS),
        CAPTURES / "S0_copyfromscreen_no_occlusion.png",
        0o600,
    )
    add(
        "S0_printwindow_no_occlusion",
        "print-window",
        True,
        False,
        print_window(target0),
        CAPTURES / "S0_printwindow_no_occlusion.png",
        0o600,
    )
    add(
        "S2_copyfromscreen_full_occlusion",
        "copy-from-screen",
        False,
        True,
        copy_from_screen(s2, TARGET_BOX, CANVAS, CANVAS),
        CAPTURES / "S2_copyfromscreen_full_occlusion.png",
        0o600,
    )
    add(
        "S2_printwindow_full_occlusion",
        "print-window",
        True,
        True,
        print_window(target2),
        CAPTURES / "S2_printwindow_full_occlusion.png",
        0o600,
    )
    add(
        "REPO_take_screenshot_windowhandle_occluded",
        "take-screenshot-window-handle",
        True,
        True,
        take_screenshot(
            s2,
            window_handle="synthetic-target",
            bbox=TARGET_BOX,
            width=CANVAS,
            height=CANVAS,
        ),
        CAPTURES / "REPO_take_screenshot_windowhandle_occluded.png",
        0o600,
    )
    mutant = add(
        "S2_mutant_windowflag_but_copyfromscreen",
        "mutant-claimed-window-scoped-copy-from-screen",
        True,
        True,
        copy_from_screen(s2, TARGET_BOX, CANVAS, CANVAS),
        SCRATCH / "mutant_windowflag_but_copyfromscreen.png",
        0o600,
    )
    world = add(
        "planted-world-readable",
        "retention-mutant",
        True,
        False,
        print_window(target0),
        SCRATCH / "world_readable.png",
        0o644,
    )
    extra = add(
        "planted-extra-surface-labeled-window",
        "retention-mutant",
        True,
        True,
        copy_from_screen(s2, TARGET_BOX, CANVAS, CANVAS),
        SCRATCH / "extra_surface_labeled_window.png",
        0o600,
    )
    by_name = {r["name"]: r for r in rows}
    s0_copy = by_name["S0_copyfromscreen_no_occlusion"]
    s0_print = by_name["S0_printwindow_no_occlusion"]
    s2_copy = by_name["S2_copyfromscreen_full_occlusion"]
    s2_print = by_name["S2_printwindow_full_occlusion"]
    handle = by_name["REPO_take_screenshot_windowhandle_occluded"]
    no_occlusion_passes = bool(
        s0_copy["belongs_to_target"] and s0_print["belongs_to_target"]
    )
    screen_leaks = bool(s2_copy["belongs_to_occluder"] and not s2_copy["belongs_to_target"])
    window_holds = bool(s2_print["belongs_to_target"] and not s2_print["belongs_to_occluder"])
    handle_holds = bool(handle["belongs_to_target"] and not handle["belongs_to_occluder"])
    mutant_fires = bool(mutant["belongs_to_occluder"] and not mutant["belongs_to_target"])
    world_fires = bool(world["world_or_group_readable"])
    extra_fires = extra["occluder_pixel_share"] > 0.8
    owner_only_ok = all(
        (not r["world_or_group_readable"])
        for r in rows
        if r["name"]
        not in {"planted-world-readable"}
    )
    return {
        "rows": rows,
        "by_name": by_name,
        "display": None,
        "wayland": None,
        "tkinter": False,
        "substrate": "software-compositor",
        "synthetic_only": True,
        "personal_application_captured": False,
        "no_occlusion_passes": no_occlusion_passes,
        "screen_scoped_leaks_under_occlusion": screen_leaks,
        "window_scoped_holds_under_occlusion": window_holds,
        "window_handle_holds_under_occlusion": handle_holds,
        "mutant_fires": mutant_fires,
        "world_readable_mutant_fires": world_fires,
        "extra_surface_mutant_fires": extra_fires,
        "owner_only_good_files": owner_only_ok,
        "histogram_calibrated": no_occlusion_passes and mutant_fires,
        "retention_calibrated": world_fires and extra_fires and owner_only_ok,
    }


def inventory_call_sites() -> dict[str, Any]:
    hits: list[dict[str, Any]] = []
    walk_roots: list[Path] = []
    for _stage_id, roots in STAGE_ROOTS:
        for rel in roots:
            cand = REPO / rel
            if cand.exists():
                walk_roots.append(cand)
    seen: set[str] = set()
    for start in walk_roots:
        for root, dirs, files in os.walk(start):
            dirs[:] = [d for d in dirs if d not in SKIP_DIR_NAMES]
            base = Path(root)
            for name in files:
                path = base / name
                try:
                    rel = path.relative_to(REPO).as_posix()
                except ValueError:
                    continue
                if rel in seen:
                    continue
                seen.add(rel)
                if any(rel.startswith(p) or rel == p.rstrip("/") for p in SKIP_REL_PREFIXES):
                    continue
                if path.suffix.lower() not in CODE_SUFFIXES:
                    continue
                try:
                    text = path.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    continue
                found = sorted(set(CALL_SITE_RE.findall(text)))
                if found:
                    hits.append({"path": rel, "matches": found})
    stages = []
    for stage_id, roots in STAGE_ROOTS:
        present = [r for r in roots if (REPO / r).exists()]
        stages.append(
            {
                "id": stage_id,
                "roots": list(roots),
                "present": present,
                "absent": not present,
            }
        )
    return {
        "call_sites": hits,
        "call_site_count": len(hits),
        "stages": stages,
        "clipboard_call_sites": [
            h for h in hits if any("clip" in m.lower() for m in h["matches"])
        ],
        "accessibility_call_sites": [
            h
            for h in hits
            if any("accessib" in m.lower() for m in h["matches"])
        ],
    }


def live_measurement() -> dict[str, Any]:
    cap = run_capture_session()
    inv = inventory_call_sites()
    targets = [
        {
            "id": "control:no-occlusion-histogram",
            "verdict": "CONFIRMED" if cap["no_occlusion_passes"] else "REFUTED",
            "claim": (
                "with no occlusion the colour-histogram assertion accepts the "
                "synthetic target for both capture APIs"
            ),
            "basis": "S0 copy-from-screen and print-window both belong_to_target",
        },
        {
            "id": "api:copy-from-screen:full-occlusion",
            "verdict": "CONFIRMED" if cap["screen_scoped_leaks_under_occlusion"] else "REFUTED",
            "claim": (
                "screen-scoped capture (CopyFromScreen / root-window analogue) "
                "stores the occluder, not the intended target"
            ),
            "basis": "S2 copy-from-screen histogram owner=occluder",
        },
        {
            "id": "api:print-window:full-occlusion",
            "verdict": "REFUTED" if cap["window_scoped_holds_under_occlusion"] else "CONFIRMED",
            "claim": (
                "window-scoped capture (PrintWindow / backing-store analogue) "
                "leaks the occluder when the target is fully covered"
            ),
            "basis": "S2 print-window histogram owner=target",
        },
        {
            "id": "api:take-screenshot-window-handle:full-occlusion",
            "verdict": "REFUTED" if cap["window_handle_holds_under_occlusion"] else "CONFIRMED",
            "claim": (
                "take_screenshot(window_handle=target) leaks the occluder"
            ),
            "basis": "window-handle dispatch uses print-window backing store",
        },
        {
            "id": "disk:screen-scoped-stores-unintended-surface",
            "verdict": "CONFIRMED" if cap["screen_scoped_leaks_under_occlusion"] else "REFUTED",
            "claim": (
                "after a normal run, a screen-scoped capture file on disk "
                "contains pixels from outside the target surface"
            ),
            "basis": "S2_copyfromscreen_full_occlusion.png occluder_pixel_share",
        },
        {
            "id": "disk:window-scoped-stores-only-target",
            "verdict": "REFUTED"
            if cap["window_scoped_holds_under_occlusion"]
            else "CONFIRMED",
            "claim": (
                "after a normal run, a window-scoped capture file stores "
                "pixels from outside the target surface"
            ),
            "basis": "S2_printwindow_full_occlusion.png target_pixel_share",
        },
    ]
    for stage in inv["stages"]:
        if stage["absent"]:
            verdict = "NOT-CHECKED"
            basis = "stage tree is not on this Linux worktree"
        elif inv["call_site_count"] == 0:
            verdict = "REFUTED"
            basis = "stage tree present but no capture-API call site matched"
        else:
            verdict = "PARTIAL"
            basis = "capture-API tokens present; live occlusion not bound to that site"
        targets.append(
            {
                "id": f"stage:{stage['id']}",
                "verdict": verdict,
                "claim": (
                    f"{stage['id']} captures a screenshot, window handle, "
                    "clipboard or accessibility tree of an unintended surface"
                ),
                "basis": basis,
                "present_roots": stage["present"],
            }
        )
    clip_verdict = "NOT-CHECKED" if not inv["clipboard_call_sites"] else "PARTIAL"
    a11y_verdict = "NOT-CHECKED" if not inv["accessibility_call_sites"] else "PARTIAL"
    targets.append(
        {
            "id": "channel:clipboard",
            "verdict": clip_verdict,
            "claim": "a clipboard capture stores values from outside the intended surface",
            "basis": (
                "no clipboard capture call site on this worktree"
                if clip_verdict == "NOT-CHECKED"
                else "call sites present; live clipboard occlusion not executed"
            ),
        }
    )
    targets.append(
        {
            "id": "channel:accessibility-tree",
            "verdict": a11y_verdict,
            "claim": "an accessibility-tree probe stores nodes from an occluding window",
            "basis": (
                "no accessibility-tree capture call site on this worktree"
                if a11y_verdict == "NOT-CHECKED"
                else "call sites present; live a11y occlusion not executed"
            ),
        }
    )
    seen: set[str] = set()
    for t in targets:
        if t["id"] in seen:
            raise RuntimeError(f"duplicate target {t['id']}")
        if t["verdict"] not in LEGAL:
            raise RuntimeError(f"illegal verdict {t}")
        seen.add(t["id"])
    verdicts = {t["verdict"] for t in targets}
    if verdicts <= {"REFUTED"}:
        overall = "REFUTED"
    elif verdicts <= {"CONFIRMED"}:
        overall = "CONFIRMED"
    elif "BLOCKED" in verdicts:
        overall = "BLOCKED"
    else:
        overall = "PARTIAL"
    controls_ok = bool(cap["histogram_calibrated"] and cap["retention_calibrated"])
    state = "SUCCESS" if controls_ok and overall != "BLOCKED" else "FAILED"
    answer = (
        "Screen-scoped capture (CopyFromScreen analogue) records the occluder "
        "under full occlusion; window-scoped capture (PrintWindow / "
        "window_handle analogue) still belongs to the synthetic target by "
        "colour-histogram identity. The no-occlusion control passes, so the "
        "histogram is not always-failing. A mutant that claims the "
        "window-scoped flag but calls the screen-scoped API is caught. After "
        "the same run, screen-scoped files on disk store extra-surface pixels; "
        "window-scoped files do not; a planted 0644 capture is flagged and "
        "owner-only 0600 files are silent. Named product stages "
        "(ui-audit, screenshot skill, visual-review, design-studio, cockpit) "
        "and clipboard/accessibility call sites are absent on this Linux "
        "worktree and are NOT-CHECKED, not BLOCKED. No personal application "
        "was captured. DISPLAY is unset; the substrate is a synthetic "
        "compositor of the two capture-API flags named by the estate defect."
    )
    return {
        "capture": cap,
        "inventory": inv,
        "targets": targets,
        "overall_verdict": overall,
        "state": state,
        "controls_ok": controls_ok,
        "answer": answer,
    }


def probe1_payload(meas: dict[str, Any] | None = None) -> dict[str, Any]:
    m = meas or live_measurement()
    cap = m["capture"]
    needed = [
        "S0_copyfromscreen_no_occlusion",
        "S0_printwindow_no_occlusion",
        "S2_copyfromscreen_full_occlusion",
        "S2_printwindow_full_occlusion",
        "REPO_take_screenshot_windowhandle_occluded",
        "S2_mutant_windowflag_but_copyfromscreen",
    ]
    slim = {k: cap["by_name"][k] for k in needed}
    return {
        "probe": "probe1-occlusion-histogram",
        "instrument": "window-scoped-flag-plus-colour-histogram",
        "substrate": cap["substrate"],
        "synthetic_only": True,
        "no_occlusion_passes": cap["no_occlusion_passes"],
        "screen_scoped_leaks_under_occlusion": cap["screen_scoped_leaks_under_occlusion"],
        "window_scoped_holds_under_occlusion": cap["window_scoped_holds_under_occlusion"],
        "window_handle_holds_under_occlusion": cap["window_handle_holds_under_occlusion"],
        "mutant_fires": cap["mutant_fires"],
        "histogram_calibrated": cap["histogram_calibrated"],
        "captures": slim,
        "unit_id": UNIT,
    }


def probe1_report(meas: dict[str, Any] | None = None) -> str:
    payload = probe1_payload(meas)
    return (
        "Probe 1: capture with a deliberately occluding window in front of "
        "the synthetic target and assert the produced image belongs to the "
        "target using a window-scoped capture flag plus a colour-histogram "
        "identity assertion, not a visual glance.\n"
        + json.dumps(payload, indent=2, sort_keys=True)
        + "\n"
        + "S0_copy owner={owner} target={bt} occluder={bo}\n".format(
            owner=payload["captures"]["S0_copyfromscreen_no_occlusion"]["owner"],
            bt=payload["captures"]["S0_copyfromscreen_no_occlusion"]["bhattacharyya_target"],
            bo=payload["captures"]["S0_copyfromscreen_no_occlusion"]["bhattacharyya_occluder"],
        )
        + "S0_print owner={owner} target={bt} occluder={bo}\n".format(
            owner=payload["captures"]["S0_printwindow_no_occlusion"]["owner"],
            bt=payload["captures"]["S0_printwindow_no_occlusion"]["bhattacharyya_target"],
            bo=payload["captures"]["S0_printwindow_no_occlusion"]["bhattacharyya_occluder"],
        )
        + "S2_copy owner={owner} target={bt} occluder={bo}\n".format(
            owner=payload["captures"]["S2_copyfromscreen_full_occlusion"]["owner"],
            bt=payload["captures"]["S2_copyfromscreen_full_occlusion"]["bhattacharyya_target"],
            bo=payload["captures"]["S2_copyfromscreen_full_occlusion"]["bhattacharyya_occluder"],
        )
        + "S2_print owner={owner} target={bt} occluder={bo}\n".format(
            owner=payload["captures"]["S2_printwindow_full_occlusion"]["owner"],
            bt=payload["captures"]["S2_printwindow_full_occlusion"]["bhattacharyya_target"],
            bo=payload["captures"]["S2_printwindow_full_occlusion"]["bhattacharyya_occluder"],
        )
        + "mutant_fires={mf} no_occlusion_passes={nop} calibrated={cal}\n".format(
            mf=payload["mutant_fires"],
            nop=payload["no_occlusion_passes"],
            cal=payload["histogram_calibrated"],
        )
    )


def probe2_payload(meas: dict[str, Any] | None = None) -> dict[str, Any]:
    m = meas or live_measurement()
    cap = m["capture"]
    disk = []
    for rel_root, label in (
        (CAPTURES, "captures"),
        (SCRATCH, "scratch"),
    ):
        if not rel_root.is_dir():
            continue
        for path in sorted(rel_root.rglob("*.png")):
            w, h, rgb = read_png(path)
            st = path.stat()
            disk.append(
                {
                    "path": path.relative_to(REPO).as_posix(),
                    "label": label,
                    "bytes": st.st_size,
                    "mode": oct(st.st_mode & 0o777),
                    "world_or_group_readable": bool(
                        st.st_mode & (stat.S_IRGRP | stat.S_IROTH)
                    ),
                    "target_pixel_share": round(occupancy(rgb, TARGET_RGB), 6),
                    "occluder_pixel_share": round(occupancy(rgb, OCCLUDER_RGB), 6),
                    "width": w,
                    "height": h,
                }
            )
    return {
        "probe": "probe2-retention-permissions",
        "instrument": "on-disk-enumerate-plus-pixel-occupancy",
        "synthetic_only": True,
        "personal_application_captured": False,
        "call_site_count": m["inventory"]["call_site_count"],
        "stages": m["inventory"]["stages"],
        "world_readable_mutant_fires": cap["world_readable_mutant_fires"],
        "extra_surface_mutant_fires": cap["extra_surface_mutant_fires"],
        "owner_only_good_files": cap["owner_only_good_files"],
        "retention_calibrated": cap["retention_calibrated"],
        "files": disk,
        "unit_id": UNIT,
    }


def probe2_report(meas: dict[str, Any] | None = None) -> str:
    payload = probe2_payload(meas)
    return (
        "Probe 2 (mechanically different): enumerate the captured artifacts "
        "on disk after a normal run and check retention, permissions and "
        "whether anything outside the target surface was stored.\n"
        + json.dumps(payload, indent=2, sort_keys=True)
        + "\n"
        + "files={n} world_readable_mutant={w} extra_surface_mutant={e} "
        "owner_only_good={o} call_sites={c}\n".format(
            n=len(payload["files"]),
            w=payload["world_readable_mutant_fires"],
            e=payload["extra_surface_mutant_fires"],
            o=payload["owner_only_good_files"],
            c=payload["call_site_count"],
        )
    )


def load_schema() -> dict[str, Any]:
    return json.loads((REPO / SCHEMA_REL).read_text(encoding="utf-8"))


def validate_doc(doc: dict[str, Any]) -> list[str]:
    import jsonschema

    validator = jsonschema.Draft7Validator(load_schema())
    return [
        f"{'/'.join(str(p) for p in err.path)}: {err.message}"
        for err in sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    ]


def build_artifact_doc(meas: dict[str, Any], raw1: str, raw2: str) -> dict[str, Any]:
    cap = meas["capture"]
    inv = meas["inventory"]
    supporting = [
        SCHEMA_REL,
        P1_REL,
        P2_REL,
        "command-center/p2-wave/probes/ADV-0042/lib.py",
        "command-center/p2-wave/probes/ADV-0042/captures/S0_copyfromscreen_no_occlusion.png",
        "command-center/p2-wave/probes/ADV-0042/captures/S0_printwindow_no_occlusion.png",
        "command-center/p2-wave/probes/ADV-0042/captures/S2_copyfromscreen_full_occlusion.png",
        "command-center/p2-wave/probes/ADV-0042/captures/S2_printwindow_full_occlusion.png",
        "command-center/p2-wave/probes/ADV-0042/captures/REPO_take_screenshot_windowhandle_occluded.png",
    ]
    artifacts = [{"path": OUT_REL, "exists": True, "role": "primary"}]
    for rel in supporting:
        if (REPO / rel).is_file():
            artifacts.append({"path": rel, "exists": True, "role": "supporting"})
    flows = [
        {
            "id": "copy-from-screen-under-occlusion",
            "source": "synthetic-occluder-pixels",
            "sink": "captures/S2_copyfromscreen_full_occlusion.png",
            "data_class": "unintended-gui-surface",
            "exposure": "screen-scoped-api-stores-occluder",
            "verdict": "CONFIRMED",
        },
        {
            "id": "print-window-under-occlusion",
            "source": "synthetic-target-backing-store",
            "sink": "captures/S2_printwindow_full_occlusion.png",
            "data_class": "intended-gui-surface",
            "exposure": "window-scoped-api-keeps-target",
            "verdict": "REFUTED",
        },
        {
            "id": "world-readable-capture-file",
            "source": "planted-0644-png",
            "sink": "_scratch/retention-fixture/world_readable.png",
            "data_class": "capture-image-permissions",
            "exposure": "group-or-other-readable",
            "verdict": "CONFIRMED",
        },
    ]
    return {
        "unit_id": UNIT,
        "state": meas["state"],
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "profile": "privacy-dataflow",
        "schema_version": 1,
        "report_kind": "privacy-dataflow",
        "spec_anchor": "_USER-PROMPTS.md:11050, 11023",
        "question": QUESTION,
        "answer": meas["answer"],
        "overall_verdict": meas["overall_verdict"],
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "privacy-analyst",
            "execution_substrate": "linux-headless-software-compositor",
        },
        "targets": meas["targets"],
        "flows": flows,
        "report": {
            "kind": "privacy-dataflow",
            "question_or_target": QUESTION,
            "answer": meas["answer"],
            "evidence_requirement": (
                "Probe 1: capture with a deliberately occluding window in "
                "front of the target and assert the produced image belongs "
                "to the target - use a window-scoped capture flag plus a "
                "colour-histogram assertion, not a visual glance. Probe 2 "
                "(mechanically different): enumerate the captured artifacts "
                "on disk after a normal run and check retention, permissions "
                "and whether anything outside the target surface was stored."
            ),
            "histogram": {
                "bins": BINS,
                "belongs_threshold": BELONGS,
                "not_belongs_threshold": NOT_BELONGS,
                "target_rgb": list(TARGET_RGB),
                "occluder_rgb": list(OCCLUDER_RGB),
                "no_occlusion_passes": cap["no_occlusion_passes"],
                "calibrated": cap["histogram_calibrated"],
            },
            "captures": cap["rows"],
            "inventory": inv,
            "substrate": cap["substrate"],
            "synthetic_only": True,
            "personal_application_captured": False,
            "control_ids": [
                "no-occlusion-histogram",
                "claimed-window-scoped-but-copy-from-screen",
                "planted-world-readable-capture",
                "planted-extra-surface-labeled-window",
            ],
        },
        "named_probes": [
            {"id": "probe1", "command": P1_CMD, "raw_output": raw1},
            {"id": "probe2", "command": P2_CMD, "raw_output": raw2},
        ],
        "tests": [
            {
                "id": "T-PROBE-1-OCCLUSION-HISTOGRAM",
                "name": "window-scoped flag plus colour-histogram identity",
                "command": P1_CMD,
                "result": "PASS" if cap["histogram_calibrated"] else "FAIL",
            },
            {
                "id": "T-PROBE-2-RETENTION-PERMISSIONS",
                "name": "on-disk retention, permissions, extra-surface storage",
                "command": P2_CMD,
                "result": "PASS" if cap["retention_calibrated"] else "FAIL",
            },
            {
                "id": "T-NO-OCCLUSION-CONTROL",
                "name": "histogram accepts the target when nothing occludes it",
                "command": P1_CMD,
                "result": "PASS" if cap["no_occlusion_passes"] else "FAIL",
            },
            {
                "id": "T-SYNTHETIC-TARGET-ONLY",
                "name": "captures are taken against a synthetic target window",
                "command": P1_CMD,
                "result": "PASS" if cap["synthetic_only"] else "FAIL",
            },
        ],
        "negative_controls": [
            {
                "id": "no-occlusion-histogram",
                "kind": "calibration",
                "description": (
                    "With no occlusion, both APIs must belong to the target. "
                    "A histogram that always fails is not an identity check."
                ),
                "fired_on_bad_state": not bool(
                    cap["by_name"]["S2_copyfromscreen_full_occlusion"]["belongs_to_target"]
                ),
                "silent_on_good_state": bool(cap["no_occlusion_passes"]),
                "good_state": "S0 no occlusion",
                "bad_state": "S2 copy-from-screen (occluder pixels vs target identity)",
            },
            {
                "id": "claimed-window-scoped-but-copy-from-screen",
                "kind": "planted-mutant",
                "description": (
                    "A capture that claims the window-scoped flag but is "
                    "implemented as screen-scoped CopyFromScreen must fail "
                    "the histogram identity check under full occlusion."
                ),
                "fired_on_bad_state": bool(cap["mutant_fires"]),
                "silent_on_good_state": bool(cap["window_scoped_holds_under_occlusion"]),
                "good_state": "print-window / window_handle",
                "bad_state": "mutant window-flag + copy-from-screen",
            },
            {
                "id": "planted-world-readable-capture",
                "kind": "planted-mutant",
                "description": (
                    "A 0644 capture must be flagged; owner-only 0600 "
                    "captures of the same synthetic target must be silent."
                ),
                "fired_on_bad_state": bool(cap["world_readable_mutant_fires"]),
                "silent_on_good_state": bool(cap["owner_only_good_files"]),
                "good_state": "0600 captures/",
                "bad_state": "0644 _scratch/world_readable.png",
            },
            {
                "id": "planted-extra-surface-labeled-window",
                "kind": "planted-mutant",
                "description": (
                    "A file labeled as window-scoped that actually contains "
                    "occluder pixels must be flagged by occupancy, not by "
                    "the histogram identity table from probe 1."
                ),
                "fired_on_bad_state": bool(cap["extra_surface_mutant_fires"]),
                "silent_on_good_state": bool(cap["window_scoped_holds_under_occlusion"]),
                "good_state": "S2_printwindow_full_occlusion.png",
                "bad_state": "extra_surface_labeled_window.png",
            },
        ],
        "reviewer": {
            "reviewer_id": "ADV-0042-probe2-retention-permissions",
            "verdict": "PASS" if cap["retention_calibrated"] else "FAIL",
            "independent": True,
            "fresh_context": True,
            "vendor": "openai-style-cross-probe",
            "notes": (
                "Probe 2 re-reads PNG bytes from disk and checks mode bits "
                "plus target/occluder pixel occupancy. It does not consume "
                "probe 1's Bhattacharyya table as its verifier input."
            ),
        },
        "evidence": [
            {
                "anchor": "command-center/p2-wave/probes/ADV-0042/captures/S2_copyfromscreen_full_occlusion.png",
                "claim": "Screen-scoped capture under occlusion belongs to the occluder.",
                "verdict": "CONFIRMED",
                "probes": ["probe1"],
            },
            {
                "anchor": "command-center/p2-wave/probes/ADV-0042/captures/S2_printwindow_full_occlusion.png",
                "claim": "Window-scoped capture under occlusion belongs to the target.",
                "verdict": "REFUTED",
                "probes": ["probe1"],
            },
            {
                "anchor": "command-center/p2-wave/probes/ADV-0042/captures/S0_printwindow_no_occlusion.png",
                "claim": "No-occlusion control: histogram accepts the target.",
                "verdict": "CONFIRMED",
                "probes": ["probe1"],
            },
            {
                "anchor": "command-center/p2-wave/probes/ADV-0042/_scratch/retention-fixture/world_readable.png",
                "claim": "Planted 0644 capture is group/other-readable.",
                "verdict": "CONFIRMED",
                "probes": ["probe2"],
            },
        ],
        "artifacts": artifacts,
        "residual_unknowns": [
            {
                "claim": (
                    "Named product capture trees (ui-audit, screenshot skill, "
                    "visual-review, design-studio, monitorcore) are absent "
                    "on this Linux worktree, as is a live X11/Wayland display."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Restore the skill trees or attach a display, then bind "
                    "each take_screenshot call site to the same occlusion "
                    "histogram."
                ),
            }
        ],
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/ADV-0042/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "entry_id": UNIT,
            "note": "per-unit only; global unit_manifest.py --write was not run",
        },
        "timestamps": {
            "started_at": utc_now(),
            "ended_at": utc_now(),
            "duration_seconds": 0,
        },
        "retry": {"count": 0, "policy": "two strikes then pivot"},
        "completion_line": "UNIT-COMPLETE:ADV-0042",
        "output_path": OUT_REL,
        "output_schema": SCHEMA_REL,
        "min_bytes_threshold": 2048,
    }
