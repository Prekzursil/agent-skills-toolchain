#!/usr/bin/env python3
"""ADV-0036 probe 2 payload: runs INSIDE the restricted (normal-user) token.

Writes its results JSON next to the probe scripts. Measures:
  - write-open decision on each deployed execution-influencing file
  - directory marker create/delete decision
  - controls: System32 marker (must be DENIED for a normal user) and a
    probe-owned file (must be ALLOWED)
No file content is modified (open r+b, zero writes; sha verified).
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "probe2-nonadmin.raw.json"
HOME = Path.home()
REPO = HERE.parents[3]


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def elevated() -> bool | None:
    try:
        import ctypes

        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:  # noqa: BLE001
        return None


def write_open(p: Path) -> dict:
    before = sha(p)
    try:
        with open(p, "r+b"):
            return {"write_open_ok": True, "error": None, "content_unchanged": before == sha(p)}
    except OSError as exc:
        return {"write_open_ok": False, "error": f"{type(exc).__name__}:{getattr(exc, 'winerror', '')}", "content_unchanged": before == sha(p)}


def dir_marker(p: Path) -> dict:
    marker = p.parent / ".adv0036-marker-r"
    try:
        marker.write_text("x", encoding="utf-8")
        marker.unlink()
        return {"dir_marker_created": True, "error": None}
    except OSError as exc:
        return {"dir_marker_created": False, "error": f"{type(exc).__name__}:{getattr(exc, 'winerror', '')}"}


def main() -> int:
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
    rows = []
    for cid, p in cand:
        if not p.is_file():
            continue
        rows.append({"id": cid, "path": str(p), **write_open(p), **dir_marker(p)})
    # controls
    try:
        m = Path(os.environ["SYSTEMROOT"]) / "System32" / "adv0036-rtest"
        m.write_text("x", encoding="utf-8")
        m.unlink()
        prot_denied = False
        prot_err = None
    except OSError as exc:
        prot_denied = True
        prot_err = f"{type(exc).__name__}:{getattr(exc, 'winerror', '')}"
    ctrl = HERE / "controls" / "user-owned.txt"
    ctrl.parent.mkdir(exist_ok=True)
    if not ctrl.exists():
        ctrl.write_text("control\n", encoding="utf-8")
    report = {
        "unit_id": "ADV-0036",
        "probe": "probe2_nonadmin_write (restricted normal-user token)",
        "host": {"os": os.name, "user": os.environ.get("USERNAME"), "elevated": elevated()},
        "targets": rows,
        "controls": {"protected_system32_write_denied": prot_denied, "protected_error": prot_err, "user_owned_write_ok": write_open(ctrl)["write_open_ok"]},
        "no_file_content_modified": all(r["content_unchanged"] for r in rows),
        "no_acl_modified": True,
    }
    OUT.write_text(json.dumps(report, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report["host"]))
    print("restricted-control denied:", prot_denied, "| user-owned ok:", report["controls"]["user_owned_write_ok"])
    for r in rows:
        print(f"{r['id']}: open={r['write_open_ok']} dir={r['dir_marker_created']} err={r['error']}")
    ok = (report["host"]["elevated"] is False) and prot_denied and report["controls"]["user_owned_write_ok"]
    print("NONADMIN_PROBE_STATUS=" + ("OK" if ok else "DEGRADED"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
