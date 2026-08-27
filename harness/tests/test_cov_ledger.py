from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path

import pytest

import harness.ledger as L
from harness.ledger import EventLedger


# ---------------------------------------------------------------------------
# Construction helpers (mirror test_ledger_receipts_and_taint.py style).
# ---------------------------------------------------------------------------


def _ledger(tmp_path):
    return EventLedger(tmp_path / "state", legacy_root=tmp_path / "no-legacy")


# ---------------------------------------------------------------------------
# canonical_project_path — file->parent normalization + .git OSError fail-open
# ---------------------------------------------------------------------------


def test_canonical_project_path_resolves_file_to_parent(tmp_path):
    # A path pointing at a FILE resolves to the file's parent dir (line 52).
    f = tmp_path / "somefile.txt"
    f.write_text("x", encoding="utf-8")
    resolved = L.canonical_project_path(str(f))
    assert Path(resolved) == tmp_path


def test_canonical_project_path_breaks_on_git_probe_oserror(tmp_path, monkeypatch):
    # When probing (parent/".git").exists() raises OSError, the walk stops and
    # falls back to the candidate dir (lines 57-58).
    # canonical_project_path only ever calls .exists() on ".git" probe paths, so
    # an unconditional raise faithfully simulates a stat failure on that probe.
    def boom_exists(self):
        raise OSError("simulated stat failure")

    monkeypatch.setattr(Path, "exists", boom_exists)
    resolved = L.canonical_project_path(str(tmp_path))
    assert Path(resolved) == Path(os.path.abspath(str(tmp_path)))


# ---------------------------------------------------------------------------
# _sanitize_value — depth cap + non-primitive catch-all
# ---------------------------------------------------------------------------


def test_sanitize_value_depth_cap_reprs_deeply_nested(tmp_path):
    # Nesting past depth 5 collapses to a redacted repr string (line 72).
    deep = {"a": {"b": {"c": {"d": {"e": {"f": {"g": 1}}}}}}}
    out = L._sanitize_value(deep)
    # Walk down to where the cap kicks in; the innermost value becomes a str.
    node = out
    for key in ("a", "b", "c", "d", "e"):
        node = node[key]
    assert isinstance(node, str)  # depth>=5 -> repr string


def test_sanitize_value_catch_all_reprs_unknown_object():
    # A non-str/dict/list/tuple/set/None/bool/int/float value hits the final
    # repr branch (line 84).
    class Weird:
        def __repr__(self):
            return "WEIRD_OBJECT"

    out = L._sanitize_value(Weird())
    assert isinstance(out, str)
    assert "WEIRD_OBJECT" in out


# ---------------------------------------------------------------------------
# _receipt_command — list/tuple argv join
# ---------------------------------------------------------------------------


def test_classify_receipt_joins_list_argv():
    # A list command value is joined into an argv string (lines 278-279).
    receipt = L.classify_receipt(
        "Bash", {"command": ["pytest", "-q"]}, {"exit_code": 0}
    )
    assert receipt is not None
    assert receipt.receipt_class == "test"


def test_receipt_command_empty_for_non_str_non_dict_input():
    # tool_input that is neither str nor dict falls straight through to "" (273->280).
    assert L._receipt_command("Bash", None) == ""
    assert L._receipt_command("Bash", 123) == ""
    # A dict whose argv value is an empty list also yields "" (loop exhausts).
    assert L._receipt_command("Bash", {"command": []}) == ""


# ---------------------------------------------------------------------------
# _is_health_command — bare 'ping' token
# ---------------------------------------------------------------------------


def test_classify_receipt_ping_is_health():
    # A bare 'ping' token classifies as health (lines 296-297).
    receipt = L.classify_receipt("Bash", {"command": "ping example.com"}, {})
    assert receipt is not None
    assert receipt.receipt_class == "health"


# ---------------------------------------------------------------------------
# _result_text / _exit_code — string result + non-dict result + bool/str exits
# ---------------------------------------------------------------------------


def test_classify_receipt_string_result_parses_counts():
    # A bare-string tool_result exercises _result_text's str fast-path (315) and
    # _exit_code's non-dict short-circuit (323->332); the parsed pass count still
    # drives status via the passed>0 branch (361).
    receipt = L.classify_receipt("Bash", "pytest -q", "5 passed")
    assert receipt is not None
    assert receipt.passed == 5
    assert receipt.status == "pass"


def test_result_text_falls_back_to_repr_on_unserializable():
    # A circular structure makes json.dumps raise -> repr fallback (318-319).
    circular: list = []
    circular.append(circular)
    text = L._result_text(circular)
    assert isinstance(text, str)
    assert text  # non-empty repr


def test_exit_code_skips_bool_and_reads_string_digit():
    # A boolean exit_code is skipped (326-327); a string-digit returncode is
    # parsed (330-331).
    assert L._exit_code({"exit_code": True, "returncode": "1"}) == 1
    # Pure-bool dict with no numeric fallback -> None.
    assert L._exit_code({"exit_code": False}) is None


def test_classify_receipt_bool_exit_uses_count_status():
    # exit_code True is ignored; passed>0 makes it a pass (326-327 + 360-361).
    receipt = L.classify_receipt(
        "Bash", {"command": "pytest"}, {"exit_code": True, "output": "3 passed"}
    )
    assert receipt is not None
    assert receipt.status == "pass"


def test_classify_receipt_string_returncode_nonzero_fails():
    # A string returncode of "1" is parsed and drives a fail (330-331).
    receipt = L.classify_receipt(
        "Bash", {"command": "pytest"}, {"returncode": "1", "output": "boom"}
    )
    assert receipt is not None
    assert receipt.status == "fail"


# ---------------------------------------------------------------------------
# _sum_matches — non-int capture group fail-open
# ---------------------------------------------------------------------------


def test_sum_matches_skips_non_integer_group():
    # A pattern whose group(1) is non-numeric hits the except: continue (344-345).
    pattern = re.compile(r"(x+)")
    assert L._sum_matches(pattern, "xxx yyy xx") == 0


# ---------------------------------------------------------------------------
# _as_int — fail-open on non-convertible values
# ---------------------------------------------------------------------------


def test_as_int_returns_zero_on_bad_value():
    assert L._as_int("not-a-number") == 0  # 409-410
    assert L._as_int(None) == 0
    assert L._as_int(7) == 7


# ---------------------------------------------------------------------------
# _timestamp — invalid iso string fail-open + tz-naive normalization
# ---------------------------------------------------------------------------


def test_timestamp_zero_on_empty_and_invalid():
    assert EventLedger._timestamp("") == 0.0  # not value -> 0.0
    assert EventLedger._timestamp("not-a-date") == 0.0  # 953-954
    # A valid tz-naive timestamp is normalized to UTC and returns a positive ts.
    assert EventLedger._timestamp("2026-07-12T00:00:00") > 0.0


# ---------------------------------------------------------------------------
# _FileLock — stale-lock reclaim, timeout, and fail-open teardown
# ---------------------------------------------------------------------------


def test_filelock_reclaims_stale_lock(tmp_path):
    # A lock file older than 30s is treated as stale, unlinked, and reacquired
    # (lines 447-449).
    lock_path = tmp_path / "stale.lock"
    lock_path.write_text("999999", encoding="utf-8")
    old = time.time() - 60
    os.utime(lock_path, (old, old))
    with L._FileLock(lock_path, timeout=5.0) as held:
        assert held.fd is not None
        assert lock_path.exists()  # our freshly-created lock
    assert not lock_path.exists()  # released on exit


def test_filelock_times_out_on_fresh_held_lock(tmp_path):
    # A fresh (non-stale) lock plus a past deadline forces the timeout raise
    # (452->453).
    lock_path = tmp_path / "held.lock"
    lock_path.write_text("111", encoding="utf-8")
    with pytest.raises(TimeoutError):
        L._FileLock(lock_path, timeout=-1.0).__enter__()
    lock_path.unlink(missing_ok=True)


def test_filelock_exit_swallows_unlink_oserror(tmp_path):
    # fd is None so the close branch is skipped (457->462); unlinking a directory
    # raises OSError which is swallowed (464-465).
    lock = L._FileLock(tmp_path / "unused.lock")
    lock.fd = None
    target_dir = tmp_path / "dir.lock"
    target_dir.mkdir()
    lock.path = target_dir
    lock.__exit__()  # must not raise
    assert target_dir.exists()  # unlink failed and was swallowed


def test_filelock_exit_swallows_close_oserror(tmp_path):
    # A second os.close on an already-closed fd raises OSError, swallowed (460-461).
    lock_path = tmp_path / "closed.lock"
    lock = L._FileLock(lock_path)
    lock.__enter__()
    assert lock.fd is not None
    os.close(lock.fd)  # close it out from under __exit__
    lock.__exit__()  # must not raise
    assert not lock_path.exists()  # unlink still ran


# ---------------------------------------------------------------------------
# _shared_event_paths / _load_state — glob fail-open + non-dict state fallback
# ---------------------------------------------------------------------------


def test_shared_event_paths_glob_oserror_returns_target_only(tmp_path, monkeypatch):
    ledger = _ledger(tmp_path)
    cwd = str(tmp_path)
    target = ledger._events(cwd)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text('{"seq":1,"kind":"decision"}\n', encoding="utf-8")

    def boom_glob(self, *a, **k):
        raise OSError("glob failed")

    monkeypatch.setattr(type(ledger.root), "glob", boom_glob)
    paths = ledger._shared_event_paths(cwd)  # 498-499
    assert paths == [target]


def test_load_state_returns_default_when_state_json_not_dict(tmp_path):
    ledger = _ledger(tmp_path)
    cwd = str(tmp_path)
    state_path = ledger._state_path(cwd)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text("[1, 2, 3]", encoding="utf-8")  # non-dict JSON
    loaded = ledger._load_state(cwd)  # 520-521
    assert loaded["seq"] == 0
    assert loaded["project"] == L.project_key(cwd)


# ---------------------------------------------------------------------------
# _shared_events — blank/invalid/non-dict handling + repair rewrite
# ---------------------------------------------------------------------------


def test_shared_events_parses_and_repairs_corrupt_target(tmp_path):
    ledger = _ledger(tmp_path)
    cwd = str(tmp_path)
    target = ledger._events(cwd)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        '{"seq":1,"kind":"decision","text":"a"}\n'
        "\n"  # blank -> 535-536
        "   \n"  # whitespace-only -> 535-536
        "not valid json\n"  # ValueError -> 539-541
        "[1, 2, 3]\n"  # valid JSON, non-dict -> 542->545
        '{"seq":2,"kind":"decision","text":"b"}\n',
        encoding="utf-8",
    )
    # Non-repair read keeps valid dicts, drops corrupt lines, leaves file intact.
    events = ledger._shared_events(cwd)
    assert sorted(int(e["seq"]) for e in events) == [1, 2]
    assert "not valid json" in target.read_text(encoding="utf-8")

    # Repair read on the target rewrites it clean (547-548, 552).
    events2 = ledger._shared_events(cwd, repair=True)
    assert sorted(int(e["seq"]) for e in events2) == [1, 2]
    after = target.read_text(encoding="utf-8")
    assert "not valid json" not in after
    assert "[1, 2, 3]" not in after
    assert sorted(int(e["seq"]) for e in ledger._shared_events(cwd)) == [1, 2]


def test_shared_events_skips_unreadable_path(tmp_path):
    ledger = _ledger(tmp_path)
    cwd = str(tmp_path)
    target = ledger._events(cwd)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.mkdir()  # events.jsonl as a directory -> read_text raises OSError
    assert ledger._shared_events(cwd) == []  # 531-532


# ---------------------------------------------------------------------------
# _tail_bytes / _last_event_from_path / _last_shared_seq — byte-tail scanning
# ---------------------------------------------------------------------------


def test_tail_bytes_oserror_on_missing_path(tmp_path):
    data, from_start = EventLedger._tail_bytes(tmp_path / "nope.jsonl", 1024)
    assert data == b"" and from_start is False  # 563-564


def test_tail_bytes_no_boundary_when_tail_has_no_newline(tmp_path):
    f = tmp_path / "big.jsonl"
    f.write_bytes(b"x" * 1000)  # no newline anywhere
    data, from_start = EventLedger._tail_bytes(f, 10)  # seek into the middle
    assert data == b"" and from_start is False  # 567-568 (boundary < 0)


def test_last_event_from_path_scans_reversed_and_skips_noise(tmp_path):
    f = tmp_path / "ev.jsonl"
    f.write_text(
        '{"seq":1,"kind":"decision"}\n'
        "[1, 2, 3]\n"  # valid JSON, non-dict -> 582->575
        "not json\n"  # ValueError -> 580-581
        "\n",  # blank -> 576-577
        encoding="utf-8",
    )
    item = EventLedger._last_event_from_path(f)
    assert item is not None and item["seq"] == 1


def test_last_event_from_path_returns_none_when_all_noise(tmp_path):
    f = tmp_path / "noise.jsonl"
    f.write_text("\n   \nnot json\n", encoding="utf-8")
    assert EventLedger._last_event_from_path(f) is None  # 575->584


def test_last_shared_seq_skips_paths_yielding_no_event(tmp_path):
    blank = tmp_path / "blank.jsonl"
    blank.write_text("\n\n", encoding="utf-8")  # no parseable event -> None
    good = tmp_path / "good.jsonl"
    good.write_text('{"seq":7,"kind":"decision"}\n', encoding="utf-8")
    assert EventLedger._last_shared_seq([blank, good]) == 7  # 591->589 on blank


# ---------------------------------------------------------------------------
# _find_event_by_id — id lookup edge cases
# ---------------------------------------------------------------------------


def test_find_event_by_id_covers_edge_cases(tmp_path):
    # OSError on read (directory path) -> continue (617-618).
    d = tmp_path / "as_dir"
    d.mkdir()
    assert EventLedger._find_event_by_id([d], "X") is None

    # Match on the final line with NO trailing newline -> end<0 -> len(data) (622-623).
    f_w = tmp_path / "w.jsonl"
    f_w.write_bytes(b'{"event_id":"W","seq":1}')
    found = EventLedger._find_event_by_id([f_w], "W")
    assert found is not None and found["event_id"] == "W"

    # Malformed JSON around the matched id -> ValueError -> continue (626-627).
    f_z = tmp_path / "z.jsonl"
    f_z.write_bytes(b'{bad "event_id":"Z"}\n')
    assert EventLedger._find_event_by_id([f_z], "Z") is None

    # Valid JSON but non-dict containing the id -> 628 False -> loop (628->619).
    f_x = tmp_path / "x.jsonl"
    f_x.write_bytes(b'[{"event_id":"X"}]\n')
    assert EventLedger._find_event_by_id([f_x], "X") is None


# ---------------------------------------------------------------------------
# _tail_events_from_path / _recent_shared_events / _ensure_append_boundary
# ---------------------------------------------------------------------------


def test_tail_events_from_path_skips_blank_and_invalid(tmp_path):
    f = tmp_path / "tail.jsonl"
    f.write_text(
        '{"seq":1}\n'
        "\n"  # blank -> 639-640
        "   \n"
        "not json\n"  # invalid -> 643-644
        "[1, 2, 3]\n"  # valid JSON, non-dict -> 645->638
        '{"seq":2}\n',
        encoding="utf-8",
    )
    events = EventLedger._tail_events_from_path(f, max_bytes=10**6)
    assert [int(e["seq"]) for e in events] == [1, 2]


def test_recent_shared_events_empty_when_all_below_floor(tmp_path):
    f = tmp_path / "r.jsonl"
    f.write_text('{"seq":1}\n{"seq":2}\n{"seq":3}\n', encoding="utf-8")
    events, complete = EventLedger._recent_shared_events(
        [f], after_seq=5, through_seq=6
    )
    assert events == [] and complete is False  # 666-667


def test_ensure_append_boundary_appends_missing_newline(tmp_path):
    f = tmp_path / "b.jsonl"
    f.write_text("partial line no newline", encoding="utf-8")
    EventLedger._ensure_append_boundary(f)  # 693 True -> 694-697
    assert f.read_text(encoding="utf-8").endswith("\n")


def test_ensure_append_boundary_fail_open_on_fsync_error(tmp_path, monkeypatch):
    f = tmp_path / "c.jsonl"
    f.write_text("unterminated", encoding="utf-8")

    def boom_fsync(_fd):
        raise OSError("simulated fsync failure")

    monkeypatch.setattr(L.os, "fsync", boom_fsync)
    EventLedger._ensure_append_boundary(f)  # 698-699, must not raise


# ---------------------------------------------------------------------------
# _apply_events_to_state / _project_state — reducer branches
# ---------------------------------------------------------------------------


def test_apply_events_to_state_skip_and_no_ts_branches(tmp_path):
    ledger = _ledger(tmp_path)
    cwd = str(tmp_path)
    fallback = ledger._load_state(cwd)  # default, seq 0
    events = [
        {"seq": 1, "kind": "mutation"},  # no ts -> 724->726 and 755->719
        {"seq": 2, "kind": "milestone", "supersedes_failures": []},  # empty -> 742->719
        {"seq": 0, "kind": "decision", "text": "stale"},  # seq<=state -> 722 continue
        {"seq": 3, "kind": "decision", "text": "keep"},
    ]
    state = ledger._apply_events_to_state(cwd, fallback, events)
    assert state["seq"] == 3
    assert state["last_mutation_seq"] == 1
    assert state["last_mutation_ts"] is None  # mutation carried no ts
    texts = [d["text"] for d in state["decisions"]]
    assert "keep" in texts and "stale" not in texts


def test_project_state_full_reducer_coverage(tmp_path):
    ledger = _ledger(tmp_path)
    cwd = str(tmp_path)
    target = ledger._events(cwd)
    target.parent.mkdir(parents=True, exist_ok=True)
    events = [
        {"seq": 1, "kind": "goal", "text": "G"},  # no ts -> 785->787; goal branch
        {"seq": 2, "kind": "decision", "text": "D", "ts": "2026-07-12T00:00:01+00:00"},
        {"seq": 3, "kind": "failure", "text": "F", "preconditions": "P"},  # 793-794
        {"seq": 4, "kind": "milestone", "supersedes_failures": [3]},  # 803->804
        {"seq": 5, "kind": "milestone", "supersedes_failures": []},  # 803->782
        {"seq": 6, "kind": "mutation"},  # no ts -> 807 True, 811->782
        {"seq": 7, "kind": "mutation", "ts": "2026-07-12T00:00:07+00:00"},  # 811->812
        {"seq": 8, "kind": "tool_result", "tool": "Bash"},  # unmatched -> 807->782
    ]
    target.write_text("".join(json.dumps(e) + "\n" for e in events), encoding="utf-8")
    assert not ledger._state_path(cwd).exists()  # force full projection
    state = ledger.state(cwd)
    assert state["seq"] == 8
    assert state["goal"] == "G"
    assert all(f.get("seq") != 3 for f in state["open_failures"])  # superseded
    assert state["last_mutation_seq"] == 7


# ---------------------------------------------------------------------------
# session goals — _read_session_goal, set_goal, goal (per-session isolation)
# ---------------------------------------------------------------------------


def test_read_session_goal_non_dict_returns_empty(tmp_path):
    ledger = _ledger(tmp_path)
    goal_path = ledger._session_goal_path("sess-1")
    goal_path.parent.mkdir(parents=True, exist_ok=True)
    goal_path.write_text("[1, 2, 3]", encoding="utf-8")  # non-dict
    assert ledger._read_session_goal("sess-1") == ""  # 1004->1008


def test_read_session_goal_dict_without_goal_returns_empty(tmp_path):
    ledger = _ledger(tmp_path)
    goal_path = ledger._session_goal_path("sess-2")
    goal_path.parent.mkdir(parents=True, exist_ok=True)
    goal_path.write_text('{"ts": "x"}', encoding="utf-8")  # dict, no goal key
    assert ledger._read_session_goal("sess-2") == ""  # 1006 False -> 1008


def test_set_goal_ignores_blank_text(tmp_path):
    ledger = _ledger(tmp_path)
    cwd = str(tmp_path)
    ledger.set_goal(cwd, "   ")  # redact+strip -> "" -> early return (1021-1022)
    assert ledger.replay(cwd, limit=50) == []  # nothing appended
    assert ledger.goal(cwd) == ""  # session_id None, no goal -> 1043


def test_set_goal_and_goal_per_session_isolation(tmp_path):
    ledger = _ledger(tmp_path)
    cwd = str(tmp_path)
    ledger.set_goal(cwd, "Ship the receipt gate", session_id="sess-A")
    assert ledger.goal(cwd, session_id="sess-A") == "Ship the receipt gate"  # 1037-1038
    assert ledger.goal(cwd, session_id="sess-B") == ""  # own goal only
    assert ledger.goal(cwd, session_id="unknown") == ""  # non-isolatable -> 1039
    assert ledger.goal(cwd, session_id="") == ""  # empty session -> 1039
    assert ledger.goal(cwd) == "Ship the receipt gate"  # project fallback -> 1042


# ---------------------------------------------------------------------------
# receipt / verification turn-scoping skips
# ---------------------------------------------------------------------------


def _append_receipt(
    ledger,
    cwd,
    *,
    turn_id,
    receipt_class="test",
    status="pass",
    passed=1,
    failed=0,
    fingerprint="",
    key=None,
):
    return ledger.append(
        cwd,
        "tool_result",
        dedupe_key=key,
        turn_id=turn_id,
        tool="Bash",
        receipt_class=receipt_class,
        receipt_status=status,
        receipt_passed=passed,
        receipt_failed=failed,
        receipt_fp=fingerprint,
    )


def test_has_fresh_receipt_skips_other_turn(tmp_path):
    ledger = _ledger(tmp_path)
    cwd = str(tmp_path)
    _append_receipt(ledger, cwd, turn_id="turn-OTHER", key="o")
    # Different turn -> skipped inside _receipts (1086->1087).
    assert ledger.has_fresh_receipt(cwd, "turn-1", ("test",)) is False


def test_receipt_for_fingerprint_skips_noise_and_invalid(tmp_path):
    ledger = _ledger(tmp_path)
    cwd = str(tmp_path)
    ledger.append(cwd, "decision", text="noise")  # non-tool_result -> 1126->1127
    _append_receipt(
        ledger, cwd, turn_id="t", receipt_class="bogus", fingerprint="beef", key="b"
    )
    # Matching fp but invalid class -> _receipt_from_event None (1131->1125).
    assert ledger.receipt_for_fingerprint(cwd, "beef") is None


def test_last_failed_fingerprint_skips_non_tool_result(tmp_path):
    ledger = _ledger(tmp_path)
    cwd = str(tmp_path)
    ledger.append(cwd, "decision", text="noise")  # 1150->1151
    fp = L.argv_fingerprint("pytest -q tests/x.py")
    _append_receipt(ledger, cwd, turn_id="t", status="fail", fingerprint=fp, key="f")
    assert ledger.last_failed_fingerprint(cwd) == fp


def test_has_verification_skips_other_turn_legacy_flag(tmp_path):
    ledger = _ledger(tmp_path)
    cwd = str(tmp_path)
    ledger.append(cwd, "decision", text="noise")  # non-tool_result -> 1170->1171
    ledger.append(cwd, "tool_result", turn_id="turn-OTHER", tool="Bash", verified=True)
    # Scoped to turn-1: the other turn's verified flag is skipped (1172->1173).
    assert ledger.has_verification(cwd, "turn-1") is False
    assert ledger.has_verification(cwd) is True  # unscoped still sees it


# ---------------------------------------------------------------------------
# taint_dependents — a matching edge on a seq-0 event is not counted
# ---------------------------------------------------------------------------


def test_taint_dependents_ignores_zero_seq_match(tmp_path):
    ledger = _ledger(tmp_path)
    cwd = str(tmp_path)
    target = ledger._events(cwd)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps({"seq": 0, "kind": "decision", "derived_from": ["ref0"]}) + "\n",
        encoding="utf-8",
    )
    assert ledger.taint_dependents(cwd, "ref0") == []  # 1201->1195 (if seq: False)


# ---------------------------------------------------------------------------
# _find_legacy / _legacy_events — legacy migration read paths
# ---------------------------------------------------------------------------


def test_find_legacy_glob_oserror_returns_empty(tmp_path, monkeypatch):
    legacy_root = tmp_path / "legacy"
    legacy_root.mkdir()
    ledger = EventLedger(tmp_path / "state", legacy_root=legacy_root)
    cwd = str(tmp_path)

    def boom_glob(self, *a, **k):
        raise OSError("glob failed")

    monkeypatch.setattr(type(legacy_root), "glob", boom_glob)
    assert ledger._find_legacy(cwd) == ({}, None)  # 1228-1231


def test_find_legacy_skips_non_dict_state(tmp_path):
    legacy_root = tmp_path / "legacy"
    proj = legacy_root / "proj1"
    proj.mkdir(parents=True)
    (proj / "state.json").write_text("[1, 2, 3]", encoding="utf-8")  # non-dict
    ledger = EventLedger(tmp_path / "state", legacy_root=legacy_root)
    assert ledger._find_legacy(str(tmp_path)) == ({}, None)  # 1234-1235


def _legacy_ledger(tmp_path, *, project, events_text=None, events_is_dir=False):
    legacy_root = tmp_path / "legacy"
    proj = legacy_root / "proj1"
    proj.mkdir(parents=True)
    (proj / "state.json").write_text(
        json.dumps({"project": project, "seq": 3}), encoding="utf-8"
    )
    if events_is_dir:
        (proj / "events.jsonl").mkdir()
    elif events_text is not None:
        (proj / "events.jsonl").write_text(events_text, encoding="utf-8")
    ledger = EventLedger(tmp_path / "state", legacy_root=legacy_root)
    return ledger, proj


def test_legacy_events_no_events_file(tmp_path):
    ledger, _proj = _legacy_ledger(tmp_path, project=str(tmp_path))
    assert ledger._legacy_events(str(tmp_path)) == []  # 1259-1260


def test_legacy_events_unreadable_file(tmp_path):
    ledger, _proj = _legacy_ledger(tmp_path, project=str(tmp_path), events_is_dir=True)
    assert ledger._legacy_events(str(tmp_path)) == []  # 1267-1268


def test_legacy_events_parses_and_skips_noise(tmp_path):
    ledger, _proj = _legacy_ledger(
        tmp_path,
        project=str(tmp_path),
        events_text=(
            "\n"  # blank -> 1264->1265 (line.strip() False)
            "not json\n"  # ValueError -> 1273-1274
            "[1, 2, 3]\n"  # valid JSON, non-dict -> 1275->1276
            '{"kind":"decision","text":"legacy-d"}\n'  # dict -> append 1279
        ),
    )
    events = ledger._legacy_events(str(tmp_path))
    assert len(events) == 1
    assert events[0]["kind"] == "decision"
    assert events[0]["text"] == "legacy-d"


def test_legacy_events_skips_non_dict_sanitized(tmp_path, monkeypatch):
    ledger, _proj = _legacy_ledger(
        tmp_path,
        project=str(tmp_path),
        events_text='{"kind":"decision","text":"d"}\n',
    )
    # Force a non-dict sanitize result so the defensive skip fires (1278->1270).
    monkeypatch.setattr(L, "_sanitize_value", lambda value, depth=0: ["not-a-dict"])
    assert ledger._legacy_events(str(tmp_path)) == []
