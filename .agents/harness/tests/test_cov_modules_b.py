"""Branch-coverage tests for the SECOND half of harness/modules.py.

Targets RecallModule, AntiDegenerationModule, ClaimWarningModule,
SubagentLifecycleModule, DesignToolReminderModule and BcOffsetGuardModule
(lines ~1572-end). Every test asserts real observable behavior (HookResult
fields, return values, or on-disk effects) and documents CURRENT behavior; no
source is modified. Cross-platform: state root is redirected into tmp_path, env
and platform gates are set explicitly, and no real OS symlinks are created.
"""

from __future__ import annotations

import json
import types
from datetime import datetime, timedelta, timezone

import pytest

from harness.adapters import normalize_event
from harness.ledger import EventLedger
import harness.modules as m
from harness.modules import (
    AntiDegenerationModule,
    BcOffsetGuardModule,
    ClaimWarningModule,
    DesignToolReminderModule,
    RecallModule,
    SubagentLifecycleModule,
    _digest,
)


# --------------------------------------------------------------------------- #
# Shared helpers / fixtures
# --------------------------------------------------------------------------- #
def _event(tmp_path, name, **overrides):
    raw = {
        "session_id": "session-1",
        "turn_id": "turn-1",
        "cwd": str(tmp_path),
        "hook_event_name": name,
    }
    raw.update(overrides)
    return normalize_event(raw, provider="codex", event_name=name)


def _boom(*args, **kwargs):
    raise RuntimeError("boom")


def _raise_oserror(*args, **kwargs):
    raise OSError("disk full")


@pytest.fixture
def iso(monkeypatch, tmp_path):
    """Redirect default_state_root() into a per-test tmp dir (never real home)."""
    root = tmp_path / "_hstate"
    monkeypatch.setenv("AGENT_HARNESS_STATE_ROOT", str(root))
    return root


def _recall_index(tmp_path, notes, *, name="recall-index.json", **document):
    """A document shaped like a REAL recall_index.py build: the P1C22 freshness
    guard skips any index that does not declare a supported schema_version and a
    fresh built_at, so a fixture without them is not a servable index."""
    index = tmp_path / name
    payload = {
        "schema_version": 2,
        "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "vault_hash": "0" * 64,
        "notes": notes,
    }
    payload.update(document)
    index.write_text(json.dumps(payload), encoding="utf-8")
    return index


class _ClaimLedger:
    """Configurable SI-1 query-surface stub for ClaimWarningModule. Each method
    returns its preset or raises, to exercise the module's except-guards."""

    def __init__(
        self,
        *,
        fresh=False,
        verify=False,
        mutations=0,
        fp="",
        fp_status=None,
        fresh_raises=False,
        verify_raises=False,
        mut_raises=False,
        fp_raises=False,
    ):
        self._fresh = fresh
        self._verify = verify
        self._mutations = mutations
        self._fp = fp
        self._fp_status = fp_status
        self._fresh_raises = fresh_raises
        self._verify_raises = verify_raises
        self._mut_raises = mut_raises
        self._fp_raises = fp_raises

    def has_fresh_receipt(self, cwd, turn_id, classes, *, min_seq=None):
        if self._fresh_raises:
            raise RuntimeError("fresh boom")
        return self._fresh

    def has_verification(self, cwd, turn_id=""):
        if self._verify_raises:
            raise RuntimeError("verify boom")
        return self._verify

    def last_mutation_seq(self, cwd, turn_id=""):
        if self._mut_raises:
            raise RuntimeError("mut boom")
        return self._mutations

    def last_failed_fingerprint(self, cwd, turn_id=""):
        if self._fp_raises:
            raise RuntimeError("fp boom")
        return self._fp

    def receipt_for_fingerprint(self, cwd, fp):
        if self._fp_status is None:
            return None
        return types.SimpleNamespace(status=self._fp_status)


class _ReplayRaisesLedger:
    """EventLedger-shaped stub whose replay() raises (RecallModule guard)."""

    def replay(self, cwd, limit=40):
        raise RuntimeError("replay boom")


# --------------------------------------------------------------------------- #
# RecallModule
# --------------------------------------------------------------------------- #
def test_recall_noop_when_too_few_tokens(iso, tmp_path):
    # >=40 chars but <4 distinct qualifying tokens -> early success (line 1613).
    module = RecallModule(index_paths=[tmp_path / "none.json"], state_root=tmp_path)
    prompt = "abcdefghij " * 4  # 44 chars, single distinct token
    out = module.run(_event(tmp_path, "UserPromptSubmit", prompt=prompt))
    assert out.action == "allow"


def test_recall_fault_isolated_when_stigmergic_raises(iso, tmp_path, monkeypatch):
    # A raised _stigmergic_prior must NOT suppress the composite recall inject.
    index = _recall_index(
        tmp_path,
        [
            {
                "title": "reframe shorts auto transcribe",
                "permalink": "a/recall-note",
                "summary": "s",
                "keywords": ["reframe", "shorts", "auto", "transcribe"],
            }
        ],
    )
    monkeypatch.setattr(RecallModule, "_stigmergic_prior", _boom)
    module = RecallModule(index_paths=[index], max_results=2, state_root=tmp_path)
    out = module.run(
        _event(
            tmp_path,
            "UserPromptSubmit",
            prompt="reframe shorts auto transcribe pipeline decision here now",
        )
    )
    assert out.action == "inject" and out.reason_code == "lexical_recall"


def test_recall_skips_model_cache_path_notes(iso, tmp_path):
    # A note whose path lives under a model/cache tree is skipped (line 1643).
    index = _recall_index(
        tmp_path,
        [
            {
                "title": "reframe shorts auto transcribe",
                "permalink": "hf/model",
                "path": "cache/.hf/reframe-notes.json",
                "summary": "s",
                "keywords": ["reframe", "shorts", "auto", "transcribe"],
            }
        ],
    )
    module = RecallModule(index_paths=[index], max_results=2, state_root=tmp_path)
    out = module.run(
        _event(
            tmp_path,
            "UserPromptSubmit",
            prompt="reframe shorts auto transcribe pipeline decision here now",
        )
    )
    assert out.action == "allow"  # only candidate was skipped -> nothing scored


def test_recall_lists_note_with_empty_permalink(iso, tmp_path):
    # A scored note with an EMPTY permalink is still listed but never added to
    # the injected set: exercises the 1674->1660 false branch and the empty-set
    # early return in _remember_injected (line 1724).
    index = _recall_index(
        tmp_path,
        [
            {
                "title": "reframe shorts auto transcribe",
                "permalink": "",
                "summary": "s",
                "keywords": [],
            }
        ],
    )
    module = RecallModule(index_paths=[index], max_results=2, state_root=tmp_path)
    out = module.run(
        _event(
            tmp_path,
            "UserPromptSubmit",
            prompt="reframe shorts auto transcribe pipeline decision here now",
        )
    )
    assert out.action == "inject"
    assert "transcribe" in out.additional_context[0].lower()
    # No permalink was chosen -> _remember_injected returned early, so the
    # session-injected directory was never created.
    assert not (module.state_root / "recall-injected").exists()


def test_recall_quality_factor_valid_and_bad_mtime(iso, tmp_path):
    # One note carries a numeric mtime (recency decay path 1703-1704); the other
    # a non-numeric mtime that raises inside float() (fallback path 1705-1706).
    notes = [
        {
            "title": "reframe shorts auto transcribe",
            "permalink": "a/valid-mtime",
            "summary": "s",
            "keywords": [],
            "mtime": 1_700_000_000.0,
        },
        {
            "title": "reframe shorts auto transcribe",
            "permalink": "b/bad-mtime",
            "summary": "s",
            "keywords": [],
            "mtime": "not-a-timestamp",
        },
    ]
    module = RecallModule(
        index_paths=[_recall_index(tmp_path, notes)], max_results=2, state_root=tmp_path
    )
    out = module.run(
        _event(
            tmp_path,
            "UserPromptSubmit",
            prompt="reframe shorts auto transcribe pipeline decision here now",
        )
    )
    assert out.action == "inject"
    body = out.additional_context[0]
    assert "a/valid-mtime" in body and "b/bad-mtime" in body


def test_recall_remember_injected_survives_oserror(iso, tmp_path, monkeypatch):
    # A failed atomic_write_json inside _remember_injected is swallowed (1729-1730)
    # and the recall inject is still returned.
    index = _recall_index(
        tmp_path,
        [
            {
                "title": "reframe shorts auto transcribe",
                "permalink": "a/persist-fail",
                "summary": "s",
                "keywords": ["reframe", "shorts", "auto", "transcribe"],
            }
        ],
    )
    module = RecallModule(index_paths=[index], max_results=2, state_root=tmp_path)
    monkeypatch.setattr(m, "atomic_write_json", _raise_oserror)
    out = module.run(
        _event(
            tmp_path,
            "UserPromptSubmit",
            prompt="reframe shorts auto transcribe pipeline decision here now",
        )
    )
    assert out.action == "inject" and out.reason_code == "lexical_recall"


def test_recall_stigmergic_prior_replay_exception(iso, tmp_path):
    # A ledger whose replay() raises -> _stigmergic_prior returns success (1742-1743)
    # and, with an empty index, run() returns that allow.
    module = RecallModule(
        index_paths=[tmp_path / "empty.json"],
        max_results=2,
        ledger=_ReplayRaisesLedger(),
        state_root=tmp_path,
    )
    out = module.run(
        _event(
            tmp_path,
            "UserPromptSubmit",
            prompt="please continue the reframe transcribe pipeline work today thanks",
        )
    )
    assert out.action == "allow"


def test_recall_stigmergic_prior_too_few_overlap(iso, tmp_path):
    # A ledger with events overlapping the prompt on only ONE token -> the
    # stigmergic prior declines (len(strong) < 2, line 1754).
    ledger = EventLedger(tmp_path / "state")
    for _ in range(3):
        ledger.append(str(tmp_path), "mutation", path="reframe/only.py", tool="Edit")
    module = RecallModule(
        index_paths=[tmp_path / "empty.json"],
        max_results=2,
        ledger=ledger,
        state_root=tmp_path,
    )
    out = module.run(
        _event(
            tmp_path,
            "UserPromptSubmit",
            prompt="please work on the reframe module carefully today thanks now",
        )
    )
    assert out.action == "allow"


# --------------------------------------------------------------------------- #
# P1C22 · recall-index freshness contract
#
# Regression for "an obsolete index left on disk after its source notes changed
# or were deleted is still scored and injected". Every case below shares ONE
# prompt and ONE note, so the only variable is the index document's freshness
# metadata; _P1C22_CONTROL is the known-positive that proves the probe can see
# an inject at all (without it, an always-allow bug would look like a pass).
# --------------------------------------------------------------------------- #
_P1C22_PROMPT = "reframe shorts auto transcribe pipeline decision here now"
_P1C22_NOTES = [
    {
        "title": "reframe shorts auto transcribe",
        "permalink": "retired/alpha-beta-gamma-delta",
        "summary": "Use the retired command; the source note has since been deleted.",
        "keywords": ["reframe", "shorts", "auto", "transcribe"],
    }
]


def _p1c22_run(tmp_path, *index_paths, session="session-1"):
    # `session` isolates repeated calls: a successful inject records the chosen
    # permalink in the per-session suppress set, which would mask a later run.
    module = RecallModule(
        index_paths=list(index_paths), max_results=2, state_root=tmp_path
    )
    return module.run(
        _event(tmp_path, "UserPromptSubmit", prompt=_P1C22_PROMPT, session_id=session)
    )


def test_p1c22_control_fresh_index_is_still_injected(iso, tmp_path):
    # KNOWN-POSITIVE control: the same note through a freshly-stamped document
    # MUST inject, so a rejection below is the guard firing and not a dead probe.
    out = _p1c22_run(tmp_path, _recall_index(tmp_path, _P1C22_NOTES))
    assert out.action == "inject" and out.reason_code == "lexical_recall"
    assert "retired/alpha-beta-gamma-delta" in out.additional_context[0]


def test_p1c22_schema_v1_index_without_freshness_metadata_is_not_served(iso, tmp_path):
    # The exact reported state: a schema-v1 document with no built_at and no
    # vault_hash. It has no freshness guarantee, so it must not be injected.
    index = tmp_path / "v1.json"
    index.write_text(
        json.dumps({"schema_version": 1, "notes": _P1C22_NOTES}), encoding="utf-8"
    )
    out = _p1c22_run(tmp_path, index)
    assert out.action == "allow"


def test_p1c22_index_older_than_the_age_limit_is_not_served(iso, tmp_path):
    stale = datetime.now(timezone.utc) - timedelta(days=90)
    index = _recall_index(
        tmp_path, _P1C22_NOTES, built_at=stale.isoformat(timespec="seconds")
    )
    assert _p1c22_run(tmp_path, index).action == "allow"


def test_p1c22_naive_built_at_is_read_as_utc_and_still_ages_out(iso, tmp_path):
    # A tz-naive stamp (an older producer) is interpreted as UTC rather than
    # crashing the comparison; a naive stamp inside the window still serves.
    stale = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=90)
    fresh = datetime.now(timezone.utc).replace(tzinfo=None)
    old = _recall_index(
        tmp_path,
        _P1C22_NOTES,
        name="naive-old.json",
        built_at=stale.isoformat(timespec="seconds"),
    )
    new = _recall_index(
        tmp_path,
        _P1C22_NOTES,
        name="naive-new.json",
        built_at=fresh.isoformat(timespec="seconds"),
    )
    assert _p1c22_run(tmp_path, old, session="naive-old").action == "allow"
    assert _p1c22_run(tmp_path, new, session="naive-new").action == "inject"


@pytest.mark.parametrize(
    "built_at", ["", "   ", "not-a-timestamp", 1_700_000_000, None]
)
def test_p1c22_unusable_built_at_is_not_served(iso, tmp_path, built_at):
    index = _recall_index(tmp_path, _P1C22_NOTES, built_at=built_at)
    assert _p1c22_run(tmp_path, index).action == "allow"


@pytest.mark.parametrize("version", [0, 99, True, "2", 2.0, None])
def test_p1c22_unsupported_schema_version_is_not_served(iso, tmp_path, version):
    index = _recall_index(tmp_path, _P1C22_NOTES, schema_version=version)
    assert _p1c22_run(tmp_path, index).action == "allow"


def test_p1c22_stale_candidate_falls_through_to_a_fresh_one(iso, tmp_path):
    # The legacy path is the second candidate: a rejected first index must not
    # shadow a servable one (the pre-fix _notes() returned on the first hit).
    stale = _recall_index(
        tmp_path,
        _P1C22_NOTES,
        name="stale.json",
        built_at=(datetime.now(timezone.utc) - timedelta(days=400)).isoformat(
            timespec="seconds"
        ),
    )
    fresh = _recall_index(tmp_path, _P1C22_NOTES, name="fresh.json")
    out = _p1c22_run(tmp_path, stale, fresh)
    assert out.action == "inject" and out.reason_code == "lexical_recall"


def test_p1c22_age_limit_env_override(iso, tmp_path, monkeypatch):
    ancient = (datetime.now(timezone.utc) - timedelta(days=400)).isoformat(
        timespec="seconds"
    )
    index = _recall_index(tmp_path, _P1C22_NOTES, built_at=ancient)
    monkeypatch.setenv("AGENT_HARNESS_RECALL_MAX_AGE_DAYS", "0")
    assert _p1c22_run(tmp_path, index, session="s0").action == "inject"  # disabled
    monkeypatch.setenv("AGENT_HARNESS_RECALL_MAX_AGE_DAYS", "500")
    assert _p1c22_run(tmp_path, index, session="s1").action == "inject"  # widened
    monkeypatch.setenv("AGENT_HARNESS_RECALL_MAX_AGE_DAYS", "not-a-number")
    assert _p1c22_run(tmp_path, index, session="s2").action == "allow"  # -> default
    monkeypatch.setenv("AGENT_HARNESS_RECALL_MAX_AGE_DAYS", "  ")
    assert _p1c22_run(tmp_path, index, session="s3").action == "allow"  # -> default
    monkeypatch.setenv("AGENT_HARNESS_RECALL_MAX_AGE_DAYS", "-5")
    assert _p1c22_run(tmp_path, index, session="s4").action == "inject"  # clamp 0


def test_p1c22_index_without_a_notes_list_is_skipped(iso, tmp_path):
    # A fresh, well-versioned document whose `notes` is not a list is still not
    # servable; the next candidate is used instead.
    broken = tmp_path / "broken.json"
    broken.write_text(
        json.dumps({"schema_version": 2, "notes": "nope"}), encoding="utf-8"
    )
    fresh = _recall_index(tmp_path, _P1C22_NOTES, name="ok.json")
    assert _p1c22_run(tmp_path, broken, fresh).action == "inject"


def test_p1c22_consumer_schema_ceiling_tracks_the_producer():
    # Drift gate: bumping recall_index.SCHEMA_VERSION without bumping the
    # consumer ceiling would make every freshly built index unservable.
    from harness import recall_index

    assert m._RECALL_INDEX_SCHEMA_VERSION == recall_index.SCHEMA_VERSION


# --------------------------------------------------------------------------- #
# AntiDegenerationModule
# --------------------------------------------------------------------------- #
def test_antidegen_resets_non_list_window(iso, tmp_path):
    # A corrupt (non-list) window file on disk is reset to [] (line 1817) and the
    # call proceeds, rewriting a proper list.
    root = tmp_path / "ad"
    root.mkdir(parents=True, exist_ok=True)
    window_file = root / f"{_digest('session-1', 20)}.json"
    window_file.write_text(json.dumps({"corrupt": "dict"}), encoding="utf-8")
    module = AntiDegenerationModule(state_root=root, threshold=3)
    ev = _event(
        tmp_path,
        "PostToolUse",
        tool_name="Read",
        tool_input={"file_path": "a.py"},
        tool_response={"content": "x"},
    )
    out = module.run(ev)
    assert out.action == "allow"
    assert isinstance(json.loads(window_file.read_text(encoding="utf-8")), list)


def test_antidegen_stuck_defers_on_exact_args(iso, tmp_path, monkeypatch):
    # Same tool + same stripped signature + IDENTICAL args -> _stuck_signature
    # defers to the base gate and returns success (line 1881), so even under
    # enforce the result stays allow.
    monkeypatch.setenv("HARNESS_GATE_MODE__stuck_signature", "enforce")
    module = AntiDegenerationModule(state_root=tmp_path / "ad", threshold=3)
    last = None
    for addr in ("0xdeadbeef", "0xcafef00d", "0x12345678"):
        last = module.run(
            _event(
                tmp_path,
                "PostToolUse",
                tool_name="gamma",
                tool_input={"cmd": "x"},
                tool_response={"error": f"boom at {addr}"},
            )
        )
    assert last.action == "allow"


def test_antidegen_abab_alternation_fires(iso, tmp_path, monkeypatch):
    # A-B-A-B ping-pong across the last four calls fires the alternation gate
    # (lines 1897-1908).
    monkeypatch.setenv("HARNESS_GATE_MODE__stuck_signature", "enforce")
    module = AntiDegenerationModule(state_root=tmp_path / "ad", threshold=3)
    calls = [
        ("alpha", {"a": 1}, {"ok": "aa"}),
        ("beta", {"b": 2}, {"ok": "bb"}),
        ("alpha", {"a": 1}, {"ok": "aa"}),
        ("beta", {"b": 2}, {"ok": "bb"}),
    ]
    out = None
    for tool, ti, tr in calls:
        out = module.run(
            _event(
                tmp_path,
                "PostToolUse",
                tool_name=tool,
                tool_input=ti,
                tool_response=tr,
            )
        )
    assert out.action == "inject" and out.reason_code == "stuck_signature"
    assert any("A-B-A-B" in c for c in out.additional_context)


def test_antidegen_abab_no_fire_non_alternating(iso, tmp_path, monkeypatch):
    # Four DISTINCT calls do not alternate -> abab falls through to success (1909).
    monkeypatch.setenv("HARNESS_GATE_MODE__stuck_signature", "enforce")
    module = AntiDegenerationModule(state_root=tmp_path / "ad", threshold=3)
    out = None
    for i, tool in enumerate(("alpha", "beta", "gamma", "delta")):
        out = module.run(
            _event(
                tmp_path,
                "PostToolUse",
                tool_name=tool,
                tool_input={"i": i},
                tool_response={"n": i},
            )
        )
    assert out.action == "allow"


def test_antidegen_post_error_haste_fires(iso, tmp_path, monkeypatch):
    # A successful Edit immediately after a FAILED call with no intervening read
    # fires post-error caution (lines 1920, 1923-1930). NOTE: current
    # _result_is_failure reads ANY dict as a failure, so the succeeding write uses
    # a benign STRING result to register as non-failed.
    monkeypatch.setenv("HARNESS_GATE_MODE__post_error_haste", "enforce")
    module = AntiDegenerationModule(state_root=tmp_path / "ad", threshold=3)
    module.run(
        _event(
            tmp_path,
            "PostToolUse",
            tool_name="runner",
            tool_input={"cmd": "test"},
            tool_response={"error": "boom"},
        )
    )
    out = module.run(
        _event(
            tmp_path,
            "PostToolUse",
            tool_name="Edit",
            tool_input={"file_path": "x.py", "old_string": "a", "new_string": "b"},
            tool_response="patched ok",
        )
    )
    assert out.action == "inject" and out.reason_code == "post_error_haste"


def test_antidegen_post_error_haste_silent_when_prev_ok(iso, tmp_path, monkeypatch):
    # Same Edit but the previous call SUCCEEDED -> no caution (line 1922). Benign
    # STRING results register as non-failed under current _result_is_failure.
    monkeypatch.setenv("HARNESS_GATE_MODE__post_error_haste", "enforce")
    module = AntiDegenerationModule(state_root=tmp_path / "ad", threshold=3)
    module.run(
        _event(
            tmp_path,
            "PostToolUse",
            tool_name="Read",
            tool_input={"file_path": "a.py"},
            tool_response="read fine",
        )
    )
    out = module.run(
        _event(
            tmp_path,
            "PostToolUse",
            tool_name="Edit",
            tool_input={"file_path": "x.py", "old_string": "a", "new_string": "b"},
            tool_response="patched ok",
        )
    )
    assert out.action == "allow"


def test_antidegen_low_info_gain_fires(iso, tmp_path, monkeypatch):
    # A full window of diverse calls collapsing to only 2 distinct result shapes
    # fires the information-gain governor (lines 1939, 1942-1949).
    monkeypatch.setenv("HARNESS_GATE_MODE__low_info_gain", "enforce")
    module = AntiDegenerationModule(
        state_root=tmp_path / "ad", threshold=3, window_size=8
    )
    out = None
    for k in range(8):
        shape = {"out": "shape-a"} if k % 2 == 0 else {"out": "shape-b"}
        out = module.run(
            _event(
                tmp_path,
                "PostToolUse",
                tool_name=f"probe{k}",
                tool_input={"i": k},
                tool_response=shape,
            )
        )
    assert out.action == "inject" and out.reason_code == "low_info_gain"
    assert any("Low information gain" in c for c in out.additional_context)


def test_antidegen_low_info_gain_silent_when_diverse(iso, tmp_path, monkeypatch):
    # A full window with >2 distinct shapes is informative -> no fire (line 1941).
    # Results are digit-free distinct words: _stripped_signature strips DIGITS, so
    # "shape-0".."shape-7" would collapse to one signature and wrongly fire.
    monkeypatch.setenv("HARNESS_GATE_MODE__low_info_gain", "enforce")
    module = AntiDegenerationModule(
        state_root=tmp_path / "ad", threshold=3, window_size=8
    )
    words = ["alpha", "bravo", "charlie", "delta", "echo", "foxtrot", "golf", "hotel"]
    out = None
    for k, word in enumerate(words):
        out = module.run(
            _event(
                tmp_path,
                "PostToolUse",
                tool_name=f"probe{k}",
                tool_input={"i": k},
                tool_response=word,
            )
        )
    assert out.action == "allow"


# --------------------------------------------------------------------------- #
# ClaimWarningModule
# --------------------------------------------------------------------------- #
def test_claim_detector_fault_isolation(iso, tmp_path, monkeypatch):
    # A raised sub-detector AND a raised basic-memory nudge are both isolated
    # (lines 2083-2084 and 2088-2089); the base gate still injects.
    monkeypatch.setattr(ClaimWarningModule, "_zero_diff", _boom)
    monkeypatch.setattr(ClaimWarningModule, "_basic_memory_nudge", _boom)
    module = ClaimWarningModule(_ClaimLedger(fresh=False, verify=False))
    out = module.run(
        _event(tmp_path, "Stop", last_assistant_message="Everything is fixed and done.")
    )
    assert out.action == "inject"
    assert out.reason_code == "unverified_completion_claim"


def test_has_evidence_fresh_and_verify_raise(iso, tmp_path):
    # has_fresh_receipt raises (2104-2105) then has_verification raises
    # (2108-2109) -> _has_evidence degrades to False.
    module = ClaimWarningModule(_ClaimLedger(fresh_raises=True, verify_raises=True))
    ev = _event(tmp_path, "Stop")
    assert module._has_evidence(ev, ["fixed"]) is False


def test_has_evidence_empty_classes_uses_verification(iso, tmp_path, monkeypatch):
    # A family that maps to NO receipt classes skips the fresh-receipt lane and
    # falls back to has_verification (branch 2101->2106).
    monkeypatch.setattr(m, "CLAIM_RECEIPT_MAP", {"fixed": ()})
    module = ClaimWarningModule(_ClaimLedger(verify=True))
    ev = _event(tmp_path, "Stop")
    assert module._has_evidence(ev, ["fixed"]) is True


def test_has_evidence_true_on_fresh_receipt(iso, tmp_path):
    # A present fresh receipt short-circuits to True (fresh-receipt lane).
    module = ClaimWarningModule(_ClaimLedger(fresh=True))
    ev = _event(tmp_path, "Stop")
    assert module._has_evidence(ev, ["fixed"]) is True


def test_mutations_this_turn_none_when_absent(iso, tmp_path):
    # A ledger with no last_mutation_seq -> None (line 2142).
    module = ClaimWarningModule(object())
    assert module._mutations_this_turn(_event(tmp_path, "Stop")) is None


def test_mutations_this_turn_none_on_exception(iso, tmp_path):
    # last_mutation_seq raising -> None (lines 2145-2146).
    module = ClaimWarningModule(_ClaimLedger(mut_raises=True))
    assert module._mutations_this_turn(_event(tmp_path, "Stop")) is None


def test_zero_diff_silent_when_mutations_present(iso, tmp_path):
    # A 'fixed' claim WITH mutations this turn -> zero-diff declines (line 2157).
    module = ClaimWarningModule(_ClaimLedger(mutations=3))
    out = module._zero_diff(_event(tmp_path, "Stop"), "I fixed it.", ["fixed"])
    assert out.action == "allow"


def test_repro_fingerprint_noop_when_surface_absent(iso, tmp_path):
    # No fingerprint query surface on the ledger -> success (line 2178).
    module = ClaimWarningModule(object())
    out = module._repro_fingerprint(_event(tmp_path, "Stop"), "fixed it", ["fixed"])
    assert out.action == "allow"


def test_repro_fingerprint_noop_on_exception(iso, tmp_path):
    # last_failed_fingerprint raising -> success (lines 2182-2183).
    module = ClaimWarningModule(_ClaimLedger(fp_raises=True))
    out = module._repro_fingerprint(_event(tmp_path, "Stop"), "fixed it", ["fixed"])
    assert out.action == "allow"


def test_repro_fingerprint_silent_on_green_receipt(iso, tmp_path):
    # A failing fingerprint WITH a passing rerun receipt -> no nudge (2186->2187).
    module = ClaimWarningModule(_ClaimLedger(fp="abc123", fp_status="pass"))
    out = module._repro_fingerprint(_event(tmp_path, "Stop"), "fixed it", ["fixed"])
    assert out.action == "allow"


def test_repro_fingerprint_fires_without_green_receipt(iso, tmp_path, monkeypatch):
    # A failing fingerprint with NO passing receipt fires the repro gate
    # (lines 2188-2195).
    monkeypatch.setenv("HARNESS_GATE_MODE__repro_fingerprint", "enforce")
    module = ClaimWarningModule(_ClaimLedger(fp="abc123", fp_status=None))
    out = module._repro_fingerprint(_event(tmp_path, "Stop"), "fixed it", ["fixed"])
    assert out.action == "inject" and out.reason_code == "repro_fingerprint"


def test_receipt_gate_noop_when_no_classes(iso, tmp_path, monkeypatch):
    # A family mapping to no classes -> receipt gate declines (line 2210).
    monkeypatch.setattr(m, "CLAIM_RECEIPT_MAP", {"fixed": ()})
    module = ClaimWarningModule(_ClaimLedger(fresh=False))
    out = module._receipt_gate(_event(tmp_path, "Stop"), "fixed it", ["fixed"])
    assert out.action == "allow"


def test_receipt_gate_noop_on_exception(iso, tmp_path, monkeypatch):
    # has_fresh_receipt raising inside the receipt gate -> success (2214-2215).
    monkeypatch.setattr(m, "CLAIM_RECEIPT_MAP", {"fixed": ("test",)})
    module = ClaimWarningModule(_ClaimLedger(fresh_raises=True))
    out = module._receipt_gate(_event(tmp_path, "Stop"), "fixed it", ["fixed"])
    assert out.action == "allow"


def test_basic_memory_nudge_spool_oserror_never_raises(iso, tmp_path, monkeypatch):
    # 2026-10-22 port: the cooldown marker write is gone with the de-injection.
    # The best-effort write under the Stop path is now the session-note SPOOL,
    # and an OSError writing it is swallowed AND recorded in the capped
    # flush-errors sidecar so the capture carrier cannot rot invisibly.
    monkeypatch.setenv("HARNESS_GATE_MODE__basic_memory_nudge", "enforce")
    ledger = EventLedger(tmp_path / "state")
    ledger.append(str(tmp_path), "mutation", canonical_tree=True, path="harness/x.py")
    module = ClaimWarningModule(ledger)
    monkeypatch.setattr(m, "atomic_write_json", _raise_oserror)
    out = module._basic_memory_nudge(_event(tmp_path, "Stop"))
    assert out.action == "allow"
    assert out.reason_code != "basic_memory_nudge" and not out.additional_context
    sidecar = iso / "bm-spool" / "flush-errors.log"
    assert any(
        "spool-write OSError" in line
        for line in sidecar.read_text(encoding="utf-8").splitlines()
    )


# --------------------------------------------------------------------------- #
# SubagentLifecycleModule
# --------------------------------------------------------------------------- #
def test_subagent_start_fault_isolated_when_readback_raises(iso, tmp_path, monkeypatch):
    # A raised _ipass_readback must not suppress the handoff inject (2343-2344).
    monkeypatch.setattr(SubagentLifecycleModule, "_ipass_readback", _boom)
    module = SubagentLifecycleModule(EventLedger(tmp_path / "state"))
    out = module.run(_event(tmp_path, "SubagentStart", agent_type="reviewer"))
    assert out.action == "inject" and out.reason_code == "subagent_handoff"


def test_subagent_stalled_sentinel_fault_isolated(iso, tmp_path, monkeypatch):
    # A raised stalled sentinel on a non-lifecycle event is isolated (2352-2353).
    monkeypatch.setattr(SubagentLifecycleModule, "_stalled_sentinel", _boom)
    module = SubagentLifecycleModule(EventLedger(tmp_path / "state"))
    out = module.run(_event(tmp_path, "PreToolUse", tool_name="Bash"))
    assert out.action == "allow"


def test_subagent_stop_allows_substantive_output(iso, tmp_path):
    # A substantive (non-terminal, >=20 chars) SubagentStop message -> allow (2396).
    module = SubagentLifecycleModule(EventLedger(tmp_path / "state"))
    out = module.run(
        _event(
            tmp_path,
            "SubagentStop",
            last_assistant_message="A detailed and substantive handoff summary.",
        )
    )
    assert out.action == "allow"


def test_stalled_sentinel_oserror_on_missing_transcript(iso, tmp_path):
    # A transcript path that cannot be stat'd -> success (lines 2409-2410).
    module = SubagentLifecycleModule(EventLedger(tmp_path / "state"))
    out = module.run(
        _event(
            tmp_path,
            "PreToolUse",
            tool_name="Bash",
            agent_id="a1",
            agent_transcript_path=str(tmp_path / "does-not-exist.jsonl"),
        )
    )
    assert out.action == "allow"


def test_stalled_sentinel_silent_when_fresh(iso, tmp_path):
    # A freshly-written transcript (age < 25 min) -> not stalled (line 2412).
    transcript = tmp_path / "agent-fresh.jsonl"
    transcript.write_text("{}", encoding="utf-8")
    module = SubagentLifecycleModule(EventLedger(tmp_path / "state"))
    out = module.run(
        _event(
            tmp_path,
            "PreToolUse",
            tool_name="Bash",
            agent_id="a1",
            agent_transcript_path=str(transcript),
        )
    )
    assert out.action == "allow"


# --------------------------------------------------------------------------- #
# DesignToolReminderModule
# --------------------------------------------------------------------------- #
def test_design_write_state_survives_oserror(iso, tmp_path, monkeypatch):
    # A failed state write is swallowed (lines 2473-2474) and the reminder fires.
    module = DesignToolReminderModule(state_root=tmp_path)
    monkeypatch.setattr(m, "atomic_write_json", _raise_oserror)
    out = module.run(
        _event(tmp_path, "UserPromptSubmit", prompt="redesign the settings screen")
    )
    assert out.action == "inject" and out.reason_code == "design_tool_reminder"


def test_design_reminder_skips_subagent(iso, tmp_path):
    # A subagent's own event is never nudged off its spawn task (line 2480).
    module = DesignToolReminderModule(state_root=tmp_path)
    out = module.run(
        _event(
            tmp_path,
            "UserPromptSubmit",
            prompt="redesign the settings screen",
            agent_id="sub-1",
        )
    )
    assert out.action == "allow"


def test_design_drift_detector_fault_isolated(iso, tmp_path, monkeypatch):
    # A raised drift detector on a PreToolUse event is isolated (2486-2487).
    module = DesignToolReminderModule(state_root=tmp_path)
    monkeypatch.setattr(DesignToolReminderModule, "_drift_detector", _boom)
    out = module.run(
        _event(
            tmp_path,
            "PreToolUse",
            tool_name="Edit",
            tool_input={"file_path": "src/styles/theme.css"},
        )
    )
    assert out.action == "allow"


def test_design_run_allows_other_events(iso, tmp_path):
    # An event that is neither UserPromptSubmit nor PreToolUse -> allow (line 2488).
    module = DesignToolReminderModule(state_root=tmp_path)
    out = module.run(_event(tmp_path, "Stop", last_assistant_message="done"))
    assert out.action == "allow"


def test_design_drift_ignores_non_style_file(iso, tmp_path):
    # A Write/Edit to a non-style file is ignored by the drift detector (line 2530).
    module = DesignToolReminderModule(state_root=tmp_path)
    out = module.run(
        _event(
            tmp_path,
            "PreToolUse",
            tool_name="Edit",
            tool_input={"file_path": "src/logic/core.py"},
        )
    )
    assert out.action == "allow"


# --------------------------------------------------------------------------- #
# BcOffsetGuardModule
# --------------------------------------------------------------------------- #
def test_bc_offset_ignores_unrelated_events(iso, tmp_path):
    # An event outside {PreToolUse, UserPromptSubmit, SessionStart} -> allow (2570).
    out = BcOffsetGuardModule().run(
        _event(tmp_path, "Stop", last_assistant_message="done")
    )
    assert out.action == "allow"


def test_bc_offset_fault_isolated_when_check_raises(iso, tmp_path, monkeypatch):
    # A raised _check inside BC context is isolated (lines 2575-2576).
    monkeypatch.setenv("HARNESS_BC_SO_PATH", str(tmp_path / "libnative-lib.so"))
    monkeypatch.setattr(BcOffsetGuardModule, "_check", _boom)
    out = BcOffsetGuardModule().run(
        _event(tmp_path, "PreToolUse", tool_name="Read", tool_input={"file_path": "x"})
    )
    assert out.action == "allow"


def test_bc_offset_silent_without_baseline(iso, tmp_path, monkeypatch):
    # BC context via cwd but no SO/pinned env -> nothing to compare (line 2582).
    monkeypatch.delenv("HARNESS_BC_SO_PATH", raising=False)
    monkeypatch.delenv("HARNESS_BC_PINNED_SHA", raising=False)
    out = BcOffsetGuardModule().run(
        _event(
            tmp_path,
            "UserPromptSubmit",
            cwd=str(tmp_path / "battlecats"),
            prompt="continue the battlecats offset work here now please today",
        )
    )
    assert out.action == "allow"


def test_bc_offset_silent_when_so_unreadable(iso, tmp_path, monkeypatch):
    # A configured .so path that cannot be read -> success (lines 2585-2586).
    monkeypatch.setenv("HARNESS_BC_SO_PATH", str(tmp_path / "missing.so"))
    monkeypatch.setenv("HARNESS_BC_PINNED_SHA", "abc123")
    out = BcOffsetGuardModule().run(
        _event(tmp_path, "PreToolUse", tool_name="Read", tool_input={"file_path": "x"})
    )
    assert out.action == "allow"
