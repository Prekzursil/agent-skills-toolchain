#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\source\ast-integrate")
WAVE = REPO / "command-center" / "p2-wave" / "ovh-monitor"
UIDS = [
    "WFA-0146",
    "TST-0222",
    "IMP-0201",
    "IMP-0093",
    "IMP-0301",
    "ADV-0096",
    "ADV-0135",
    "ADV-0011",
    "AUD-0037",
    "ARC-0043",
    "TST-0039",
    "TST-0310",
]
NAMES = {
    "recommend.py",
    "workspace_permissions.py",
    "baseline.py",
    "compatibility.py",
    "targets.py",
    "unique_ideas.py",
    "gold.py",
    "corpus.py",
    "fit.py",
    "license.py",
    "report.py",
}


def is_stub(text: str) -> bool:
    head = text[:2500]
    return "# g1-surface: generated" in head or "# g1-mod: real-surface" in head or "class _NS:" in head


def main() -> None:
    roots = []
    ep = WAVE / "error-pull"
    for kind in ("extracted", "extracted-delta"):
        base = ep / kind
        if not base.is_dir():
            continue
        for box in base.iterdir():
            probes = box / "probes"
            if probes.is_dir():
                roots.append(probes)
    mp = WAVE / "missing-pull"
    if mp.is_dir():
        for box in mp.iterdir():
            d = box / "delta"
            if d.is_dir():
                roots.append(d)

    print("probe-roots", len(roots))
    for uid in UIDS:
        hits = []
        for root in roots:
            d = root / uid
            if not d.is_dir():
                continue
            for p in d.rglob("*.py"):
                if p.name in NAMES or p.name.startswith("recommend"):
                    try:
                        text = p.read_text(encoding="utf-8", errors="replace")
                    except OSError:
                        continue
                    hits.append((p.stat().st_size, is_stub(text), str(p)[-160:]))
        if hits:
            print(f"\n## {uid}")
            hits.sort(reverse=True)
            for n, stub, path in hits[:12]:
                print(f"  {n:7d} stub={stub} {path}")

    print("\n## missing-pull foundry")
    if mp.is_dir():
        for p in mp.rglob("recommend.py"):
            print(" ", p, p.stat().st_size)
        for p in mp.rglob("gold.py"):
            if "routing" in str(p).replace("\\", "/"):
                print(" ", p, p.stat().st_size)


if __name__ == "__main__":
    main()
