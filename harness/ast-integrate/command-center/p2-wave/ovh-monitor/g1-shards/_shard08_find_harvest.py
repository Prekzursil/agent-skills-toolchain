#!/usr/bin/env python3
"""Find harvest copies of shard-08 shared modules. Shallow, named-path only."""
from __future__ import annotations

from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\source\ast-integrate")
WAVE = REPO / "command-center" / "p2-wave" / "ovh-monitor"
NEEDLES = [
    "tools/council/quota/targets.py",
    "tools/council/quota/unique_ideas.py",
    "tools/lib/workspace_permissions.py",
    "tools/marketplace/compatibility.py",
    "tools/marketplace/license.py",
    "tools/agentspec/agentspec/evals/baseline.py",
    "command-center/foundry/routing/recommend.py",
    "command-center/foundry/routing/gold.py",
    "command-center/foundry/routing/corpus.py",
    "command-center/foundry/routing/fit.py",
    "tools/bench/report.py",
    "tools/command-center/eol_policy.py",
]


def is_stub(text: str) -> bool:
    head = text[:2500]
    return (
        "# g1-surface: generated" in head
        or "# g1-mod: real-surface" in head
        or "class _NS:" in head
    )


def hosts() -> list[Path]:
    out: list[Path] = [REPO]
    for kind in ("delivery-pull", "missing-pull"):
        base = WAVE / kind
        if not base.is_dir():
            continue
        for box in base.iterdir():
            if box.is_dir():
                for sub in ("tree", "delta"):
                    p = box / sub
                    if p.is_dir():
                        out.append(p)
    ep = WAVE / "error-pull"
    for kind in ("extracted", "extracted-delta"):
        base = ep / kind
        if not base.is_dir():
            continue
        for box in base.iterdir():
            if box.is_dir():
                out.append(box)
                for extra in ("tree", "delta", "tools", "command-center"):
                    p = box / extra
                    if p.is_dir():
                        out.append(p)
    return out


def main() -> None:
    hs = hosts()
    print("hosts", len(hs))
    for needle in NEEDLES:
        print(f"\n== {needle} ==")
        live = REPO / needle
        if live.is_file():
            text = live.read_text(encoding="utf-8", errors="replace")
            print(f" LIVE bytes={live.stat().st_size} stub={is_stub(text)}")
        else:
            print(" LIVE MISSING")
        found = []
        for host in hs:
            p = host / needle
            if not p.is_file():
                # also probe-local dumps
                continue
            try:
                text = p.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            found.append((p, p.stat().st_size, is_stub(text)))
        found.sort(key=lambda x: (-x[1], str(x[0])))
        seen = set()
        shown = 0
        for p, n, stub in found:
            key = (n, stub)
            if key in seen and shown >= 4:
                continue
            seen.add(key)
            rel = str(p).replace("\\", "/")
            print(f"  {n:7d} stub={stub} {rel[-140:]}")
            shown += 1
            if shown >= 8:
                break
        if not found:
            print("  none")


if __name__ == "__main__":
    main()
