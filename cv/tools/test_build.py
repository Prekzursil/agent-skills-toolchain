#!/usr/bin/env python3
"""Tests for tools/build.py — the render pipeline and its fail-closed gate.

Run:  ~/.agents/cv/.venv/Scripts/python -m pytest tools/test_build.py -q

The point of most of these is BOTH STATES: it is not enough that a passing gate
lets a render through — a failing gate, and a MISSING gate, must each stop it.
A gate that only ever passes is not a gate.

Every fixture persona below is fictional. Nothing here touches the real
profile.yaml.
"""

from __future__ import annotations

import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parent
BUILD = TOOLS / "build.py"
sys.path.insert(0, str(TOOLS))

import build as B  # noqa: E402

FIXTURE_PROFILE = textwrap.dedent(
    """
    basics:
      name: Dana Fictional
      label: Test persona
      email: dana.fictional@example.com
      summary: A fixture persona used only to test the render pipeline.
      location: {city: Testville, countryCode: XX}
      birthDate: "1990-01-01"
      profiles:
        - {network: GitHub, username: danafictional}
    work:
      - name: Example Works SRL
        position: Engineer
        startDate: 2020-01
        endDate: 2022-06
        highlights: [Did a thing that can be checked.]
      - name: Later Labs
        position: Senior Engineer
        startDate: 2022-07
        endDate: TODO-CONFIRM
        highlights: [Did another thing.]
    education:
      - institution: Universitatea Babes-Bolyai
        area: Computer Science
        studyType: BSc
        startDate: 2015-09
        endDate: 2016-07
      - institution: Testville Polytechnic
        area: Computer Science
        studyType: BSc
        startDate: 2016-09
        endDate: 2019-07
    skills:
      - {name: Languages, keywords: [Python, SQL]}
    languages:
      - {language: English, fluency: Advanced}
    x_privacy:
      held_but_never_rendered: {date_of_birth: "1990-01-01"}
    x_views:
      - id: full
        page_size: A4
        section_order: [Summary, Experience, Education, Skills, Languages]
      - id: no-ubb
        page_size: A4
        include_ubb: false
        section_order: [Summary, Education]
      - id: merged-titles
        page_size: A4
        section_order: [Summary, "Selected software (things)", "Research engineering (more)"]
      - id: textonly
        outputs: [headline, about]
      - id: designed-view
        engine: design pipeline
    """
)

GATE_PASS = "import sys\nprint('gate: ok')\nsys.exit(0)\n"
GATE_FAIL = "import sys\nprint('gate: 1 fabricated figure')\nsys.exit(1)\n"
GATE_NEEDS_PROFILE_FLAG = textwrap.dedent(
    """
    import argparse, sys
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", required=True)
    ap.add_argument("--view")
    a = ap.parse_args()
    print("gate saw", a.profile)
    sys.exit(0)
    """
)


@pytest.fixture
def work(tmp_path: Path) -> Path:
    (tmp_path / "profile.yaml").write_text(FIXTURE_PROFILE, encoding="utf-8")
    (tmp_path / "out").mkdir()
    return tmp_path


def run_build(work: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(BUILD), "--profile", str(work / "profile.yaml"),
         "--out", str(work / "out"), *args],
        capture_output=True, text=True, check=False, encoding="utf-8", errors="replace",
    )


# ---------------------------------------------------------------- the gate -- #
def test_gate_missing_refuses_to_render(work: Path):
    """FAIL CLOSED: no gate on disk must NOT mean 'nothing to check'."""
    r = run_build(work, "--view", "full", "--gate", str(work / "nope.py"))
    assert r.returncode == 3, r.stdout
    assert r.stdout.strip().splitlines()[-1] == "FAILED:full"
    assert not list((work / "out").glob("*.pdf")), "a refused build must leave no PDF"


def test_gate_failing_refuses_to_render(work: Path):
    (work / "gate.py").write_text(GATE_FAIL, encoding="utf-8")
    r = run_build(work, "--view", "full", "--gate", str(work / "gate.py"))
    assert r.returncode == 3, r.stdout
    assert "gate: 1 fabricated figure" in r.stdout      # the gate's own words survive
    assert r.stdout.strip().splitlines()[-1] == "FAILED:full"
    assert not list((work / "out").glob("*.pdf"))


def test_gate_passing_renders_and_verifies(work: Path):
    """The other state: a passing gate produces a real, contract-clean PDF."""
    (work / "gate.py").write_text(GATE_PASS, encoding="utf-8")
    r = run_build(work, "--view", "full", "--gate", str(work / "gate.py"))
    assert r.returncode == 0, r.stdout + r.stderr
    assert r.stdout.strip().splitlines()[-1] == "SUCCESS:full"
    pdfs = list((work / "out").glob("*.pdf"))
    assert len(pdfs) == 1 and pdfs[0].stat().st_size > 10_000
    for code in ("C1", "C2", "C3", "C4", "C5", "C6", "C7"):
        assert f"PASS  {code}" in r.stdout


def test_gate_cli_shape_is_probed_not_assumed(work: Path):
    """A gate that takes --profile instead of a positional still runs."""
    (work / "gate.py").write_text(GATE_NEEDS_PROFILE_FLAG, encoding="utf-8")
    r = run_build(work, "--view", "full", "--gate", str(work / "gate.py"))
    assert r.returncode == 0, r.stdout + r.stderr
    assert "gate saw" in r.stdout


def test_gate_runs_before_the_renderer(work: Path):
    """Ordering is the whole design: a failing gate must leave no intermediate."""
    (work / "gate.py").write_text(GATE_FAIL, encoding="utf-8")
    run_build(work, "--view", "full", "--gate", str(work / "gate.py"))
    assert not list((work / "out").glob("*.rendercv.yaml"))


def test_skip_gate_is_loud(work: Path):
    r = run_build(work, "--view", "full", "--skip-gate")
    assert r.returncode == 0
    assert "SKIPPED via --skip-gate" in r.stdout
    assert "must not be sent to anyone" in r.stdout


# ------------------------------------------------------------ view mechanics -- #
def test_list_shaped_x_views_resolve():
    profile = B.load_yaml_string(FIXTURE_PROFILE) if hasattr(B, "load_yaml_string") else None
    if profile is None:
        import io

        import ruamel.yaml

        profile = ruamel.yaml.YAML(typ="safe").load(io.StringIO(FIXTURE_PROFILE))
    assert B.list_views(profile) == ["full", "no-ubb", "merged-titles",
                                     "textonly", "designed-view"]
    view = B.resolve_view(profile, "full")
    assert view["sections"] == ["summary", "experience", "education", "skills", "languages"]
    assert view["page"] == "A4"


def test_include_ubb_false_drops_that_institution(work: Path):
    (work / "gate.py").write_text(GATE_PASS, encoding="utf-8")
    r = run_build(work, "--view", "no-ubb", "--gate", str(work / "gate.py"))
    assert r.returncode == 0, r.stdout
    import json

    m = json.loads(next((work / "out").glob("*no_ubb.manifest.json")).read_text())
    assert m["institutions"] == ["Testville Polytechnic"]


def test_duplicate_section_titles_merge_with_a_warning(work: Path):
    (work / "gate.py").write_text(GATE_PASS, encoding="utf-8")
    r = run_build(work, "--view", "merged-titles", "--gate", str(work / "gate.py"),
                  "--emit-only")
    assert "already rendered as" in r.stdout


def test_non_pdf_views_are_skipped_not_failed(work: Path):
    for view in ("textonly", "designed-view"):
        r = run_build(work, "--view", view, "--skip-gate")
        assert r.returncode == 0, r.stdout
        assert r.stdout.strip().splitlines()[-1] == f"SKIPPED:{view}"


def test_unknown_view_is_an_error_not_a_default(work: Path):
    r = run_build(work, "--view", "does-not-exist", "--skip-gate")
    assert r.returncode == 2
    assert r.stdout.strip().splitlines()[-1] == "FAILED:does-not-exist"


# -------------------------------------------------------- honesty guardrails -- #
def test_unparseable_date_is_never_silently_turned_into_present(work: Path):
    """`endDate: TODO-CONFIRM` must not become 'present' — that would assert an
    ongoing engagement nobody verified."""
    (work / "gate.py").write_text(GATE_PASS, encoding="utf-8")
    r = run_build(work, "--view", "full", "--gate", str(work / "gate.py"))
    assert r.returncode == 0, r.stdout
    yaml_text = next((work / "out").glob("*.rendercv.yaml")).read_text(encoding="utf-8")
    assert "TODO-CONFIRM" in yaml_text            # the uncertainty survives
    assert "end_date: present" not in yaml_text   # but is not upgraded to a claim


def test_personal_data_is_stripped_from_parsed_views(work: Path):
    (work / "gate.py").write_text(GATE_PASS, encoding="utf-8")
    r = run_build(work, "--view", "full", "--gate", str(work / "gate.py"))
    assert r.returncode == 0
    yaml_text = next((work / "out").glob("*.rendercv.yaml")).read_text(encoding="utf-8")
    assert "1990-01-01" not in yaml_text
    assert "PASS  C6" in r.stdout


def test_todo_policy_fail_blocks_the_build(work: Path):
    import io

    import ruamel.yaml

    profile = ruamel.yaml.YAML(typ="safe").load(io.StringIO(FIXTURE_PROFILE))
    profile["x_views"][0]["todo_policy"] = "fail"
    y = ruamel.yaml.YAML()
    with (work / "profile.yaml").open("w", encoding="utf-8") as fh:
        y.dump(profile, fh)
    r = run_build(work, "--view", "full", "--skip-gate")
    assert r.returncode == 2
    assert "todo_policy=fail" in r.stdout


def test_page_budget_override_can_fail_a_render(work: Path):
    """C3 must be able to reject a document that is too long."""
    (work / "gate.py").write_text(GATE_PASS, encoding="utf-8")
    r = run_build(work, "--view", "full", "--gate", str(work / "gate.py"),
                  "--page-budget", "3-4")
    assert r.returncode == 5, r.stdout
    assert "FAIL  C3" in r.stdout
    assert r.stdout.strip().splitlines()[-1] == "FAILED:full"


def test_a4_is_the_page_size_that_reaches_the_renderer(work: Path):
    (work / "gate.py").write_text(GATE_PASS, encoding="utf-8")
    run_build(work, "--view", "full", "--gate", str(work / "gate.py"), "--emit-only")
    yaml_text = next((work / "out").glob("*.rendercv.yaml")).read_text(encoding="utf-8")
    assert "size: a4" in yaml_text
