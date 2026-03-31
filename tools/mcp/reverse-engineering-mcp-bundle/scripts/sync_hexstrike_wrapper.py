from __future__ import annotations

import argparse
import shutil
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description='Copy the canonical HexStrike launcher from the repo bundle into the local HexStrike install root.')
    parser.add_argument('--install-root', type=Path, default=Path.home() / '.local' / 'opt' / 'hexstrike-ai')
    args = parser.parse_args()

    source = Path(__file__).resolve().parents[1] / 'wrappers' / 'hexstrike_mcp_launcher.py'
    target = args.install_root / 'hexstrike_mcp_launcher.py'
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    print(target)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
