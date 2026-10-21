#!/usr/bin/env python3
"""ADV-0036 Probe 2 (REAL Windows): empirically attempt to open each deployed
execution-influencing path for WRITE access from this NON-ELEVATED context.

Opens with 'r+b' (write access requested, zero bytes written, content
byte-identical afterwards - verified) so the probe measures the ACL decision
without modifying any deployed file. A directory writability sample is added
by attempting to create+delete a scratch marker file beside each target.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
OUT = HERE / "probe2-write-real.raw.json"
UNIT = "ADV-0036"
HOME = Path.home()


def targets() -> list[tuple[str, Path]]:
    cand = [
        ("claude-settings", HOME / ".claude" / "settings.json"),
        ("claude-agents-md", HOME / ".claude" / "AGENTS.md"),
        ("claude-json", HOME / ".claude.json"),
        ("codex-config", HOME / ".codex" / "config.toml"),
        ("mcp-json", HOME / ".mcp.json"),
        ("zcode-settings", HOME / ".zcode" / "settings.json"),
        ("repo-orchestration", REPO / "ORCHESTRATION.md"),
    ]
    hooks = HOME / ".claude" / "hooks"
    if hooks.is_dir():
        for h in sorted(hooks.rglob("*")):
            if h.is_file() and len(h.relative_to(hooks).parts) <= 2:
                cand.append(("claude-hook:" + h.name, h))
    return [(cid, p) for cid, p in cand if p.is_file()]


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def try_write_open(p: Path) -> dict:
    before = sha(p)
    err = None
    ok = False
    try:
        with open(p, "r+b"):
            ok = True
    except PermissionError as exc:
        err = f"PermissionError: {exc.winerror if hasattr(exc, 'winerror') else ''}"
    except OSError as exc:
        err = f"OSError: {exc}"
    after = sha(p)
    return {"write_open_ok": ok, "error": err, "content_unchanged": before == after}


def try_dir_marker(p: Path) -> dict:
    marker = p.parent / ".adv0036-marker"
    created = False
    err = None
    try:
        marker.write_text("probe", encoding="utf-8")
        created = True
        marker.unlink()
    except PermissionError as exc:
        err = f"PermissionError: {getattr(exc, 'winerror', '')}"
    except OSError as exc:
        err = f"OSError: {exc}"
    if marker.exists():
        marker.unlink(missing_ok=True)
    return {"dir_marker_created": created, "error": err}


def main() -> int:
    rows = []
    for cid, p in targets():
        rows.append({"id": cid, "path": str(p), **try_write_open(p), **try_dir_marker(p)})
    # Controls: protected (System32 write must FAIL), user-owned (must succeed)
    import subprocess

    sysroot = Path(os.environ.get("SYSTEMROOT", r"C:\Windows"))
    protected = sysroot / "System32" / "adv0036-marker-test"
    prot_err = None
    prot_created = False
    try:
        protected.write_text("x", encoding="utf-8")
        prot_created = True
        protected.unlink()
    except OSError as exc:
        prot_err = str(exc)[:120]
    ctrl_file = HERE / "controls" / "user-owned.txt"
    ctrl_file.parent.mkdir(exist_ok=True)
    ctrl_file.write_text("control\n", encoding="utf-8")
    user_ok = try_write_open(ctrl_file)["write_open_ok"]
    report = {
        "unit_id": UNIT,
        "probe": "probe2_write_real",
        "host": {"os": os.name, "user": os.environ.get("USERNAME"), "elevated": _elevated()},
        "targets": rows,
        "controls": {
            "protected_system32_write_denied": (not prot_created),
            "protected_error": prot_err,
            "user_owned_write_ok": user_ok,
        },
        "no_file_content_modified": all(r["content_unchanged"] for r in rows),
        "no_acl_modified": True,
    }
    OUT.write_text(json.dumps(report, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"unit_id": UNIT, "host": report["host"]}, indent=1))
    for r in rows:
        print(f"{r['id']}: write_open_ok={r['write_open_ok']} dir_marker={r['dir_marker_created']} err={r['error']}")
    print("CONTROL protected System32 denied:", report["controls"]["protected_system32_write_denied"], "|", report["controls"]["protected_error"])
    print("CONTROL user-owned write ok:", report["controls"]["user_owned_write_ok"])
    print("content_unchanged_all:", report["no_file_content_modified"])
    print("PROBE2_REAL_STATUS=OK")
    return 0


def _elevated() -> bool:
    try:
        import ctypes

        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:  # noqa: BLE001
        return False


if __name__ == "__main__":
    raise SystemExit(main())
