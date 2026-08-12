"""Both-states controls for the P2 delivery gate.

Every case builds its own throwaway git repo and its own in-memory catalog, and every green-state
assertion is paired with a mutation that must go RED. A gate whose tests only exercise the good
state is the no-op this whole tool tree exists to catch.

HERMETIC ON PURPOSE, and the scope that leaves. These tests use a FAKE resolver -- a dozen lines
with the same two methods `ready_units` calls -- so the file needs nothing but pytest. That is
deliberate: the `measure-guard` CI step installs only pytest and its comment records what happened
the last time a step leaned on a sibling's transitive `jsonschema`. The consequence, stated rather
than hidden: these tests prove the gate's LOGIC discriminates, not that the real schema pack does.
That second question is answered by the gate itself, which runs as its own `gate-p2-delivery` step
with `jsonschema` pinned and refuses to report anything unless it can first show its checker is lit.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import unitgate as ug  # noqa: E402
from conftest import commit_all, make_git_repo  # noqa: E402


class FakeResolver:
    """Stand-in for ``platform/lib/schema_resolver`` with the two methods the predicate calls.

    A "discriminating" contract demands a ``sentinel`` key, so garbage is rejected and a real
    artifact is not. A "vacuous" contract returns no errors for anything, which is precisely what
    the three meta-schema declarations in the live catalog do.
    """

    def __init__(
        self, vacuous: tuple[str, ...] = (), raises: tuple[str, ...] = ()
    ) -> None:
        self.vacuous = set(vacuous)
        self.raises = set(raises)

    def validate_artifact(self, doc, schema):
        if schema in self.raises:
            raise KeyError(schema)
        if schema in self.vacuous:
            return []
        if isinstance(doc, dict) and "sentinel" in doc:
            return []
        return ["missing sentinel"]

    def build_registry(self):
        return None


class DeadResolver(FakeResolver):
    """A checker that is simply off: nothing is ever rejected, so everything looks vacuous."""

    def validate_artifact(self, doc, schema):  # noqa: ARG002
        return []


@pytest.fixture()
def ru():
    """The real predicate module. Importing it needs no third-party package."""
    mod = ug.load_ready_units()
    mod._DISCRIMINATES.clear()
    mod._REGISTRY_CACHE.clear()
    return mod


def _lit() -> FakeResolver:
    return FakeResolver(vacuous=(ug.KNOWN_VACUOUS,))


# --------------------------------------------------------------------------------------------
# 1. The lit check. Its whole job is to refuse to report a verdict from a checker that is off.
# --------------------------------------------------------------------------------------------


def test_lit_check_is_silent_when_the_checker_discriminates(ru) -> None:
    assert ug.check_checker_is_lit(ru, _lit()) == []


def test_lit_check_fires_when_the_resolver_is_absent(ru) -> None:
    findings = ug.check_checker_is_lit(ru, None)
    assert len(findings) == 1
    assert "UNAVAILABLE" in findings[0]


def test_lit_check_fires_on_a_DEAD_checker_that_calls_everything_vacuous(ru) -> None:
    """The half a vacuous-only control cannot catch.

    A dead checker rejects nothing, so every declaration -- including the known-vacuous one --
    reads as vacuous and the first assertion passes. Only requiring a known-DISCRIMINATING
    declaration to be accepted distinguishes "correctly flagged the meta-schema" from
    "cannot flag anything".
    """
    findings = ug.check_checker_is_lit(ru, DeadResolver())
    assert len(findings) == 1
    assert ug.KNOWN_DISCRIMINATING in findings[0]


def test_lit_check_fires_when_a_vacuous_declaration_is_not_flagged(ru) -> None:
    findings = ug.check_checker_is_lit(ru, FakeResolver())
    assert len(findings) == 1
    assert ug.KNOWN_VACUOUS in findings[0]


# --------------------------------------------------------------------------------------------
# 2. blob_verdict rests on one assumption: relocating the bytes cannot change the verdict.
# --------------------------------------------------------------------------------------------


def test_blob_verdict_is_location_independent(ru, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(ru, "REPO", tmp_path)
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    payload = json.dumps({"sentinel": "x"}).encode()
    for rel in ("a/art.json", "b/art.json"):
        (tmp_path / rel).write_bytes(payload)

    res = _lit()
    here = ru.artifact_delivered(
        {"id": "U", "output_path": "a/art.json", "output_schema": "s.json"}, res
    )
    there = ru.artifact_delivered(
        {"id": "U", "output_path": "b/art.json", "output_schema": "s.json"}, res
    )
    relocated = ug.blob_verdict(
        ru,
        res,
        {"id": "U", "output_path": "a/art.json", "output_schema": "s.json"},
        payload,
    )
    assert here == there == relocated == (True, "delivered")


# --------------------------------------------------------------------------------------------
# 3. scan(), against real git repos. Good state first, then one mutation per finding class.
# --------------------------------------------------------------------------------------------


def _repo_with(
    tmp_path: Path, monkeypatch, artifacts: dict[str, dict], commit: bool = True
) -> Path:
    root = make_git_repo(tmp_path / "r")
    # Always seed one unrelated tracked file: `git commit` refuses an empty tree, and a repo with
    # no HEAD would make `tracked_paths` raise for a reason the test is not about.
    (root / "seed.txt").write_text("seed", encoding="utf-8")
    for rel, doc in artifacts.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(doc), encoding="utf-8")
    if commit:
        commit_all(root)
    monkeypatch.setattr(ug, "REPO", root)
    monkeypatch.setattr(ug.blobread, "REPO", root)
    return root


def _units(n: int, extra: list[dict] | None = None) -> list[dict]:
    """`n` artifact-less filler units so the floors are not what fails a scan test."""
    out = [{"id": f"F-{i:04d}", "output_schema": "s.json"} for i in range(n)]
    return out + (extra or [])


def test_scan_is_clean_when_every_artifact_is_committed_and_valid(
    ru, tmp_path, monkeypatch
) -> None:
    root = _repo_with(tmp_path, monkeypatch, {"art/one.json": {"sentinel": "x"}})
    monkeypatch.setattr(ru, "REPO", root)
    unit = {"id": "U-1", "output_path": "art/one.json", "output_schema": "s.json"}
    rep = ug.scan(ru, _lit(), _units(3, [unit]))
    assert rep["artifacts_seen"] == 1
    assert rep["untracked_artifacts"] == []
    assert rep["blob_worktree_divergence"] == []
    assert rep["forged_completions"] == []


def test_scan_fires_on_an_artifact_that_was_never_committed(
    ru, tmp_path, monkeypatch
) -> None:
    root = _repo_with(
        tmp_path, monkeypatch, {"art/one.json": {"sentinel": "x"}}, commit=False
    )
    monkeypatch.setattr(ru, "REPO", root)
    # Commit ONLY the seed, so HEAD exists but does not contain the artifact -- the shape of an
    # artifact that is green on the author's box and absent from the clone CI grades.
    import subprocess

    subprocess.run(
        ["git", "-C", str(root), "add", "seed.txt"], check=True, capture_output=True
    )
    subprocess.run(
        ["git", "-C", str(root), "commit", "-qm", "seed"],
        check=True,
        capture_output=True,
    )

    unit = {"id": "U-1", "output_path": "art/one.json", "output_schema": "s.json"}
    rep = ug.scan(ru, _lit(), _units(3, [unit]))
    assert rep["untracked_artifacts"] == ["art/one.json"]


def test_scan_fires_when_the_blob_and_the_worktree_disagree(
    ru, tmp_path, monkeypatch
) -> None:
    """The clone-green trap: valid in the tree the author looks at, invalid in the bytes CI gets."""
    root = _repo_with(
        tmp_path, monkeypatch, {"art/one.json": {}}
    )  # committed WITHOUT the sentinel
    monkeypatch.setattr(ru, "REPO", root)
    (root / "art/one.json").write_text(
        json.dumps({"sentinel": "x"}), encoding="utf-8"
    )  # fixed only locally

    unit = {"id": "U-1", "output_path": "art/one.json", "output_schema": "s.json"}
    rep = ug.scan(ru, _lit(), _units(3, [unit]))
    assert len(rep["blob_worktree_divergence"]) == 1
    uid, path, why = rep["blob_worktree_divergence"][0]
    assert (uid, path) == ("U-1", "art/one.json")
    assert "worktree=True" in why and "blob=False" in why


def test_scan_fires_on_a_completion_the_contract_does_not_support(
    ru, tmp_path, monkeypatch
) -> None:
    root = _repo_with(tmp_path, monkeypatch, {"art/one.json": {"state": "SUCCESS"}})
    monkeypatch.setattr(ru, "REPO", root)
    unit = {"id": "U-1", "output_path": "art/one.json", "output_schema": "s.json"}
    rep = ug.scan(ru, _lit(), _units(3, [unit]))
    assert len(rep["forged_completions"]) == 1
    assert "state=SUCCESS" in rep["forged_completions"][0][2]


def test_scan_does_not_call_an_honest_blocked_receipt_a_forged_completion(
    ru, tmp_path, monkeypatch
) -> None:
    """The false-positive direction. Every real artifact today is BLOCKED; none may be flagged."""
    root = _repo_with(tmp_path, monkeypatch, {"art/one.json": {"state": "BLOCKED"}})
    monkeypatch.setattr(ru, "REPO", root)
    unit = {"id": "U-1", "output_path": "art/one.json", "output_schema": "s.json"}
    rep = ug.scan(ru, _lit(), _units(3, [unit]))
    assert rep["forged_completions"] == []


def test_scan_counts_units_declaring_a_vacuous_contract(
    ru, tmp_path, monkeypatch
) -> None:
    _repo_with(tmp_path, monkeypatch, {})
    res = FakeResolver(vacuous=("meta.json",))
    units = [
        {"id": "A", "output_schema": "meta.json"},
        {"id": "B", "output_schema": "meta.json"},
        {"id": "C", "output_schema": "s.json"},
    ]
    rep = ug.scan(ru, res, units)
    assert rep["vacuous_declarations"] == ["meta.json"]
    assert rep["units_declaring_a_vacuous_contract"] == 2


# --------------------------------------------------------------------------------------------
# 4. The ratchet, both directions.
# --------------------------------------------------------------------------------------------


def _report(decl: list[str], units: int) -> dict:
    return {"vacuous_declarations": decl, "units_declaring_a_vacuous_contract": units}


def test_ratchet_is_silent_at_the_baseline() -> None:
    rep = _report(["a", "b", "c"], ug.BASELINE["units_declaring_a_vacuous_contract"])
    assert ug.regressions(rep) == []
    assert ug.improvements(rep) == []


def test_ratchet_fires_when_a_new_vacuous_declaration_appears() -> None:
    rep = _report(
        ["a", "b", "c", "d"], ug.BASELINE["units_declaring_a_vacuous_contract"]
    )
    assert len(ug.regressions(rep)) == 1


def test_ratchet_fires_when_more_units_adopt_a_vacuous_contract() -> None:
    rep = _report(
        ["a", "b", "c"], ug.BASELINE["units_declaring_a_vacuous_contract"] + 1
    )
    assert len(ug.regressions(rep)) == 1


def test_ratchet_reports_an_improvement_so_the_floor_gets_lowered() -> None:
    """An unreported improvement is how a ratchet quietly stops ratcheting."""
    rep = _report(["a"], 1)
    assert len(ug.improvements(rep)) == 2
    assert ug.regressions(rep) == []


# --------------------------------------------------------------------------------------------
# 5. Fail-closed floors. A green computed over nothing is the failure mode, not the pass.
# --------------------------------------------------------------------------------------------


def test_unit_floor_and_artifact_floor_are_ordered_so_a_collapse_cannot_read_as_clean() -> (
    None
):
    assert ug.MIN_UNITS >= 1500
    assert ug.MIN_ARTIFACTS >= 40


def test_the_gate_refuses_to_run_when_the_predicate_is_missing(
    monkeypatch, tmp_path
) -> None:
    monkeypatch.setattr(ug, "READY_UNITS", tmp_path / "not-here.py")
    with pytest.raises(ug.UnitGateUnrunnable):
        ug.load_ready_units()


def test_tracked_paths_raises_rather_than_returning_an_empty_set(tmp_path) -> None:
    """An empty set would silently mark every artifact untracked, or nothing tracked at all."""
    bare = tmp_path / "not-a-repo"
    bare.mkdir()
    with pytest.raises(ug.UnitGateUnrunnable):
        ug.tracked_paths("HEAD", repo=bare)


# --------------------------------------------------------------------------------------------
# 6. The forged-completion control must itself be a known-broken state, or it proves nothing.
# --------------------------------------------------------------------------------------------


def test_ci_still_invokes_this_gate(pytestconfig) -> None:
    """The integration itself, asserted from a step that is NOT the gate.

    This test runs under `gate-tests-coverage measure-guard`. Deleting the `gate-p2-delivery` step
    therefore cannot silence it -- which is the only arrangement in which removing the wiring
    turns something red. Read from the COMMITTED blob: a workflow edited only in a worktree is not
    what any runner executes.
    """
    text = ug.blobread.read_blob(ug.CI_WORKFLOW, "HEAD").decode("utf-8")
    assert ug.ci_wiring_findings(text) == []


def test_the_wiring_check_fires_when_the_invocation_is_removed() -> None:
    """The other half. Without this, a wiring check that can never fail proves nothing."""
    text = ug.blobread.read_blob(ug.CI_WORKFLOW, "HEAD").decode("utf-8")
    findings = ug.ci_wiring_findings(
        text.replace(ug.CI_INVOCATION, "# removed by the control")
    )
    assert len(findings) == 1
    assert "unreachable from CI" in findings[0]


def test_the_forged_control_fixture_is_tracked_and_still_declares_a_done_state() -> (
    None
):
    """If the fixture stops being forged, `forged_completions == []` stops meaning anything.

    Read from the COMMITTED blob, because a fixture that exists only in a worktree would leave CI
    with no control at all -- and this is the file the whole check's credibility rests on.
    """
    blob = ug.blobread.read_blob(ug.MUTANT_FIXTURE, "HEAD")
    doc = json.loads(blob.decode("utf-8"))
    assert str(doc.get("state", "")).upper() in ug.DONE_STATES
