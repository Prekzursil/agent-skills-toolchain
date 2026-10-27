"""IMP-0230 CLI: scaffold / validate a blueprint.

Usage:
  python -m tools.blueprint_contract scaffold <dest-dir>
  python -m tools.blueprint_contract validate <blueprint.json>
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from tools.blueprint_contract.contract import (
    GateResult,
    validate_blueprint,
)
from tools.blueprint_contract.scaffold import emit_scaffold


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) >= 2 and argv[0] == "scaffold":
        path = emit_scaffold(argv[1])
        print(f"SUCCESS:blueprint-scaffold {path}")
        return 0
    if len(argv) >= 2 and argv[0] == "validate":
        doc = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
        res: GateResult = validate_blueprint(doc)
        print(json.dumps(res.as_dict(), indent=1))
        if not res.ok:
            print(f"FAILED:blueprint-validate {res.violations}")
            return 1
        print("SUCCESS:blueprint-validate")
        return 0
    print(
        "FAILED:blueprint-cli usage: python -m tools.blueprint_contract "
        "scaffold <dest-dir> | validate <blueprint.json>"
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
