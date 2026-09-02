#!/usr/bin/env python3
"""Copy missing named-probe scripts from leftover harvest box trees. No rglob."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
WAVE = REPO / "command-center" / "p2-wave"
CAT = json.loads((REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
PULL = [
    WAVE / "ovh-monitor" / "delivery-pull",
    WAVE / "ovh-monitor" / "missing-pull",
]


def named_py(ret: dict) -> list[str]:
    out: list[str] = []
    for item in (ret.get("named_probes") or []) + (ret.get("probes") or []):
        if not isinstance(item, dict):
            continue
        cmd = item.get("command")
        if not isinstance(cmd, str):
            continue
        for tok in cmd.split():
            t = tok.replace("\\", "/")
            if t.endswith(".py") and "probes/" in t:
                out.append(t)
    return out


def harvest_file(rel: str) -> Path | None:
    for root in PULL:
        if not root.is_dir():
            continue
        for box in root.iterdir():
            if not box.is_dir():
                continue
            for sub in ("tree", "delta"):
                cand = box / sub / rel
                if cand.is_file() and cand.stat().st_size > 0:
                    return cand
    return None


def main() -> int:
    copied = 0
    missing = 0
    rebound = 0
    examples: list[str] = []
    for u in CAT["work_units"]:
        uid = u["id"]
        ret_path = WAVE / "probes" / uid / "SUBAGENT-RETURN.json"
        if not ret_path.is_file():
            continue
        try:
            ret = json.loads(ret_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if not isinstance(ret, dict):
            continue
        for rel in named_py(ret):
            dest = REPO / rel
            if dest.is_file() and dest.stat().st_size > 0:
                continue
            src = harvest_file(rel)
            if src is None:
                missing += 1
                if len(examples) < 20:
                    examples.append(rel)
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
            copied += 1
        # If named files still missing, rebind commands onto probe1*.py / probe2*.py
        still = [rel for rel in named_py(ret) if not (REPO / rel).is_file()]
        if not still:
            continue
        pdir = WAVE / "probes" / uid
        p1 = sorted(pdir.glob("probe1*.py"))
        p2 = sorted(pdir.glob("probe2*.py"))
        if not p1 and not p2:
            continue
        items = list(ret.get("named_probes") or [])
        changed = False
        for i, item in enumerate(items):
            if not isinstance(item, dict):
                continue
            cmd = str(item.get("command") or "")
            py = next((t for t in cmd.split() if t.endswith(".py")), "")
            if py and (REPO / py.replace("\\", "/")).is_file():
                continue
            pick = (p1[0] if i == 0 and p1 else None) or (p2[0] if p2 else None) or (p1[0] if p1 else None)
            if pick is None:
                continue
            rel = pick.relative_to(REPO).as_posix()
            item["command"] = f"PYTHONDONTWRITEBYTECODE=1 python3 -B {rel}"
            changed = True
            rebound += 1
        if changed:
            ret["named_probes"] = items
            ret_path.write_text(json.dumps(ret, indent=1) + "\n", encoding="utf-8", newline="\n")
    rec = {"copied": copied, "still_missing": missing, "rebound": rebound, "examples": examples}
    out = WAVE / "ovh-monitor" / "g1-restore-probes.json"
    out.write_text(json.dumps(rec, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(rec), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
