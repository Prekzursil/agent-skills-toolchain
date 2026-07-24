import json
from pathlib import Path
from harness import build_batch
from harness.contract import Unit
def test_serializes_with_n():
    b = build_batch.build_batch([Unit(id="u1",lane="coverage",prompt="p",artifact="/dbfs/r/u1.md")], "E")
    assert b["meta"]["n"] == 1 and b["units"][0]["lane"] == "coverage"
def test_write_roundtrips(tmp_path):
    b = build_batch.build_batch([Unit(id="u1",lane="coverage",prompt="p",artifact="/d/u1.md")], "x")
    d = build_batch.write_batch(b, tmp_path/"b.json")
    assert json.loads(Path(d).read_text(encoding="utf-8"))["meta"]["n"] == 1
