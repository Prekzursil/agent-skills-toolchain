#!/usr/bin/env python3
"""probe2 for TST-0054: duplicate-key resolution, measured live per parser.

Fixture: {"name":"first","name":"second","keep":true}
  stdlib json.loads / json.load / JSONDecoder / node JSON.parse / jq -> last-wins
  object_pairs_hook                                                  -> records BOTH
  tools/plugin/strict_json.py loads_strict                           -> REJECTS
Producer both-states via emit_strict: clean emits, duplicate refused.
The independent pairs hook is the source; the last-wins readers are the
verifier (mechanically different parser, not a re-run).
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
UID = "TST-0054"
HERE = Path(__file__).resolve().parent
FIXTURE = '{"name":"first","name":"second","keep":true}'


def load_strict():
    spec = importlib.util.spec_from_file_location("t54_strict", REPO / "tools" / "plugin" / "strict_json.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["t54_strict"] = mod
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    strict = load_strict()
    checks: dict[str, object] = {}
    last_wins: list[str] = []
    error_parsers: list[str] = []

    # 1. stdlib family: last-wins
    doc = json.loads(FIXTURE)
    if doc.get("name") == "second":
        last_wins.append("stdlib.json.loads")
    dec = json.JSONDecoder()
    if dec.decode(FIXTURE).get("name") == "second":
        last_wins.append("stdlib.JSONDecoder.decode")
    fixture_path = HERE / "fixtures" / "duplicate-name.json"
    fixture_path.parent.mkdir(parents=True, exist_ok=True)
    fixture_path.write_text(FIXTURE, encoding="utf-8", newline="\n")
    if json.load(open(fixture_path, encoding="utf-8")).get("name") == "second":
        last_wins.append("stdlib.json.load")

    # 2. pairs hook records both (source signal)
    pairs: list[tuple[str, object]] = []
    json.loads(FIXTURE, object_pairs_hook=lambda ps: pairs.extend(ps) or dict(ps))
    name_pairs = [v for k, v in pairs if k == "name"]
    checks["pairs_hook_records_both"] = name_pairs == ["first", "second"]

    # 3. strict parser rejects
    rejected = False
    try:
        strict.loads_strict(FIXTURE)
    except strict.DuplicateKeyError:
        rejected = True
    except Exception:
        rejected = False
    if rejected:
        error_parsers.append("plugin.strict_json.loads_strict")
    checks["strict_rejects_duplicate"] = rejected
    checks["strict_accepts_clean"] = strict.loads_strict('{"name":"only","keep":true}') is not None

    # 4. node last-wins
    node = subprocess.run(
        ["node", "-e", "console.log(JSON.parse(process.argv[1]).name)", FIXTURE],
        capture_output=True, text=True,
    )
    if node.returncode == 0 and node.stdout.strip() == "second":
        last_wins.append("node.JSON.parse")

    # 5. jq last-wins
    jq = subprocess.run(["jq", "-r", ".name", "-"], input=FIXTURE.encode(), capture_output=True)
    if jq.returncode == 0 and jq.stdout.decode().strip() == "second":
        last_wins.append("jq")

    # 6. producer both-states: the strict pipeline refuses duplicates at LOAD
    def producer_emit(text: str) -> str:
        return strict.emit_strict(strict.loads_strict(text))

    clean_ok = json.loads(producer_emit('{"name":"only","keep":true}'))["name"] == "only"
    prod_refused = False
    try:
        producer_emit(FIXTURE)
    except strict.DuplicateKeyError:
        prod_refused = True
    except Exception:
        prod_refused = False
    checks["producer_emits_clean"] = clean_ok
    checks["producer_refuses_duplicate"] = prod_refused

    checks["last_wins_family_recorded_not_assumed"] = len(last_wins) >= 5
    checks["error_parser_recorded"] = bool(error_parsers)
    checks["occurrence_count_is_two"] = len(name_pairs) == 2
    ok = all(bool(v) for v in checks.values())
    table = {
        "last_wins": last_wins,
        "first_wins": [],
        "error": error_parsers,
        "pairs_hook_independent": ["cpython.object_pairs_hook"],
    }
    print(json.dumps({"unit_id": UID, "probe": "probe2-duplicate-key-live", "pass": ok,
                      "table": table, "checks": checks}))
    if ok:
        print(f"SUCCESS:{UID}-probe2 live matrix: {len(last_wins)} parsers resolve duplicates last-wins; pairs hook records both occurrences; strict_json REJECTS; producer emits clean and refuses duplicates")
        return 0
    print(f"FAILED:{UID}-probe2 " + ",".join(k for k, v in checks.items() if not v))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
