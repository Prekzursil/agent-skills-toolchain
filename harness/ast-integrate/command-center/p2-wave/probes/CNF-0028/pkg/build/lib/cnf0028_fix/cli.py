"""Console-script and python -m entry. Prints sys.path JSON for CNF-0028."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from cnf0028_fix import PAYLOAD_TOKEN, packaged_payload


def report() -> dict:
    payload = packaged_payload()
    return {
        "ok": payload == PAYLOAD_TOKEN,
        "payload": payload,
        "expected_payload": PAYLOAD_TOKEN,
        "module_file": str(Path(__file__).resolve()),
        "sys_path": list(sys.path),
        "sys_prefix": sys.prefix,
        "executable": sys.executable,
        "cwd": os.getcwd(),
        "argv0": sys.argv[0],
    }


def main(argv: list[str] | None = None) -> int:
    del argv
    json.dump(report(), sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 0
