#!/usr/bin/env python3
"""emit.py — render the academic CV and every auxiliary view from profile.yaml.

    python emit.py --list
    python emit.py --view academic            # -> out/templates/*.rendercv.yaml + PDF
    python emit.py --all                      # every view
    python emit.py --view linkedin --todo omit

What this produces
------------------
  academic        A4 academic CV: education-first, researcher-leading, no summary
                  block, no page cap, running footer with page numbers.
                  Emits <stem>.rendercv.yaml and renders <stem>.pdf via RenderCV.
  cover-en        Cover letter, English  ]  share one identity block
  cover-ro        Cover letter, Romanian ]  (templates/_shared/identity.j2)
  linkedin        Headline (<=220 chars) + About (strong first 300) + skills
  pack-ejobs      eJobs profile paste pack        ]  field-sized snippets, cut from
  pack-bestjobs   BestJobs profile paste pack     ]  the same facts so the platforms
  pack-hipo       Hipo profile paste pack         ]  agree with the PDFs word for word
  europass        Europass-model emission; DOB / nationality / gender fields present
                  and deliberately EMPTY.

Contracts this script enforces
------------------------------
  * ZERO FABRICATION. Every rendered string comes from profile.yaml. Nothing is
    invented; an unknown renders as a TODO-CONFIRM marker or not at all.
  * FAIL CLOSED. Every artefact is scanned by killlist.py BEFORE it is written.
    A kill-list hit or an unmet wording lock aborts the view and writes nothing.
  * The name is normalised to the hyphenated spelling on every surface.
  * No photo, date of birth, nationality, marital status or street address on any
    view, including Europass, where those fields render as empty labels.

Exit codes: 0 success · 2 bad input/config · 3 kill-list gate failed · 4 render failed
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent                                   # .../.agents/cv
DEFAULT_PROFILE = ROOT / "profile.yaml"
DEFAULT_OUT = ROOT / "out" / "templates"

sys.path.insert(0, str(HERE))
import killlist

try:
    import yaml
except ModuleNotFoundError:                          # pragma: no cover
    print("ERROR PyYAML is missing. Install it into the project venv:\n"
          f"  {ROOT / '.venv/Scripts/python.exe'} -m pip install pyyaml jinja2",
          file=sys.stderr)
    raise SystemExit(2) from None

try:
    from jinja2 import Environment, FileSystemLoader, StrictUndefined
except ModuleNotFoundError:                          # pragma: no cover
    print("ERROR Jinja2 is missing. Install it into the project venv:\n"
          f"  {ROOT / '.venv/Scripts/python.exe'} -m pip install jinja2",
          file=sys.stderr)
    raise SystemExit(2) from None


# --------------------------------------------------------------------------- #
# Views                                                                        #
# --------------------------------------------------------------------------- #
# kind: "rendercv" -> a PDF document; "text" -> a Jinja-rendered text artefact.
VIEWS: dict[str, dict[str, Any]] = {
    "academic":      {"kind": "rendercv", "stem": "academic_cv"},
    "cover-en":      {"kind": "text", "template": "cover-letter/cover_en.md.j2",
                      "stem": "cover_letter_en", "ext": "md"},
    "cover-ro":      {"kind": "text", "template": "cover-letter/cover_ro.md.j2",
                      "stem": "cover_letter_ro", "ext": "md"},
    "linkedin":      {"kind": "text", "template": "linkedin/linkedin.md.j2",
                      "stem": "linkedin", "ext": "md"},
    "pack-ejobs":    {"kind": "text", "template": "platform-packs/ejobs.md.j2",
                      "stem": "pack_ejobs", "ext": "md"},
    "pack-bestjobs": {"kind": "text", "template": "platform-packs/bestjobs.md.j2",
                      "stem": "pack_bestjobs", "ext": "md"},
    "pack-hipo":     {"kind": "text", "template": "platform-packs/hipo.md.j2",
                      "stem": "pack_hipo", "ext": "md"},
    "europass":      {"kind": "text", "template": "europass/europass.md.j2",
                      "stem": "europass", "ext": "md"},
    "europass-yaml": {"kind": "text", "template": "europass/europass.yaml.j2",
                      "stem": "europass", "ext": "yaml"},
}

CANONICAL_NAME = "Andrei-Mihai Visalon"
TODO = "TODO-CONFIRM"


def log(msg: str) -> None:
    print(msg, flush=True)


def s(v: Any) -> str:
    return "" if v is None else str(v).strip()


def squash(v: Any) -> str:
    """Collapse a YAML folded block into one clean line."""
    return re.sub(r"\s+", " ", s(v)).strip()


def is_todo(v: Any) -> bool:
    return TODO in s(v).upper()


# --------------------------------------------------------------------------- #
# Profile -> context                                                           #
# --------------------------------------------------------------------------- #
def load_profile(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise TypeError(f"{path} does not parse to a mapping")
    return data


def _renderable(item: dict[str, Any]) -> bool:
    """An item with TODO-CONFIRM provenance and nothing verified renders nowhere.

    profile.yaml says this in so many words for tracelines and llm-anthology:
    "Until answered this project RENDERS ON NO VIEW."
    """
    if s(item.get("x_provenance")).upper() != TODO:
        return True
    return bool(item.get("highlights"))


def _identity(item: dict[str, Any]) -> str:
    """The field a filter matches on, whichever block the item came from."""
    for field in ("name", "institution", "title", "label"):
        if squash(item.get(field)):
            return squash(item.get(field))
    return ""


def _match(items: list[dict[str, Any]], flt: dict[str, Any] | None) -> list[dict[str, Any]]:
    out = [i for i in items if _renderable(i)]
    if not flt:
        return out
    include = [squash(x).lower() for x in (flt.get("include") or [])]
    exclude = [squash(x).lower() for x in (flt.get("exclude") or [])]
    exclude_matching = [squash(x).lower() for x in (flt.get("exclude_matching") or [])]
    if include:
        order = {n: k for k, n in enumerate(include)}
        out = [i for i in out if _identity(i).lower() in order]
        out.sort(key=lambda i: order[_identity(i).lower()])
    if exclude:
        out = [i for i in out if _identity(i).lower() not in exclude]
    if exclude_matching:
        out = [i for i in out
               if not any(frag in _identity(i).lower() for frag in exclude_matching)]
    return out


def _highlights(item: dict[str, Any], todo_policy: str) -> list[str]:
    out: list[str] = []
    for h in item.get("highlights") or []:
        text = squash(h)
        if text:
            out.append(text)
    if todo_policy == "annotate":
        for t in item.get("x_todo") or []:
            out.append(f"[{TODO}] {squash(t)}")
    return out


def build_context(profile: dict[str, Any], todo_policy: str) -> dict[str, Any]:
    basics = profile.get("basics") or {}
    name = squash(basics.get("name")) or CANONICAL_NAME
    if name != CANONICAL_NAME:
        raise ValueError(f"profile basics.name is {name!r}; the canonical spelling is "
                         f"{CANONICAL_NAME!r} (hyphenated, no diacritics)")

    profiles = {s(p.get("network")).lower(): p for p in (basics.get("profiles") or [])}
    loc = basics.get("location") or {}

    projects = [p for p in (profile.get("projects") or []) if _renderable(p)]
    by_name = {squash(p.get("name")): p for p in projects}

    def proj(fragment: str) -> dict[str, Any]:
        for n, p in by_name.items():
            if fragment.lower() in n.lower():
                return p
        return {}

    awards = profile.get("awards") or []
    pbinfo = squash(awards[0].get("title")) if awards else ""

    grace = proj("GRACE")
    grace_metric = ""
    for h in grace.get("highlights") or []:
        if "0.743" in s(h):
            grace_metric = squash(h)
    reframe = proj("Reframe")
    zhm = proj("ZHMModSDK")
    agent = proj("Agent platform")
    agent_runjournal = ""
    for h in agent.get("highlights") or []:
        if "689" in s(h):
            agent_runjournal = squash(h)

    momentstudio = next((w for w in (profile.get("work") or [])
                         if "momentstudio" in squash(w.get("name")).lower()), {})

    langs = []
    for lg in profile.get("languages") or []:
        fluency = squash(lg.get("fluency"))
        if is_todo(fluency):
            # Never render a guessed CEFR level. "Advanced" is what is verified.
            fluency = ("Advanced" if todo_policy == "omit"
                       else f"Advanced [{TODO}: exact CEFR level, C1 or C2]")
        langs.append({"language": squash(lg.get("language")), "fluency": fluency})

    skills = [{"name": squash(sk.get("name")),
               "keywords": [squash(k) for k in (sk.get("keywords") or [])]}
              for sk in (profile.get("skills") or [])]

    return {
        "today": _dt.datetime.now(_dt.UTC).date().isoformat(),
        "name": name,
        "email": squash(basics.get("email")),
        "phone": squash(basics.get("phone")),
        "city": squash(loc.get("city")),
        "country": "Romania" if s(loc.get("countryCode")).upper() == "RO"
                   else squash(loc.get("countryCode")),
        # The Romanian surfaces name the city in Romanian. This is a rendering
        # of the SAME verified fact, not a second fact; anything unmapped falls
        # through unchanged rather than being transliterated by guesswork.
        "city_ro": {"bucharest": "Bucuresti",
                    "cluj-napoca": "Cluj-Napoca",
                    "ramnicu valcea": "Ramnicu Valcea"}.get(
                        squash(loc.get("city")).lower(), squash(loc.get("city"))),
        "github": squash((profiles.get("github") or {}).get("url")),
        "linkedin_url": squash((profiles.get("linkedin") or {}).get("url")),
        "orcid": squash((profiles.get("orcid") or {}).get("username")),
        "orcid_blocked": bool(squash((profiles.get("orcid") or {}).get("x_state_warning"))),
        "headline_engineering": squash(basics.get("label")),
        "summary": squash(basics.get("summary")),
        "education": profile.get("education") or [],
        "work": profile.get("work") or [],
        "projects": projects,
        "publications": profile.get("publications") or [],
        "data_software": profile.get("x_data_and_software") or [],
        "presentations": profile.get("x_presentations") or [],
        "references": profile.get("x_references") or [],
        "skills": skills,
        "languages": langs,
        "awards": awards,
        "pbinfo": pbinfo,
        "grace_metric": grace_metric,
        "grace": grace,
        "reframe": reframe,
        "zhm": zhm,
        "agent": agent,
        "agent_runjournal": agent_runjournal,
        "momentstudio": momentstudio,
        "todo_policy": todo_policy,
        "TODO": TODO,
    }


# --------------------------------------------------------------------------- #
# Academic CV -> RenderCV document                                             #
# --------------------------------------------------------------------------- #
def _date(value: Any) -> str | int | None:
    """Return a RenderCV-safe date, or None. A TODO-CONFIRM date NEVER renders.

    A bare year is returned as an INT. Quoted, RenderCV reads "2022" as a full
    date and prints "Jan 2022" - a month nobody verified. Verified on this box
    against RenderCV 2.8: unquoted 2022 renders "2022", quoted renders "Jan 2022".
    """
    text = s(value)
    if not text or is_todo(text):
        return None
    if re.fullmatch(r"\d{4}", text):
        return int(text)
    if re.fullmatch(r"\d{4}-\d{2}(-\d{2})?", text):
        return text
    return None


_MONTHS = ("", "Jan", "Feb", "Mar", "Apr", "May", "June", "July", "Aug",
           "Sept", "Oct", "Nov", "Dec")


def _pretty(value: Any) -> str:
    """Render a resolved date the way RenderCV does, for hand-built date strings."""
    text = s(value)
    m = re.fullmatch(r"(\d{4})-(\d{2})(?:-\d{2})?", text)
    if m:
        return f"{_MONTHS[int(m.group(2))]} {m.group(1)}"
    return text


def _scrub_todo(text: str, todo_policy: str) -> str:
    """Strip an inline TODO-CONFIRM tail from a LABEL field under --todo omit.

    profile.yaml carries the marker inside some labels, e.g.
    "Software developer (contract) - TODO-CONFIRM exact title". In annotate mode
    that is exactly what the owner should see. In omit mode the document goes to
    a reader, and the honest rendering is the part BOTH of the owner's 2023 CVs
    agree on - the marker is dropped, nothing is invented in its place.
    """
    if todo_policy != "omit" or not is_todo(text):
        return text
    head = re.split(r"\s*[-–—(]?\s*TODO-CONFIRM", text, maxsplit=1)[0]
    return head.strip(" -–—,;:") or text


def _education_entries(rows: list[dict[str, Any]], todo_policy: str) -> list[dict[str, Any]]:
    out = []
    for e in rows:
        entry: dict[str, Any] = {
            "institution": squash(e.get("institution")),
            "area": squash(e.get("area")),
            "degree": _scrub_todo(squash(e.get("studyType")), todo_policy),
            "location": squash(e.get("location")),
        }
        start, end = _date(e.get("startDate")), _date(e.get("endDate"))
        in_progress = s(e.get("x_status")).upper() == "IN_PROGRESS"
        if start and end:
            entry["start_date"], entry["end_date"] = start, end
        elif start and in_progress:
            entry["start_date"], entry["end_date"] = start, "present"
        elif start or end:
            # "present" is a CLAIM that the study is still running. It is made
            # only where profile.yaml states x_status: IN_PROGRESS.
            known = _pretty(start or end)
            entry["date"] = (f"{known} - [{TODO}]" if todo_policy == "annotate"
                             else f"from {known}")
        hl = _highlights(e, todo_policy)
        if hl:
            entry["highlights"] = hl
        out.append(entry)
    return out


def _experience_entries(rows: list[dict[str, Any]], todo_policy: str) -> list[dict[str, Any]]:
    out = []
    for w in rows:
        entry: dict[str, Any] = {
            "company": squash(w.get("name") or w.get("company")),
            "position": _scrub_todo(squash(w.get("position")), todo_policy),
            "location": squash(w.get("location")),
        }
        start, end = _date(w.get("startDate")), _date(w.get("endDate"))
        if start and end:
            entry["start_date"], entry["end_date"] = start, end
        elif start or end:
            # An unresolved end date prints NO date span at all. Rendering
            # "May 2021 - present" would assert an engagement is still running,
            # which is a fabricated claim, not a missing one. DINUPLAST's end
            # date contradicts itself across the owner's two 2023 CVs.
            known = _pretty(start or end)
            entry["date"] = (f"{known} - [{TODO}]" if todo_policy == "annotate"
                             else f"from {known}")
        hl = _highlights(w, todo_policy)
        if hl:
            entry["highlights"] = hl
        out.append(entry)
    return out


def _normal_entries(rows: list[dict[str, Any]], todo_policy: str) -> list[dict[str, Any]]:
    out = []
    for p in rows:
        entry: dict[str, Any] = {"name": squash(p.get("name"))}
        desc = squash(p.get("description"))
        repo = squash(p.get("repository"))
        if repo and repo.lower() not in desc.lower():
            desc = f"{desc} ({repo})".strip()
        if desc and not is_todo(desc):
            entry["summary"] = desc
        hl = _highlights(p, todo_policy)
        if hl:
            entry["highlights"] = hl
        out.append(entry)
    return out


def _publication_entries(rows: list[dict[str, Any]], name: str,
                         todo_policy: str) -> list[dict[str, Any]]:
    """Publications with HONEST status labels baked into the rendered title.

    The status is part of the title, not a footnote, because a title is what a
    reader skims and what a committee copies into a list.
    """
    out = []
    for p in rows:
        title = squash(p.get("name"))
        kind = s(p.get("x_type")).lower()
        if kind == "preprint":
            label = "preprint"
        elif "preparation" in kind or "preparation" in title.lower():
            label = "manuscript in preparation"
        else:
            label = f"{TODO}: publication status"
        if is_todo(title):
            title = (f"[{TODO}: exact title] — {label}" if todo_policy == "annotate"
                     else f"[title to confirm] — {label}")
        elif label.replace("manuscript ", "") not in title.lower():
            title = f"{title} — {label}"

        entry: dict[str, Any] = {"title": title,
                                 "authors": [squash(a) for a in (p.get("authors") or [])] or [name]}
        journal = squash(p.get("publisher"))
        if journal:
            # RenderCV already parenthesises the venue, so the status is appended
            # with a comma: the reader sees "(ChemRxiv, preprint)", not nested
            # brackets. The word "preprint" appears in BOTH title and venue on
            # purpose - a list pasted from either field still carries the status.
            entry["journal"] = f"{journal}, {label}" if label == "preprint" else journal
        doi = squash(p.get("doi"))
        if doi and not is_todo(doi):
            entry["doi"] = doi
        date = _date(p.get("releaseDate"))
        if date:
            entry["date"] = date
        out.append(entry)
    return out


def _one_line_entries(pairs: list[tuple[str, str]]) -> list[dict[str, str]]:
    return [{"label": a, "details": b} for a, b in pairs if a and b]


def _bullets(rows: list[Any]) -> list[dict[str, str]]:
    out = []
    for r in rows:
        if isinstance(r, dict):
            text = squash(r.get("bullet") or r.get("title") or r.get("name"))
            awarder, date = squash(r.get("awarder")), squash(r.get("date"))
            tail = " — ".join(x for x in (awarder, date) if x)
            if tail and tail.lower() not in text.lower():
                text = f"{text} — {tail}"
        else:
            text = squash(r)
        if text:
            out.append({"bullet": text})
    return out


def build_academic(profile: dict[str, Any], ctx: dict[str, Any], spec: dict[str, Any],
                   design: dict[str, Any], include_experience: bool,
                   todo_policy: str) -> tuple[dict[str, Any], list[str]]:
    warns: list[str] = []
    meta = spec.get("meta") or {}
    sections: dict[str, Any] = {}

    for sec in spec.get("sections") or []:
        title = squash(sec.get("title"))
        src = s(sec.get("source"))
        kind = s(sec.get("entry"))
        if sec.get("optional") and src == "work" and not include_experience:
            warns.append(f"section {title!r} disabled (--no-experience)")
            continue

        raw = profile.get(src) or ctx.get(src) or []
        if not isinstance(raw, list):
            raw = []
        rows = _match([r for r in raw if isinstance(r, dict)], sec.get("filter"))

        if kind == "education":
            items: list[Any] = _education_entries(rows, todo_policy)
        elif kind == "experience":
            items = _experience_entries(rows, todo_policy)
        elif kind == "publication":
            items = _publication_entries(rows, ctx["name"], todo_policy)
        elif kind == "normal":
            items = _normal_entries(rows, todo_policy)
        elif kind == "one_line":
            if src == "skills":
                items = _one_line_entries([(sk["name"], ", ".join(sk["keywords"]))
                                           for sk in ctx["skills"]])
            elif src == "languages":
                items = _one_line_entries([(lg["language"], lg["fluency"])
                                           for lg in ctx["languages"]])
            else:
                items = _one_line_entries([(squash(r.get("label")), squash(r.get("details")))
                                           for r in rows])
        elif kind == "bullet":
            items = _bullets(rows)
        else:
            raise ValueError(f"section {title!r}: unknown entry type {kind!r}")

        if not items:
            fallback = squash(sec.get("fallback_text"))
            if fallback:
                items = [fallback]                   # RenderCV accepts a bare string
            elif sec.get("omit_if_empty", True):
                warns.append(f"section {title!r} OMITTED — no renderable item in "
                             f"profile.{src} (a hollow heading is worse than no heading)")
                continue
            else:
                raise ValueError(f"section {title!r} is mandatory but has no items")
        sections[title] = items

    cv: dict[str, Any] = {
        "name": ctx["name"],
        "headline": squash(meta.get("headline")),
        "location": f"{ctx['city']}, {ctx['country']}",
        "email": ctx["email"],
        "phone": ctx["phone"],
        "social_networks": [],
    }
    if ctx["github"]:
        cv["social_networks"].append({"network": "GitHub",
                                      "username": ctx["github"].rstrip("/").split("/")[-1]})
    if ctx["linkedin_url"]:
        cv["social_networks"].append({"network": "LinkedIn",
                                      "username": ctx["linkedin_url"].rstrip("/").split("/")[-1]})
    if ctx["orcid"]:
        if ctx["orcid_blocked"]:
            warns.append("ORCID is NOT linked: the record has zero registered works and a "
                         "wrong education entry (it credits the BSc to the University of "
                         "Bucharest). A reviewer who clicks it today sees an empty, "
                         "factually wrong record. Fix the record, then re-render.")
        else:
            cv["social_networks"].append({"network": "ORCID", "username": ctx["orcid"]})
    if not cv["social_networks"]:
        cv.pop("social_networks")

    if meta.get("summary_block"):
        raise ValueError("academic.sections.yaml meta.summary_block must stay false — "
                         "the academic CV carries no summary block")

    cv["sections"] = sections
    doc: dict[str, Any] = {"cv": cv}
    doc.update(design)
    return doc, warns


# --------------------------------------------------------------------------- #
# RenderCV                                                                     #
# --------------------------------------------------------------------------- #
def find_rendercv() -> str | None:
    for cand in (Path(sys.executable).parent / "rendercv.exe",
                 Path(sys.executable).parent / "rendercv",
                 ROOT / ".venv/Scripts/rendercv.exe",
                 ROOT / ".venv/bin/rendercv"):
        if cand.exists():
            return str(cand)
    return shutil.which("rendercv")


def render_pdf(intermediate: Path, out_dir: Path, pdf_name: str) -> tuple[bool, str, Path]:
    engine = find_rendercv()
    pdf = out_dir / pdf_name
    if not engine:
        return False, ("rendercv not found. Install it into the project venv:\n"
                       f"  {ROOT / '.venv/Scripts/python.exe'} -m pip install 'rendercv[full]'"), pdf
    proc = subprocess.run(
        [engine, "render", str(intermediate), "-o", str(out_dir),
         "-pdf", pdf_name, "-nopng", "-nomd", "-nohtml", "-q"],
        capture_output=True, text=True, check=False, encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        tail = ((proc.stdout or "") + "\n" + (proc.stderr or "")).strip().splitlines()
        for line in tail[-25:]:
            log(f"  | {line}")
        return False, f"rendercv exited {proc.returncode}", pdf
    if not pdf.exists():
        return False, "rendercv reported success but produced no PDF", pdf
    return True, f"rendered {pdf.name}", pdf


# --------------------------------------------------------------------------- #
# Text views                                                                   #
# --------------------------------------------------------------------------- #
def jinja_env() -> Environment:
    env = Environment(
        loader=FileSystemLoader(str(HERE)),
        undefined=StrictUndefined,       # a missing variable is an ERROR, never blank
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )
    env.filters["squash"] = squash
    return env


def check_limits(view: str, text: str) -> list[str]:
    """Platform field limits, measured on the emitted text rather than assumed."""
    problems: list[str] = []
    if view == "linkedin":
        for line in text.splitlines():
            m = re.match(r"^HEADLINE\s*\((\d+)/220\)", line)
            if m and int(m.group(1)) > 220:
                problems.append(f"LinkedIn headline is {m.group(1)} chars (limit 220)")
        block = re.search(r"<<<ABOUT>>>(.*?)<<<END ABOUT>>>", text, re.DOTALL)
        if block:
            about = block.group(1).strip()
            if len(about) > 2600:
                problems.append(f"LinkedIn About is {len(about)} chars (limit 2600)")
            if len(about) < 300:
                problems.append(f"LinkedIn About is only {len(about)} chars; the first 300 "
                                f"are the visible fold and must carry the argument")
    return problems


# --------------------------------------------------------------------------- #
# Driver                                                                       #
# --------------------------------------------------------------------------- #
def gate(text: str, artefact: str) -> list[killlist.Finding]:
    return killlist.errors(killlist.scan(text, artefact))


def emit_view(view: str, profile: dict[str, Any], ctx: dict[str, Any],
              out_dir: Path, args: argparse.Namespace) -> int:
    spec = VIEWS[view]
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = spec["stem"]
    log(f"  VIEW   {view} (kind={spec['kind']} todo={args.todo})")

    if spec["kind"] == "text":
        env = jinja_env()
        text = env.get_template(spec["template"]).render(**ctx)
        problems = check_limits(view, text)
        for p in problems:
            log(f"  LIMIT  {p}")
        findings = gate(text, f"{stem}.{spec['ext']}")
        for f in findings:
            log(f"  {f}")
        if findings:
            log(f"  GATE   FAILED — {len(findings)} error(s); nothing written")
            log(f"FAILED:{view}")
            return 3
        if problems:
            log(f"FAILED:{view}")
            return 3
        log("  GATE   clean")
        path = out_dir / f"{stem}.{spec['ext']}"
        path.write_text(text, encoding="utf-8")
        log(f"  WROTE  {path} ({path.stat().st_size} bytes)")
        log(f"SUCCESS:{view}")
        return 0

    # ---- academic ---------------------------------------------------------- #
    sec_spec = yaml.safe_load((HERE / "academic/academic.sections.yaml").read_text("utf-8"))
    design = yaml.safe_load((HERE / "academic/academic.design.yaml").read_text("utf-8"))
    doc, warns = build_academic(profile, ctx, sec_spec, design,
                                include_experience=args.experience,
                                todo_policy=args.todo)
    for w in warns:
        log(f"  WARN   {w}")

    text = yaml.safe_dump(doc, sort_keys=False, allow_unicode=True, width=100)
    findings = gate(text, f"{stem}.rendercv.yaml")
    for f in findings:
        log(f"  {f}")
    if findings:
        log(f"  GATE   FAILED — {len(findings)} error(s); nothing written")
        log(f"FAILED:{view}")
        return 3
    log("  GATE   clean")

    intermediate = out_dir / f"{stem}.rendercv.yaml"
    intermediate.write_text(text, encoding="utf-8")
    log(f"  EMIT   {intermediate} ({intermediate.stat().st_size} bytes)")

    manifest: dict[str, Any] = {
        "view": view, "generated": _dt.datetime.now(_dt.UTC).date().isoformat(),
        "sections": list((doc["cv"]["sections"] or {}).keys()),
        "summary_block": False, "page": "A4", "page_budget": None,
        "include_experience": bool(args.experience), "todo_policy": args.todo,
        "warnings": warns, "intermediate": str(intermediate),
    }

    if args.emit_only:
        (out_dir / f"{stem}.manifest.json").write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        log("  NOTE   --emit-only: stopped before rendering")
        log(f"SUCCESS:{view}")
        return 0

    ok, msg, pdf = render_pdf(intermediate, out_dir, f"{stem}.pdf")
    log(f"  RENDER {msg}")
    if not ok:
        log(f"FAILED:{view}")
        return 4
    manifest["pdf"] = str(pdf)
    manifest["pdf_bytes"] = pdf.stat().st_size
    (out_dir / f"{stem}.manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    log(f"  PDF    {pdf} ({pdf.stat().st_size} bytes)")
    log(f"SUCCESS:{view}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="emit.py", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--view", action="append", default=[],
                    help="view to emit (repeatable); see --list")
    ap.add_argument("--all", action="store_true", help="emit every view")
    ap.add_argument("--list", action="store_true", help="list the views and exit")
    ap.add_argument("--profile", default=str(DEFAULT_PROFILE))
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--todo", choices=["annotate", "omit"], default="annotate",
                    help="annotate: print [TODO-CONFIRM] markers (working copy). "
                         "omit: leave the gap silent (a copy that goes to a reader).")
    ap.add_argument("--no-experience", dest="experience", action="store_false",
                    help="academic CV: drop the Professional experience section")
    ap.add_argument("--experience", dest="experience", action="store_true")
    ap.add_argument("--emit-only", action="store_true", help="academic: skip the PDF render")
    ap.set_defaults(experience=True)
    args = ap.parse_args(argv)

    if args.list:
        for name, spec in VIEWS.items():
            log(f"{name:15s} {spec['kind']:9s} -> {spec['stem']}."
                f"{spec.get('ext', 'pdf')}")
        return 0

    views = list(VIEWS) if args.all else list(dict.fromkeys(args.view))
    if not views:
        ap.error("give --view NAME (repeatable), --all, or --list")
    unknown = [v for v in views if v not in VIEWS]
    if unknown:
        ap.error(f"unknown view(s) {unknown}; known: {', '.join(VIEWS)}")

    profile_path = Path(args.profile).resolve()
    if not profile_path.exists():
        log(f"ERROR profile not found: {profile_path}")
        return 2
    try:
        profile = load_profile(profile_path)
        ctx = build_context(profile, args.todo)
    except (TypeError, ValueError, yaml.YAMLError) as exc:
        log(f"ERROR {exc}")
        return 2

    log(f"PROFILE {profile_path}")
    log(f"OUT     {Path(args.out).resolve()}")
    rc = 0
    for view in views:
        try:
            rc = emit_view(view, profile, ctx, Path(args.out).resolve(), args) or rc
        except Exception as exc:                     # noqa: BLE001 — report, do not mask
            log(f"  ERROR {view}: {exc!r}")
            log(f"FAILED:{view}")
            rc = rc or 2
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
