"""One-command executable proof for contracts/completion-predicate.

Runs, in order, and fails closed on the first red:
  1. both schemas check against the JSON Schema 2020-12 metaschema (check_schema, not a hand read);
  2. the pytest suite including the twelve-mutation battery;
  3. the differential oracle (condition->function table, schema-only coverage, legacy differential);
  4. the real-artifact run (3 real + 3 deliberately incomplete, per-condition breakdown published);
  5. the platform/__init__.py shadowing both-states control.

Ends with the AGENTS.md section 4 terminal marker.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
SCHEMAS = [
    REPO_ROOT / "platform" / "schema" / "completion-predicate-result.schema.json",
    REPO_ROOT / "platform" / "schema" / "receipt.schema.json",
]


def step(name: str, argv: list[str]) -> tuple[bool, str]:
    proc = subprocess.run(
        argv, capture_output=True, text=True, check=False, cwd=str(REPO_ROOT)
    )
    tail = (proc.stdout + proc.stderr).strip().splitlines()
    return (
        proc.returncode == 0,
        f"{name}: exit={proc.returncode} :: {tail[-1] if tail else '<no output>'}",
    )


def check_schemas() -> tuple[bool, str]:
    try:
        import jsonschema
    except ImportError:
        return False, "schemas: NOT-CHECKED jsonschema not installed"
    lines = []
    ok = True
    for path in SCHEMAS:
        if not path.is_file():
            lines.append(f"{path.name}=ABSENT")
            ok = False
            continue
        try:
            schema = json.loads(path.read_text(encoding="utf-8"))
            cls = jsonschema.validators.validator_for(schema)
            cls.check_schema(schema)
            dialect = schema.get("$schema", "<none>").rsplit("/", 2)[-2:]
            lines.append(f"{path.name}=VALID({'/'.join(dialect)},{cls.__name__})")
        except Exception as exc:  # noqa: BLE001
            lines.append(f"{path.name}=INVALID({exc})")
            ok = False
    return ok, "schemas: " + " ".join(lines)


def main() -> int:
    results: list[tuple[bool, str]] = [check_schemas()]
    results.append(
        step(
            "pytest",
            [
                sys.executable,
                "-m",
                "pytest",
                "platform/lib/test_completion_predicate.py",
                "-q",
            ],
        )
    )
    results.append(
        step("differential", [sys.executable, str(HERE / "_predicate_differential.py")])
    )
    results.append(
        step("real-units", [sys.executable, str(HERE / "_predicate_real_units.py")])
    )
    results.append(
        step(
            "shadow-control", [sys.executable, str(HERE / "_probe_platform_shadow.py")]
        )
    )
    results.append(
        step(
            "mutation-selfcheck", [sys.executable, str(HERE / "_mutation_selfcheck.py")]
        )
    )

    for ok, line in results:
        print(("PASS " if ok else "FAIL ") + line)
    failed = [line.split(":")[0] for ok, line in results if not ok]
    if failed:
        print(f"FAILED:contracts-completion-predicate red_steps={failed}")
        return 1
    print(
        f"SUCCESS:contracts-completion-predicate {len(results)}/{len(results)} steps green"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
