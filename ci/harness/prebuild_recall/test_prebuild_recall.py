#!/usr/bin/env python3
"""Tests for the pre-build recall gate.

The two that matter are the KNOWN-POSITIVE CONTROLS:

  * test_control_surfaces_enshrine_note — given the real 2026-07-18 trigger
    context, the gate MUST surface
    `main/harness/reconcile-committed-2026-07-13-enshrine-runtime-config`.
    If it does not, the gate is not built.

  * test_control_detects_the_real_duplicate — the measured basename overlap
    between chore/enshrine-runtime-config (ci/harness/) and
    chore/enshrine-full-harness (agent-self/harness/) must be flagged.

Both run against fixtures derived from the real vault/branches, so they do
not require a live D: vault or a git repo to execute.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import prebuild_recall as pr  # noqa: E402

TARGET = "main/harness/reconcile-committed-2026-07-13-enshrine-runtime-config"


# ─── fixtures ────────────────────────────────────────────────────────────────


def _note(permalink, title, summary="", keywords=(), importance=0.5, mtime=None):
    return {
        "permalink": permalink,
        "title": title,
        "summary": summary,
        "keywords": list(keywords),
        "importance": importance,
        "mtime": mtime if mtime is not None else time.time(),
        "poisoned": False,
        "superseded_by": "",
        "is_failure_head": False,
    }


@pytest.fixture
def index():
    """A 61-note fixture SAMPLED FROM THE REAL VAULT (not invented).

    Stratified: the target note + 20 harness-adjacent notes (the hard
    negatives that actually compete with it) + 40 unrelated notes. Sampled
    from an index built with the two indexer defects FIXED — the control is
    predicated on that fix (see test_live_indexer_defects_are_real).

    An invented toy fixture was tried first and rejected: with ~12 keywords
    per note it could not reproduce the real vocabulary, so it failed the
    control for reasons that had nothing to do with the gate's logic and
    would have pressured the thresholds down to meaningless values.
    """
    path = Path(__file__).resolve().parent / "fixture_index.json"
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture
def build_event():
    """The REAL 2026-07-18 trigger: first Write into agent-self/harness/.

    Prompt text is the owner/agent framing recorded in the session timeline at
    04:18:43Z ("the full-harness enshrine is a genuine project").
    """
    return {
        "event": "PreToolUse",
        "tool_name": "Write",
        "cwd": "C:/repo/agent-skills-toolchain",
        "tool_input": {
            "file_path": "C:/repo/agent-skills-toolchain/agent-self/harness/recall_index.py"
        },
        "prompt": "the full-harness enshrine is a genuine project; scope it into a plan first",
        "branch": "chore/enshrine-full-harness",
    }


# ─── (d) KNOWN-POSITIVE CONTROL ──────────────────────────────────────────────


def test_control_surfaces_enshrine_note(index, build_event):
    """THE control. Given today's context, the enshrine note must surface."""
    result = pr.run(build_event, index=index, seen_dirs=set())
    assert result.fired, f"gate stayed silent: {result.reason}"
    permalinks = [h.permalink for h in result.hits]
    assert TARGET in permalinks, (
        f"known-positive control FAILED — {TARGET} not surfaced. Got: {permalinks}"
    )


def test_control_ranks_enshrine_note_first(index, build_event):
    """Not merely present — it should lead, since it is the closest prior work."""
    result = pr.run(build_event, index=index, seen_dirs=set())
    assert result.hits[0].permalink == TARGET, (
        f"expected {TARGET} first, got {result.hits[0].permalink}"
    )


def test_control_message_is_actionable(index, build_event):
    """The injected text must name the note AND how to read it."""
    result = pr.run(build_event, index=index, seen_dirs=set())
    assert "read_note" in result.message
    assert TARGET in result.message


# ─── (c) silence is the default ──────────────────────────────────────────────


def test_unrelated_write_stays_silent(index):
    event = {
        "event": "PreToolUse",
        "tool_name": "Write",
        "cwd": "C:/tmp/scratch",
        "tool_input": {"file_path": "C:/tmp/scratch/notes/hello.txt"},
        "prompt": "jot a quick note",
    }
    result = pr.run(event, index=index, seen_dirs=set())
    assert not result.fired, f"should be silent, fired with {result.hits}"


def test_non_build_shaped_tool_never_fires(index):
    for tool in ("Read", "Grep", "Glob", "Bash"):
        event = {"event": "PreToolUse", "tool_name": tool, "tool_input": {}}
        result = pr.run(event, index=index)
        assert not result.fired
        assert result.reason == "not-build-shaped"


def test_write_into_already_seen_dir_does_not_refire(index, build_event):
    seen = {str(Path(build_event["tool_input"]["file_path"]).parent)}
    result = pr.run(build_event, index=index, seen_dirs=seen)
    assert not result.fired, "must not re-fire for a directory already visited"


def test_flat_distribution_stays_silent(index):
    """A query matching everything weakly is noise, not recall."""
    query = [("harness", 1.0)]
    df = pr.build_df(index["notes"])
    hits, reason = pr.select_hits(query, index["notes"], df, len(index["notes"]))
    assert not hits
    assert reason.startswith(
        ("below-floor", "flat-distribution", "no-discriminative-token",
         "query-too-thin", "insufficient-coverage")
    ), reason


def test_common_token_only_match_is_rejected(index):
    """Gate 3: a hit built purely from common words must not fire."""
    notes = index["notes"]
    # All three tokens are in EVERY note, so none is discriminative.
    df = {"harness": len(notes), "agent": len(notes), "config": len(notes)}
    query = [("harness", 50.0), ("agent", 40.0), ("config", 30.0)]
    hits, reason = pr.select_hits(query, notes, df, len(notes))
    assert not hits
    assert reason == "no-discriminative-token"


# ─── (b) query derivation ────────────────────────────────────────────────────


def test_unmatchable_tokens_are_dropped(index):
    """DF=0 tokens carry MAX idf and would otherwise crowd out real terms."""
    notes = index["notes"]
    df = pr.build_df(notes)
    ctx = pr.BuildContext(
        kind="plan",
        cwd="C:/repo/agent-skills-toolchain",
        program_dir="C:/repo/agent-skills-toolchain/agent-self/harness",
        prompt="enshrine the harness",
        paths=("C:/repo/agent-skills-toolchain/RESCUE-PLAN-XYZZY.md",),
    )
    tokens = [t for t, _ in pr.derive_query(ctx, df, len(notes))]
    assert "xyzzy" not in tokens
    assert all(df.get(t, 0) > 0 for t in tokens), "every query token must be matchable"


def test_machine_identity_is_not_a_query_term():
    """The Windows username is rare in the vault and ubiquitous in paths —
    the worst possible combination for an IDF-weighted term."""
    home_parts = {p.strip("\\/:").lower() for p in Path.home().parts if p.strip("\\/:")}
    for part in home_parts:
        if len(part) >= 3:
            assert not pr._usable(part), f"{part!r} (home dir segment) reached the query"


def test_compound_and_parts_both_emitted():
    """`agent-skills-toolchain` is discriminative (5.1% of notes); its bare part
    `toolchain` matches nothing on its own. Emit both; let IDF choose."""
    expanded = pr._expand("C:/repo/agent-skills-toolchain")
    assert "agent-skills-toolchain" in expanded
    assert "toolchain" in expanded


def test_note_side_expands_compounds_symmetrically():
    """Asymmetric expansion is a silent recall hole: a note whose only relevant
    term is `enshrine-runtime-config` must be reachable by `runtime`."""
    note = _note("x/y", "T", "", ["enshrine-runtime-config"])
    terms = pr.note_terms(note)
    assert "enshrine-runtime-config" in terms
    assert {"enshrine", "runtime", "config"} <= terms


def test_part_match_scores_below_exact_match():
    exact = _note("a/b", "T", "", ["runtime"])
    viapart = _note("a/c", "T", "", ["enshrine-runtime-config"])
    query = [("runtime", 10.0)]
    assert pr.score_note(query, exact)[0] > pr.score_note(query, viapart)[0]


def test_ubiquitous_tokens_are_dropped(index):
    notes = index["notes"]
    df = {"harness": len(notes), "enshrine": 1}
    ctx = pr.BuildContext(kind="plan", prompt="harness enshrine")
    tokens = [t for t, _ in pr.derive_query(ctx, df, len(notes))]
    assert "harness" not in tokens, "a token in 100% of notes must be dropped"
    assert "enshrine" in tokens


# ─── (a) build-shape detection ───────────────────────────────────────────────


def test_detects_workflow_launch():
    ctx = pr.detect_build_shape(
        {"event": "PreToolUse", "tool_name": "Workflow", "tool_input": {"description": "build the cockpit"}}
    )
    assert ctx is not None and ctx.kind == "workflow"


def test_detects_worktree_create():
    ctx = pr.detect_build_shape({"event": "WorktreeCreate", "tool_input": {"path": "C:/repo/wt-1"}})
    assert ctx is not None and ctx.kind == "worktree"


@pytest.mark.parametrize(
    "path",
    ["C:/r/PLAN.md", "C:/r/docs/DESIGN.md", "C:/r/x-plan.md", "C:/r/.beads/plans/active.md"],
)
def test_detects_plan_write(path):
    ctx = pr.detect_build_shape(
        {"event": "PreToolUse", "tool_name": "Write", "tool_input": {"file_path": path}}
    )
    assert ctx is not None and ctx.kind == "plan", path


def test_detects_new_program_dir():
    ctx = pr.detect_build_shape(
        {"event": "PreToolUse", "tool_name": "Write", "tool_input": {"file_path": "C:/r/newthing/a.py"}},
        seen_dirs=set(),
    )
    assert ctx is not None and ctx.kind == "new-program-dir"


# ─── branch-overlap: the second known-positive control ───────────────────────


def test_control_detects_the_real_duplicate():
    """The measured 2026-07-18 case: same harness, two destination dirs.

    Real numbers: 29 shared basenames, 1 shared full path. A path-level check
    sees nothing; a basename check sees the rebuild.
    """
    shared = [
        "__init__.py", "adapters.py", "dispatcher.py", "injection_grammar.py",
        "install.py", "ledger.py", "models.py", "modules.py", "recall_index.py",
        "redaction.py", "registration.py", "storage.py",
    ]
    about_to_write = [f"agent-self/harness/{n}" for n in shared]
    existing = {"chore/enshrine-runtime-config": [f"ci/harness/{n}" for n in shared]}

    hits = branch_lister_overlap(about_to_write, existing)
    assert hits, "the real duplicate was not detected"
    assert hits[0].branch == "chore/enshrine-runtime-config"
    message = pr.format_overlap(hits)
    assert "already exist" in message.lower()
    assert "12 shared filenames" in message


def test_overlap_ignores_incidental_collisions():
    """Two __init__.py files are not a rebuild."""
    hits = branch_lister_overlap(
        ["src/newpkg/__init__.py", "src/newpkg/README.md"],
        {"other": ["totally/unrelated/__init__.py", "elsewhere/README.md"]},
    )
    assert not hits, "2 incidental basenames must stay below the bar"


def test_overlap_fails_open_on_lister_error():
    def boom(_branch):
        raise RuntimeError("git exploded")

    assert pr.branch_overlap(["a/b.py"], boom, ["main"]) == []


def branch_lister_overlap(targets, branch_map):
    return pr.branch_overlap(targets, lambda b: branch_map.get(b, []), list(branch_map))


# ─── (1) freshness ───────────────────────────────────────────────────────────


def test_stale_index_is_reported_not_hidden():
    """The 2026-07-18 failure mode: an 8-day-stale index that says nothing."""
    stale = {"schema_version": 2, "built_at": time.time() - 8 * 86400, "notes": [_note("a/b", "T")]}
    health = pr.index_health(stale)
    assert health.stale
    assert "age-8" in health.reason


def test_old_schema_counts_as_stale():
    """The live index is schema_version 1 while the builder emits 2."""
    old = {"schema_version": 1, "built_at": time.time(), "notes": [_note("a/b", "T")]}
    health = pr.index_health(old)
    assert health.stale and health.reason.startswith("schema-1")


def test_fresh_index_is_not_stale():
    fresh = {"schema_version": 2, "built_at": time.time(), "notes": [_note("a/b", "T")]}
    assert not pr.index_health(fresh).stale


def test_empty_index_warns_loudly():
    """Silence on an unusable index is exactly what cost the day."""
    result = pr.run(
        {"event": "PreToolUse", "tool_name": "Workflow", "tool_input": {"description": "x"}},
        index={"notes": []},
    )
    assert result.fired and "unusable" in result.message.lower()


def test_stale_warning_rides_along_with_hits(index, build_event):
    index["built_at"] = time.time() - 9 * 86400
    result = pr.run(build_event, index=index, seen_dirs=set())
    assert result.fired
    assert "STALE" in result.message


def test_iso_built_at_is_parsed():
    health = pr.index_health(
        {"schema_version": 2, "built_at": "2026-07-10T22:06:53+00:00", "notes": [_note("a/b", "T")]},
        now=time.mktime(time.strptime("2026-07-18", "%Y-%m-%d")),
    )
    assert health.stale and health.age_days and health.age_days > 6.5


# ─── fail-open contract ──────────────────────────────────────────────────────


def test_never_blocks_and_never_raises():
    for junk in [{}, {"tool_name": None}, {"tool_input": "not-a-dict"}, {"event": 123}]:
        result = pr.run(junk, index={"notes": []})
        assert isinstance(result, pr.GateResult)


def test_poisoned_notes_are_skipped(index, build_event):
    for note in index["notes"]:
        note["poisoned"] = True
    result = pr.run(build_event, index=index, seen_dirs=set())
    assert not result.fired


def test_main_exits_zero(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", type("S", (), {"read": staticmethod(lambda: "{}")})())
    assert pr.main() == 0


# ─── the upstream defects this gate depends on ───────────────────────────────

LIVE_INDEXER = Path.home() / ".agents" / "harness" / "recall_index.py"


@pytest.mark.skipif(not LIVE_INDEXER.exists(), reason="live indexer not present")
def test_live_indexer_defects_are_real():
    """Documents the two upstream defects that cap this gate's recall.

    Measured 2026-07-18 against the real vault (513 notes), same gate code,
    same query, only the indexer differing:

        broken indexer  -> target has 130 terms, ranks 12  -> CONTROL FAILS
        patched indexer -> target has 246 terms, ranks  2  -> CONTROL PASSES

    D1  `sorted(words)[:80]` truncates ALPHABETICALLY, so every note silently
        loses its m-z vocabulary. Not a random 80 — a biased 80.
    D2  frontmatter `tags` are parsed (`_tag_set`) and used for importance,
        but never passed to `_keywords`, so the most human-curated terms in
        a note are absent from search. `agent-skills-toolchain` is a tag on
        the target note and was unfindable.

    When these are fixed upstream this test should be updated, not deleted —
    it is the record of why the fixture is built the way it is.
    """
    source = LIVE_INDEXER.read_text(encoding="utf-8", errors="replace")
    assert "sorted(words)[:80]" in source, "D1 signature changed — re-measure"
    keyword_call = source[source.index('"keywords": _keywords(') :][:220]
    assert "tags" not in keyword_call, "D2 signature changed — re-measure"
