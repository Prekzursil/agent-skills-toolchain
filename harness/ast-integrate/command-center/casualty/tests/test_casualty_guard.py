"""Tests for the CASUALTY lane integration guard.

DESIGN RULE FOR THIS FILE: every test that asserts an ABSENCE (no finding, probe green) is
paired with a mutation that makes the same probe RED. A suite that only ever sees the good
state cannot tell a working probe from an inert one -- measured on this estate as an
UNKNOWN-sentinel grep that scored 8 hits on a complete 162 KB artifact and 8 on a 1.8 KB
skeleton, and as a `codex exec` probe that printed nothing in the broken state either.

Hermetic: stdlib + pytest only, no network, no agent transcripts. The fixtures are built in
tmp_path from the real lane so the tests measure the shipped rule, not a restatement of it.
"""

from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path

import casualty_guard as cg
import pytest

LANE = Path(cg.__file__).resolve().parent
REPO = LANE.parents[1]


@pytest.fixture
def mirror(tmp_path: Path) -> Path:
    """A minimal copy of the repo that the probes can run against."""
    return cg._mirror(REPO, tmp_path / "repo")


# --------------------------------------------------------------------------- P1 wiring


def test_wiring_probe_passes_on_the_real_workflow(mirror: Path) -> None:
    """The GOOD state. If this ever fails, CI has stopped invoking the guard."""
    res = cg.probe_wiring(mirror, allow_uncommitted=True)
    assert res.ok, res.detail
    assert res.facts["invocation_lines"], "no run: line invokes the guard"


def test_wiring_probe_rejects_a_reference_that_is_only_a_mention(mirror: Path) -> None:
    """use-vs-mention: a path NAMED in a comment is not a dependency on it.

    This exact confusion produced four false findings in one wave here, so the guard counts the
    FIELD (a `run:` command line) and not the document.
    """
    wf = mirror / cg.WORKFLOW_REL
    body = cg._read_text(wf).replace("\r\n", "\n")
    stripped = "\n".join(ln for ln in body.split("\n") if cg.GUARD_REL not in ln)
    wf.write_text(
        stripped + f"\n# the casualty guard lives at {cg.GUARD_REL}\n",
        encoding="utf-8",
        newline="",
    )
    res = cg.probe_wiring(mirror, allow_uncommitted=True)
    assert not res.ok
    assert res.facts["mentions_anywhere"] >= 1, "the mention must still be present"
    assert res.facts["invocation_lines"] == [], (
        "a comment must not count as an invocation"
    )


def test_wiring_probe_fails_when_the_workflow_is_gone(mirror: Path) -> None:
    (mirror / cg.WORKFLOW_REL).unlink()
    assert not cg.probe_wiring(mirror, allow_uncommitted=True).ok


def test_wiring_probe_tolerates_an_unreadable_blob(mirror: Path) -> None:
    """tmp_path is not a git repo, so the blob signal is unavailable, not contradictory.

    An unavailable second signal must not be read as a failing second signal -- a tool's auth or
    environment failure is a DETECTOR failure, never a verdict.
    """
    res = cg.probe_wiring(mirror, allow_uncommitted=False)
    assert res.ok
    assert res.facts["blob_readable"] is False


# --------------------------------------------------------------------------- P2 inventory


def test_inventory_is_green_on_the_real_lane(mirror: Path) -> None:
    res = cg.probe_inventory(mirror)
    assert res.ok, res.detail
    assert res.facts["shipped"], "an empty instrument list would be a path bug"


def test_inventory_flags_an_instrument_with_no_disposition(mirror: Path) -> None:
    (mirror / cg.LANE_REL / "brand_new_tool.py").write_text("x = 1\n", encoding="utf-8")
    res = cg.probe_inventory(mirror)
    assert not res.ok
    assert "brand_new_tool.py" in res.facts["ungated"]


def test_inventory_flags_a_disposition_whose_file_is_gone(mirror: Path) -> None:
    (mirror / cg.LANE_REL / "verify_blob_parity.py").unlink()
    res = cg.probe_inventory(mirror)
    assert not res.ok
    assert "verify_blob_parity.py" in res.facts["orphaned_dispositions"]


def test_inventory_fails_closed_on_an_empty_walk(tmp_path: Path) -> None:
    """A walk that finds nothing is a path bug, never a pass."""
    (tmp_path / cg.LANE_REL).mkdir(parents=True)
    res = cg.probe_inventory(tmp_path)
    assert not res.ok
    assert "ZERO" in res.detail


def test_inventory_flags_unparseable_python(mirror: Path) -> None:
    (mirror / cg.LANE_REL / "census_v2.py").write_text("def (\n", encoding="utf-8")
    res = cg.probe_inventory(mirror)
    assert not res.ok
    assert res.facts["unparseable"]


def test_every_shipped_instrument_has_a_disposition_with_a_reason() -> None:
    """Registry integrity: an exemption without a written reason is a shrug, not a policy."""
    assert cg.INSTRUMENTS, "an empty disposition table gates nothing"
    for name, disposition in cg.INSTRUMENTS.items():
        kind, _, reason = disposition.partition(":")
        assert kind in {"EXECUTED", "CI-EXECUTED", "TESTED", "EXEMPT"}, (
            f"{name}: unknown kind {kind!r}"
        )
        assert reason.strip(), f"{name}: {kind} with no stated reason"


def _call_site_strings(source: str) -> set[str]:
    """Every str literal in a CALL-SITE position: not a docstring, not a registry key.

    Two exclusions, and the second one was a defect in the first version of this helper. A
    filename in a docstring is a MENTION, so docstrings go. But every instrument name is also a
    KEY of the INSTRUMENTS dict, so without excluding the registry itself the matcher returned
    True for all eight names and the test below was VACUOUS -- it would have passed for an
    instrument that no line of code ever touches, which is precisely what it exists to catch.
    Counting the document instead of the field, reproduced inside the check written to prevent
    it. `test_the_call_site_matcher_discriminates` is the control that keeps it honest.
    """
    tree = ast.parse(source)
    skip: set[int] = set()

    for node in ast.walk(tree):
        if isinstance(
            node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
        ):
            body = getattr(node, "body", [])
            if (
                body
                and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)
            ):
                skip.add(id(body[0].value))
        # The INSTRUMENTS registry: its keys and its prose values are declarations, not uses.
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.target.id == "INSTRUMENTS" and node.value is not None:
                for sub in ast.walk(node.value):
                    if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
                        skip.add(id(sub))

    return {
        n.value
        for n in ast.walk(tree)
        if isinstance(n, ast.Constant)
        and isinstance(n.value, str)
        and id(n) not in skip
    }


def test_the_call_site_matcher_discriminates() -> None:
    """BOTH-STATES control for the matcher itself, before any verdict is read from it.

    liveness_v2.py is launched by P6 (a real call site) and census_v2.py is only TESTED (named
    in the registry and nowhere else). If the matcher cannot tell those two apart it is
    measuring the document, and every result below it is worthless.
    """
    used = _call_site_strings(cg._read_text(Path(cg.__file__)))
    assert "liveness_v2.py" in used, "matcher misses a REAL call site - it is inert"
    assert "census_v2.py" not in used, "matcher counts a registry key as a call site"


def test_every_executed_instrument_is_actually_invoked_by_the_guard() -> None:
    """Anti-rot: a disposition of EXECUTED must correspond to a real call site.

    Without this, relabelling an instrument EXECUTED is enough to make the table look complete
    while nothing runs it -- the bytes-not-behaviour shape that turned `ui-audit` into a green
    no-op. CI-EXECUTED is deliberately excluded: the WORKFLOW invokes those, not this file, and
    the wiring for them is what P1 checks.
    """
    used = _call_site_strings(cg._read_text(Path(cg.__file__)))
    executed = [n for n, d in cg.INSTRUMENTS.items() if d.startswith("EXECUTED:")]
    assert executed, (
        "no instrument is EXECUTED - the guard would be checking bytes only"
    )
    for name in executed:
        if name == "casualty_guard.py":
            continue  # this file; its "call site" is the process itself
        assert name in used, (
            f"{name} is dispositioned EXECUTED but appears in no code position in the guard"
        )


def test_the_redproof_is_ci_executed_and_never_executed_by_the_guard() -> None:
    """Recursion guard: integration_redproof runs the guard, so the guard must not run it."""
    assert cg.INSTRUMENTS["integration_redproof.py"].startswith("CI-EXECUTED:")
    used = _call_site_strings(cg._read_text(Path(cg.__file__)))
    assert "integration_redproof.py" not in used


# --------------------------------------------------------------------------- P3 receipts


def test_receipts_are_green_on_the_real_lane(mirror: Path) -> None:
    res = cg.probe_receipts(mirror, cross_check=False)
    assert res.ok, res.detail
    for unit in cg.UNITS:
        assert res.facts[unit]["digest_match"]
        assert res.facts[unit]["bytes_match"]


def test_receipts_detect_a_single_byte_mutation(mirror: Path) -> None:
    victim = mirror / cg.LANE_REL / cg.UNITS["ADV-0021"]
    raw = cg._read_text(victim)
    mutated = raw.replace('"schema_version": 1', '"schema_version": 2', 1)
    assert mutated != raw, "the mutation did not apply - the control would be inert"
    victim.write_text(mutated, encoding="utf-8", newline="")
    res = cg.probe_receipts(mirror, cross_check=False)
    assert not res.ok
    assert res.facts["ADV-0021"]["digest_match"] is False


def test_receipts_detect_a_declared_byte_count_that_lies(mirror: Path) -> None:
    """The digest could still match while the declared size is wrong; both are checked."""
    victim = mirror / cg.LANE_REL / cg.UNITS["ADV-0022"]
    doc = json.loads(cg._read_text(victim))
    doc["artifacts"][0]["bytes"] = 1
    victim.write_text(json.dumps(doc), encoding="utf-8", newline="")
    res = cg.probe_receipts(mirror, cross_check=False)
    assert not res.ok


def test_receipts_fail_when_a_receipt_is_missing(mirror: Path) -> None:
    (mirror / cg.LANE_REL / cg.UNITS["ADV-0021"]).unlink()
    res = cg.probe_receipts(mirror, cross_check=False)
    assert not res.ok
    assert res.facts["ADV-0021"]["present"] is False


def test_the_guards_elision_rule_agrees_with_the_shipped_verifier() -> None:
    """Two copies of a rule drift. Execute the other one and require agreement.

    The guard restates verify_elided_digest.py's elision so it can run against a mutated copy
    that has no git and no subprocess budget. That duplication is only safe because this test
    (and P3's cross_check at run time) turns it into a measured invariant.
    """
    receipts = [str(LANE / f) for f in cg.UNITS.values()]
    proc = subprocess.run(
        [sys.executable, str(LANE / "verify_elided_digest.py"), *receipts],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    for fname in cg.UNITS.values():
        facts = cg._digest_facts(LANE / fname)
        assert facts["digest_match"], (
            f"{fname}: guard disagrees with the shipped verifier"
        )
        assert facts["recomputed"] in proc.stdout, (
            "the two tools computed different digests"
        )


def test_the_shipped_verifier_still_fails_closed_on_empty_input() -> None:
    """Round-2 defect D2: it used to print nothing and exit 0 with no arguments."""
    proc = subprocess.run(
        [sys.executable, str(LANE / "verify_elided_digest.py")],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode != 0
    assert "FAILED:elided-digest" in proc.stdout


# --------------------------------------------------------------------------- P4 no-lost-work


def test_no_lost_work_is_green_with_the_receipt_in_the_lane(mirror: Path) -> None:
    res = cg.probe_no_lost_work(mirror)
    assert res.ok, res.detail
    assert res.facts["ADV-0021"]["best_location"] == "lane"


def test_no_lost_work_accepts_promotion_to_the_canonical_path(mirror: Path) -> None:
    """The intended END state is the receipt living at command-center/adversarial/.

    A guard that pinned the location would go red on the act of finishing the job.
    """
    canon = mirror / "command-center" / "adversarial"
    canon.mkdir(parents=True, exist_ok=True)
    for fname in cg.UNITS.values():
        src = mirror / cg.LANE_REL / fname
        (canon / fname).write_bytes(src.read_bytes())
        src.unlink()
    res = cg.probe_no_lost_work(mirror)
    assert res.ok, res.detail
    assert res.facts["ADV-0021"]["best_location"] == "canonical"


def test_no_lost_work_fails_when_every_copy_is_a_skeleton(mirror: Path) -> None:
    skeleton = json.dumps(
        {
            "unit_id": "ADV-0021",
            "status": "in-progress",
            "evidence": [],
            "tests": [],
            "negative_controls": [],
        }
    )
    (mirror / cg.LANE_REL / cg.UNITS["ADV-0021"]).write_text(
        skeleton, encoding="utf-8", newline=""
    )
    res = cg.probe_no_lost_work(mirror)
    assert not res.ok
    assert "LOST" in res.detail


def test_no_lost_work_fails_named_when_its_scorer_is_gone(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A missing dependency must produce a NAMED failure, not a traceback.

    P4 imports `_probe_census.py`, which is `_`-prefixed and therefore deliberately outside the
    instrument inventory P2 gates. Before this check, deleting it crashed the guard -- and a
    crashed gate in a CI log reads as an infrastructure hiccup, not as a finding.
    """
    empty = Path(str(cg.REPO)) / "definitely-not-a-real-root"
    monkeypatch.setattr(cg, "REPO", empty)
    res = cg.probe_no_lost_work(empty)
    assert not res.ok
    assert res.facts["missing_dependencies"] == ["_probe_census.py"]
    assert "never a pass" in res.detail


def test_the_structural_scorer_separates_complete_from_skeleton() -> None:
    """This is the TESTED disposition standing in for census_v2 in CI.

    census_v2 itself reads command-center/adversarial/, which a live sibling wave writes, so
    pinning its control pairs in CI would make an unrelated sibling commit a red build. The
    SEPARATION -- the property the census actually depends on -- is measured here instead.
    """
    score = cg._load_scorer()
    complete = json.loads(cg._read_text(LANE / cg.UNITS["ADV-0021"]))
    skeleton = {
        "unit_id": "ADV-0021",
        "status": "in-progress",
        "evidence": [],
        "tests": [],
        "negative_controls": [],
    }
    hi = score(complete, (LANE / cg.UNITS["ADV-0021"]).stat().st_size)[
        "substance_score"
    ]
    lo = score(skeleton, 1800)["substance_score"]
    assert hi > lo, f"the scorer does not separate: complete {hi} vs skeleton {lo}"
    assert hi >= 5, f"a finished receipt should score near the top, got {hi}"
    assert lo <= 1, f"a bare skeleton should score near zero, got {lo}"


# --------------------------------------------------------------------------- P5 banners


def test_banners_are_green_on_the_real_lane(mirror: Path) -> None:
    assert cg.probe_banners(mirror).ok


def test_banners_flag_a_stripped_banner(mirror: Path) -> None:
    victim = mirror / cg.LANE_REL / cg.SUPERSEDED[0]
    text = cg._read_text(victim)
    for key in cg.BANNER_KEYS:
        text = text.replace(key, "_retired_note")
    victim.write_text(text, encoding="utf-8", newline="")
    res = cg.probe_banners(mirror)
    assert not res.ok
    assert res.facts[cg.SUPERSEDED[0]]["banners"] == []


def test_banners_flag_a_deleted_superseded_file(mirror: Path) -> None:
    """Deleting the evidence of a defect is how the defect comes back."""
    (mirror / cg.LANE_REL / cg.SUPERSEDED[0]).unlink()
    assert not cg.probe_banners(mirror).ok


# --------------------------------------------------------------------------- helpers and cli


def test_strip_comment_lines_drops_comments_and_keeps_original_line_numbers() -> None:
    """The locator must be the line in the REAL file, not the index in the stripped list."""
    text = "  # a comment\nrun: python x.py\n#another\n    indented: true\n"
    kept = cg._strip_comment_lines(text)
    assert (2, "run: python x.py") in kept
    assert (4, "    indented: true") in kept
    assert not [ln for _, ln in kept if ln.lstrip().startswith("#")]


def test_the_reported_invocation_line_is_the_real_file_line(mirror: Path) -> None:
    """Regression: the first version reported the stripped-list index (176 for a line at 411)."""
    res = cg.probe_wiring(mirror, allow_uncommitted=True)
    raw = cg._read_text(mirror / cg.WORKFLOW_REL).replace("\r\n", "\n").split("\n")
    for lineno in res.facts["invocation_lines"]:
        assert cg.GUARD_REL in raw[lineno - 1], (
            f"line {lineno} of the workflow does not contain the invocation"
        )


def test_run_all_returns_one_result_per_declared_probe(mirror: Path) -> None:
    """Fail-closed shape: the probe list and the result vector must not drift apart."""
    results = cg.run_all(mirror, allow_uncommitted=True, skip_executed=True)
    assert [r.probe for r in results] == list(cg.PROBES[:-1])


def test_main_json_mode_reports_every_probe(capsys: pytest.CaptureFixture[str]) -> None:
    """--json emits the vector AND still ends on the terminal marker, so both are parsed."""
    rc = cg.main(["--json", "--skip-executed", "--allow-uncommitted-wiring"])
    out = capsys.readouterr().out
    body, _, marker = out.rstrip("\n").rpartition("\n")
    payload = json.loads(body)
    assert [r["probe"] for r in payload["results"]] == list(cg.PROBES[:-1])
    assert marker.startswith(("SUCCESS:casualty-guard", "FAILED:casualty-guard"))
    assert rc in (0, 1)


def test_the_guard_emits_a_terminal_marker(capsys: pytest.CaptureFixture[str]) -> None:
    """AGENTS.md 4: a terminal SUCCESS:/FAILED: marker, never open-ended prose."""
    cg.main(["--skip-executed", "--allow-uncommitted-wiring"])
    out = capsys.readouterr().out
    assert "SUCCESS:casualty-guard" in out or "FAILED:casualty-guard" in out
