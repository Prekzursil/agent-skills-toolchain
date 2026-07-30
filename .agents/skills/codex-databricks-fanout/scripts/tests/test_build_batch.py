import json
from pathlib import Path
from harness import build_batch
from harness.contract import Unit


def test_serializes_with_n():
    b = build_batch.build_batch(
        [Unit(id="u1", lane="coverage", prompt="p", artifact="/dbfs/r/u1.md")], "E"
    )
    assert b["meta"]["n"] == 1 and b["units"][0]["lane"] == "coverage"


def test_write_roundtrips(tmp_path):
    b = build_batch.build_batch(
        [Unit(id="u1", lane="coverage", prompt="p", artifact="/d/u1.md")], "x"
    )
    d = build_batch.write_batch(b, tmp_path / "b.json")
    assert json.loads(Path(d).read_text(encoding="utf-8"))["meta"]["n"] == 1


def test_emitted_field_set_is_pinned_and_timeout_s_is_never_omitted():
    """Pins the exact per-unit key set build_batch writes into batch.json.

    Load-bearing because the node-side consumer reads the timeout as
    ``int(u.get("timeout_s", 2400))`` (batch_runner.py). A ``dict.get`` default
    only fires when the key is ABSENT, so a unit carrying ``timeout_s=None``
    serializes to JSON ``null`` and raises ``TypeError`` on the node instead of
    falling back to that default. Measured 2026-07-29: None -> TypeError,
    900 -> 900, key-absent -> 2400. Neither pre-merge test covered this, so a
    change to the emitted field set (or to ``Unit.timeout_s``'s default) could
    land silently. If this assertion is ever relaxed, fix the consumer first.
    """
    unit = Unit(
        id="u1", lane="coverage", prompt="p", artifact="/d/u1.md", timeout_s=None
    )
    emitted = build_batch.build_batch([unit], "E")["units"][0]
    assert set(emitted) == {"id", "lane", "prompt", "artifact", "timeout_s"}
    assert emitted["timeout_s"] is None
    assert json.loads(json.dumps(emitted))["timeout_s"] is None
