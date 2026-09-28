#!/usr/bin/env python3
"""test_templates.py — the contract tests for templates/.

Run:
    .venv/Scripts/python.exe -m pytest templates/test_templates.py -q

These tests are not decoration. Each one pins a rule that, if it broke silently,
would put a false claim in front of an employer or a doctoral committee:

  * the kill-list gate fires in BOTH states (clean -> 0, every defect -> caught);
  * the gate's documentation exemption suppresses claim rules, reports itself,
    and still catches privacy leaks and anything outside the region;
  * a TODO-CONFIRM date never renders as a real date, and "present" is only
    claimed where the profile says the engagement is in progress;
  * Babes-Bolyai, tracelines and llm-anthology render on no view;
  * every ChemRxiv mention carries "preprint" and the second manuscript reads
    "in preparation";
  * the Zenodo deposit is filed under Data and software, never Publications;
  * the academic CV has no summary block;
  * the LinkedIn headline fits 220 characters and the About fits 2600;
  * Europass emits the personal-data fields EMPTY;
  * the hyphenated name is the only spelling that appears.
"""

from __future__ import annotations

import copy
import re
import sys
from pathlib import Path

import pytest
import yaml

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))

import emit
import killlist

PROFILE = ROOT / "profile.yaml"
pytestmark = pytest.mark.skipif(not PROFILE.exists(),
                                reason=f"{PROFILE} not present on this machine")


# --------------------------------------------------------------------------- #
# Fixtures                                                                     #
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="module")
def profile() -> dict:
    return emit.load_profile(PROFILE)


@pytest.fixture(scope="module")
def spec() -> dict:
    return yaml.safe_load((HERE / "academic/academic.sections.yaml").read_text("utf-8"))


@pytest.fixture(scope="module")
def design() -> dict:
    return yaml.safe_load((HERE / "academic/academic.design.yaml").read_text("utf-8"))


def _doc(profile, spec, design, todo="annotate", experience=True):
    ctx = emit.build_context(profile, todo)
    doc, _ = emit.build_academic(profile, ctx, spec, design,
                                 include_experience=experience, todo_policy=todo)
    return doc


def _text(view: str, profile, todo="annotate") -> str:
    ctx = emit.build_context(profile, todo)
    tpl = emit.VIEWS[view]["template"]
    return emit.jinja_env().get_template(tpl).render(**ctx)


# --------------------------------------------------------------------------- #
# The gate itself                                                              #
# --------------------------------------------------------------------------- #
def test_gate_self_test_passes_both_states():
    assert killlist.self_test() == 0


def test_gate_is_armed():
    assert killlist.RULES and killlist.LINE_RULES and killlist.LOCKS


@pytest.mark.parametrize("rule_id", sorted(killlist.DEFECTS))
def test_every_defect_fixture_is_caught_by_its_own_rule(rule_id):
    hits = {f.rule for f in killlist.scan(killlist.DEFECTS[rule_id], "t")}
    assert rule_id in hits


def test_exemption_does_not_cover_privacy():
    text = (f"{killlist.EXEMPT_OPEN}\nNationality: Romanian\n{killlist.EXEMPT_CLOSE}\n")
    assert any(f.rule == "F21" for f in killlist.scan(text, "t"))


def test_exemption_is_always_reported():
    text = f"{killlist.EXEMPT_OPEN}\nnothing here\n{killlist.EXEMPT_CLOSE}\n"
    assert any(f.rule == "NOTE" for f in killlist.scan(text, "t"))


# --------------------------------------------------------------------------- #
# Dates: a guess is worse than a gap                                           #
# --------------------------------------------------------------------------- #
def test_todo_date_never_renders():
    assert emit._date("TODO-CONFIRM") is None
    assert emit._date("") is None
    assert emit._date("soon") is None


def test_bare_year_stays_a_year():
    # Quoted, RenderCV reads "2022" as a full date and prints "Jan 2022".
    assert emit._date("2022") == 2022
    assert isinstance(emit._date("2022"), int)
    assert emit._date("2022-09") == "2022-09"


def _dinuplast(doc):
    exp = doc["cv"]["sections"].get("Professional experience", [])
    hits = [e for e in exp if "DINUPLAST" in str(e.get("company", ""))]
    assert hits, "DINUPLAST should render on the academic CV"
    return hits[0]


def test_resolved_end_date_renders_a_closed_range(profile, spec, design):
    """The owner supplied the end month on 2026-09-24 (OWNER-ANSWERS), closing the gap.

    The previous version of this test asserted the OPPOSITE -- that the date must
    still contain "TODO" -- so it went red the moment the gap it rode on was closed.
    A test that only passes while a defect is unfixed punishes fixing the defect;
    the state assertion belongs here and the behaviour assertion belongs in the
    test below, where no profile edit can invalidate it.
    """
    entry = _dinuplast(_doc(profile, spec, design))
    assert entry.get("end_date") != "present", \
        "a closed engagement must never render as open"
    assert "TODO" not in str(entry.get("date", "")), \
        "the end date is resolved; it must no longer render as a TODO span"
    assert str(entry.get("start_date", "")).startswith("2021-05")
    assert str(entry.get("end_date", "")).startswith("2023-06")


def test_unresolved_end_date_never_becomes_present(profile, spec, design):
    """Data-INDEPENDENT guard on the renderer, per the contract in this module's docstring.

    Mutates a COPY (the profile fixture is module-scoped, so mutating it in place
    would leak into every later test) and asserts that an unresolved endDate is
    never silently promoted to an open engagement -- which would put a false claim
    in front of a reader.
    """
    mutated = copy.deepcopy(profile)
    target = next(
        (w for w in mutated.get("work", []) if "DINUPLAST" in str(w.get("name", ""))),
        None,
    )
    assert target is not None, \
        "fixture must contain a work entry named DINUPLAST to mutate"
    target["endDate"] = "TODO-CONFIRM"

    entry = _dinuplast(_doc(mutated, spec, design))
    assert entry.get("end_date") != "present", \
        "an unresolved end date must never silently become an open engagement"
    assert "2023" not in str(entry.get("end_date", "")), \
        "an unresolved end date must not retain the previously resolved value"


# --------------------------------------------------------------------------- #
# Items that must render nowhere                                               #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("forbidden", ["Babes-Bolyai", "tracelines", "llm-anthology"])
def test_item_renders_on_no_view(profile, spec, design, forbidden):
    doc = _doc(profile, spec, design)
    assert forbidden.lower() not in yaml.safe_dump(doc, allow_unicode=True).lower()


# --------------------------------------------------------------------------- #
# Wording locks                                                                #
# --------------------------------------------------------------------------- #
def test_every_chemrxiv_mention_carries_preprint(profile, spec, design):
    pubs = _doc(profile, spec, design)["cv"]["sections"]["Publications"]
    chem = [p for p in pubs if "ChemRxiv" in str(p.get("journal", ""))]
    assert chem
    for p in chem:
        assert "preprint" in (str(p["title"]) + str(p["journal"])).lower()


def test_second_manuscript_is_in_preparation(profile, spec, design):
    pubs = _doc(profile, spec, design)["cv"]["sections"]["Publications"]
    blob = " ".join(str(p.get("title", "")) for p in pubs).lower()
    assert "in preparation" in blob
    for banned in ("submitted", "under review", "forthcoming"):
        assert banned not in blob


def test_zenodo_is_not_filed_under_publications(profile, spec, design):
    sections = _doc(profile, spec, design)["cv"]["sections"]
    assert "zenodo" not in yaml.safe_dump(sections["Publications"]).lower()
    assert "zenodo" in yaml.safe_dump(sections["Data and software"]).lower()


def test_grace_metric_renders_in_full(profile, spec, design):
    # Normalise first: YAML line-wrapping splits the sentence, and the gate
    # normalises too. A raw substring check would pass or fail on wrap width.
    blob = killlist.normalise(
        yaml.safe_dump(_doc(profile, spec, design), allow_unicode=True))
    if "0.743" in blob:
        assert "0.705" in blob
        assert "without dev-set model selection" in blob
        assert "0.737" in blob


# --------------------------------------------------------------------------- #
# Academic CV shape                                                            #
# --------------------------------------------------------------------------- #
def test_no_summary_block(profile, spec, design):
    assert spec["meta"]["summary_block"] is False
    assert "summary" not in _doc(profile, spec, design)["cv"]


def test_running_footer_and_page_numbers(design):
    page = design["design"]["page"]
    footer = design["design"]["templates"]["footer"]
    assert page["show_footer"] is True
    assert "PAGE_NUMBER" in footer and "TOTAL_PAGES" in footer
    assert page["size"] == "a4"


def test_no_page_cap(spec):
    assert spec["meta"]["page_budget"] is None


def test_empty_section_omits_itself(profile, spec, design):
    # No verified presentation exists, so a hollow heading must not print.
    assert "Presentations" not in _doc(profile, spec, design)["cv"]["sections"]


def test_references_falls_back_rather_than_vanishing(profile, spec, design):
    refs = _doc(profile, spec, design)["cv"]["sections"]["References"]
    assert refs == ["Available on request."]


def test_section_order_follows_the_spec(profile, spec, design):
    rendered = list(_doc(profile, spec, design)["cv"]["sections"])
    declared = [s["title"] for s in spec["sections"]]
    assert rendered == [t for t in declared if t in rendered]


def test_experience_can_be_switched_off(profile, spec, design):
    doc = _doc(profile, spec, design, experience=False)
    assert "Professional experience" not in doc["cv"]["sections"]


def test_omit_mode_leaves_no_todo_markers(profile, spec, design):
    blob = yaml.safe_dump(_doc(profile, spec, design, todo="omit"), allow_unicode=True)
    assert "TODO-CONFIRM" not in blob


# --------------------------------------------------------------------------- #
# Auxiliary views                                                              #
# --------------------------------------------------------------------------- #
def test_linkedin_headlines_fit(profile):
    text = _text("linkedin", profile)
    found = re.findall(r"HEADLINE \(\w\) \((\d+)/220\)", text)
    assert found, "the LinkedIn pack must report its own headline lengths"
    assert all(int(n) <= 220 for n in found)


def test_linkedin_about_fits_and_leads_strongly(profile):
    text = _text("linkedin", profile)
    about = re.search(r"<<<ABOUT>>>(.*?)<<<END ABOUT>>>", text, re.DOTALL).group(1).strip()
    assert 300 <= len(about) <= 2600
    fold = about.split("--- fold")[0].strip()
    assert 150 <= len(fold) <= 320, "the pre-fold paragraph must carry the argument alone"


@pytest.mark.parametrize("view", ["cover-en", "cover-ro"])
def test_cover_letters_share_the_identity_block(profile, view):
    text = _text(view, profile)
    ctx = emit.build_context(profile, "annotate")
    for field in (ctx["name"], ctx["email"], ctx["phone"], ctx["city"]):
        assert field in text


@pytest.mark.parametrize("view", ["europass", "europass-yaml"])
def test_europass_personal_fields_are_empty(profile, view):
    text = _text(view, profile)
    assert not killlist.errors(killlist.scan(text, view))
    low = text.lower()
    assert "nationality" in low
    for leak in ("romanian nationality", "8 june 2002", "2002-06-08"):
        assert leak not in low


def test_europass_yaml_parses(profile):
    data = yaml.safe_load(_text("europass-yaml", profile))
    pi = data["europass_cv"]["personal_information"]
    for field in ("nationality", "date_of_birth", "gender", "address"):
        assert pi[field] == "", f"{field} must be present and empty"
    assert pi["photo"] is None


@pytest.mark.parametrize("view", sorted(VIEW for VIEW in emit.VIEWS
                                        if emit.VIEWS[VIEW]["kind"] == "text"))
def test_every_text_view_passes_the_gate(profile, view):
    assert not killlist.errors(killlist.scan(_text(view, profile), view))


@pytest.mark.parametrize("view", sorted(VIEW for VIEW in emit.VIEWS
                                        if emit.VIEWS[VIEW]["kind"] == "text"))
def test_name_is_hyphenated_everywhere(profile, view):
    assert "Andrei Mihai" not in _text(view, profile)


def test_academic_document_passes_the_gate(profile, spec, design):
    blob = yaml.safe_dump(_doc(profile, spec, design), allow_unicode=True)
    assert not killlist.errors(killlist.scan(blob, "academic"))


def test_profile_name_must_be_canonical(profile):
    broken = dict(profile)
    broken["basics"] = dict(profile["basics"], name="Andrei Mihai Visalon")
    with pytest.raises(ValueError, match="canonical"):
        emit.build_context(broken, "annotate")
