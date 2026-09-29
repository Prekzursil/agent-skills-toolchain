#!/usr/bin/env python3
"""cv/tools/convert_cv.py — copy two rendered views into Claude Design data files.

The Claude Design project "Resume design system" reads the CV from two scripts,
data/resume.js (window.RESUME) and data/resume-academic.js (window.RESUME_ACADEMIC).
This tool builds them from the intermediates tools/build.py writes AFTER the
zerofab gate, so nothing reaches the designs that the gate has not passed:

    out/<slug>_ats_en.rendercv.yaml    ->  <out>/resume.js
    out/<slug>_academic.rendercv.yaml  ->  <out>/resume-academic.js

It copies, never writes: text passes through verbatim with only markdown markup
([text](url), **, __) removed, and unresolved facts stay visible as TODO-CONFIRM
markers. To change a claim, change profile.yaml, rebuild, then rerun this.

Usage
-----
    PY=~/.agents/cv/.venv/Scripts/python          # POSIX venv: .venv/bin/python
    $PY tools/build.py --view ats-en
    $PY tools/build.py --view academic
    $PY tools/convert_cv.py                       # -> out/design/data/
    $PY tools/convert_cv.py --src out --out <dir>

Then upload both files to the project's data/ folder with /design-sync.

Exit codes: 0 ok · 2 input missing, ambiguous or unreadable.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import re
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

# Windows consoles default to cp1252 on Python 3.14; one em dash in a log line
# would otherwise raise UnicodeEncodeError and lose the terminal SUCCESS/FAILED.
# A replaced stream (pytest capture) has no reconfigure(): leave it as it is.
for _stream in (sys.stdout, sys.stderr):
    with contextlib.suppress(AttributeError, OSError, ValueError):
        _stream.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent          # ~/.agents/cv
DEFAULT_SRC = ROOT / "out"
DEFAULT_OUT = ROOT / "out" / "design" / "data"
HEADER = ("// Real content, converted verbatim from the zero-fabrication CV pipeline ({label}).\n"
          "// Copied as rendered: unresolved facts stay visible as TODO markers. "
          "Do not reword claims here; change them in the pipeline.\n")


class InputError(Exception):
    """An input view is missing, ambiguous or unreadable."""


def plain(s: Any) -> str:
    s = str(s)
    s = re.sub(r"\[([^\]]+)\]\((?:[^)]+)\)", r"\1", s)
    return s.replace("**", "").replace("__", "").strip()


def year(d: Any) -> str:
    if d is None:
        return ""
    d = str(d).strip()
    if d.lower() == "present":
        return "Present"
    m = re.match(r"(\d{4})", d)
    return m.group(1) if m else plain(d)


def contact(cv: dict[str, Any]) -> list[dict[str, str]]:
    c = []
    if cv.get("location"):
        c.append({"kind": "location", "value": plain(cv["location"])})
    if cv.get("email"):
        c.append({"kind": "email", "value": cv["email"], "href": "mailto:" + cv["email"]})
    if cv.get("phone"):
        ph = str(cv["phone"]).replace("tel:", "")
        c.append({"kind": "phone", "value": ph, "href": "tel:" + re.sub(r"[^\d+]", "", ph)})
    for s in cv.get("social_networks") or []:
        n, u = s.get("network", ""), s.get("username", "")
        if n == "GitHub":
            c.append({"kind": "github", "value": "github.com/" + u, "href": "https://github.com/" + u})
        elif n == "LinkedIn":
            c.append({"kind": "linkedin", "value": "linkedin.com/in/" + u, "href": "https://linkedin.com/in/" + u})
        elif n == "ORCID":
            c.append({"kind": "orcid", "value": "ORCID " + u, "href": "https://orcid.org/" + u})
        else:
            c.append({"kind": n.lower(), "value": u})
    return c


def base(cv: dict[str, Any]) -> dict[str, Any]:
    return {"name": cv["name"], "title": plain(cv.get("headline", "")),
            "location": plain(cv.get("location", "")), "contact": contact(cv)}


def experience(e: dict[str, Any]) -> dict[str, Any]:
    return {"role": plain(e.get("position", "")),
            "org": plain(", ".join(x for x in (e.get("company"), e.get("location")) if x)),
            "start": year(e.get("start_date")),
            "end": year(e.get("end_date")) if e.get("start_date") else "",
            "bullets": [plain(h) for h in e.get("highlights") or []]}


def education(entries: list[dict[str, Any]]) -> list[dict[str, str]]:
    return [{"degree": plain(" ".join(x for x in (e.get("degree"), e.get("area")) if x)),
             "school": plain(e.get("institution", "")),
             "start": year(e.get("start_date")), "end": year(e.get("end_date"))} for e in entries]


def projects(entries: list[dict[str, Any]]) -> list[dict[str, str]]:
    out = []
    for e in entries:
        desc = " ".join([plain(e.get("summary", ""))] + [plain(h) for h in e.get("highlights") or []]).strip()
        out.append({"name": plain(e.get("name", "")), "kind": "",
                    "start": year(e.get("start_date") or e.get("date")), "end": year(e.get("end_date")),
                    "description": desc, **({"url": e["url"]} if e.get("url") else {})})
    return out


def publication(e: dict[str, Any]) -> dict[str, str]:
    authors = e.get("authors") or []
    citation = (plain(", ".join(authors)) + ". " if authors else "") + plain(e.get("title", "")).rstrip(".") + "."
    return {"citation": citation, "venue": plain(e.get("journal", "")) or "Preprint"}


def pairs(entries: list[dict[str, Any]], a: str, b: str) -> list[dict[str, str]]:
    return [{a: plain(e.get("label", "")), b: plain(e.get("details", ""))} for e in entries]


def honors(entries: list[Any]) -> list[str]:
    return [plain(e.get("bullet", e) if isinstance(e, dict) else e) for e in entries]


def convert_main(cv: dict[str, Any]) -> dict[str, Any]:
    s = cv["sections"]
    doc = base(cv)
    doc["summary"] = plain((s.get("Summary") or [""])[0])
    doc["experience"] = [experience(e) for e in s.get("Experience", [])]
    doc["education"] = education(s.get("Education", []))
    doc["projects"] = projects(s.get("Projects", []))
    doc["publications"] = []
    doc["skills"] = pairs(s.get("Skills", []), "group", "items")
    doc["languages"] = pairs(s.get("Languages", []), "name", "level")
    doc["certifications"] = []
    doc["honors"] = honors(s.get("Honors", []))
    return doc


def convert_academic(cv: dict[str, Any]) -> dict[str, Any]:
    s = cv["sections"]
    doc = base(cv)
    doc["summary"] = ""
    doc["experience"] = []
    doc["education"] = education(s.get("Education", []))
    doc["projects"] = projects(s.get("Research engineering", [])) + projects(s.get("Data and software", []))
    doc["publications"] = [publication(e) for e in s.get("Research output", [])]
    doc["skills"] = []
    doc["languages"] = pairs(s.get("Languages", []), "name", "level")
    doc["certifications"] = []
    doc["honors"] = honors(s.get("Honors", []))
    return doc


@dataclass(frozen=True)
class View:
    slug: str                                   # the intermediate's suffix, e.g. ats_en
    filename: str
    variable: str
    label: str                                  # shown in the provenance header
    convert: Callable[[dict[str, Any]], dict[str, Any]]


VIEWS = (View("ats_en", "resume.js", "RESUME", "ats_en view", convert_main),
         View("academic", "resume-academic.js", "RESUME_ACADEMIC", "academic view", convert_academic))


def find_view(src: Path, slug: str) -> Path:
    hits = sorted(src.glob(f"*_{slug}.rendercv.yaml"))
    if len(hits) != 1:
        raise InputError(f"expected 1 file matching *_{slug}.rendercv.yaml in {src}, found {len(hits)}")
    return hits[0]


def load_cv(path: Path) -> dict[str, Any]:
    try:
        cv = yaml.safe_load(path.read_text(encoding="utf-8"))["cv"]
        cv["sections"]
    except (OSError, yaml.YAMLError, KeyError, TypeError) as exc:
        raise InputError(f"{path.name}: {type(exc).__name__}: {exc}") from exc
    return cv


def render(view: View, doc: dict[str, Any]) -> str:
    return (HEADER.format(label=view.label) + f"window.{view.variable} = "
            + json.dumps(doc, ensure_ascii=False, indent=2) + ";\n")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Copy the ats_en and academic views into Claude Design data files.")
    ap.add_argument("--src", type=Path, default=DEFAULT_SRC, help="directory holding the *.rendercv.yaml intermediates")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT, help="directory to write resume.js and resume-academic.js")
    args = ap.parse_args(argv)

    # Resolve and parse every input before writing anything: a half-written pair
    # would pair a fresh main resume with a stale academic one.
    try:
        docs = [(view, view.convert(load_cv(find_view(args.src, view.slug)))) for view in VIEWS]
    except InputError as exc:
        print(f"FAILED:convert {exc}")
        return 2

    args.out.mkdir(parents=True, exist_ok=True)
    for view, doc in docs:
        target = args.out / view.filename
        with target.open("w", encoding="utf-8", newline="\n") as fh:
            fh.write(render(view, doc))
        counts = {k: len(v) for k, v in doc.items() if isinstance(v, list)}
        todos = sorted(set(re.findall(r"TODO[^\"\]\.;]{0,50}", json.dumps(doc, ensure_ascii=False))))
        print(f"{view.filename}: {target.stat().st_size} bytes | {counts} | TODO markers: {len(todos)}")
    print(f"SUCCESS:convert {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
