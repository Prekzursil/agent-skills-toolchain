#!/usr/bin/env python3
"""Tests for tools/convert_cv.py — rendered views -> Claude Design data files.

Run:  ~/.agents/cv/.venv/Scripts/python -m pytest tools/test_convert_cv.py -q

The converter must COPY, never write: every claim in the output has to be the
text the zerofab-gated intermediate already holds, with only markdown markup
removed. So the fixtures below carry an unresolved TODO-CONFIRM marker and
assert it survives untouched.

Both states for the input contract: a missing or ambiguous input must refuse
(non-zero, FAILED:convert, nothing written), not produce an empty file.

Every fixture persona below is fictional. Nothing here touches the real
profile.yaml or out/.
"""

from __future__ import annotations

import json
import sys
import textwrap
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))

import convert_cv as C  # noqa: E402

ATS = textwrap.dedent(
    """
    cv:
      name: Dana Fictional
      headline: Test **persona**
      location: Testville, XX
      email: dana.fictional@example.com
      phone: tel:+00-111-222-333
      social_networks:
        - {network: GitHub, username: danafictional}
        - {network: ORCID, username: 0000-0000-0000-0000}
      sections:
        Summary:
          - Builds fixture pipelines. TODO-CONFIRM exact years.
        Experience:
          - company: Example Labs
            position: Engineer
            location: Testville
            start_date: 2022-09
            end_date: present
            highlights:
              - Shipped the [fixture repo](https://example.com/repo) to **3** teams.
        Education:
          - {institution: Test University, degree: BSc, area: Testing, start_date: 2019, end_date: 2022}
        Projects:
          - name: Fixture Tool
            date: 2024
            summary: A tool.
            highlights: [Used by two teams.]
            url: https://example.com/tool
        Skills:
          - {label: Languages, details: Python}
        Languages:
          - {label: English, details: C1}
        Honors:
          - {bullet: Fixture award}
    """
)

ACADEMIC = textwrap.dedent(
    """
    cv:
      name: Dana Fictional
      headline: Researcher
      location: Testville, XX
      email: dana.fictional@example.com
      sections:
        Education:
          - {institution: Test University, degree: MSc, area: Data, start_date: 2025, end_date: present}
        Research engineering:
          - {name: Pipeline A, date: 2025, summary: Reproducible runs.}
        Data and software:
          - {name: Dataset B, date: 2024, summary: Open data.}
        Research output:
          - {title: A fixture study., authors: [D. Fictional, E. Example]}
        Languages:
          - {label: English, details: C1}
        Honors:
          - {bullet: Fixture grant}
    """
)


def _src(tmp_path: Path, ats: str | None = ATS, academic: str | None = ACADEMIC) -> Path:
    src = tmp_path / "out"
    src.mkdir()
    if ats is not None:
        (src / "Dana_Fictional_ats_en.rendercv.yaml").write_text(ats, encoding="utf-8")
    if academic is not None:
        (src / "Dana_Fictional_academic.rendercv.yaml").write_text(academic, encoding="utf-8")
    return src


def _load(path: Path, var: str) -> dict:
    text = path.read_text(encoding="utf-8")
    prefix = f"window.{var} = "
    body = text[text.index(prefix) + len(prefix):].rstrip()
    assert body.endswith(";")
    return json.loads(body[:-1])


def test_plain_strips_markup_only():
    assert C.plain("[repo](https://x.example) and **bold** __u__") == "repo and bold u"
    assert C.plain("  TODO-CONFIRM stays  ") == "TODO-CONFIRM stays"


def test_year_keeps_present_and_takes_the_year():
    assert C.year("present") == "Present"
    assert C.year("2022-09") == "2022"
    assert C.year(2019) == "2019"
    assert C.year(None) == ""


def test_converts_both_views_verbatim(tmp_path, capsys):
    out = tmp_path / "design"
    assert C.main(["--src", str(_src(tmp_path)), "--out", str(out)]) == 0
    assert "SUCCESS:convert" in capsys.readouterr().out

    main = _load(out / "resume.js", "RESUME")
    assert list(main) == ["name", "title", "location", "contact", "summary", "experience",
                          "education", "projects", "publications", "skills", "languages",
                          "certifications", "honors"]
    assert main["title"] == "Test persona"
    assert main["summary"] == "Builds fixture pipelines. TODO-CONFIRM exact years."
    assert main["contact"][2] == {"kind": "phone", "value": "+00-111-222-333", "href": "tel:+00111222333"}
    assert main["contact"][4] == {"kind": "orcid", "value": "ORCID 0000-0000-0000-0000",
                                  "href": "https://orcid.org/0000-0000-0000-0000"}
    job = main["experience"][0]
    assert (job["org"], job["start"], job["end"]) == ("Example Labs, Testville", "2022", "Present")
    assert job["bullets"] == ["Shipped the fixture repo to 3 teams."]
    assert main["projects"][0] == {"name": "Fixture Tool", "kind": "", "start": "2024", "end": "",
                                   "description": "A tool. Used by two teams.",
                                   "url": "https://example.com/tool"}
    assert main["publications"] == [] and main["certifications"] == []
    assert main["honors"] == ["Fixture award"]

    acad = _load(out / "resume-academic.js", "RESUME_ACADEMIC")
    assert acad["summary"] == "" and acad["experience"] == [] and acad["skills"] == []
    assert [p["name"] for p in acad["projects"]] == ["Pipeline A", "Dataset B"]
    assert acad["publications"] == [{"citation": "D. Fictional, E. Example. A fixture study.",
                                     "venue": "Preprint"}]


def test_output_is_lf_with_provenance_header(tmp_path):
    out = tmp_path / "design"
    assert C.main(["--src", str(_src(tmp_path)), "--out", str(out)]) == 0
    raw = (out / "resume.js").read_bytes()
    assert b"\r\n" not in raw
    assert raw.startswith(b"// Real content, converted verbatim from the zero-fabrication CV pipeline (ats_en view).\n")


@pytest.mark.parametrize("ats,academic", [(None, ACADEMIC), (ATS, None)])
def test_missing_view_refuses_and_writes_nothing(tmp_path, capsys, ats, academic):
    out = tmp_path / "design"
    assert C.main(["--src", str(_src(tmp_path, ats, academic)), "--out", str(out)]) != 0
    assert "FAILED:convert" in capsys.readouterr().out
    assert not out.exists()


def test_ambiguous_view_refuses(tmp_path, capsys):
    src = _src(tmp_path)
    (src / "Other_Person_ats_en.rendercv.yaml").write_text(ATS, encoding="utf-8")
    out = tmp_path / "design"
    assert C.main(["--src", str(src), "--out", str(out)]) != 0
    assert "FAILED:convert" in capsys.readouterr().out
    assert not out.exists()
