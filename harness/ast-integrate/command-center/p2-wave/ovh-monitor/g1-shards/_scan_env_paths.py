#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

IDS = [
    "ADV-0139",
    "ARC-0005",
    "ARC-0004",
    "ARC-0049",
    "ARC-0089",
    "AUD-0074",
    "BLD-0036",
    "CNF-0045",
    "CNF-0101",
    "IMP-0025",
    "IMP-0036",
    "RES-0010",
]
ROOT = Path(__file__).resolve().parents[2] / "probes"
NEEDLES = (
    "/root/",
    "Path.home",
    "expanduser",
    "~/.claude",
    "~/.cursor",
    "~/.local",
    "CLAUDE_HOME",
    "os.environ.get(\"HOME\"",
    "os.environ.get('HOME'",
    "os.getenv(\"HOME\"",
    "os.getenv('HOME'",
    "Path(\"/root",
    "Path('/root",
    '".claude"',
    "'.claude'",
)


def main() -> None:
    for uid in IDS:
        d = ROOT / uid
        print("====", uid)
        for p in sorted(d.glob("*.py")):
            txt = p.read_text(encoding="utf-8", errors="replace")
            hits = []
            for i, line in enumerate(txt.splitlines(), 1):
                if any(n in line for n in NEEDLES):
                    hits.append((i, line.strip()[:200]))
            if hits:
                print(" ", p.name)
                for i, l in hits[:30]:
                    print(f"    {i}: {l}")


if __name__ == "__main__":
    main()
