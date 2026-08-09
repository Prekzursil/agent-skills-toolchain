"""Conformance tests for receipt.schema.json and the 12-condition predicate.

Three things are proven here, and nothing wider is claimed:

  A. ACCEPTS a real receipt  - a complete receipt with artifacts actually on disk
     validates against the schema and satisfies all 12 conditions.
  B. REJECTS malformed input - a schema that accepts everything is worse than none,
     so every malformed shape must produce at least one error, and the bare `{}`
     must be rejected.
  C. The gate has TEETH     - a 12-mutation battery breaks each condition in turn
     and the corresponding condition must go UNSATISFIED. A no-op control gate that
     always returns complete is run through the same battery and must FAIL it; if
     the battery cannot tell the real gate from a no-op, the battery measures nothing.

Cascade honesty: 8 of the 12 mutations are ALSO caught at the schema layer (defense
in depth), so a mutation is not guaranteed to break exactly one condition. The tests
assert the mutated condition is among the blocking ones and print the cascade set;
"exactly one condition per mutation" is NOT claimed.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from pathlib import Path

import pytest

import receipt_schema_gate as rg

REPO = Path(__file__).resolve().parents[2]
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"


# --------------------------------------------------------------------------- #
# fixtures
# --------------------------------------------------------------------------- #


@pytest.fixture(scope="module")
def schema() -> dict:
    return rg.load_schema()


@pytest.fixture
def live_repo(tmp_path: Path) -> Path:
    """A throwaway repo root holding a real artifact and a real manifest."""
    art = tmp_path / "command-center" / "out" / "unit.json"
    art.parent.mkdir(parents=True, exist_ok=True)
    art.write_text(json.dumps({"finding": "x" * 4000}), encoding="utf-8")
    man = tmp_path / "command-center" / "ARTIFACT-MANIFEST.json"
    man.write_text(
        json.dumps({"artifacts": ["command-center/out/unit.json"]}), encoding="utf-8"
    )
    return tmp_path


@pytest.fixture
def good_receipt(live_repo: Path) -> dict:
    art = live_repo / "command-center" / "out" / "unit.json"
    raw = art.read_bytes()
    return {
        "schema_version": 1,
        "unit_id": "ADV-0001",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:ADV-0001",
        "spec_anchor": "_USER-PROMPTS.md:10631-10644",
        "min_bytes_threshold": 1024,
        "artifacts": [
            {
                "path": "command-center/out/unit.json",
                "bytes": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
                "exists": True,
                "eol": "LF",
                "role": "primary",
            }
        ],
        "evidence": [
            {
                "claim": "The reducer rejects a receipt whose sentinel names another unit.",
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "platform/lib/receipt_schema_gate.py:311",
                "probes": [
                    {
                        "role": "source",
                        "method": "test-run",
                        "command": "python -m pytest platform/lib/test_receipt_schema_gate.py -k sentinel",
                        "raw_output": "1 passed",
                        "fingerprint": "pytest:sentinel",
                    },
                    {
                        "role": "verifier",
                        "method": "command",
                        "command": "python platform/lib/receipt_schema_gate.py fixtures/wrong-sentinel.json",
                        "raw_output": "FAILED:ADV-0001 predicate-unsatisfied c5=UNSATISFIED",
                        "fingerprint": "cli:wrong-sentinel",
                    },
                ],
            },
            {
                "claim": "All 14 catalog-referenced $defs fragments resolve.",
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "platform/lib/_probe_schema_selfcheck.py:1",
                "probes": [
                    {
                        "role": "source",
                        "method": "schema-validate",
                        "command": "python platform/lib/_probe_schema_selfcheck.py",
                        "raw_output": "all 14 catalog fragments resolve",
                        "fingerprint": "selfcheck:fragments",
                    },
                    {
                        "role": "verifier",
                        "method": "static-analysis",
                        "command": "python -c 'json.load(...)[\"$defs\"].keys()'",
                        "raw_output": "14 of 14 names present",
                        "fingerprint": "keys:defs",
                    },
                ],
            },
        ],
        "tests": [
            {
                "id": "T-001",
                "name": "good receipt passes 12/12",
                "command": "python -m pytest platform/lib/test_receipt_schema_gate.py",
                "result": "PASS",
                "assertions": 12,
            }
        ],
        "negative_controls": [
            {
                "id": "NC-001",
                "kind": "malformed-input",
                "description": "empty object {} must be rejected by the schema",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "10 schema errors",
                "good_state_output": "0 schema errors",
            }
        ],
        "reviewer": {
            "reviewer_id": "adversarial-refuter-1",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "vendor": "openai",
        },
        "defects": [
            {
                "id": "D-1",
                "severity": "P2",
                "status": "open",
                "summary": "docstring typo",
            }
        ],
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/ARTIFACT-MANIFEST.json",
            "entry_id": "ADV-0001",
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/_catalog_integrity.py",
                "artifact_path": "command-center/out/unit.json",
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": {
                    "role": "verifier",
                    "method": "command",
                    "command": "python command-center/_catalog_integrity.py --read out/unit.json",
                    "raw_output": "parsed 1 record",
                    "fingerprint": "consumer:integrity",
                    "exit_code": 0,
                },
            }
        ],
        "timestamps": {
            "started_at": "2026-08-09T20:00:00Z",
            "ended_at": "2026-08-09T20:30:00Z",
            "duration_seconds": 1800,
        },
        "retry": {"count": 0, "policy": "two strikes then pivot (AGENTS.md 4b)"},
        "residual_unknowns": [
            {
                "claim": "Behaviour under a 512-artifact receipt is unmeasured.",
                "verdict": "NOT-CHECKED",
                "settling_experiment": "generate a 512-artifact receipt and time validate_receipt().",
            }
        ],
        "produced_by": {"vendor": "anthropic", "model": "opus", "role": "implementer"},
    }


# --------------------------------------------------------------------------- #
# A. the schema itself
# --------------------------------------------------------------------------- #


def test_schema_is_metaschema_valid(schema: dict) -> None:
    from jsonschema import Draft202012Validator

    Draft202012Validator.check_schema(schema)


def test_all_catalog_referenced_fragments_exist(schema: dict) -> None:
    """Every #/$defs/... pointer the catalog uses must be present."""
    cat = json.loads(CATALOG.read_bytes().decode("utf-8"))
    frags = set()
    for u in cat["work_units"]:
        m = re.search(
            r"receipt\.schema\.json#/\$defs/(\w+)", u.get("output_schema") or ""
        )
        if m:
            frags.add(m.group(1))
    assert frags, "detector control: found no fragments at all, the regex is broken"
    missing = sorted(frags - set(schema["$defs"]))
    assert not missing, f"catalog references absent fragments: {missing}"


def test_absent_fragment_raises(schema: dict) -> None:
    """Detector control for the fragment lookup: a bogus name must raise."""
    with pytest.raises(KeyError):
        rg.build_validator(schema, "no_such_report_xyz")


# --------------------------------------------------------------------------- #
# B. ACCEPTS a real receipt
# --------------------------------------------------------------------------- #


def test_good_receipt_is_schema_valid(good_receipt: dict) -> None:
    errors = rg.validate_receipt(good_receipt)
    assert errors == [], f"valid receipt rejected: {errors}"


def test_good_receipt_satisfies_all_twelve(good_receipt: dict, live_repo: Path) -> None:
    result = rg.evaluate_gate_a(good_receipt, repo_root=live_repo)
    unsat = [
        (c.n, c.outcome, c.basis)
        for c in result.conditions
        if c.outcome != rg.SATISFIED
    ]
    assert unsat == [], f"conditions not satisfied: {unsat}"
    assert len(result.conditions) == 12
    assert result.complete is True
    assert result.marker() == "SUCCESS:ADV-0001"


def test_good_receipt_has_no_coherence_problems(
    good_receipt: dict, live_repo: Path
) -> None:
    _, extra = rg.evaluate_full(good_receipt, repo_root=live_repo)
    assert extra == [], f"coherence problems: {extra}"


def test_fragment_validation_accepts_a_security_receipt(good_receipt: dict) -> None:
    """A $defs fragment must be usable standalone (the allOf/additionalProperties trap)."""
    r = copy.deepcopy(good_receipt)
    r["report"] = {
        "kind": "security_report",
        "findings": [
            {
                "id": "S-1",
                "severity": "P1",
                "summary": "path traversal in the loader",
                "anchor": "tools/x/loader.py:42",
                "exploit_proven": True,
                "credential_redacted": True,
            }
        ],
        "scanners": [{"name": "semgrep", "version": "1.2.3", "installed": True}],
    }
    errors = rg.validate_receipt(r, fragment="security_report")
    assert errors == [], f"security_report fragment rejected a valid receipt: {errors}"


def test_fragment_rejects_unredacted_security_finding(good_receipt: dict) -> None:
    r = copy.deepcopy(good_receipt)
    r["report"] = {
        "kind": "security_report",
        "findings": [
            {
                "id": "S-1",
                "severity": "P1",
                "summary": "leaked token",
                "anchor": "a.py:1",
                "exploit_proven": True,
                "credential_redacted": False,
            }
        ],
        "scanners": [{"name": "gitleaks", "version": "8", "installed": True}],
    }
    assert rg.validate_receipt(r, fragment="security_report"), (
        "a finding declaring credential_redacted=false must be rejected"
    )


# --------------------------------------------------------------------------- #
# C. REJECTS malformed input
# --------------------------------------------------------------------------- #

MALFORMED: dict[str, object] = {
    "empty-object": {},
    "empty-array": [],
    "null": None,
    "string": "SUCCESS:ADV-0001",
    "number": 7,
}


@pytest.mark.parametrize("name", sorted(MALFORMED))
def test_structurally_malformed_is_rejected(name: str) -> None:
    errors = rg.validate_receipt(MALFORMED[name])
    assert errors, (
        f"{name!r} was ACCEPTED; a schema that accepts everything is worse than none"
    )


def _mutate(base: dict, **changes) -> dict:
    r = copy.deepcopy(base)
    r.update(changes)
    return r


@pytest.mark.parametrize(
    "field",
    [
        "schema_version",
        "unit_id",
        "state",
        "sentinel",
        "spec_anchor",
        "min_bytes_threshold",
        "artifacts",
        "evidence",
        "timestamps",
        "retry",
    ],
)
def test_omitting_a_required_field_is_rejected(field: str, good_receipt: dict) -> None:
    """Closes a hole the mutation battery found.

    Every malformed case above supplies a FULL receipt with one value wrong, so
    weakening receipt_core.required to [schema_version] survived the whole suite:
    nothing exercised OMISSION. Each required field is dropped here in turn.
    """
    doc = copy.deepcopy(good_receipt)
    del doc[field]
    errors = rg.validate_receipt(doc)
    assert errors, f"receipt with {field!r} omitted was ACCEPTED"
    assert any(field in e for e in errors), (
        f"rejected, but no error mentions the omitted field {field!r}: {errors[:3]}"
    )


@pytest.mark.parametrize(
    "field",
    [
        "tests",
        "negative_controls",
        "reviewer",
        "manifest_registration",
        "downstream_consumers",
        "residual_unknowns",
    ],
)
def test_omitting_a_success_only_required_field_is_rejected(
    field: str, good_receipt: dict
) -> None:
    """These are required only when state==SUCCESS (the conditional branch)."""
    doc = copy.deepcopy(good_receipt)
    del doc[field]
    errors = rg.validate_receipt(doc)
    assert errors, f"SUCCESS receipt with {field!r} omitted was ACCEPTED"


def test_schema_invalidity_is_caught_by_condition_4_alone(
    good_receipt: dict, live_repo: Path
) -> None:
    """Equivalence proof for a surviving mutant.

    GateResult.complete short-circuits on schema_errors AND condition 4 goes
    UNSATISFIED whenever schema_errors is non-empty, so deleting the
    short-circuit changes nothing observable (an EQUIVALENT mutant, not a test
    hole). This test pins the property the short-circuit is redundant with.
    """
    doc = _mutate(good_receipt, unexpected_field="x")
    result = rg.evaluate_gate_a(doc, repo_root=live_repo)
    assert result.schema_errors, "control: this doc must be schema-invalid"
    c4 = next(c for c in result.conditions if c.n == 4)
    assert c4.outcome == rg.UNSATISFIED
    assert 4 in {c.n for c in result.blocking_conditions}
    assert result.complete is False


def test_field_level_malformations_are_rejected(good_receipt: dict) -> None:
    """Each row must produce at least one schema error. Reported as a table."""
    cases: list[tuple[str, dict]] = [
        ("unknown top-level field", _mutate(good_receipt, totally_new_field="x")),
        (
            "misspelled core field",
            {k if k != "sentinel" else "sentinal": v for k, v in good_receipt.items()},
        ),
        ("unit_id lowercase", _mutate(good_receipt, unit_id="adv-0001")),
        ("unit_id wrong shape", _mutate(good_receipt, unit_id="ADV-1")),
        ("state not terminal", _mutate(good_receipt, state="RUNNING")),
        ("schema_version wrong", _mutate(good_receipt, schema_version=2)),
        ("sentinel bare prose", _mutate(good_receipt, sentinel="all done, looks good")),
        ("sentinel wrong prefix", _mutate(good_receipt, sentinel="OK:ADV-0001")),
        ("min_bytes_threshold zero", _mutate(good_receipt, min_bytes_threshold=0)),
        ("artifacts empty", _mutate(good_receipt, artifacts=[])),
        (
            "artifact 0 bytes",
            _mutate(
                good_receipt, artifacts=[{**good_receipt["artifacts"][0], "bytes": 0}]
            ),
        ),
        (
            "artifact sha256 truncated",
            _mutate(
                good_receipt,
                artifacts=[{**good_receipt["artifacts"][0], "sha256": "abc123"}],
            ),
        ),
        (
            "artifact sha256 uppercase",
            _mutate(
                good_receipt,
                artifacts=[{**good_receipt["artifacts"][0], "sha256": "A" * 64}],
            ),
        ),
        (
            "artifact exists=false",
            _mutate(
                good_receipt,
                artifacts=[{**good_receipt["artifacts"][0], "exists": False}],
            ),
        ),
        (
            "artifact windows path",
            _mutate(
                good_receipt,
                artifacts=[
                    {
                        **good_receipt["artifacts"][0],
                        "path": "command-center\\out\\unit.json",
                    }
                ],
            ),
        ),
        (
            "naive timestamp (no offset)",
            _mutate(
                good_receipt,
                timestamps={
                    "started_at": "2026-08-09T20:00:00",
                    "ended_at": "2026-08-09T20:30:00Z",
                },
            ),
        ),
        (
            "evidence single item on SUCCESS",
            _mutate(good_receipt, evidence=good_receipt["evidence"][:1]),
        ),
        (
            "test result SKIP on SUCCESS",
            _mutate(
                good_receipt, tests=[{**good_receipt["tests"][0], "result": "SKIP"}]
            ),
        ),
        (
            "test result invalid enum",
            _mutate(
                good_receipt,
                tests=[{**good_receipt["tests"][0], "result": "probably fine"}],
            ),
        ),
        (
            "control inert on bad state",
            _mutate(
                good_receipt,
                negative_controls=[
                    {
                        **good_receipt["negative_controls"][0],
                        "fired_on_bad_state": False,
                    }
                ],
            ),
        ),
        (
            "control over-fires",
            _mutate(
                good_receipt,
                negative_controls=[
                    {
                        **good_receipt["negative_controls"][0],
                        "silent_on_good_state": False,
                    }
                ],
            ),
        ),
        (
            "reviewer FAIL on SUCCESS",
            _mutate(
                good_receipt, reviewer={**good_receipt["reviewer"], "verdict": "FAIL"}
            ),
        ),
        (
            "reviewer not independent",
            _mutate(
                good_receipt,
                reviewer={**good_receipt["reviewer"], "independent": False},
            ),
        ),
        (
            "open P0 defect",
            _mutate(
                good_receipt,
                defects=[
                    {"id": "D-9", "severity": "P0", "status": "open", "summary": "rce"}
                ],
            ),
        ),
        (
            "waiver with no reference",
            _mutate(
                good_receipt,
                defects=[
                    {
                        "id": "D-9",
                        "severity": "P1",
                        "status": "waived-by-owner",
                        "summary": "x",
                    }
                ],
            ),
        ),
        (
            "manifest not registered",
            _mutate(
                good_receipt,
                manifest_registration={
                    **good_receipt["manifest_registration"],
                    "registered": False,
                },
            ),
        ),
        (
            "consumer not executed",
            _mutate(
                good_receipt,
                downstream_consumers=[
                    {**good_receipt["downstream_consumers"][0], "executed": False}
                ],
            ),
        ),
        (
            "consumer read_ok false",
            _mutate(
                good_receipt,
                downstream_consumers=[
                    {**good_receipt["downstream_consumers"][0], "read_ok": False}
                ],
            ),
        ),
        ("FAILED state without failure block", _mutate(good_receipt, state="FAILED")),
        (
            "FAILED sentinel with SUCCESS state",
            _mutate(good_receipt, sentinel="FAILED:ADV-0001 boom"),
        ),
        (
            "failure classification empty",
            _mutate(
                good_receipt,
                state="FAILED",
                failure={"classification": [], "reason": "x"},
            ),
        ),
        (
            "failure classification blank string",
            _mutate(
                good_receipt,
                state="FAILED",
                failure={"classification": ["  "], "reason": "x"},
            ),
        ),
        (
            "UNVERIFIED with no settling experiment",
            _mutate(
                good_receipt,
                evidence=[
                    {**good_receipt["evidence"][0], "unverified": True},
                    good_receipt["evidence"][1],
                ],
            ),
        ),
        (
            "CONFIRMED with a single probe",
            _mutate(
                good_receipt,
                evidence=[
                    {
                        **good_receipt["evidence"][0],
                        "probes": good_receipt["evidence"][0]["probes"][:1],
                    },
                    good_receipt["evidence"][1],
                ],
            ),
        ),
        (
            "retry count negative",
            _mutate(good_receipt, retry={"count": -1, "policy": "p"}),
        ),
        ("SUPERSEDED without disposition", _mutate(good_receipt, state="SUPERSEDED")),
        (
            "residual unknown missing experiment",
            _mutate(
                good_receipt,
                residual_unknowns=[{"claim": "c", "verdict": "NOT-CHECKED"}],
            ),
        ),
        (
            "extensions wrong type",
            _mutate(good_receipt, extensions=["not", "an", "object"]),
        ),
    ]
    accepted = [name for name, doc in cases if not rg.validate_receipt(doc)]
    print(f"\nmalformed cases: {len(cases)}, rejected: {len(cases) - len(accepted)}")
    assert not accepted, f"these malformed receipts were ACCEPTED: {accepted}"


# --------------------------------------------------------------------------- #
# C2. the 12-mutation battery
# --------------------------------------------------------------------------- #


def _battery(good: dict, live_repo: Path) -> list[tuple[int, dict]]:
    """One mutation per condition. Returns (condition_number, mutated receipt)."""
    art0 = good["artifacts"][0]
    ev = copy.deepcopy(good["evidence"])
    ev[0]["probes"][1]["fingerprint"] = ev[0]["probes"][0][
        "fingerprint"
    ]  # same-probe-rerun
    return [
        (
            1,
            _mutate(
                good,
                state="FAILED",
                failure={"classification": ["overclaim"], "reason": "n/a"},
            ),
        ),
        (
            2,
            _mutate(
                good,
                artifacts=[{**art0, "path": "command-center/out/DOES-NOT-EXIST.json"}],
            ),
        ),
        (3, _mutate(good, min_bytes_threshold=10_000_000)),
        (4, _mutate(good, unexpected_field="breaks the schema")),
        (5, _mutate(good, sentinel="SUCCESS:ZZZ-9999")),
        (6, _mutate(good, evidence=ev)),
        (7, _mutate(good, tests=[{**good["tests"][0], "result": "SKIP"}])),
        (
            8,
            _mutate(
                good,
                negative_controls=[
                    {**good["negative_controls"][0], "fired_on_bad_state": False}
                ],
            ),
        ),
        (9, _mutate(good, reviewer={**good["reviewer"], "verdict": "FAIL"})),
        (
            10,
            _mutate(
                good,
                defects=[
                    {"id": "D-0", "severity": "P0", "status": "open", "summary": "rce"}
                ],
            ),
        ),
        (
            11,
            _mutate(
                good,
                manifest_registration={
                    **good["manifest_registration"],
                    "registered": False,
                },
            ),
        ),
        (
            12,
            _mutate(
                good,
                downstream_consumers=[
                    {**good["downstream_consumers"][0], "executed": False}
                ],
            ),
        ),
    ]


@pytest.mark.parametrize("target", list(range(1, 13)))
def test_mutation_battery_catches_each_condition(
    target: int, good_receipt: dict, live_repo: Path
) -> None:
    cases = dict(_battery(good_receipt, live_repo))
    result = rg.evaluate_gate_a(cases[target], repo_root=live_repo)
    blocking = {c.n for c in result.blocking_conditions}
    assert target in blocking, (
        f"mutation of condition {target} was NOT caught; blocking={sorted(blocking)}"
    )
    assert result.complete is False
    assert result.marker().startswith("FAILED:")


def test_battery_cascade_is_reported(good_receipt: dict, live_repo: Path) -> None:
    """Print the cascade set. 'Exactly one condition per mutation' is NOT claimed."""
    rows = []
    for target, doc in _battery(good_receipt, live_repo):
        res = rg.evaluate_gate_a(doc, repo_root=live_repo)
        blocking = sorted(c.n for c in res.blocking_conditions)
        rows.append((target, blocking, bool(res.schema_errors)))
    print("\ncondition -> blocking set (schema_layer_also_fired)")
    for target, blocking, sch in rows:
        print(f"  c{target:<2d} -> {blocking}  schema={sch}")
    exact = [t for t, b, _ in rows if b == [t]]
    print(f"mutations isolating exactly one condition: {len(exact)}/12 -> {exact}")
    assert all(t in b for t, b, _ in rows)


def test_noop_gate_fails_the_battery(good_receipt: dict, live_repo: Path) -> None:
    """Control: a gate that always says complete must FAIL this battery.

    If the battery cannot separate the real gate from a no-op, the battery is
    measuring nothing and its green is uncitable.
    """

    class NoOpResult:
        complete = True
        blocking_conditions: list = []

    caught_real = 0
    caught_noop = 0
    for target, doc in _battery(good_receipt, live_repo):
        real = rg.evaluate_gate_a(doc, repo_root=live_repo)
        if target in {c.n for c in real.blocking_conditions}:
            caught_real += 1
        noop = NoOpResult()
        if target in {c.n for c in noop.blocking_conditions}:  # always false
            caught_noop += 1
    assert caught_real == 12, f"real gate caught only {caught_real}/12"
    assert caught_noop == 0, "no-op control unexpectedly caught something"


def test_filesystem_disabled_reports_not_checked_not_pass(
    good_receipt: dict, live_repo: Path
) -> None:
    """An unrunnable probe is NOT-CHECKED, never a silent pass."""
    result = rg.evaluate_gate_a(
        good_receipt, repo_root=live_repo, verify_filesystem=False
    )
    outcomes = {c.n: c.outcome for c in result.conditions}
    assert outcomes[2] == rg.NOT_CHECKED
    assert result.complete is False, "NOT-CHECKED must not be folded into a pass"


def test_sha256_mismatch_is_caught(good_receipt: dict, live_repo: Path) -> None:
    """A hand-typed hash must not survive: the reducer re-hashes off disk."""
    doc = copy.deepcopy(good_receipt)
    doc["artifacts"][0]["sha256"] = "0" * 64
    result = rg.evaluate_gate_a(doc, repo_root=live_repo)
    assert 3 in {c.n for c in result.blocking_conditions}
    assert rg.validate_receipt(doc) == [], (
        "control: this doc must stay schema-valid, only the reducer catches it"
    )


def test_declared_size_disagreeing_with_disk_is_caught(
    good_receipt: dict, live_repo: Path
) -> None:
    doc = copy.deepcopy(good_receipt)
    doc["artifacts"][0]["bytes"] = doc["artifacts"][0]["bytes"] + 1
    result = rg.evaluate_gate_a(doc, repo_root=live_repo)
    assert 3 in {c.n for c in result.blocking_conditions}


def test_timestamp_inversion_is_caught(good_receipt: dict) -> None:
    doc = copy.deepcopy(good_receipt)
    doc["timestamps"] = {
        "started_at": "2026-08-09T21:00:00Z",
        "ended_at": "2026-08-09T20:00:00Z",
    }
    assert rg.check_timestamps(doc), "inverted timestamps must be flagged"
    assert rg.validate_receipt(doc) == [], (
        "control: schema alone cannot compare two fields"
    )


def test_duration_disagreement_is_caught(good_receipt: dict) -> None:
    doc = copy.deepcopy(good_receipt)
    doc["timestamps"]["duration_seconds"] = 5
    assert rg.check_timestamps(doc)


def test_two_strikes_without_pivot_is_caught(good_receipt: dict) -> None:
    doc = copy.deepcopy(good_receipt)
    doc["retry"] = {
        "count": 2,
        "policy": "two strikes then pivot",
        "attempts": [
            {"attempt": 1, "error_fingerprint": "win-arg-limit", "outcome": "FAILED"},
            {"attempt": 2, "error_fingerprint": "win-arg-limit", "outcome": "FAILED"},
        ],
    }
    assert rg.check_retry_policy(doc), (
        "two strikes on one fingerprint needs >=2 alternatives"
    )
    doc["retry"]["pivot_alternatives"] = ["use --prompt-file", "route via stdin"]
    assert rg.check_retry_policy(doc) == []


# --------------------------------------------------------------------------- #
# D. conformance with the real catalog (exact algorithm, not judgement)
# --------------------------------------------------------------------------- #


@pytest.fixture(scope="module")
def catalog() -> dict:
    return json.loads(CATALOG.read_bytes().decode("utf-8"))


def test_every_catalog_unit_id_matches_the_schema_pattern(
    schema: dict, catalog: dict
) -> None:
    pat = re.compile(schema["$defs"]["unit_id"]["pattern"])
    bad = [u["id"] for u in catalog["work_units"] if not pat.match(u["id"])]
    assert not bad, (
        f"{len(bad)} catalogued ids rejected by the schema pattern: {bad[:10]}"
    )


def test_unit_id_pattern_rejects_known_bad(schema: dict) -> None:
    """Detector control: the id pattern must not be a rubber stamp."""
    pat = re.compile(schema["$defs"]["unit_id"]["pattern"])
    for bad in ("adv-0001", "ADV-1", "ADV-00001", "", "0001-ADV", "ADV_0001"):
        assert not pat.match(bad), f"id pattern wrongly accepted {bad!r}"


def test_every_catalog_sentinel_matches_the_schema_pattern(
    schema: dict, catalog: dict
) -> None:
    pat = re.compile(schema["$defs"]["sentinel"]["pattern"], re.DOTALL)
    bad = [
        (u["id"], u["completion_sentinel"][:70])
        for u in catalog["work_units"]
        if not pat.match(u.get("completion_sentinel") or "")
    ]
    assert not bad, f"{len(bad)} catalogued sentinels rejected: {bad[:5]}"


def test_sentinel_pattern_rejects_known_bad(schema: dict) -> None:
    pat = re.compile(schema["$defs"]["sentinel"]["pattern"], re.DOTALL)
    for bad in (
        "done",
        "SUCCESS",
        "SUCCESS:",
        "OK:ADV-0001",
        "started in the background",
        "",
    ):
        assert not pat.match(bad), f"sentinel pattern wrongly accepted {bad!r}"


def test_every_catalog_failure_class_matches_the_schema_pattern(
    schema: dict, catalog: dict
) -> None:
    """699 distinct values occur; a closed enum would reject valid units."""
    spec = schema["$defs"]["failure_classification_code"]
    pat = re.compile(spec["pattern"], re.DOTALL)
    values = set()
    for u in catalog["work_units"]:
        fc = u.get("failure_classification")
        if isinstance(fc, list):
            values.update(fc)
        elif fc:
            values.add(fc)
    assert len(values) > 500, (
        f"detector control: expected the open vocabulary, saw {len(values)}"
    )
    bad = [
        v
        for v in values
        if not pat.match(v) or not (spec["minLength"] <= len(v) <= spec["maxLength"])
    ]
    assert not bad, f"{len(bad)} of {len(values)} failure classes rejected: {bad[:5]}"


def test_failure_class_pattern_rejects_blank(schema: dict) -> None:
    pat = re.compile(schema["$defs"]["failure_classification_code"]["pattern"])
    for bad in ("", " ", "  \t ", " leading", "trailing "):
        assert not pat.match(bad), f"failure-class pattern wrongly accepted {bad!r}"


def test_parse_schema_ref_handles_every_catalog_form(catalog: dict) -> None:
    """The catalog decorates output_schema; the parser must recover the real ref."""
    forms = {u.get("output_schema") or "" for u in catalog["work_units"]}
    receipt_forms = {f for f in forms if "schema/receipt.schema.json" in f}
    assert len(receipt_forms) > 50, (
        f"detector control: only {len(receipt_forms)} forms found"
    )
    frags, plain = set(), 0
    for f in receipt_forms:
        base, frag = rg.parse_schema_ref(f)
        assert base == "command-center/schema/receipt.schema.json", (
            f"bad base {base!r} from {f!r}"
        )
        if frag:
            frags.add(frag)
        else:
            plain += 1
    assert plain > 0 and frags, f"plain={plain} frags={sorted(frags)}"


def test_catalog_units_pointing_at_receipt_schema_are_counted(catalog: dict) -> None:
    """Records the blast radius of this file being absent."""
    n = sum(
        1
        for u in catalog["work_units"]
        if rg.parse_schema_ref(u.get("output_schema") or "")[0]
        == "command-center/schema/receipt.schema.json"
    )
    print(f"\nunits whose output_schema resolves to receipt.schema.json: {n}")
    assert n >= 387, f"expected at least the 387 plain references, counted {n}"
