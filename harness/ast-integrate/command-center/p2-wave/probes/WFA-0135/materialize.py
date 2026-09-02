#!/usr/bin/env python3
"""Materialize the WFA-0135 fixture estate and execute every test once."""
from __future__ import annotations

import json
import runpy
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from library import BLUEPRINT_SCHEMA, FLAGSHIP_COUNT, build_library  # noqa: E402
from runner import write_receipt  # noqa: E402

ESTATE = HERE / "estate"

E2E_TEMPLATE = '''#!/usr/bin/env python3
"""Flagship end-to-end test for {bid}."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ESTATE = HERE.parents[1]
sys.path.insert(0, str(ESTATE.parent))
from runner import execute_from_estate  # noqa: E402

BLUEPRINT_ID = "{bid}"


def test_end_to_end() -> dict:
    result = execute_from_estate(ESTATE, BLUEPRINT_ID, kind="e2e")
    art = Path(result["artifact_path"])
    # FLAGSHIP_E2E_ANCHOR
    assert art.is_file(), "missing produced artifact"
    assert art.stat().st_size >= 32, "artifact too small"
    payload = json.loads(art.read_text(encoding="utf-8"))
    assert payload.get("ok") is True
    assert payload.get("blueprint_id") == BLUEPRINT_ID
    return result


if __name__ == "__main__":
    r = test_end_to_end()
    print(f"PASS {{BLUEPRINT_ID}} run_id={{r['run_id']}}")
'''

SMOKE_TEMPLATE = '''#!/usr/bin/env python3
"""Smoke test for remainder blueprint {bid}."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ESTATE = HERE.parents[1]
sys.path.insert(0, str(ESTATE.parent))
from runner import execute_from_estate  # noqa: E402

BLUEPRINT_ID = "{bid}"


def test_smoke() -> dict:
    bp = json.loads((ESTATE / "blueprints" / f"{{BLUEPRINT_ID}}.json").read_text(encoding="utf-8"))
    assert bp["id"] == BLUEPRINT_ID
    result = execute_from_estate(ESTATE, BLUEPRINT_ID, kind="smoke")
    assert result.get("ok") is True
    return result


if __name__ == "__main__":
    r = test_smoke()
    print(f"PASS {{BLUEPRINT_ID}} run_id={{r['run_id']}}")
'''


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_estate(estate: Path = ESTATE) -> list[dict]:
    library = build_library()
    if estate.exists():
        # Recreate generated trees so receipts cannot go stale against old files.
        for sub in ("blueprints", "docs", "tests", "runs", "artifacts"):
            target = estate / sub
            if target.is_dir():
                for child in target.rglob("*"):
                    if child.is_file():
                        child.unlink()
    payload = {
        "schema_version": 1,
        "unit_id": "WFA-0135",
        "flagship_floor": 40,
        "claimed_flagship": FLAGSHIP_COUNT,
        "blueprint_schema": BLUEPRINT_SCHEMA,
        "blueprints": library,
    }
    _write(estate / "library.json", json.dumps(payload, indent=2, sort_keys=True) + "\n")
    for bp in library:
        bid = bp["id"]
        _write(estate / "blueprints" / f"{bid}.json", json.dumps(bp, indent=2, sort_keys=True) + "\n")
        doc = (
            f"# {bid}\n\n"
            f"Title: {bp['title']}\n\n"
            f"Claimed tier: {bp['claimed_tier']}\n\n"
            f"Mechanism: {bp['mechanism']}\n\n"
            f"Not a duplicate because: {bp['not_a_duplicate_because']}\n\n"
            f"Execute with runner.execute_from_estate on this estate.\n"
        )
        _write(estate / "docs" / f"{bid}.md", doc)
        if bp["claimed_tier"] == "flagship":
            _write(estate / "tests" / "e2e" / f"{bid}.py", E2E_TEMPLATE.format(bid=bid))
        else:
            _write(estate / "tests" / "smoke" / f"{bid}.py", SMOKE_TEMPLATE.format(bid=bid))
    return library


def _anchor_line(path: Path, needle: str) -> int:
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if needle in line:
            return i
    raise RuntimeError(f"{path} missing {needle}")


def run_and_receipt(estate: Path = ESTATE) -> list[dict]:
    library = json.loads((estate / "library.json").read_text(encoding="utf-8"))["blueprints"]
    receipts: list[dict] = []
    for bp in library:
        bid = bp["id"]
        if bp["claimed_tier"] == "flagship":
            test_path = estate / "tests" / "e2e" / f"{bid}.py"
            ns = runpy.run_path(str(test_path), run_name="wfa0135_e2e")
            result = ns["test_end_to_end"]()
            line = _anchor_line(test_path, "FLAGSHIP_E2E_ANCHOR")
            write_receipt(estate, result, test_path, line)
            receipts.append(result)
        else:
            test_path = estate / "tests" / "smoke" / f"{bid}.py"
            ns = runpy.run_path(str(test_path), run_name="wfa0135_smoke")
            result = ns["test_smoke"]()
            line = _anchor_line(test_path, "def test_smoke")
            write_receipt(estate, result, test_path, line)
            receipts.append(result)
    return receipts


def main() -> int:
    write_estate(ESTATE)
    recs = run_and_receipt(ESTATE)
    flagship = sum(1 for r in recs if r["kind"] == "e2e")
    smoke = sum(1 for r in recs if r["kind"] == "smoke")
    print(f"estate {ESTATE} e2e={flagship} smoke={smoke}")
    if flagship != FLAGSHIP_COUNT or smoke != 56:
        print(f"FAILED:materialize counts e2e={flagship} smoke={smoke}")
        return 1
    print("SUCCESS:WFA-0135-materialize")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
