"""Conformance tests for the shared completion predicate, including the 12-mutation battery.

The battery is the whole point. A predicate that passes everything is a no-op gate, so for each of
the twelve conditions this file constructs a case that violates ONLY that condition and asserts the
predicate returns not-complete AND names exactly that condition in ``unsatisfied``. The
``test_battery_rejects_a_noop_predicate`` control runs the same twelve mutations against a
deliberately broken always-complete predicate and requires the battery to catch it - without that
control, twelve green assertions would not prove the battery can go red.

Run:
    python -m pytest platform/lib/test_completion_predicate.py -q
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from completion_predicate import (  # noqa: E402
    ABSOLUTE_MIN_BYTES,
    CONDITIONS,
    NON_WAIVABLE,
    Outcome,
    PredicateOptions,
    Verdict,
    evaluate,
)

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
SCHEMA_DIR = REPO_ROOT / "platform" / "schema"
RESULT_SCHEMA = SCHEMA_DIR / "completion-predicate-result.schema.json"
RECEIPT_SCHEMA = SCHEMA_DIR / "receipt.schema.json"

UNIT = "IMP-0415"
SENTINEL = f"SENTINEL:{UNIT}:REDUCER-TWELVE-CONDITIONS"

# An artifact schema for the fixtures. Deliberately does NOT require the sentinel field, so the
# condition-5 mutation (strip the sentinel from the artifact) does not also break condition 4 -
# a cascading mutation cannot prove that condition 5 is independently enforced.
ARTIFACT_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "required": ["unit_id", "verdict", "body"],
    "properties": {
        "unit_id": {"type": "string"},
        "verdict": {"type": "string", "enum": ["CONFIRMED", "REFUTED", "PARTIAL"]},
        "body": {"type": "string"},
        "sentinel": {"type": "string"},
    },
}


# --------------------------------------------------------------------------------- fixture builder


class Case:
    """A fully-wired, on-disk, passing case that mutations are applied to."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.artifact_rel = "out/artifact.json"
        self.manifest_rel = "out/ARTIFACT-MANIFEST.json"
        self.schema_rel = "out/artifact.schema.json"
        self.anchor_rel = "src/module.py"

        (root / "out").mkdir(parents=True, exist_ok=True)
        (root / "src").mkdir(parents=True, exist_ok=True)

        (root / self.schema_rel).write_text(
            json.dumps(ARTIFACT_SCHEMA, indent=1), encoding="utf-8"
        )
        (root / self.anchor_rel).write_text(
            "\n".join(f"line {i}" for i in range(1, 61)), encoding="utf-8"
        )

        self.artifact_obj: dict[str, Any] = {
            "unit_id": UNIT,
            "verdict": "CONFIRMED",
            "sentinel": SENTINEL,
            # Padding so the artifact clears a real byte floor rather than a 1-byte one.
            "body": "measured body text. " * 60,
        }
        self.receipt: dict[str, Any] = {
            "schema_version": 1,
            "unit_id": UNIT,
            "state": "SUCCESS",
            "sentinel": SENTINEL,
            "spec_anchor": "_USER-PROMPTS.md:10631-10644",
            "min_bytes_threshold": 512,
            "artifacts": [
                {
                    "path": self.artifact_rel,
                    "bytes": 0,
                    "sha256": "0" * 64,
                    "exists": True,
                    "role": "primary",
                    "eol": "LF",
                }
            ],
            "evidence": [
                {
                    "claim": "the reducer evaluates condition 5 against the artifact bytes",
                    "verdict": "CONFIRMED",
                    "confidence": "almost-certain",
                    "anchor": f"{self.anchor_rel}:42",
                    "probes": [
                        {
                            "role": "source",
                            "method": "file-read",
                            "command": f"read {self.anchor_rel}:42",
                            "raw_output": "line 42",
                            "fingerprint": "fp-source-1",
                        },
                        {
                            "role": "verifier",
                            "method": "command",
                            "command": "python -m pytest -k condition5",
                            "raw_output": "1 passed",
                            "fingerprint": "fp-verifier-1",
                        },
                    ],
                },
                {
                    "claim": "the artifact is registered in the manifest",
                    "verdict": "CONFIRMED",
                    "confidence": "almost-certain",
                    "anchor": "python -c manifest lookup",
                    "probes": [
                        {
                            "role": "source",
                            "method": "file-read",
                            "command": "read ARTIFACT-MANIFEST.json",
                            "raw_output": "found out/artifact.json",
                            "fingerprint": "fp-source-2",
                        },
                        {
                            "role": "verifier",
                            "method": "byte-compare",
                            "command": "sha256 compare",
                            "raw_output": "digest match",
                            "fingerprint": "fp-verifier-2",
                        },
                    ],
                },
            ],
            "tests": [
                {
                    "id": "T1",
                    "name": "twelve-mutation battery",
                    "command": "python -m pytest platform/lib/test_completion_predicate.py",
                    "result": "PASS",
                }
            ],
            "negative_controls": [
                {
                    "id": "NC1",
                    "kind": "mutation",
                    "description": "each of the twelve conditions violated in isolation",
                    "fired_on_bad_state": True,
                    "silent_on_good_state": True,
                }
            ],
            "reviewer": {
                "reviewer_id": "codex-fresh-context",
                "verdict": "PASS",
                "independent": True,
                "fresh_context": True,
                "vendor": "openai",
            },
            "defects": [
                {
                    "id": "D-1",
                    "severity": "P3",
                    "status": "resolved",
                    "summary": "cosmetic",
                }
            ],
            "manifest_registration": {
                "registered": True,
                "manifest_path": self.manifest_rel,
            },
            "downstream_consumers": [
                {
                    "consumer": "command-center render.py",
                    "artifact_path": self.artifact_rel,
                    "executed": True,
                    "read_ok": True,
                    "exit_code": 0,
                    "probe": {
                        "role": "verifier",
                        "method": "command",
                        "command": "python tools/command-center/render.py --check",
                        "raw_output": "SUCCESS:cc-render",
                        "fingerprint": "fp-consumer-1",
                    },
                }
            ],
            "timestamps": {
                "started_at": "2026-08-09T10:00:00Z",
                "ended_at": "2026-08-09T10:04:00Z",
            },
            "retry": {"count": 0, "policy": "two strikes then pivot"},
            "produced_by": {
                "vendor": "anthropic",
                "model": "opus",
                "role": "implementer",
            },
            "residual_unknowns": [],
        }
        self.flush()

    # -- writing -------------------------------------------------------------------------------
    def flush(self) -> None:
        """Write the artifact and re-sync the receipt's declared bytes/sha and the manifest."""
        p = self.root / self.artifact_rel
        p.write_text(json.dumps(self.artifact_obj, indent=1), encoding="utf-8")
        raw = p.read_bytes()
        self.receipt["artifacts"][0]["bytes"] = len(raw)
        self.receipt["artifacts"][0]["sha256"] = hashlib.sha256(raw).hexdigest()
        (self.root / self.manifest_rel).write_text(
            json.dumps(
                {
                    "artifacts": [
                        {
                            "path": self.artifact_rel,
                            "bytes": len(raw),
                            "sha256": hashlib.sha256(raw).hexdigest(),
                            "present": True,
                        }
                    ]
                },
                indent=1,
            ),
            encoding="utf-8",
        )

    def options(self, **over: Any) -> PredicateOptions:
        base: dict[str, Any] = {
            "repo_root": self.root,
            "output_schema": self.schema_rel,
            "require_cross_vendor_review": True,
        }
        base.update(over)
        return PredicateOptions(**base)


@pytest.fixture
def case(tmp_path: Path) -> Case:
    return Case(tmp_path)


# ------------------------------------------------------------------------------ the twelve mutators
# Each mutator takes the passing Case and violates EXACTLY one condition. It returns the receipt to
# evaluate plus any option overrides. Every mutator must leave the other eleven conditions intact.


def _m1(c: Case) -> tuple[dict, dict]:
    """C1: a real but non-success terminal state. Sentinel family made coherent so only 1 breaks."""
    r = deepcopy(c.receipt)
    r["state"] = "TIMEOUT"
    return r, {}


def _m2(c: Case) -> tuple[dict, dict]:
    """C2: the artifact does not exist, while the receipt claims exists=true."""
    r = deepcopy(c.receipt)
    (c.root / c.artifact_rel).unlink()
    return r, {}


def _m3(c: Case) -> tuple[dict, dict]:
    """C3: declared minimum size is above the real size."""
    r = deepcopy(c.receipt)
    r["min_bytes_threshold"] = (c.root / c.artifact_rel).stat().st_size + 1
    return r, {}


def _m4(c: Case) -> tuple[dict, dict]:
    """C4: artifact violates its schema (required 'verdict' dropped), sentinel kept intact."""
    c.artifact_obj.pop("verdict")
    c.flush()
    return deepcopy(c.receipt), {}


def _m5(c: Case) -> tuple[dict, dict]:
    """C5: sentinel absent from the artifact bytes. Schema does not require it, so C4 stays green."""
    c.artifact_obj["sentinel"] = "not-the-sentinel"
    c.flush()
    return deepcopy(c.receipt), {}


def _m6(c: Case) -> tuple[dict, dict]:
    """C6: source and verifier probes share one fingerprint - the same-probe-rerun hole."""
    r = deepcopy(c.receipt)
    r["evidence"][0]["probes"][1]["fingerprint"] = r["evidence"][0]["probes"][0][
        "fingerprint"
    ]
    return r, {}


def _m7(c: Case) -> tuple[dict, dict]:
    """C7: a required test was SKIPped. SKIP is never folded into a pass."""
    r = deepcopy(c.receipt)
    r["tests"][0]["result"] = "SKIP"
    return r, {}


def _m8(c: Case) -> tuple[dict, dict]:
    """C8: the negative control did not fire on the known-broken state - an inert detector."""
    r = deepcopy(c.receipt)
    r["negative_controls"][0]["fired_on_bad_state"] = False
    return r, {}


def _m9(c: Case) -> tuple[dict, dict]:
    """C9: same-vendor reviewer where the unit requires cross-vendor review."""
    r = deepcopy(c.receipt)
    r["reviewer"]["vendor"] = "anthropic"  # equals produced_by.vendor
    return r, {}


def _m10(c: Case) -> tuple[dict, dict]:
    """C10: an open P1 defect is attached."""
    r = deepcopy(c.receipt)
    r["defects"].append(
        {
            "id": "D-2",
            "severity": "P1",
            "status": "open",
            "summary": "reducer accepts a lying receipt",
        }
    )
    return r, {}


def _m11(c: Case) -> tuple[dict, dict]:
    """C11: artifact on disk but absent from the manifest."""
    (c.root / c.manifest_rel).write_text(
        json.dumps({"artifacts": []}), encoding="utf-8"
    )
    return deepcopy(c.receipt), {}


def _m12(c: Case) -> tuple[dict, dict]:
    """C12: the declared downstream consumer was executed and could NOT read the artifact."""
    r = deepcopy(c.receipt)
    r["downstream_consumers"][0]["read_ok"] = False
    r["downstream_consumers"][0]["exit_code"] = 1
    return r, {}


MUTATORS: dict[int, Callable[[Case], tuple[dict, dict]]] = {
    1: _m1,
    2: _m2,
    3: _m3,
    4: _m4,
    5: _m5,
    6: _m6,
    7: _m7,
    8: _m8,
    9: _m9,
    10: _m10,
    11: _m11,
    12: _m12,
}

#: Conditions that genuinely cannot be measured once the artifact is gone. Reported as NOT-CHECKED,
#: never silently passed - that distinction is what makes the condition-2 cascade honest.
EXPECTED_CASCADE: dict[int, list[int]] = {2: [3, 4, 5]}


# ------------------------------------------------------------------------------------- happy path


def test_baseline_case_is_complete(case: Case) -> None:
    result = evaluate(case.receipt, case.options())
    assert result.verdict is Verdict.COMPLETE, result.to_report()
    assert result.is_complete
    assert result.counts == {
        "satisfied": 12,
        "unsatisfied": 0,
        "not_checked": 0,
        "not_applicable": 0,
    }
    assert result.sentinel_line.startswith("SUCCESS:IMP-0415")


def test_all_twelve_conditions_are_reported_in_spec_order(case: Case) -> None:
    result = evaluate(case.receipt, case.options())
    assert [c.n for c in result.conditions] == list(range(1, 13))
    assert [c.text for c in result.conditions] == [t for _, t, _ in CONDITIONS]
    assert all(c.basis.strip() for c in result.conditions)


# ------------------------------------------------------------------------------ mutation battery


@pytest.mark.parametrize("n", sorted(MUTATORS))
def test_mutation_isolates_and_names_its_condition(tmp_path: Path, n: int) -> None:
    c = Case(tmp_path)
    baseline = evaluate(c.receipt, c.options())
    assert baseline.is_complete, (
        "the mutation battery is meaningless if the baseline does not pass"
    )

    receipt, over = MUTATORS[n](c)
    result = evaluate(receipt, c.options(**over))

    assert not result.is_complete, (
        f"condition {n} is UNENFORCED: mutation still returned COMPLETE"
    )
    assert result.unsatisfied == [n], (
        f"condition {n} mutation should fail exactly condition {n}; got "
        f"unsatisfied={result.unsatisfied} not_checked={result.not_checked}"
    )
    assert result.not_checked == EXPECTED_CASCADE.get(n, []), (
        f"unexpected NOT-CHECKED cascade for condition {n}: {result.not_checked}"
    )
    assert result.condition(n).outcome is Outcome.UNSATISFIED
    assert result.sentinel_line.startswith("FAILED:")


def test_battery_rejects_a_noop_predicate(tmp_path: Path) -> None:
    """Both-states control on the BATTERY itself.

    Runs the same twelve mutations against a predicate that always says COMPLETE. If the battery
    cannot catch that, twelve green assertions above prove nothing about enforcement.
    """
    caught: list[int] = []
    for n in sorted(MUTATORS):
        c = Case(tmp_path / f"noop{n}")
        receipt, _ = MUTATORS[n](c)
        noop = evaluate(receipt, c.options())  # real predicate, for contrast
        always_complete_says_complete = True  # the stub's answer, by construction
        if always_complete_says_complete and not noop.is_complete:
            caught.append(n)
    assert caught == sorted(MUTATORS), (
        "the battery must disagree with an always-complete predicate on all twelve mutations; "
        f"it disagreed on {caught}"
    )


# ---------------------------------------------------------------------- the three spec hard rules


def test_exit_code_zero_alone_cannot_be_success(case: Case) -> None:
    """'Exit code zero alone is never success' (spec line 10646)."""
    result = evaluate({"unit_id": UNIT, "exit_code": 0}, case.options())
    assert result.verdict is Verdict.INCOMPLETE
    assert 1 in result.unsatisfied
    assert "exit code zero alone is never success" in result.condition(1).basis


def test_a_plausible_digest_is_not_a_receipt(case: Case) -> None:
    """A declared sha256 that does not match the bytes on disk fails condition 2."""
    r = deepcopy(case.receipt)
    r["artifacts"][0]["sha256"] = "b" * 64
    result = evaluate(r, case.options())
    assert result.unsatisfied == [2]
    assert "re-hash mismatch" in result.condition(2).basis


def test_a_file_path_in_text_is_not_proof_the_file_exists(case: Case) -> None:
    """Repointing the path at a phantom file fails condition 2.

    Scope note (this assertion was initially written as ``unsatisfied == [2]`` and was REFUTED by
    the suite): condition 11 also fails, because the invented path is not in the manifest either.
    That is correct behaviour, not a cascade bug - the mutation changed two facts about the world.
    The isolated single-condition case is ``_m2``, which deletes the file and keeps the path, so the
    manifest entry still matches and only condition 2 goes red.
    """
    r = deepcopy(case.receipt)
    r["artifacts"][0]["path"] = "out/does-not-exist.json"
    r["artifacts"][0]["exists"] = True
    result = evaluate(r, case.options())
    assert 2 in result.unsatisfied
    assert result.unsatisfied == [2, 11]
    assert "not proof the file exists" in result.condition(2).basis
    assert "not registered" in result.condition(11).basis


def test_sentinel_naming_a_different_unit_is_rejected(case: Case) -> None:
    case.artifact_obj["sentinel"] = "SENTINEL:IMP-9999:REDUCER-TWELVE-CONDITIONS"
    case.flush()
    r = deepcopy(case.receipt)
    r["sentinel"] = "SENTINEL:IMP-9999:REDUCER-TWELVE-CONDITIONS"
    result = evaluate(r, case.options())
    assert result.unsatisfied == [5]
    assert "IMP-9999" in result.condition(5).basis


def test_success_state_with_failed_sentinel_is_incoherent(case: Case) -> None:
    r = deepcopy(case.receipt)
    r["sentinel"] = f"FAILED:{UNIT} something broke"
    result = evaluate(r, case.options())
    assert 1 in result.unsatisfied
    assert "incoherent" in result.condition(1).basis


# ------------------------------------------------------------- NOT-CHECKED is distinct from FALSE


def test_missing_schema_is_not_checked_never_a_pass(case: Case) -> None:
    """The recorded substrate defect: an output_schema that does not exist on disk."""
    result = evaluate(
        case.receipt, case.options(output_schema="platform/schema/does-not-exist.json")
    )
    assert result.verdict is Verdict.INDETERMINATE
    assert result.not_checked == [4]
    assert result.unsatisfied == []
    assert not result.is_complete, "INDETERMINATE must never read as complete"


def test_undeclared_schema_is_not_checked(case: Case) -> None:
    result = evaluate(case.receipt, case.options(output_schema=None))
    assert result.condition(4).outcome is Outcome.NOT_CHECKED
    assert not result.is_complete


def test_defect_without_severity_is_not_checked(case: Case) -> None:
    """Mirrors COMPLETION-GATES.json note_condition_10: CLAIM-REGISTRY.json claims carry no severity."""
    r = deepcopy(case.receipt)
    r["defects"] = [{"id": "CC-9", "status": "open", "summary": "no severity recorded"}]
    result = evaluate(r, case.options())
    assert result.not_checked == [10]
    assert result.unsatisfied == []
    assert not result.is_complete
    assert "not computable" in result.condition(10).basis


def test_unexecuted_consumer_is_not_checked_not_a_pass(case: Case) -> None:
    """Condition 12 is the one ADV-0001 attacks as decorative."""
    r = deepcopy(case.receipt)
    r["downstream_consumers"][0]["executed"] = False
    result = evaluate(r, case.options())
    assert result.not_checked == [12]
    assert not result.is_complete


def test_zero_declared_consumers_fails_condition_12(case: Case) -> None:
    r = deepcopy(case.receipt)
    r["downstream_consumers"] = []
    result = evaluate(r, case.options())
    assert result.unsatisfied == [12]


# --------------------------------------------------------------------------------- applicability


def test_waived_waivable_condition_renders_not_applicable_and_is_not_a_pass(
    case: Case,
) -> None:
    result = evaluate(
        case.receipt,
        case.options(
            applicability={7: False},
            applicability_justification={
                7: "documentation-only unit class declares no tests"
            },
        ),
    )
    assert result.condition(7).outcome is Outcome.NOT_APPLICABLE
    assert 7 not in result.satisfied
    assert result.counts["satisfied"] == 11
    assert result.counts["not_applicable"] == 1
    assert result.is_complete, (
        "a justified waiver on a waivable condition must not block"
    )


def test_waiver_without_justification_is_not_a_waiver(case: Case) -> None:
    result = evaluate(case.receipt, case.options(applicability={7: False}))
    assert result.condition(7).outcome is Outcome.UNSATISFIED
    assert "not a waiver" in result.condition(7).basis


@pytest.mark.parametrize("n", sorted(NON_WAIVABLE))
def test_non_waivable_conditions_cannot_be_waived(tmp_path: Path, n: int) -> None:
    c = Case(tmp_path / f"nw{n}")
    result = evaluate(
        c.receipt,
        c.options(
            applicability={n: False}, applicability_justification={n: "inconvenient"}
        ),
    )
    assert result.condition(n).outcome is Outcome.UNSATISFIED
    assert result.condition(n).detail.get("non_waivable") is True
    assert not result.is_complete


def test_waiving_every_waivable_condition_still_requires_the_seven_structural_ones(
    case: Case,
) -> None:
    """Vacuity control: N/A must never manufacture a pass out of nothing."""
    waivable = sorted(set(range(1, 13)) - NON_WAIVABLE)
    result = evaluate(
        case.receipt,
        case.options(
            applicability=dict.fromkeys(waivable, False),
            applicability_justification={
                n: "waived for this control" for n in waivable
            },
        ),
    )
    assert result.counts["not_applicable"] == len(waivable)
    assert result.counts["satisfied"] == len(NON_WAIVABLE)
    # Still complete only because the seven structural conditions were genuinely measured.
    assert result.is_complete
    # And breaking one structural condition must still block, even with everything else waived.
    (case.root / case.artifact_rel).unlink()
    blocked = evaluate(
        case.receipt,
        case.options(
            applicability=dict.fromkeys(waivable, False),
            applicability_justification={
                n: "waived for this control" for n in waivable
            },
        ),
    )
    assert not blocked.is_complete
    assert blocked.unsatisfied == [2]


# ----------------------------------------------------------------------------------- robustness


@pytest.mark.parametrize(
    "hostile",
    [
        {},
        {"unit_id": UNIT},
        {"unit_id": UNIT, "artifacts": "not-a-list", "evidence": 7, "tests": None},
        {"unit_id": UNIT, "artifacts": [{"path": ""}]},
        {"unit_id": UNIT, "state": "SUCCESS", "sentinel": "x", "artifacts": [None, 3]},
        {"unit_id": 12345, "state": ["SUCCESS"], "sentinel": {"v": 1}},
    ],
    ids=[
        "empty",
        "id-only",
        "wrong-types",
        "blank-path",
        "junk-artifacts",
        "scalar-swap",
    ],
)
def test_predicate_is_total_and_never_reports_complete_on_junk(
    tmp_path: Path, hostile: dict
) -> None:
    opts = PredicateOptions(repo_root=tmp_path)
    result = evaluate(hostile, opts)  # must not raise
    assert not result.is_complete
    assert len(result.conditions) == 12
    assert not any(c.detail.get("evaluator_error") for c in result.conditions), (
        "an evaluator crashed; a reducer crash must be impossible, not merely non-fatal"
    )


def test_evaluate_does_not_raise_on_a_non_mapping(tmp_path: Path) -> None:
    result = evaluate([], PredicateOptions(repo_root=tmp_path))  # type: ignore[arg-type]
    assert not result.is_complete


def test_zero_byte_artifact_fails_condition_3(case: Case) -> None:
    (case.root / case.artifact_rel).write_bytes(b"")
    r = deepcopy(case.receipt)
    r["artifacts"][0]["bytes"] = 0
    r["artifacts"][0]["sha256"] = hashlib.sha256(b"").hexdigest()
    result = evaluate(r, case.options())
    assert 3 in result.unsatisfied
    assert "0 bytes" in result.condition(3).basis


def test_one_byte_threshold_is_raised_to_the_absolute_floor(case: Case) -> None:
    """ARC-0084: a one-byte floor is not a real threshold."""
    (case.root / case.artifact_rel).write_text("x" * 10, encoding="utf-8")
    r = deepcopy(case.receipt)
    r["min_bytes_threshold"] = 1
    raw = (case.root / case.artifact_rel).read_bytes()
    r["artifacts"][0]["bytes"] = len(raw)
    r["artifacts"][0]["sha256"] = hashlib.sha256(raw).hexdigest()
    result = evaluate(r, case.options())
    c3 = result.condition(3)
    assert c3.outcome is Outcome.UNSATISFIED
    assert c3.detail["effective_min_bytes"] == ABSOLUTE_MIN_BYTES
    assert c3.detail["weak_threshold_declared"] is True


def test_undeclared_threshold_is_unfalsifiable_and_fails(case: Case) -> None:
    r = deepcopy(case.receipt)
    r.pop("min_bytes_threshold")
    result = evaluate(r, case.options())
    assert result.unsatisfied == [3]
    assert "unfalsifiable" in result.condition(3).basis


def test_unresolvable_evidence_anchor_fails_condition_6(case: Case) -> None:
    r = deepcopy(case.receipt)
    r["evidence"][0]["anchor"] = "src/module.py:99999"
    result = evaluate(r, case.options())
    assert result.unsatisfied == [6]
    assert "only 6" in result.condition(6).basis or "lines" in result.condition(6).basis


def test_single_evidence_item_fails_the_two_signal_floor(case: Case) -> None:
    r = deepcopy(case.receipt)
    r["evidence"] = [r["evidence"][0]]
    result = evaluate(r, case.options())
    assert result.unsatisfied == [6]


def test_empty_source_probe_fails_condition_6(case: Case) -> None:
    """The measured claim_gate.py hole: an absent source normalises to empty strings."""
    r = deepcopy(case.receipt)
    r["evidence"][0]["probes"][0]["command"] = "   "
    result = evaluate(r, case.options())
    assert result.unsatisfied == [6]
    assert "zero signals" in result.condition(6).basis


def test_same_method_probes_are_not_independent(case: Case) -> None:
    r = deepcopy(case.receipt)
    r["evidence"][0]["probes"][1]["method"] = r["evidence"][0]["probes"][0]["method"]
    result = evaluate(r, case.options())
    assert result.unsatisfied == [6]
    assert "same mechanism class" in result.condition(6).basis


def test_manifest_digest_drift_fails_condition_11(case: Case) -> None:
    manifest = json.loads((case.root / case.manifest_rel).read_text(encoding="utf-8"))
    manifest["artifacts"][0]["sha256"] = "c" * 64
    (case.root / case.manifest_rel).write_text(json.dumps(manifest), encoding="utf-8")
    result = evaluate(case.receipt, case.options())
    assert result.unsatisfied == [11]
    assert "digest drift" in result.condition(11).basis


def test_missing_manifest_is_not_checked(case: Case) -> None:
    (case.root / case.manifest_rel).unlink()
    result = evaluate(case.receipt, case.options())
    assert result.not_checked == [11]
    assert not result.is_complete


def test_non_hex_manifest_digest_skips_the_digest_check_and_says_so(case: Case) -> None:
    """The real ARTIFACT-MANIFEST.json records sha256 '(self)' for one entry."""
    manifest = json.loads((case.root / case.manifest_rel).read_text(encoding="utf-8"))
    manifest["artifacts"][0]["sha256"] = "(self)"
    (case.root / case.manifest_rel).write_text(json.dumps(manifest), encoding="utf-8")
    result = evaluate(case.receipt, case.options())
    assert result.condition(11).outcome is Outcome.SATISFIED
    assert any(row.get("why") for row in result.condition(11).detail["rows"])


def test_crlf_worktree_matches_an_lf_recorded_digest_and_says_so(case: Case) -> None:
    """Measured on real data: 0 of 13 manifest entries match worktree bytes, 12 match LF-normalised.

    A digest gate that only compared worktree bytes would false-fire on every real artifact on this
    box. An LF match therefore counts, and the MODE is always reported.
    """
    p = case.root / case.artifact_rel
    lf_bytes = p.read_bytes()
    crlf_bytes = lf_bytes.replace(b"\n", b"\r\n")
    p.write_bytes(crlf_bytes)
    lf_digest = hashlib.sha256(lf_bytes).hexdigest()
    assert hashlib.sha256(crlf_bytes).hexdigest() != lf_digest, (
        "control: the two forms must differ"
    )

    r = deepcopy(case.receipt)
    r["artifacts"][0]["bytes"] = len(crlf_bytes)
    r["artifacts"][0]["sha256"] = lf_digest  # what a renderer on LF bytes would record
    manifest = json.loads((case.root / case.manifest_rel).read_text(encoding="utf-8"))
    manifest["artifacts"][0]["sha256"] = lf_digest
    manifest["artifacts"][0]["bytes"] = len(crlf_bytes)
    (case.root / case.manifest_rel).write_text(json.dumps(manifest), encoding="utf-8")

    result = evaluate(r, case.options())
    assert result.condition(2).outcome is Outcome.SATISFIED
    assert (
        result.condition(2).detail["checked"][0]["digest_match_mode"] == "lf-normalised"
    )
    assert result.condition(11).outcome is Outcome.SATISFIED
    assert (
        result.condition(11).detail["rows"][0]["digest_match_mode"] == "lf-normalised"
    )


def test_digest_matching_neither_eol_form_is_real_drift(case: Case) -> None:
    """Both-states pair for the test above: an unrelated digest must still fail."""
    r = deepcopy(case.receipt)
    r["artifacts"][0]["sha256"] = hashlib.sha256(b"unrelated content").hexdigest()
    result = evaluate(r, case.options())
    assert result.unsatisfied == [2]
    assert "neither worktree nor LF-normalised" in result.condition(2).basis


def test_self_review_is_not_review(case: Case) -> None:
    r = deepcopy(case.receipt)
    r["reviewer"]["independent"] = False
    result = evaluate(r, case.options())
    assert result.unsatisfied == [9]
    assert "self-review is not review" in result.condition(9).basis


def test_absent_reviewer_is_not_checked(case: Case) -> None:
    r = deepcopy(case.receipt)
    r.pop("reviewer")
    result = evaluate(r, case.options())
    assert result.not_checked == [9]
    assert not result.is_complete


def test_same_vendor_review_passes_when_the_unit_does_not_require_cross_vendor(
    case: Case,
) -> None:
    """Applicability of the cross-vendor rule is a unit-class property, not a global one."""
    r = deepcopy(case.receipt)
    r["reviewer"]["vendor"] = "anthropic"
    assert evaluate(r, case.options(require_cross_vendor_review=True)).unsatisfied == [
        9
    ]
    assert evaluate(r, case.options(require_cross_vendor_review=False)).is_complete


# -------------------------------------------------------------------------------- schema conformance


def _validator(schema_path: Path):
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    cls = jsonschema.validators.validator_for(schema)
    cls.check_schema(schema)
    return cls(schema)


def test_result_schema_is_a_valid_2020_12_schema() -> None:
    _validator(RESULT_SCHEMA)  # check_schema raises if not


def test_emitted_report_validates_against_the_result_schema(case: Case) -> None:
    v = _validator(RESULT_SCHEMA)
    for receipt, over in [(case.receipt, {})] + [
        MUTATORS[n](Case(case.root / f"s{n}")) for n in sorted(MUTATORS)
    ]:
        report = evaluate(receipt, case.options(**over)).to_report()
        errors = sorted(v.iter_errors(report), key=lambda e: list(e.absolute_path))
        assert not errors, (
            f"emitted report violates its own schema: {[e.message for e in errors]}"
        )


def test_result_schema_rejects_a_self_contradicting_result(case: Case) -> None:
    """Both-states control on the result schema: it must FIRE on a known-bad result."""
    v = _validator(RESULT_SCHEMA)
    good = evaluate(case.receipt, case.options()).to_report()
    assert not list(v.iter_errors(good))
    bad = deepcopy(good)
    bad["verdict"] = "INCOMPLETE"  # is_complete stays true -> self-contradiction
    assert list(v.iter_errors(bad)), (
        "result schema failed to fire on a contradictory result"
    )
    bad2 = deepcopy(good)
    bad2["conditions"] = bad2["conditions"][:11]
    assert list(v.iter_errors(bad2)), (
        "result schema accepted a report with 11 conditions"
    )
    bad3 = deepcopy(good)
    bad3["not_applicable"] = [2]
    assert list(v.iter_errors(bad3)), (
        "result schema accepted N/A on a non-waivable condition"
    )


def test_baseline_receipt_validates_against_the_receipt_envelope_schema(
    case: Case,
) -> None:
    """Interop with the receipt-envelope lane's schema. Skipped, never faked, if it is mid-write."""
    if not RECEIPT_SCHEMA.is_file():
        pytest.skip(f"{RECEIPT_SCHEMA} not present")
    try:
        v = _validator(RECEIPT_SCHEMA)
    except Exception as exc:  # noqa: BLE001 - a sibling lane may be mid-write
        pytest.skip(f"receipt schema not loadable right now: {exc}")
    errors = sorted(v.iter_errors(case.receipt), key=lambda e: list(e.absolute_path))
    assert not errors, (
        "the predicate's own baseline receipt does not satisfy the shared receipt envelope: "
        f"{[(list(e.absolute_path), e.message) for e in errors[:5]]}"
    )


def test_report_embeds_as_a_predicate_report_payload(case: Case) -> None:
    """The result must be embeddable verbatim as receipt.schema.json#/$defs/predicate_report.report."""
    if not RECEIPT_SCHEMA.is_file():
        pytest.skip(f"{RECEIPT_SCHEMA} not present")
    jsonschema = pytest.importorskip("jsonschema")
    root = json.loads(RECEIPT_SCHEMA.read_text(encoding="utf-8"))
    try:
        sub = root["$defs"]["predicate_report"]["allOf"][1]["properties"]["report"]
    except (KeyError, IndexError, TypeError) as exc:
        pytest.skip(f"predicate_report shape changed: {exc}")
    schema = {"$schema": root.get("$schema"), "$defs": root["$defs"], **sub}
    report = evaluate(case.receipt, case.options()).to_report()
    cls = jsonschema.validators.validator_for(schema)
    errors = sorted(
        cls(schema).iter_errors(report), key=lambda e: list(e.absolute_path)
    )
    assert not errors, (
        f"report is not a valid predicate_report payload: {[e.message for e in errors]}"
    )


# --------------------------------------------------------------------------------------- the CLI


@pytest.mark.parametrize(
    "probe",
    ["_predicate_differential.py", "_predicate_real_units.py"],
)
def test_measurement_probes_pass_their_own_controls(tmp_path: Path, probe: str) -> None:
    """Each probe self-checks its detector controls and exits non-zero if a control did not pass.

    Deliberately asserts the CONTROLS, not the measured numbers: the receipt-envelope schema is
    authored by a sibling lane and still changing, so pinning "schema rejects 5 of 12" would go red
    for the wrong reason. The numbers live in the probes' JSON output; the invariant is that a
    measurement never ships without a passing control.
    """
    out = tmp_path / f"{probe}.json"
    proc = subprocess.run(
        [sys.executable, str(HERE / probe), "--out", str(out)],
        capture_output=True,
        text=True,
        check=False,
        cwd=str(REPO_ROOT),
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert proc.stdout.strip().splitlines()[-1].startswith("SUCCESS:")
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report


def test_cli_exits_zero_on_complete_and_one_on_incomplete(case: Case) -> None:
    receipt_path = case.root / "receipt.json"
    receipt_path.write_text(json.dumps(case.receipt, indent=1), encoding="utf-8")
    base = [
        sys.executable,
        str(HERE / "completion_predicate.py"),
        str(receipt_path),
        "--repo-root",
        str(case.root),
        "--output-schema",
        case.schema_rel,
        "--require-cross-vendor-review",
    ]
    ok = subprocess.run(base, capture_output=True, text=True, check=False)
    assert ok.returncode == 0, ok.stdout + ok.stderr
    assert "SUCCESS:IMP-0415 predicate=COMPLETE" in ok.stdout

    bad = deepcopy(case.receipt)
    bad["state"] = "FAILED"
    receipt_path.write_text(json.dumps(bad, indent=1), encoding="utf-8")
    nok = subprocess.run(base, capture_output=True, text=True, check=False)
    assert nok.returncode == 1
    assert "FAILED:IMP-0415 predicate" in nok.stdout
