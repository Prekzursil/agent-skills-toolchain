#!/usr/bin/env python3
"""Defect-as-fixture tests for zerofab.

Discipline
----------
A suite that only exercises the happy path is worthless for a lint whose entire
job is to FIRE. Every defect the shipped ``cvstudio.validate`` fails open on is
seeded here as a fixture, and the test asserts zerofab turns RED on it:

  D1  a fabricated figure with no x_metrics entry          -> ZF001
  D2  NO x_metrics block at all + digit-bearing claims     -> ZF002  (the
      shipped lint's `if haystack and ...` short-circuit: zero warnings)
  D3  fields outside work[] - summary, projects, education,
      volunteer, awards - are never scanned by the shipped lint
  D4  a comma-grouped 4-digit count ("2,024 customers")    -> ZF001  (the
      shipped lint strips commas before its 1900..2099 year test and drops it)
  D5  a kill-list phrase                                   -> ZF006
  D6  a banned word                                        -> ZF007
  D7  B/U provenance, or M/E with no how_known, rendering  -> ZF003/ZF004
  D8  "open-source" with no declared LICENSE               -> ZF008
  D9  warnings that never change the exit code             -> exit 1 + FAILED:

Each firing test is paired with a CONTROL proving the lint stays SILENT on the
honest version of the same input, so a lint that simply errors on everything
cannot pass this file. Tests D2/D3/D4 additionally assert the SHIPPED lint is
silent on the identical fixture - that asymmetry is the regression proof.

Run:
    C:\\Python314\\python.exe test_zerofab.py          (no pytest needed)
    C:\\Python314\\python.exe -m pytest test_zerofab.py -q
"""

from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import zerofab  # noqa: E402
from zerofab import ERROR, Token, lint, tokenize  # noqa: E402

ZEROFAB = Path(__file__).resolve().parent / "zerofab.py"
SHIPPED_SCRIPTS = (
    Path.home() / ".agents" / "skills" / "cv-studio" / "scripts"
)


# --------------------------------------------------------------------------- #
# The CLEAN baseline: every figure traces to an M/E x_metrics entry with a     #
# how_known. Built only from material verified this session.                   #
# --------------------------------------------------------------------------- #
def clean_profile() -> dict:
    return {
        "basics": {
            "name": "Andrei-Mihai Visalon",
            "label": "Researcher and software engineer",
            "email": "andrei-mihai.visalon@s.unibuc.ro",
            "phone": "+40 740 935 228",
            "summary": (
                "Master's student in Bucharest. Ranked first all-time by problems "
                "solved at full score on pbinfo.ro, with 4,244 solved."
            ),
            "location": {"city": "Bucharest", "countryCode": "RO"},
            "profiles": [
                {"network": "ORCID", "username": "0009-0001-8776-8498"},
                {"network": "GitHub", "username": "Prekzursil"},
            ],
        },
        "work": [
            {
                "name": "momentstudio.ro",
                "position": "Freelance software developer",
                "startDate": "2024-01",
                "highlights": [
                    "Built a bilingual RO/EN storefront and admin suite on "
                    "FastAPI and Angular to a paying client's requirements.",
                ],
            }
        ],
        "education": [
            {
                "institution": "University of Bucharest",
                "area": "Computer Science",
                "studyType": "Master's",
                "startDate": "2025-10",
                "endDate": "2027-07",
                "highlights": ["Enrolled in the master's programme in 2025."],
            }
        ],
        "projects": [
            {
                "name": "Reframe",
                "description": (
                    "Cross-platform desktop app that ships 9 releases with "
                    "signed installers."
                ),
                "highlights": [
                    "Holds 100% line-and-branch coverage as a blocking CI gate.",
                ],
            },
            {
                "name": "ZHMModSDK",
                "description": "Merged a C++ contribution into a 282-star SDK.",
                "highlights": [
                    "Added 518 lines across 7 files, merged by the maintainer.",
                ],
            },
        ],
        "languages": [{"language": "English", "fluency": "C1"}],
        "x_metrics": [
            {
                "id": "pbinfo_solved",
                "value": "4,244",
                "claim": "4,244 problems solved at full score on pbinfo.ro",
                "provenance": "E",
                "how_known": "read live from the public pbinfo.ro profile on "
                "2026-09-24 and corroborated against a Wayback capture",
            },
            {
                "id": "reframe_releases",
                "value": "9",
                "claim": "9 Reframe releases with signed installers",
                "provenance": "E",
                "how_known": "counted on the public GitHub releases page",
            },
            {
                "id": "reframe_coverage",
                "value": "100%",
                "claim": "100% line-and-branch coverage, blocking CI gate",
                "provenance": "M",
                "how_known": "read the coverage gate in the repo's CI config",
            },
            {
                "id": "zhm_lines",
                "value": "518",
                "claim": "+518 lines across 7 files in the merged ZHMModSDK PR",
                "provenance": "E",
                "how_known": "diffstat on the public merged pull request",
            },
            {
                "id": "zhm_files",
                "value": "7",
                "claim": "7 files touched in the merged ZHMModSDK PR",
                "provenance": "E",
                "how_known": "diffstat on the public merged pull request",
            },
            {
                "id": "zhm_stars",
                "value": "282",
                "claim": "282 stars on the ZHMModSDK repository",
                "provenance": "E",
                "how_known": "star count read from the public GitHub repo",
            },
        ],
    }


# --------------------------------------------------------------------------- #
# helpers                                                                      #
# --------------------------------------------------------------------------- #
def codes(findings, severity=ERROR) -> list[str]:
    return [f.code for f in findings if f.severity == severity]


def paths_for(findings, code) -> list[str]:
    return [f.path for f in findings if f.code == code]


def shipped_zerofab_warnings(profile: dict) -> list[str]:
    """Warnings the SHIPPED cvstudio lint emits. Empty == it failed open."""
    sys.path.insert(0, str(SHIPPED_SCRIPTS))
    try:
        import cvstudio  # noqa: PLC0415
    except Exception:  # pragma: no cover - shipped script unavailable
        return ["<shipped lint unavailable>"]
    _errors, warnings = cvstudio.validate(copy.deepcopy(profile))
    return [w for w in warnings if "[zero-fab] metric" in w]


def run_cli(profile: dict, suffix: str = ".json") -> subprocess.CompletedProcess:
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / f"profile{suffix}"
        if suffix == ".json":
            p.write_text(json.dumps(profile), encoding="utf-8")
        else:
            import yaml  # noqa: PLC0415

            p.write_text(yaml.safe_dump(profile), encoding="utf-8")
        return subprocess.run(
            [sys.executable, str(ZEROFAB), str(p)],
            capture_output=True,
            text=True,
        )


# --------------------------------------------------------------------------- #
# CONTROL: the honest profile must be SILENT                                   #
# --------------------------------------------------------------------------- #
def test_clean_profile_is_silent():
    found = lint(clean_profile())
    assert found == [], "clean profile produced findings:\n" + "\n".join(
        f.render() for f in found
    )


def test_clean_profile_exits_zero_and_prints_success():
    proc = run_cli(clean_profile())
    assert proc.returncode == 0, proc.stdout
    assert proc.stdout.strip().splitlines()[-1] == "SUCCESS:zerofab"


def test_clean_profile_loads_from_yaml_too():
    proc = run_cli(clean_profile(), suffix=".yaml")
    assert proc.returncode == 0, proc.stdout
    assert proc.stdout.strip().splitlines()[-1] == "SUCCESS:zerofab"


# --------------------------------------------------------------------------- #
# D1 - a seeded fabricated number                                              #
# --------------------------------------------------------------------------- #
def test_d1_seeded_fabricated_number_fires():
    p = clean_profile()
    p["work"][0]["highlights"].append("Cut deployment time by 47% across the fleet.")
    found = lint(p)
    hits = [f for f in found if f.code == zerofab.ZF_UNSOURCED]
    assert hits, "a 47% figure absent from x_metrics did not fire"
    assert "47%" in hits[0].message
    assert hits[0].path == "work[0].highlights[1]"
    assert hits[0].severity == ERROR


def test_d1_control_same_number_passes_once_it_is_evidenced():
    p = clean_profile()
    p["work"][0]["highlights"].append("Cut deployment time by 47% across the fleet.")
    p["x_metrics"].append(
        {
            "value": "47%",
            "claim": "47% deployment-time reduction",
            "provenance": "M",
            "how_known": "measured before/after on the build log",
        }
    )
    assert codes(lint(p)) == []


# --------------------------------------------------------------------------- #
# D2 - NO x_metrics block at all. The shipped lint's flagship fail-open.       #
# --------------------------------------------------------------------------- #
def test_d2_missing_x_metrics_block_is_an_error_not_a_pass():
    p = clean_profile()
    del p["x_metrics"]
    found = lint(p)
    errs = [f for f in found if f.code == zerofab.ZF_NO_METRICS]
    assert len(errs) >= 4, f"expected every figure to fire, got {len(errs)}"
    assert all(f.severity == ERROR for f in errs)
    assert any("NO \nx_metrics" in f.message or "NO x_metrics" in f.message for f in errs)


def test_d2_empty_x_metrics_list_is_also_an_error():
    p = clean_profile()
    p["x_metrics"] = []
    assert zerofab.ZF_NO_METRICS in codes(lint(p))


def test_d2_shipped_lint_stays_silent_on_the_identical_fixture():
    """The regression proof: same input, shipped lint reports nothing."""
    p = clean_profile()
    del p["x_metrics"]
    p["work"][0]["highlights"].append("Delivered 1,234,567 requests per second.")
    shipped = shipped_zerofab_warnings(p)
    if shipped == ["<shipped lint unavailable>"]:  # pragma: no cover
        return
    assert shipped == [], f"shipped lint unexpectedly fired: {shipped}"
    assert codes(lint(p)), "zerofab must fire where the shipped lint is silent"


# --------------------------------------------------------------------------- #
# D3 - fields the shipped lint never scans                                     #
# --------------------------------------------------------------------------- #
def test_d3_every_string_bearing_section_is_scanned():
    p = clean_profile()
    p["basics"]["summary"] += " Mentored 31 engineers."
    p["projects"][0]["highlights"].append("Drove 63 releases in one quarter.")
    p["education"][0]["highlights"].append("Graduated in the top 3 of 77 students.")
    p["volunteer"] = [
        {
            "organization": "Local club",
            "position": "Coach",
            "highlights": ["Coached 29 students."],
        }
    ]
    p["awards"] = [{"title": "Winner of 41 contests", "awarder": "Nobody"}]
    p["publications"] = [{"name": "A study of 53 samples", "publisher": "Nowhere"}]

    hit_paths = paths_for(lint(p), zerofab.ZF_UNSOURCED)
    for expected in (
        "basics.summary",
        "projects[0].highlights[1]",
        "education[0].highlights[1]",
        "volunteer[0].highlights[0]",
        "awards[0].title",
        "publications[0].name",
    ):
        assert expected in hit_paths, f"{expected} was never scanned; got {hit_paths}"


def test_d3_shipped_lint_scans_none_of_those_sections():
    p = clean_profile()
    p["basics"]["summary"] += " Mentored 31 engineers."
    p["projects"][0]["highlights"].append("Drove 63 releases in one quarter.")
    p["awards"] = [{"title": "Winner of 41 contests", "awarder": "Nobody"}]
    shipped = shipped_zerofab_warnings(p)
    if shipped == ["<shipped lint unavailable>"]:  # pragma: no cover
        return
    assert all(
        tok not in " ".join(shipped) for tok in ("31", "63", "41")
    ), f"shipped lint unexpectedly scanned outside work[]: {shipped}"


# --------------------------------------------------------------------------- #
# D4 - the comma-grouped four-digit count bug                                  #
# --------------------------------------------------------------------------- #
def test_d4_comma_grouped_four_digit_count_fires():
    p = clean_profile()
    p["work"][0]["highlights"].append("Served 2,024 customers in the storefront.")
    hits = [f for f in lint(p) if f.code == zerofab.ZF_UNSOURCED]
    assert hits, "a comma-grouped 2,024 was swallowed as a year"
    assert "2,024" in hits[0].message


def test_d4_control_a_bare_year_is_still_exempt():
    p = clean_profile()
    p["work"][0]["highlights"].append("Joined the project in 2024 and shipped it.")
    assert codes(lint(p)) == [], "a bare year must not be treated as a claim"


def test_d4_token_year_classification():
    assert tokenize("in 2024")[0].is_year is True
    grouped = tokenize("2,024 customers")[0]
    assert grouped.grouped is True
    assert grouped.is_year is False, "comma-grouped counts are not years"
    assert tokenize("2024+ users")[0].is_year is False
    assert tokenize("$2024 saved")[0].is_year is False
    assert tokenize("2024K requests")[0].is_year is False
    assert tokenize("1899 things")[0].is_year is False
    assert Token("2100", "2100", "", False, False, False).is_year is False


def test_d4_shipped_lint_swallows_the_grouped_count():
    """Prove the bonus bug exists in the shipped implementation."""
    sys.path.insert(0, str(SHIPPED_SCRIPTS))
    try:
        import cvstudio  # noqa: PLC0415
    except Exception:  # pragma: no cover
        return
    assert cvstudio._flag_metrics("Served 2,024 customers.") == [], (
        "shipped bonus bug is gone - re-check this suite's premise"
    )
    assert tokenize("Served 2,024 customers.")[0].is_year is False


# --------------------------------------------------------------------------- #
# D5 - kill list                                                               #
# --------------------------------------------------------------------------- #
def test_d5_kill_list_phrase_fires():
    p = clean_profile()
    p["work"][0]["highlights"].append("Merged 1,590 PRs across the monorepo.")
    found = lint(p)
    assert zerofab.ZF_KILL_LIST in codes(found)
    assert any("1,590 merged PRs" in f.message for f in found)


def test_d5_the_candidacy_ending_phrase_fires():
    p = clean_profile()
    p["awards"] = [{"title": "Finished 4th overall at GRACE @ IberLEF 2026"}]
    found = lint(p)
    assert zerofab.ZF_KILL_LIST in codes(found)
    assert any("FABRICATED DOCUMENT" in f.message for f in found)


def test_d5_kill_list_is_comma_insensitive_and_covers_the_roster():
    seeds = {
        "6,432 contributions to the monorepo": zerofab.ZF_KILL_LIST,
        "Wrote 556K LOC and 345K lines of code": zerofab.ZF_KILL_LIST,
        "Authored 400+ skills for the platform": zerofab.ZF_KILL_LIST,
        "Wrote 40+ MCP servers": zerofab.ZF_KILL_LIST,
        "Ran a 1000-agent audit": zerofab.ZF_KILL_LIST,
        "A 97-slice audit produced 1,582 findings": zerofab.ZF_KILL_LIST,
        "Found 3 critical RCE issues": zerofab.ZF_KILL_LIST,
        "Built a 12,272-record corpus": zerofab.ZF_KILL_LIST,
        "Swept a 26-repo fleet": zerofab.ZF_KILL_LIST,
        "Shipped Reframe v1.4.2": zerofab.ZF_KILL_LIST,
        "A peer-reviewed publication in the field": zerofab.ZF_KILL_LIST,
        "Ran the 608-unit Databricks fan-out": zerofab.ZF_KILL_LIST,
        "Reframe reached 5,000 downloads": zerofab.ZF_KILL_LIST,
    }
    for text, code in seeds.items():
        p = clean_profile()
        p["work"][0]["highlights"].append(text)
        assert code in codes(lint(p)), f"kill-list miss on: {text}"


def test_d5_control_the_corrected_wording_is_clean():
    p = clean_profile()
    p["work"][0]["highlights"].append("Opened 351 pull requests in the monorepo.")
    p["x_metrics"].append(
        {
            "value": "351",
            "claim": "351 pull requests in the monorepo, Mar-Sep 2026",
            "provenance": "M",
            "how_known": "counted from the repo's own PR list",
        }
    )
    assert codes(lint(p)) == []


# --------------------------------------------------------------------------- #
# D6 - banned words                                                            #
# --------------------------------------------------------------------------- #
def test_d6_banned_words_fire():
    for text in (
        "Ships 8,000 passing tests.",
        "Keeps all gates green on every push.",
        "The tool is widely used by researchers.",
    ):
        p = clean_profile()
        p["projects"][0]["highlights"].append(text)
        assert zerofab.ZF_BANNED_WORD in codes(lint(p)), f"banned-word miss: {text}"


def test_d6_control_provenance_verb_is_clean():
    p = clean_profile()
    p["projects"][0]["highlights"].append("Ships 8,000 test functions.")
    p["x_metrics"].append(
        {
            "value": "8,000",
            "claim": "8,000 test functions in the suite",
            "provenance": "M",
            "how_known": "counted with a collect-only run of the suite",
        }
    )
    found = lint(p)
    assert zerofab.ZF_BANNED_WORD not in codes(found)
    assert codes(found) == []


# --------------------------------------------------------------------------- #
# D7 - provenance discipline                                                   #
# --------------------------------------------------------------------------- #
def test_d7_believed_provenance_must_not_render():
    p = clean_profile()
    p["work"][0]["highlights"].append("Ran 689 agent launches in the window.")
    p["x_metrics"].append(
        {
            "value": "689",
            "claim": "689 agent launches",
            "provenance": "B",
            "how_known": "recalled from a previous session",
        }
    )
    found = lint(p)
    assert zerofab.ZF_WEAK_PROV in codes(found)
    assert any("tagged B" in f.message for f in found)


def test_d7_measured_without_how_known_is_an_error():
    p = clean_profile()
    p["work"][0]["highlights"].append("Ran 689 agent launches in the window.")
    p["x_metrics"].append(
        {"value": "689", "claim": "689 agent launches", "provenance": "M"}
    )
    found = lint(p)
    assert zerofab.ZF_NO_HOW_KNOWN in codes(found)
    assert zerofab.ZF_WEAK_PROV in codes(found)


def test_d7_invalid_provenance_tag_is_an_error():
    p = clean_profile()
    p["x_metrics"][0]["provenance"] = "verified"
    assert zerofab.ZF_BAD_TAG in codes(lint(p))


def test_d7_legacy_bare_string_metrics_license_nothing():
    """The shipped sample format - a list of prose strings - is not evidence."""
    p = clean_profile()
    p["x_metrics"] = [
        "4,244 problems solved at full score",
        "9 releases with signed installers",
        "100% line-and-branch coverage",
        "518 lines across 7 files",
        "282 stars",
    ]
    found = lint(p)
    assert zerofab.ZF_LEGACY_METRIC in codes(found)
    assert zerofab.ZF_WEAK_PROV in codes(found)


# --------------------------------------------------------------------------- #
# D8 - "open-source" needs a LICENSE                                           #
# --------------------------------------------------------------------------- #
def test_d8_open_source_without_license_fires():
    p = clean_profile()
    p["projects"][0]["description"] = "An open-source cross-platform desktop app."
    found = lint(p)
    assert zerofab.ZF_OPEN_SOURCE in codes(found)
    assert any("no LICENSE" in f.message for f in found)


def test_d8_control_declared_license_clears_it():
    p = clean_profile()
    p["projects"][0]["description"] = "An open-source cross-platform desktop app."
    p["projects"][0]["license"] = "MIT"
    assert zerofab.ZF_OPEN_SOURCE not in codes(lint(p))


def test_d8_control_explicit_allow_entry_clears_it():
    p = clean_profile()
    p["basics"]["summary"] += " Open-sourced the GRACE benchmark."
    p["x_zerofab"] = {"open_source_licensed": ["GRACE benchmark"]}
    assert zerofab.ZF_OPEN_SOURCE not in codes(lint(p))


# --------------------------------------------------------------------------- #
# D9 - findings must change the exit code                                      #
# --------------------------------------------------------------------------- #
def test_d9_errors_exit_nonzero_and_print_failed():
    p = clean_profile()
    del p["x_metrics"]
    proc = run_cli(p)
    assert proc.returncode != 0
    assert proc.stdout.strip().splitlines()[-1] == "FAILED:zerofab"


def test_d9_unreadable_profile_fails_closed():
    proc = subprocess.run(
        [sys.executable, str(ZEROFAB), str(Path(__file__).parent / "no_such.json")],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 2
    assert proc.stdout.strip().splitlines()[-1] == "FAILED:zerofab"


def test_d9_json_output_shape():
    p = clean_profile()
    p["work"][0]["highlights"].append("Served 2,024 customers.")
    with tempfile.TemporaryDirectory() as td:
        f = Path(td) / "p.json"
        f.write_text(json.dumps(p), encoding="utf-8")
        proc = subprocess.run(
            [sys.executable, str(ZEROFAB), str(f), "--json"],
            capture_output=True,
            text=True,
        )
    body = json.loads(proc.stdout.rsplit("FAILED:zerofab", 1)[0])
    assert body["errors"] >= 1
    assert any(f["code"] == zerofab.ZF_UNSOURCED for f in body["findings"])


# --------------------------------------------------------------------------- #
# Guardrails on the guardrail                                                  #
# --------------------------------------------------------------------------- #
def test_identifier_fields_do_not_need_x_metrics():
    p = clean_profile()
    p["basics"]["phone"] = "+40 740 935 228"
    p["basics"]["url"] = "https://github.com/Prekzursil/x123"
    p["publications"] = [
        {"name": "A preprint", "doi": "10.26434/chemrxiv-2026-12345"}
    ]
    hits = paths_for(lint(p), zerofab.ZF_UNSOURCED)
    assert not any(
        h.endswith(("phone", "url", "doi", "username")) for h in hits
    ), hits


def test_cefr_level_and_semver_are_not_claims():
    p = clean_profile()
    p["languages"] = [{"language": "English", "fluency": "C1/C2"}]
    p["projects"][0]["highlights"].append("Renders through Typst 0.15.0.")
    assert codes(lint(p)) == []


def test_allow_list_entry_without_a_reason_is_an_error():
    p = clean_profile()
    p["x_zerofab"] = {"allow": [{"text": "9:16"}]}
    assert zerofab.ZF_BAD_ALLOW in codes(lint(p))


def test_allow_list_entry_with_a_reason_exempts_and_is_reported():
    p = clean_profile()
    p["projects"][0]["highlights"].append("Reframes 16:9 footage to 9:16.")
    p["x_zerofab"] = {
        "allow": [{"text": "16:9", "reason": "aspect ratios, not claims"}]
    }
    found = lint(p)
    assert codes(found) == []
    assert any(f.severity == zerofab.INFO for f in found), "exemption must be visible"


def test_unused_verified_metric_warns_but_does_not_fail():
    p = clean_profile()
    p["x_metrics"].append(
        {
            "value": "88",
            "claim": "88 published problems authored on pbinfo.ro",
            "provenance": "E",
            "how_known": "counted on the public author page",
        }
    )
    found = lint(p)
    assert codes(found) == []
    assert zerofab.ZF_ORPHAN_METRIC in codes(found, zerofab.WARN)


def test_non_mapping_profile_fails_closed():
    assert lint(["not", "a", "profile"])[0].code == zerofab.ZF_SHAPE


# --------------------------------------------------------------------------- #
# Standalone runner (no pytest required)                                       #
# --------------------------------------------------------------------------- #
def _main() -> int:
    tests = [
        (n, o)
        for n, o in sorted(globals().items())
        if n.startswith("test_") and callable(o)
    ]
    failed = []
    for name, fn in tests:
        try:
            fn()
        except AssertionError as exc:
            failed.append((name, f"AssertionError: {exc}"))
            print(f"FAIL {name}\n     {exc}")
        except Exception as exc:  # noqa: BLE001
            failed.append((name, f"{type(exc).__name__}: {exc}"))
            print(f"ERROR {name}\n     {type(exc).__name__}: {exc}")
        else:
            print(f"ok   {name}")
    print(f"\n{len(tests) - len(failed)}/{len(tests)} passed")
    if failed:
        print("FAILED:test_zerofab")
        return 1
    print("SUCCESS:test_zerofab")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
