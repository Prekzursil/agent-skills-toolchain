"""CC-0009 tests: register-on-write + consumer-read gate.

Catalog tests_required (verbatim):

  1. An artifact written without registration must fail the predicate.
  2. A manifest entry whose path does not exist must fail
     (a file path in text is not proof the file exists).
  3. A manifest entry that exists but does not parse with its declared consumer must fail.
  4. Both-states: all currently-valid entries must pass, so the gate is not simply always-red.

Reviewer requirement (independent): add a phantom manifest entry and confirm rejection.
That control is also exercised here as a detector proof; the receipt stays BLOCKED until an
independent reviewer re-runs it.
"""

from __future__ import annotations

import json
import sys
from copy import deepcopy
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

# Pull the shared ``case`` fixture (and Case type) from the reducer suite so the
# two condition-11 reducer-integration tests below can run as a standalone module.
pytest_plugins = ["test_completion_predicate"]

from artifact_manifest_gate import (  # noqa: E402
    DEFAULT_MANIFEST,
    GATE_ID,
    infer_consumer,
    probe_manifest_consumers,
    register_on_write,
    write_manifest_atomic,
)
from completion_predicate import (  # noqa: E402
    Outcome,
    PredicateOptions,
    Verdict,
    evaluate,
)
from test_completion_predicate import Case  # noqa: E402

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]


@pytest.fixture
def case(tmp_path: Path) -> Case:
    return Case(tmp_path)


# --------------------------------------------------------------------------- catalog tests_required


def test_artifact_written_without_registration_fails_predicate(case: Case) -> None:
    """tests_required[0]: unregistered artifact -> condition 11 UNSATISFIED."""
    # Write a second artifact that is NOT registered in the manifest.
    orphan_rel = "out/orphan-unregistered.json"
    orphan = {
        "unit_id": "ORPHAN",
        "verdict": "CONFIRMED",
        "body": "written to disk but never registered. " * 20,
        "sentinel": case.receipt["sentinel"],
    }
    (case.root / orphan_rel).write_text(json.dumps(orphan, indent=1), encoding="utf-8")

    r = deepcopy(case.receipt)
    r["artifacts"] = [
        {
            "path": orphan_rel,
            "bytes": (case.root / orphan_rel).stat().st_size,
            "sha256": __import__("hashlib")
            .sha256((case.root / orphan_rel).read_bytes())
            .hexdigest(),
            "exists": True,
            "role": "primary",
            "eol": "LF",
        }
    ]
    # Keep sentinel search happy: put the sentinel into the orphan body already done.
    result = evaluate(r, case.options())
    assert result.verdict is Verdict.INCOMPLETE
    assert 11 in result.unsatisfied
    assert result.condition(11).outcome is Outcome.UNSATISFIED
    assert "not registered" in result.condition(11).basis


def test_manifest_entry_whose_path_does_not_exist_must_fail(tmp_path: Path) -> None:
    """tests_required[1]: registered-but-absent fails the consumer probe AND condition 11."""
    root = tmp_path
    (root / "out").mkdir()
    good = root / "out" / "good.json"
    good.write_text(json.dumps({"ok": True, "n": 1}), encoding="utf-8")
    register_on_write(root, "out/good.json", consumer="json.loads", manifest_rel="out/M.json")

    # Plant a phantom path (reviewer control shape).
    man = json.loads((root / "out/M.json").read_text(encoding="utf-8"))
    man["artifacts"].append(
        {
            "path": "out/PHANTOM-DOES-NOT-EXIST.json",
            "present": True,
            "bytes": 1,
            "sha256": "a" * 64,
            "consumer": "json.loads",
        }
    )
    write_manifest_atomic(root / "out/M.json", man)

    report = probe_manifest_consumers(root, manifest_rel="out/M.json")
    assert report.ok is False
    absent = [r for r in report.failing if "PHANTOM" in r.path]
    assert absent, report.to_dict()
    assert absent[0].exists is False
    assert "registered-but-absent" in absent[0].summary


def test_exists_but_does_not_parse_with_declared_consumer_must_fail(
    tmp_path: Path,
) -> None:
    """tests_required[2]: present bytes that the declared consumer cannot parse -> fail."""
    root = tmp_path
    (root / "out").mkdir()
    bad = root / "out" / "not-json.txt"
    bad.write_text("this is not json {{{", encoding="utf-8")
    # Deliberately declare json.loads against a non-JSON file.
    register_on_write(
        root,
        "out/not-json.txt",
        consumer="json.loads",
        manifest_rel="out/M.json",
    )

    report = probe_manifest_consumers(root, manifest_rel="out/M.json")
    assert report.ok is False
    assert len(report.failing) == 1
    assert report.failing[0].exists is True
    assert report.failing[0].read_ok is False
    assert "json.loads FAILED" in report.failing[0].summary


def test_both_states_currently_valid_entries_pass() -> None:
    """tests_required[3]: live ARTIFACT-MANIFEST.json entries all parse with their consumers.

    Both-states pair: the three red tests above prove the gate can go red; this proves it
    is not simply always-red against the contracted estate manifest.
    """
    report = probe_manifest_consumers(REPO_ROOT, manifest_rel=DEFAULT_MANIFEST)
    assert report.ok, json.dumps(report.to_dict(), indent=2)[:4000]
    assert report.results, "live manifest must list entries"
    # Every contracted entry must have been opened by a named consumer.
    for row in report.results:
        assert row.exists is True
        assert row.read_ok is True
        assert row.consumer
        assert row.summary


# --------------------------------------------------------------------------- supporting controls


def test_register_on_write_refuses_absent_path(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        register_on_write(tmp_path, "no/such/file.json", manifest_rel="M.json")


def test_register_on_write_then_probe_passes(tmp_path: Path) -> None:
    root = tmp_path
    (root / "out").mkdir()
    (root / "out" / "a.json").write_text(
        json.dumps({"hello": "world", "n": 2}), encoding="utf-8"
    )
    entry = register_on_write(
        root, "out/a.json", consumer="json.loads", manifest_rel="out/M.json", unit_id="CC-0009"
    )
    assert entry["consumer"] == "json.loads"
    assert entry["present"] is True
    report = probe_manifest_consumers(root, manifest_rel="out/M.json")
    assert report.ok
    assert report.results[0].summary.startswith("json.loads ok")


def test_phantom_entry_also_fails_condition_11_reverse_check(case: Case) -> None:
    """Independent-reviewer control shape, exercised against the shared reducer.

    Adding a phantom path to the manifest must make condition 11 UNSATISFIED even when
    every receipt primary remains registered and present.
    """
    manifest = json.loads((case.root / case.manifest_rel).read_text(encoding="utf-8"))
    manifest["artifacts"].append(
        {
            "path": "out/REVIEWER-PHANTOM.json",
            "present": True,
            "bytes": 12,
            "sha256": "b" * 64,
        }
    )
    (case.root / case.manifest_rel).write_text(
        json.dumps(manifest, indent=1), encoding="utf-8"
    )
    result = evaluate(case.receipt, case.options())
    assert result.condition(11).outcome is Outcome.UNSATISFIED
    assert "registered-but-absent" in result.condition(11).basis


def test_infer_consumer_honours_explicit_and_self() -> None:
    assert infer_consumer("x.md") == "utf8-text"
    assert infer_consumer("x.json") == "json.loads"
    assert infer_consumer("x.jsonl") == "jsonl"
    assert (
        infer_consumer(
            "command-center/ARTIFACT-MANIFEST.json",
            {"sha256": "(self)"},
        )
        == "self-manifest"
    )
    assert infer_consumer("x.bin", {"consumer": "json.loads"}) == "json.loads"


def test_gate_id_is_stable() -> None:
    assert GATE_ID.startswith("platform/lib/artifact_manifest_gate.py@")
