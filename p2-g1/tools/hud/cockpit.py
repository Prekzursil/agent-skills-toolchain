#!/usr/bin/env python3
"""HUD cockpit: --plain vs CSI-addressed TUI with matching field sets."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

CSI_CUP = re.compile(r"\x1b\[[0-9]+;[0-9]+H")
CSI_ANY = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
FIELD_NAMES = ("session_id", "session_name", "cwd", "model", "workspace", "worktree")


def has_cursor_addressing(text: str) -> bool:
    return bool(CSI_CUP.search(text))


def has_any_csi(text: str) -> bool:
    return bool(CSI_ANY.search(text))


def is_line_oriented_plain(text: str) -> bool:
    return (not has_any_csi(text)) and all(":" in ln for ln in text.splitlines() if ln.strip())


def _flatten(payload: dict) -> dict[str, str]:
    out = {}
    out["session_id"] = str(payload.get("session_id") or "")
    out["session_name"] = str(payload.get("session_name") or "")
    out["cwd"] = str(payload.get("cwd") or "")
    model = payload.get("model") or {}
    if isinstance(model, dict):
        out["model"] = str(model.get("display_name") or model.get("id") or "")
    else:
        out["model"] = str(model)
    ws = payload.get("workspace") or {}
    out["workspace"] = str(ws.get("current_dir") if isinstance(ws, dict) else ws)
    wt = payload.get("worktree") or {}
    out["worktree"] = str(wt.get("name") if isinstance(wt, dict) else wt)
    return out


def parse_plain_fields(text: str) -> dict[str, str]:
    fields = {}
    for ln in text.splitlines():
        if ":" not in ln:
            continue
        k, _, v = ln.partition(":")
        k = k.strip()
        if k in FIELD_NAMES:
            fields[k] = v.strip()
    missing = [k for k in FIELD_NAMES if k not in fields]
    if missing:
        raise ValueError(f"missing {missing}")
    return fields


def parse_tui_fields(text: str) -> dict[str, str]:
    stripped = CSI_ANY.sub("", text)
    return parse_plain_fields(stripped)


def render_plain(fields: dict[str, str], hidden: set[str]) -> str:
    lines = [f"{k}: {v}" for k, v in fields.items() if k not in hidden]
    return "\n".join(lines) + "\n"


def render_tui(fields: dict[str, str], hidden: set[str]) -> str:
    parts = []
    row = 1
    for k, v in fields.items():
        if k in hidden:
            continue
        parts.append(f"\x1b[{row};1H{k}: {v}\n")
        row += 1
    return "".join(parts)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--payload", required=True)
    p.add_argument("--plain", action="store_true")
    p.add_argument("--hide-field")
    p.add_argument("--hide-from", default="both")
    args = p.parse_args(argv)
    payload = json.loads(Path(args.payload).read_text(encoding="utf-8"))
    fields = _flatten(payload)
    hidden_plain: set[str] = set()
    hidden_tui: set[str] = set()
    if args.hide_field:
        target = (args.hide_from or "both").lower()
        if target in {"plain", "both"}:
            hidden_plain.add(args.hide_field)
        if target in {"tui", "both"}:
            hidden_tui.add(args.hide_field)
    if args.plain:
        sys.stdout.write(render_plain(fields, hidden_plain))
    else:
        sys.stdout.write(render_tui(fields, hidden_tui))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
