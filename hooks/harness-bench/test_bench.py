#!/usr/bin/env python
"""Tests for harness-bench/bench.py - the semantic-router regression-net producer.

Every test drives bench.main() with a FAKE eval_runner (a zero-arg callable returning the
raw `eval.py --json` stdout string, or None) so NO real eval subprocess ever runs and the
suite is fully deterministic. Digest + baseline paths are redirected to tmp files via the
BG_DIGEST_FILE / BENCH_BASELINE env overrides, so the tests NEVER touch the real
~/.claude/BACKGROUND-DIGEST.md or the committed baseline.
"""

import json
import re
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import bench  # noqa: E402

# Mirror the background-digest reader's ENTRY test: a real entry starts with [YYYY-MM-DD.
ENTRY_RE = re.compile(r"^\[\d{4}-\d{2}-\d{2}")
DIGEST_HEADER = "<!-- test digest header (must survive) -->\n"


def _mk(skill_hit, mcp_hit, skill_total=14, mcp_total=5, neg_fire=0, neg_total=2):
    """A single variant object in the eval --json shape."""
    return {
        "skill_hit": skill_hit,
        "skill_total": skill_total,
        "mcp_hit": mcp_hit,
        "mcp_total": mcp_total,
        "neg_fire": neg_fire,
        "neg_total": neg_total,
    }


def _raw(hybrid, lexical=None, semantic=None):
    """Full eval --json stdout string with the three variants."""
    return json.dumps(
        {
            "lexical": lexical or _mk(11, 3),
            "semantic": semantic or _mk(12, 3),
            "hybrid": hybrid,
        }
    )


def _entries(digest_path):
    lines = digest_path.read_text(encoding="utf-8").splitlines()
    return [ln for ln in lines if ENTRY_RE.match(ln)]


@pytest.fixture
def env(tmp_path, monkeypatch):
    digest = tmp_path / "BACKGROUND-DIGEST.md"
    digest.write_text(DIGEST_HEADER, encoding="utf-8")
    baseline = tmp_path / "baseline.json"
    monkeypatch.setenv("BG_DIGEST_FILE", str(digest))
    monkeypatch.setenv("BENCH_BASELINE", str(baseline))
    # Default the semantic backend to UP so the suite is deterministic and never probes
    # real Ollama; the Ollama-down test overrides this to True.
    monkeypatch.setattr(bench, "_semantic_backend_down", lambda: False)
    return {"digest": digest, "baseline": baseline}


def test_first_run_writes_baseline_no_digest(env):
    cur = _mk(12, 3)
    rc = bench.main(eval_runner=lambda: _raw(cur))
    assert rc == 0
    assert json.loads(env["baseline"].read_text(encoding="utf-8")) == cur
    assert _entries(env["digest"]) == []


def test_regression_appends_one_entry_baseline_unchanged(env):
    base = _mk(12, 3)
    env["baseline"].write_text(json.dumps(base), encoding="utf-8")
    rc = bench.main(eval_runner=lambda: _raw(_mk(9, 3)))
    assert rc == 0
    entries = _entries(env["digest"])
    assert len(entries) == 1
    line = entries[0]
    # Format EXACTLY: [YYYY-MM-DD HH:MM:SS] [harness-bench] <what> | PROPOSE: <cmd>
    assert re.match(
        r"^\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\] \[harness-bench\] .+ \| PROPOSE: .+$",
        line,
    )
    assert "skill recall 12/14 -> 9/14" in line
    assert (
        "PROPOSE: python C:/Users/Prekzursil/.claude/hooks/semantic-router/eval.py"
        in line
    )
    # baseline NOT updated on regression (keep the higher bar)
    assert json.loads(env["baseline"].read_text(encoding="utf-8")) == base


def test_mcp_regression_reported_and_baseline_kept(env):
    base = _mk(12, 3)
    env["baseline"].write_text(json.dumps(base), encoding="utf-8")
    rc = bench.main(eval_runner=lambda: _raw(_mk(12, 1)))
    assert rc == 0
    entries = _entries(env["digest"])
    assert len(entries) == 1
    assert "mcp recall 3/5 -> 1/5" in entries[0]
    assert json.loads(env["baseline"].read_text(encoding="utf-8")) == base


def test_skill_up_but_mcp_down_is_regression(env):
    # Regression has priority: mcp dropped even though skill rose -> log, do NOT ratchet.
    base = _mk(12, 3)
    env["baseline"].write_text(json.dumps(base), encoding="utf-8")
    rc = bench.main(eval_runner=lambda: _raw(_mk(13, 2)))
    assert rc == 0
    entries = _entries(env["digest"])
    assert len(entries) == 1
    assert "mcp recall 3/5 -> 2/5" in entries[0]
    assert "skill recall" not in entries[0]  # skill did NOT regress
    assert json.loads(env["baseline"].read_text(encoding="utf-8")) == base


def test_improvement_ratchets_baseline_no_digest(env):
    base = _mk(12, 3)
    env["baseline"].write_text(json.dumps(base), encoding="utf-8")
    cur = _mk(13, 3)
    rc = bench.main(eval_runner=lambda: _raw(cur))
    assert rc == 0
    assert json.loads(env["baseline"].read_text(encoding="utf-8")) == cur
    assert _entries(env["digest"]) == []


def test_no_change_silent_and_baseline_unchanged(env):
    base = _mk(12, 3)
    env["baseline"].write_text(json.dumps(base), encoding="utf-8")
    rc = bench.main(eval_runner=lambda: _raw(_mk(12, 3)))
    assert rc == 0
    assert _entries(env["digest"]) == []
    assert json.loads(env["baseline"].read_text(encoding="utf-8")) == base


def test_broken_eval_none_fails_open(env):
    rc = bench.main(eval_runner=lambda: None)
    assert rc == 0
    assert _entries(env["digest"]) == []
    assert not env["baseline"].exists()


def test_garbage_non_json_fails_open(env):
    rc = bench.main(eval_runner=lambda: "this is not json {{{")
    assert rc == 0
    assert _entries(env["digest"]) == []
    assert not env["baseline"].exists()


def test_missing_hybrid_key_fails_open(env):
    rc = bench.main(eval_runner=lambda: json.dumps({"lexical": _mk(11, 3)}))
    assert rc == 0
    assert _entries(env["digest"]) == []
    assert not env["baseline"].exists()


def test_non_int_recall_fails_open(env):
    bad = {"skill_hit": "x", "skill_total": 14, "mcp_hit": 3, "mcp_total": 5}
    rc = bench.main(eval_runner=lambda: json.dumps({"hybrid": bad}))
    assert rc == 0
    assert _entries(env["digest"]) == []
    assert not env["baseline"].exists()


def test_eval_runner_that_raises_fails_open(env):
    def boom():
        raise RuntimeError("eval blew up")

    rc = bench.main(eval_runner=boom)
    assert rc == 0
    assert _entries(env["digest"]) == []


def test_digest_header_and_prior_entries_preserved(env):
    # Seed a prior entry + header; a regression must APPEND (not clobber) exactly one line.
    env["digest"].write_text(
        DIGEST_HEADER
        + "[2026-01-01 00:00:00] [world-watch] old note | PROPOSE: noop\n",
        encoding="utf-8",
    )
    env["baseline"].write_text(json.dumps(_mk(12, 3)), encoding="utf-8")
    bench.main(eval_runner=lambda: _raw(_mk(9, 3)))
    text = env["digest"].read_text(encoding="utf-8")
    assert "<!-- test digest header (must survive) -->" in text
    assert "[world-watch] old note" in text
    assert len(_entries(env["digest"])) == 2  # old + new


def test_append_when_digest_missing_trailing_newline(env):
    # A digest whose last line lacks a newline must still yield a well-formed entry line.
    env["digest"].write_text("<!-- no trailing newline -->", encoding="utf-8")
    env["baseline"].write_text(json.dumps(_mk(12, 3)), encoding="utf-8")
    bench.main(eval_runner=lambda: _raw(_mk(9, 3)))
    entries = _entries(env["digest"])
    assert len(entries) == 1
    assert entries[0].startswith("[")


def test_default_runner_used_when_none_passed(env, monkeypatch):
    # main() with no eval_runner falls back to the default; stub it to a known raw string.
    monkeypatch.setattr(bench, "_default_eval_runner", lambda: _raw(_mk(7, 2)))
    rc = bench.main()
    assert rc == 0
    assert json.loads(env["baseline"].read_text(encoding="utf-8")) == _mk(7, 2)


# ── bench-review gap-fills ───────────────────────────────────────────────────


def test_ollama_down_suppresses_regression(env, monkeypatch):
    # A recall DROP while the semantic backend is down is infra, not a router regression.
    monkeypatch.setattr(bench, "_semantic_backend_down", lambda: True)
    env["baseline"].write_text(json.dumps(_mk(12, 3)), encoding="utf-8")
    rc = bench.main(eval_runner=lambda: _raw(_mk(7, 2)))  # big drop
    assert rc == 0
    assert _entries(env["digest"]) == []  # no false regression logged
    assert json.loads(env["baseline"].read_text(encoding="utf-8")) == _mk(12, 3)


def test_corrupt_baseline_skips_no_reseed(env):
    # A present-but-corrupt baseline must NOT be reseeded (which could lower the bar).
    env["baseline"].write_text("{ this is not valid json", encoding="utf-8")
    rc = bench.main(eval_runner=lambda: _raw(_mk(13, 3)))
    assert rc == 0
    assert _entries(env["digest"]) == []
    assert env["baseline"].read_text(encoding="utf-8") == "{ this is not valid json"


def test_regression_then_recovery_no_refire(env):
    env["baseline"].write_text(json.dumps(_mk(12, 3)), encoding="utf-8")
    bench.main(eval_runner=lambda: _raw(_mk(9, 3)))  # regress -> 1 entry
    assert len(_entries(env["digest"])) == 1
    bench.main(eval_runner=lambda: _raw(_mk(12, 3)))  # recover to bar -> no new entry
    assert len(_entries(env["digest"])) == 1
    assert json.loads(env["baseline"].read_text(encoding="utf-8")) == _mk(12, 3)


def test_both_axes_drop_reported(env):
    env["baseline"].write_text(json.dumps(_mk(12, 3)), encoding="utf-8")
    bench.main(eval_runner=lambda: _raw(_mk(9, 1)))
    line = _entries(env["digest"])[0]
    assert "skill recall 12/14 -> 9/14" in line
    assert "mcp recall 3/5 -> 1/5" in line
    assert "; " in line  # both parts joined


# ── negative-control axis (D004) ─────────────────────────────────────────────
# Known-broken before the fix: _REQUIRED held only the four recall keys and the comparison
# read only skill_hit/mcp_hit, so a NEW false positive on a negative control was accepted
# with return code 0 and no digest line, and the ratchet persisted the worse neg_fire --
# lowering the frozen bar and disarming gate.py's negative-fire check.


def test_negative_control_regression_reported_and_baseline_kept(env):
    base = _mk(13, 3, neg_fire=0)
    env["baseline"].write_text(json.dumps(base), encoding="utf-8")
    # skill + mcp IDENTICAL to baseline; only the negative controls regress 0/2 -> 1/2.
    rc = bench.main(eval_runner=lambda: _raw(_mk(13, 3, neg_fire=1)))
    assert rc == 0
    entries = _entries(env["digest"])
    assert len(entries) == 1
    assert "negative-control fires 0/2 -> 1/2" in entries[0]
    assert "skill recall" not in entries[0]
    assert "mcp recall" not in entries[0]
    # keep the higher bar
    assert json.loads(env["baseline"].read_text(encoding="utf-8")) == base


def test_negative_regression_blocks_ratchet_clobbering_the_bar(env):
    # skill IMPROVES while negatives regress: regression wins, so the frozen neg_fire=0 bar
    # must survive. Persisting neg_fire=1 here would permanently disarm gate.py.
    base = _mk(13, 3, neg_fire=0)
    env["baseline"].write_text(json.dumps(base), encoding="utf-8")
    rc = bench.main(eval_runner=lambda: _raw(_mk(14, 3, neg_fire=1)))
    assert rc == 0
    assert json.loads(env["baseline"].read_text(encoding="utf-8")) == base
    assert "negative-control fires 0/2 -> 1/2" in _entries(env["digest"])[0]


def test_all_three_axes_drop_reported_in_one_entry(env):
    env["baseline"].write_text(json.dumps(_mk(12, 3, neg_fire=0)), encoding="utf-8")
    bench.main(eval_runner=lambda: _raw(_mk(9, 1, neg_fire=2)))
    entries = _entries(env["digest"])
    assert len(entries) == 1
    line = entries[0]
    assert "skill recall 12/14 -> 9/14" in line
    assert "mcp recall 3/5 -> 1/5" in line
    assert "negative-control fires 0/2 -> 2/2" in line


def test_fewer_negative_fires_ratchets_the_bar(env):
    # A negative-control IMPROVEMENT tightens the bar even when skill/mcp are unchanged.
    env["baseline"].write_text(json.dumps(_mk(13, 3, neg_fire=2)), encoding="utf-8")
    cur = _mk(13, 3, neg_fire=0)
    rc = bench.main(eval_runner=lambda: _raw(cur))
    assert rc == 0
    assert _entries(env["digest"]) == []
    assert json.loads(env["baseline"].read_text(encoding="utf-8")) == cur


def test_equal_negative_fires_stay_silent(env):
    base = _mk(13, 3, neg_fire=1)
    env["baseline"].write_text(json.dumps(base), encoding="utf-8")
    rc = bench.main(eval_runner=lambda: _raw(_mk(13, 3, neg_fire=1)))
    assert rc == 0
    assert _entries(env["digest"]) == []
    assert json.loads(env["baseline"].read_text(encoding="utf-8")) == base


@pytest.mark.parametrize(
    "bad_neg",
    [
        {},  # legacy baseline / eval with no negative counters at all
        {"neg_fire": "1", "neg_total": 2},  # string, not int
        {
            "neg_fire": True,
            "neg_total": 2,
        },  # bool is an int subclass -> must not compare
    ],
)
def test_absent_or_malformed_negative_counters_degrade_not_silence(env, bad_neg):
    # The negative axis engages only when BOTH sides carry int counters. Missing/garbage
    # counters must fall back to the old skill/mcp behaviour, never silence the producer.
    base = {"skill_hit": 12, "skill_total": 14, "mcp_hit": 3, "mcp_total": 5, **bad_neg}
    env["baseline"].write_text(json.dumps(base), encoding="utf-8")
    cur = {**base, "skill_hit": 9}
    rc = bench.main(eval_runner=lambda: json.dumps({"hybrid": cur}))
    assert rc == 0
    entries = _entries(env["digest"])
    assert len(entries) == 1
    assert "skill recall 12/14 -> 9/14" in entries[0]
    assert "negative-control" not in entries[0]


def test_negative_regression_suppressed_when_backend_down(env, monkeypatch):
    # Same infra carve-out the recall axes already get, and the same one gate.py applies to
    # every reason it collects -- the two surfaces must agree.
    monkeypatch.setattr(bench, "_semantic_backend_down", lambda: True)
    base = _mk(13, 3, neg_fire=0)
    env["baseline"].write_text(json.dumps(base), encoding="utf-8")
    rc = bench.main(eval_runner=lambda: _raw(_mk(13, 3, neg_fire=1)))
    assert rc == 0
    assert _entries(env["digest"]) == []
    assert json.loads(env["baseline"].read_text(encoding="utf-8")) == base


def test_default_eval_runner_nonzero_returncode(monkeypatch):
    monkeypatch.setattr(
        bench.subprocess,
        "run",
        lambda *a, **k: type("R", (), {"returncode": 1, "stdout": "x"})(),
    )
    assert bench._default_eval_runner() is None


def test_default_eval_runner_exception(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("subprocess failed")

    monkeypatch.setattr(bench.subprocess, "run", boom)
    assert bench._default_eval_runner() is None


def test_default_eval_runner_success(monkeypatch):
    monkeypatch.setattr(
        bench.subprocess,
        "run",
        lambda *a, **k: type("R", (), {"returncode": 0, "stdout": '{"hybrid":1}'})(),
    )
    assert bench._default_eval_runner() == '{"hybrid":1}'
