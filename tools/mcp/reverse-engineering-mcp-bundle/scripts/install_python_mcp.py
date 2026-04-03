from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def default_root(target_name: str) -> Path:
    return Path.home() / '.local' / 'opt' / target_name


def venv_python(root: Path) -> Path:
    return root / '.venv' / ('Scripts' if sys.platform.startswith('win') else 'bin') / ('python.exe' if sys.platform.startswith('win') else 'python')


def entrypoint_path(root: Path, entrypoint: str) -> Path:
    suffix = '.exe' if sys.platform.startswith('win') else ''
    return root / '.venv' / ('Scripts' if sys.platform.startswith('win') else 'bin') / f'{entrypoint}{suffix}'


def run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True)


def main() -> int:
    parser = argparse.ArgumentParser(description='Install a Python MCP package into ~/.local/opt/<target-name>/.venv')
    parser.add_argument('--target-name', required=True)
    parser.add_argument('--package', required=True)
    parser.add_argument('--entrypoint', required=True)
    parser.add_argument('--root', type=Path)
    args = parser.parse_args()

    root = args.root or default_root(args.target_name)
    root.mkdir(parents=True, exist_ok=True)

    py = venv_python(root)
    if not py.exists():
        run([sys.executable, '-m', 'venv', str(root / '.venv')])
    run([str(py), '-m', 'pip', 'install', '--upgrade', 'pip'])
    run([str(py), '-m', 'pip', 'install', '--upgrade', args.package])

    entry = entrypoint_path(root, args.entrypoint)
    if not entry.exists():
        raise SystemExit(f'Entrypoint not found after install: {entry}')

    print(entry)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
