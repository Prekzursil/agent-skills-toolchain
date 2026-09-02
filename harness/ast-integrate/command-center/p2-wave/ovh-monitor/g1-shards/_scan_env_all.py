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
    "RES-0015",
    "RES-0102",
    "RES-0177",
    "TST-0072",
    "WFA-0018",
    "WFA-0039",
    "WFA-0044",
    "WFA-0045",
    "WFA-0133",
    "WFA-0141",
]
ROOT = Path(__file__).resolve().parents[2] / "probes"
NEEDLES = (
    "/root/",
    "/root",
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
    "PermissionError",
    "USERPROFILE",
    "XDG_",
    "stat(",
    "os.stat",
    "HOME",
)


def main() -> None:
    for uid in IDS:
        d = ROOT / uid
        print("====", uid, "exists" if d.is_dir() else "NO DIR")
        if not d.is_dir():
            continue
        files = sorted(p.name for p in d.iterdir() if p.is_file())
        print("  files n=", len(files), ":", ", ".join(files[:50]))
        for p in sorted(d.glob("*.py")):
            txt = p.read_text(encoding="utf-8", errors="replace")
            hits = []
            for i, line in enumerate(txt.splitlines(), 1):
                if any(n in line for n in NEEDLES):
                    hits.append((i, line.strip()[:240]))
            if hits:
                print(" ", p.name)
                for i, l in hits[:40]:
                    print(f"    {i}: {l}")


if __name__ == "__main__":
    main()
