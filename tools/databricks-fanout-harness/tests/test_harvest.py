from pathlib import Path
from harness import harvest
from harness.contract import Unit
U = Unit(id="u1", lane="coverage", prompt="p", artifact="/dbfs/r/u1.md")
def test_uses_fs_cat_not_cp_and_writes_body(tmp_path):
    calls = []
    def run(argv):
        calls.append(argv)
        assert "cp" not in argv, "must use fs cat, never fs cp (DBFS->local cp is a no-op)"
        return 0, "x"*1200 + "\nUNIT-COMPLETE: u1\n", ""
    res = harvest.harvest("dbfs:/r", tmp_path, [U], run)
    assert res["u1"][0] == "harvested"
    assert (tmp_path / "u1.md").read_text(encoding="utf-8").startswith("x")
    assert any("cat" in c for c in calls)
def test_below_floor_flagged(tmp_path):
    def run(argv): return 0, "tiny", ""
    res = harvest.harvest("dbfs:/r", tmp_path, [U], run)
    assert res["u1"][0] == "below-floor"
