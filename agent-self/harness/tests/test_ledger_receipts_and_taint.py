from __future__ import annotations

import pytest

from harness.ledger import (
    CLAIM_RECEIPT_MAP,
    RECEIPT_CLASSES,
    STAKE_TIERS,
    EventLedger,
    Receipt,
    argv_fingerprint,
    classify_receipt,
)


# ---------------------------------------------------------------------------
# SI-1 shared-interface contract (names + shapes other lanes depend on)
# ---------------------------------------------------------------------------


def test_receipt_classes_match_shared_interface():
    assert RECEIPT_CLASSES == (
        "test",
        "build",
        "lint",
        "typecheck",
        "coverage",
        "run",
        "e2e",
        "health",
    )


def test_claim_receipt_map_and_stake_tiers_match_shared_interface():
    # The mappings the ClaimWarning v2 consumer lane keys off of.
    for family, classes in (
        ("tests_pass", ("test",)),
        ("fixed", ("test", "run")),
        ("builds", ("build", "typecheck")),
        ("type_clean", ("typecheck",)),
        ("coverage", ("coverage",)),
        ("healthy", ("health",)),
    ):
        assert CLAIM_RECEIPT_MAP[family] == classes
    # Every mapped class is a real receipt class.
    for classes in CLAIM_RECEIPT_MAP.values():
        assert set(classes) <= set(RECEIPT_CLASSES)
    assert STAKE_TIERS == {
        "routine": "preponderance",
        "multifile": "clear_and_convincing",
        "irreversible": "beyond_reasonable_doubt",
    }


def test_receipt_is_frozen_dataclass_with_expected_fields():
    receipt = Receipt("test", "pass", 5, 0, "fp", 3, "2026-07-12T00:00:00")
    assert receipt.receipt_class == "test"
    assert (receipt.passed, receipt.failed, receipt.seq) == (5, 0, 3)
    with pytest.raises(Exception):
        receipt.status = "fail"  # type: ignore[misc]  # frozen


# ---------------------------------------------------------------------------
# classify_receipt — pure classification (argv + exit + parsed counts)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "command,expected",
    [
        ("pytest -q", "test"),
        ("python -m pytest tests/", "test"),
        ("npm test", "test"),
        ("go test ./...", "test"),
        ("pytest --cov=src --cov-report=term", "coverage"),
        ("jest --coverage", "coverage"),
        ("npx playwright test", "e2e"),
        ("cypress run", "e2e"),
        ("tsc --noEmit", "typecheck"),
        ("mypy src", "typecheck"),
        ("basedpyright", "typecheck"),
        ("eslint .", "lint"),
        ("ruff check .", "lint"),
        ("npm run build", "build"),
        ("cargo build --release", "build"),
        ("make -j4", "build"),
        ("python app.py", "run"),
        ("node server.js", "run"),
        ("curl -sf http://localhost:8000/health", "health"),
        ("curl http://localhost:8000/readyz", "health"),
    ],
)
def test_classify_receipt_class_detection(command, expected):
    receipt = classify_receipt("Bash", {"command": command}, {"exit_code": 0})
    assert receipt is not None
    assert receipt.receipt_class == expected


def test_classify_receipt_parses_pass_counts_and_status():
    receipt = classify_receipt(
        "Bash",
        {"command": "pytest -q"},
        {"exit_code": 0, "output": "42 passed in 1.2s"},
    )
    assert receipt is not None
    assert receipt.status == "pass"
    assert receipt.passed == 42
    assert receipt.failed == 0


def test_classify_receipt_fails_on_nonzero_exit():
    receipt = classify_receipt(
        "Bash", {"command": "pytest -q"}, {"exit_code": 1, "output": "boom"}
    )
    assert receipt is not None
    assert receipt.status == "fail"


def test_classify_receipt_fails_on_failed_count_despite_exit_zero():
    # A parsed failure count overrides a (contradictory) zero exit code.
    receipt = classify_receipt(
        "Bash",
        {"command": "jest"},
        {"exit_code": 0, "output": "Tests: 1 failed, 40 passed"},
    )
    assert receipt is not None
    assert receipt.status == "fail"
    assert receipt.failed == 1
    assert receipt.passed == 40


def test_classify_receipt_health_pass_from_text_without_exit_code():
    receipt = classify_receipt(
        "Bash", {"command": "curl http://x/health"}, {"output": "status: healthy"}
    )
    assert receipt is not None
    assert receipt.receipt_class == "health"
    assert receipt.status == "pass"


def test_classify_receipt_status_unknown_when_no_signal():
    receipt = classify_receipt(
        "Bash", {"command": "python app.py"}, {"output": "started"}
    )
    assert receipt is not None
    assert receipt.status == "unknown"


@pytest.mark.parametrize(
    "tool_name,tool_input",
    [
        ("Write", {"file_path": "a.py", "content": "print(1)"}),
        ("Edit", {"file_path": "a.py", "old_string": "x", "new_string": "y"}),
        ("Bash", {"command": "ls -la"}),
        ("Bash", {"command": "git status"}),
        ("Bash", {"command": "cd /tmp"}),
        ("Read", {"file_path": "a.py"}),
    ],
)
def test_classify_receipt_returns_none_for_noncommand_or_unclassifiable(
    tool_name, tool_input
):
    assert classify_receipt(tool_name, tool_input, {"exit_code": 0}) is None


def test_classify_receipt_accepts_bare_string_command():
    receipt = classify_receipt(
        "Bash", "pytest -q", {"exit_code": 0, "output": "3 passed"}
    )
    assert receipt is not None
    assert receipt.receipt_class == "test"


def test_classify_receipt_is_pure_seq_and_ts_are_placeholders():
    receipt = classify_receipt("Bash", {"command": "pytest"}, {"exit_code": 0})
    assert receipt is not None
    assert receipt.seq == 0
    assert receipt.ts == ""


def test_argv_fingerprint_is_stable_under_whitespace_and_distinguishes():
    assert argv_fingerprint("pytest  -q   tests/") == argv_fingerprint(
        "pytest -q tests/"
    )
    assert argv_fingerprint("pytest -q") != argv_fingerprint("pytest -x")
    # sha256 hex — 64 chars, redaction-safe.
    fp = argv_fingerprint("pytest -q")
    assert len(fp) == 64
    assert all(c in "0123456789abcdef" for c in fp)


# ---------------------------------------------------------------------------
# Ledger query surface: mutations, freshness, fingerprint lookup
# ---------------------------------------------------------------------------


def _ledger(tmp_path):
    return EventLedger(tmp_path / "state", legacy_root=tmp_path / "no-legacy")


def test_last_mutation_seq_tracks_mutation_events(tmp_path):
    ledger = _ledger(tmp_path)
    cwd = str(tmp_path)
    assert ledger.last_mutation_seq(cwd) == 0
    ledger.append(cwd, "tool_result", turn_id="turn-1", tool="Bash", verified=False)
    m1 = ledger.append(cwd, "mutation", turn_id="turn-1", path="src/a.py")
    assert ledger.last_mutation_seq(cwd) == m1["seq"]
    assert ledger.last_mutation_seq(cwd, "turn-1") == m1["seq"]
    # A different turn's mutation is excluded when scoping to turn-1.
    ledger.append(cwd, "mutation", turn_id="turn-OTHER", path="src/b.py")
    assert ledger.last_mutation_seq(cwd, "turn-1") == m1["seq"]


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
    verified=None,
    key=None,
):
    fields = {
        "turn_id": turn_id,
        "tool": "Bash",
        "receipt_class": receipt_class,
        "receipt_status": status,
        "receipt_passed": passed,
        "receipt_failed": failed,
        "receipt_fp": fingerprint,
    }
    if verified is not None:  # pragma: no cover
        fields["verified"] = verified
    return ledger.append(cwd, "tool_result", dedupe_key=key, **fields)


def test_has_fresh_receipt_kills_stale_green(tmp_path):
    ledger = _ledger(tmp_path)
    cwd = str(tmp_path)
    # A green receipt, THEN a file mutation -> the receipt is now stale.
    _append_receipt(ledger, cwd, turn_id="turn-1", key="r1")
    ledger.append(cwd, "mutation", turn_id="turn-1", path="src/a.py")
    assert ledger.has_fresh_receipt(cwd, "turn-1", ("test",)) is False
    # A new green receipt AFTER the mutation is fresh again.
    _append_receipt(ledger, cwd, turn_id="turn-1", key="r2")
    assert ledger.has_fresh_receipt(cwd, "turn-1", ("test",)) is True


def test_has_fresh_receipt_requires_pass_status(tmp_path):
    ledger = _ledger(tmp_path)
    cwd = str(tmp_path)
    _append_receipt(ledger, cwd, turn_id="turn-1", status="fail", key="rf")
    assert ledger.has_fresh_receipt(cwd, "turn-1", ("test",)) is False


def test_has_fresh_receipt_any_of_semantics(tmp_path):
    ledger = _ledger(tmp_path)
    cwd = str(tmp_path)
    # Only a 'run' receipt exists; required=("test","run") should match via run.
    _append_receipt(ledger, cwd, turn_id="turn-1", receipt_class="run", key="rr")
    assert ledger.has_fresh_receipt(cwd, "turn-1", ("test", "run")) is True
    assert ledger.has_fresh_receipt(cwd, "turn-1", ("build",)) is False
    assert ledger.has_fresh_receipt(cwd, "turn-1", ()) is False


def test_has_fresh_receipt_respects_min_seq(tmp_path):
    ledger = _ledger(tmp_path)
    cwd = str(tmp_path)
    receipt_event = _append_receipt(ledger, cwd, turn_id="turn-1", key="rm")
    seq = receipt_event["seq"]
    assert ledger.has_fresh_receipt(cwd, "turn-1", ("test",), min_seq=seq - 1) is True
    # min_seq at/after the receipt seq raises the floor above it -> not fresh.
    assert ledger.has_fresh_receipt(cwd, "turn-1", ("test",), min_seq=seq) is False


def test_receipt_for_fingerprint_roundtrip_survives_sanitizer(tmp_path):
    ledger = _ledger(tmp_path)
    cwd = str(tmp_path)
    fp = argv_fingerprint("pytest -q tests/failing.py")
    _append_receipt(
        ledger, cwd, turn_id="turn-1", status="fail", fingerprint=fp, key="fp1"
    )
    found = ledger.receipt_for_fingerprint(cwd, fp)
    assert found is not None
    assert found.fingerprint == fp
    assert found.status == "fail"
    assert ledger.receipt_for_fingerprint(cwd, "deadbeef") is None
    assert ledger.receipt_for_fingerprint(cwd, "") is None


def test_receipt_for_fingerprint_returns_latest(tmp_path):
    ledger = _ledger(tmp_path)
    cwd = str(tmp_path)
    fp = argv_fingerprint("pytest -q")
    _append_receipt(ledger, cwd, turn_id="t", status="fail", fingerprint=fp, key="a")
    _append_receipt(ledger, cwd, turn_id="t", status="pass", fingerprint=fp, key="b")
    found = ledger.receipt_for_fingerprint(cwd, fp)
    assert found is not None
    assert found.status == "pass"  # the newer (re-run green) receipt


# ---------------------------------------------------------------------------
# last_failed_fingerprint — the repro-gate's "which argv was failing?" query
# ---------------------------------------------------------------------------


def test_last_failed_fingerprint_returns_latest_failure(tmp_path):
    ledger = _ledger(tmp_path)
    cwd = str(tmp_path)
    assert ledger.last_failed_fingerprint(cwd) is None  # empty ledger
    fp1 = argv_fingerprint("pytest -q tests/a.py")
    fp2 = argv_fingerprint("pytest -q tests/b.py")
    _append_receipt(ledger, cwd, turn_id="t", status="fail", fingerprint=fp1, key="f1")
    _append_receipt(ledger, cwd, turn_id="t", status="fail", fingerprint=fp2, key="f2")
    # The most recent FAILED receipt's fingerprint wins.
    assert ledger.last_failed_fingerprint(cwd) == fp2
    assert ledger.last_failed_fingerprint(cwd, "t") == fp2


def test_last_failed_fingerprint_ignores_pass_and_empty_fp(tmp_path):
    ledger = _ledger(tmp_path)
    cwd = str(tmp_path)
    # A pass receipt and a fail receipt with no fingerprint are both ignored.
    _append_receipt(
        ledger,
        cwd,
        turn_id="t",
        status="pass",
        fingerprint=argv_fingerprint("pytest -q"),
        key="p",
    )
    _append_receipt(ledger, cwd, turn_id="t", status="fail", fingerprint="", key="nofp")
    assert ledger.last_failed_fingerprint(cwd) is None


def test_last_failed_fingerprint_respects_turn_scope(tmp_path):
    ledger = _ledger(tmp_path)
    cwd = str(tmp_path)
    fp = argv_fingerprint("pytest -q tests/scoped.py")
    _append_receipt(
        ledger, cwd, turn_id="turn-OTHER", status="fail", fingerprint=fp, key="o"
    )
    # Scoping to a different turn excludes the other turn's failure...
    assert ledger.last_failed_fingerprint(cwd, "turn-1") is None
    # ...but the unscoped query (empty turn_id) still sees it.
    assert ledger.last_failed_fingerprint(cwd) == fp


def test_last_failed_fingerprint_pairs_with_receipt_for_fingerprint(tmp_path):
    # The repro-gate combo: after a fail THEN a green rerun of the SAME argv, the
    # failing fingerprint stays discoverable, and receipt_for_fingerprint reports
    # the newer pass (so the gate correctly stays quiet).
    ledger = _ledger(tmp_path)
    cwd = str(tmp_path)
    fp = argv_fingerprint("pytest -q tests/fixed.py")
    _append_receipt(ledger, cwd, turn_id="t", status="fail", fingerprint=fp, key="fail")
    _append_receipt(
        ledger, cwd, turn_id="t", status="pass", fingerprint=fp, key="green"
    )
    assert ledger.last_failed_fingerprint(cwd) == fp
    receipt = ledger.receipt_for_fingerprint(cwd, fp)
    assert receipt is not None and receipt.status == "pass"


def test_last_failed_fingerprint_is_fail_open(tmp_path, monkeypatch):
    ledger = _ledger(tmp_path)
    cwd = str(tmp_path)

    def boom(*_a, **_k):
        raise OSError("simulated scan failure")

    monkeypatch.setattr(ledger, "_scan_events", boom)
    assert ledger.last_failed_fingerprint(cwd) is None  # must not raise


# ---------------------------------------------------------------------------
# has_verification back-compat shim
# ---------------------------------------------------------------------------


def test_has_verification_backcompat_legacy_verified(tmp_path):
    ledger = _ledger(tmp_path)
    cwd = str(tmp_path)
    # Legacy tool_result with verified==True and NO typed receipt fields.
    ledger.append(cwd, "tool_result", turn_id="turn-1", tool="Bash", verified=True)
    assert ledger.has_verification(cwd, "turn-1") is True
    assert ledger.has_verification(cwd) is True


def test_has_verification_uses_typed_receipt_and_freshness(tmp_path):
    ledger = _ledger(tmp_path)
    cwd = str(tmp_path)
    # Typed pass receipt, no legacy verified flag.
    _append_receipt(ledger, cwd, turn_id="turn-1", key="v1")
    assert ledger.has_verification(cwd, "turn-1") is True
    # A later mutation makes the typed receipt stale AND there is no legacy
    # verified fallback -> has_verification goes False.
    ledger.append(cwd, "mutation", turn_id="turn-1", path="src/a.py")
    assert ledger.has_verification(cwd, "turn-1") is False


def test_has_verification_false_on_empty_ledger(tmp_path):
    ledger = _ledger(tmp_path)
    assert ledger.has_verification(str(tmp_path), "turn-1") is False


# ---------------------------------------------------------------------------
# State reducers still project decisions/failures/milestones; mutation tracked
# ---------------------------------------------------------------------------


def test_mutation_tracked_in_state_without_breaking_reducers(tmp_path):
    ledger = _ledger(tmp_path)
    cwd = str(tmp_path)
    ledger.append(cwd, "decision", text="Adopt the receipt gate")
    fail_event = ledger.append(
        cwd, "failure", text="offset drift", preconditions="post-update"
    )
    mut = ledger.append(cwd, "mutation", turn_id="turn-1", path="lib/x.so")
    ledger.append(
        cwd, "milestone", text="drift resolved", supersedes_failures=[fail_event["seq"]]
    )

    state = ledger.state(cwd)
    # Existing reducers unaffected: decision present, failure superseded away.
    assert any(d["text"] == "Adopt the receipt gate" for d in state["decisions"])
    assert all(f.get("seq") != fail_event["seq"] for f in state["open_failures"])
    # New mutation tracking present.
    assert state["last_mutation_seq"] == mut["seq"]
    assert state["last_mutation_ts"]


def test_state_projection_matches_incremental_after_reload(tmp_path):
    ledger = _ledger(tmp_path)
    cwd = str(tmp_path)
    ledger.append(cwd, "mutation", turn_id="turn-1", path="a.py")
    ledger.append(cwd, "decision", text="keep it")
    incremental = ledger.state(cwd)  # state.json path
    # Force full re-projection from events on a fresh instance.
    fresh = _ledger(tmp_path)
    (fresh._dir(cwd) / "state.json").unlink(missing_ok=True)
    projected = fresh.state(cwd)
    assert projected["last_mutation_seq"] == incremental["last_mutation_seq"]
    assert projected["seq"] == incremental["seq"]


# ---------------------------------------------------------------------------
# B4 · taint propagation on derived_from provenance edges
# ---------------------------------------------------------------------------


def test_taint_dependents_returns_seqs_and_writes_marker(tmp_path):
    ledger = _ledger(tmp_path)
    cwd = str(tmp_path)
    ref = "offset:0x668C70"
    dep1 = ledger.append(
        cwd, "decision", text="hook via offset", derived_from=[ref, "other"]
    )
    dep2 = ledger.append(cwd, "failure", text="trainer crashed", derived_from=[ref])
    ledger.append(cwd, "decision", text="unrelated", derived_from=["something-else"])

    tainted = ledger.taint_dependents(cwd, ref)

    assert tainted == sorted([dep1["seq"], dep2["seq"]])
    markers = [e for e in ledger.replay(cwd, limit=50) if e.get("kind") == "taint"]
    assert len(markers) == 1
    assert markers[0]["falsified_ref"] == ref
    assert markers[0]["tainted_seqs"] == tainted


def test_taint_dependents_empty_ref_and_no_dependents(tmp_path):
    ledger = _ledger(tmp_path)
    cwd = str(tmp_path)
    assert ledger.taint_dependents(cwd, "") == []
    ledger.append(cwd, "decision", text="no provenance")
    assert ledger.taint_dependents(cwd, "nonexistent-ref") == []


def test_taint_dependents_is_fail_open_when_append_raises(tmp_path, monkeypatch):
    ledger = _ledger(tmp_path)
    cwd = str(tmp_path)
    ref = "seq:5"
    dep = ledger.append(cwd, "decision", text="derived", derived_from=[ref])

    real_append = ledger.append

    def flaky_append(cwd_, kind, **kwargs):
        if kind == "taint":
            raise OSError("simulated marker write failure")
        return real_append(cwd_, kind, **kwargs)  # pragma: no cover

    monkeypatch.setattr(ledger, "append", flaky_append)
    # Must not raise; still returns the discovered dependents.
    assert ledger.taint_dependents(cwd, ref) == [dep["seq"]]


def test_taint_dependents_ignores_nonlist_derived_from(tmp_path):
    ledger = _ledger(tmp_path)
    cwd = str(tmp_path)
    # derived_from stored as a scalar string must not crash the scan.
    ledger.append(cwd, "decision", text="scalar", derived_from="ref-as-string")
    assert ledger.taint_dependents(cwd, "ref-as-string") == []


def test_receipt_fields_do_not_leak_raw_argv_or_secrets(tmp_path):
    ledger = _ledger(tmp_path)
    cwd = str(tmp_path)
    secret = "sk-proj-abcdefghijklmnopqrstuvwxyz1234567890"
    # classify only stores class/status/counts/fingerprint — never the raw argv.
    receipt = classify_receipt(
        "Bash",
        {"command": f"pytest -q # {secret}"},
        {"exit_code": 0, "output": "1 passed"},
    )
    assert receipt is not None
    _append_receipt(
        ledger,
        cwd,
        turn_id="t",
        status=receipt.status,
        fingerprint=receipt.fingerprint,
        key="s1",
    )
    serialized = ledger._events(cwd).read_text(encoding="utf-8")
    assert secret not in serialized
    # The fingerprint is retrievable (hex survived the sanitizer intact).
    assert ledger.receipt_for_fingerprint(cwd, receipt.fingerprint) is not None
