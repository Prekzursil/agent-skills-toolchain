"""Producer rejects duplicate JSON keys; consumer behaviour is measured (TST-0054)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[1]
TOOLS = PLUGIN.parent
for entry in (TOOLS, TOOLS / "lib"):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

import strict_json as sj  # noqa: E402
from plugin import duplicate_key_matrix as dkm  # noqa: E402

NESTED_DUPLICATE = '{"outer":{"name":"first","name":"second"}}'


def test_duplicate_key_is_rejected_by_the_producer() -> dict:
    """Both states: unique pairs emit silently; duplicate pairs raise with both values."""
    producer = dkm.producer_duplicate_rejected()
    assert producer["unique_silent"], "unique-key document did not round-trip"
    assert producer["duplicate_fires"], "duplicate-key pairs were emitted"
    assert producer["both_values"] == {"key": "name", "first": "first", "second": "second"}

    try:
        sj.loads_strict(sj.DUPLICATE_KEY_FIXTURE)
    except sj.DuplicateKeyError as exc:
        both_values = {"key": exc.key, "first": exc.first, "second": exc.second}
    else:
        raise AssertionError("loads_strict accepted the duplicate-key fixture")

    try:
        sj.loads_strict(NESTED_DUPLICATE)
        nested_rejected = False
    except sj.DuplicateKeyError:
        nested_rejected = True
    assert nested_rejected, "nested duplicate key was accepted"

    return {
        "ok": True,
        "both_states": {
            "unique_silent": producer["unique_silent"],
            "duplicate_fires": producer["duplicate_fires"],
        },
        "both_values": both_values,
        "nested_duplicate_rejected": nested_rejected,
        "unique_emitted": producer["unique_emitted"],
        "error": producer["error"],
    }


def test_each_consumer_parser_behaviour_is_recorded_not_assumed() -> dict:
    """Stdlib last-wins and strict error are both observed live on the same fixture."""
    table = dkm.measure_matrix()
    check = dkm.assert_table_is_a_measurement(table)
    by_id = {row["parser_id"]: row for row in table["parsers"]}
    stdlib = by_id["stdlib.json.loads"]
    strict = by_id["plugin.strict_json.loads_strict"]
    assert stdlib["live"] and strict["live"]
    assert stdlib["resolution"] == "last-wins", stdlib
    assert strict["resolution"] == "error", strict
    assert json.loads(table["fixture"])["name"] == stdlib["resolved_value"]
    return {
        "ok": True,
        "stdlib": stdlib,
        "strict": strict,
        "resolutions_observed": table["resolutions_observed"],
        "check": check,
    }


if __name__ == "__main__":
    print(json.dumps(test_duplicate_key_is_rejected_by_the_producer(), sort_keys=True))
    print(json.dumps(test_each_consumer_parser_behaviour_is_recorded_not_assumed(),
                     sort_keys=True, default=str))
