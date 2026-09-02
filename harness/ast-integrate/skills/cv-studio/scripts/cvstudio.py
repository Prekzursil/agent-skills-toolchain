#!/usr/bin/env python3
"""cv-studio: one structured profile -> ATS-clean PDF + tailoring + self-check.

A thin, deterministic wrapper around RenderCV (MIT, YAML -> Typst -> tagged PDF).
NO LLM calls here: the mechanical pipeline lives in this file; the *content* work
(writing bullets, headline, About, cover letter) is done by the agent following
SKILL.md and references/. This script maps a JSON-Resume-superset ``profile.yaml``
onto RenderCV's schema, renders, and proves the PDF parses.

Subcommands:
  validate PROFILE                 schema + zero-fabrication lint
  build    PROFILE [--theme ..]    profile -> rendercv.yaml -> render -> self-check
  tailor   PROFILE JOB             keyword-match report vs a job description
  selfcheck PDF PROFILE            assert the PDF's text layer contains key facts
  json     PROFILE                 export a clean JSON Resume (x_ extensions stripped)

Run it with the cv-studio venv python (has ruamel.yaml + rendercv + pymupdf):
  ~/.local/share/cv-studio/venv/Scripts/python  scripts/cvstudio.py build profile.yaml
See INSTALL.md for the one-time engine setup (isolated; never pollutes global python).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

# --------------------------------------------------------------------------- #
# Constants (ground-truth from the installed RenderCV 2.8 schema, not guessed) #
# --------------------------------------------------------------------------- #
KNOWN_THEMES = (
    "classic",
    "sb2nov",
    "engineeringresumes",
    "engineeringclassic",
    "moderncv",
)
DEFAULT_ATS_THEME = "classic"  # proven to render + parse clean on this box

# RenderCV SocialNetwork enum (rendercv/schema/models/cv/social_network.py).
# An unknown network name is a hard Pydantic error, so we whitelist + canonicalise.
_NETWORKS = {
    "linkedin": "LinkedIn",
    "github": "GitHub",
    "gitlab": "GitLab",
    "imdb": "IMDB",
    "instagram": "Instagram",
    "orcid": "ORCID",
    "mastodon": "Mastodon",
    "stackoverflow": "StackOverflow",
    "stack overflow": "StackOverflow",
    "researchgate": "ResearchGate",
    "youtube": "YouTube",
    "google scholar": "Google Scholar",
    "scholar": "Google Scholar",
    "telegram": "Telegram",
    "whatsapp": "WhatsApp",
    "leetcode": "Leetcode",
    "x": "X",
    "twitter": "X",
    "bluesky": "Bluesky",
    "reddit": "Reddit",
}

# Default section order (ATS 2026: contact -> summary -> skills -> experience ->
# education -> the rest). references/ats-rules.md explains why.
DEFAULT_SECTION_ORDER = (
    "summary",
    "skills",
    "experience",
    "education",
    "projects",
    "certificates",
    "publications",
    "awards",
    "languages",
    "volunteer",
    "interests",
    "references",
)
SECTION_TITLES = {
    "summary": "Summary",
    "skills": "Skills",
    "experience": "Experience",
    "education": "Education",
    "projects": "Projects",
    "certificates": "Certifications",
    "publications": "Publications",
    "awards": "Awards & Honors",
    "languages": "Languages",
    "volunteer": "Volunteering",
    "interests": "Interests",
    "references": "References",
}

# Flag impressive-but-invented figures. Deliberately ignores bare 1-2 digit ints
# and 4-digit years (too noisy). Heuristic assist, NOT a proof of truthfulness.
_METRIC_RE = re.compile(
    r"\$\s?\d[\d,]*(?:\.\d+)?\s?[KMBkmb]?\+?"  # money  $18M  $1,200
    r"|\d[\d,]*(?:\.\d+)?\s?%"  # percent 73%
    r"|\d[\d,]*(?:\.\d+)?\s?[xX](?![\w])"  # multiplier 4.2x
    r"|\d[\d,]*(?:\.\d+)?\s?[KMB]\+?"  # magnitude 2M+  50M
    r"|\d{1,3}(?:,\d{3})+\+?"  # grouped 8,500
    r"|\d{3,}\+?"  # plain >=3 digits 340
)


# --------------------------------------------------------------------------- #
# YAML / IO helpers                                                            #
# --------------------------------------------------------------------------- #
def _load_yaml(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    try:
        from ruamel.yaml import YAML  # bundled in the cv-studio venv

        return YAML(typ="safe").load(text) or {}
    except ImportError:
        pass
    try:
        import yaml  # optional fallback

        return yaml.safe_load(text) or {}
    except ImportError:  # pragma: no cover - environment guard
        sys.exit(
            "FAILED: no YAML parser. Run under the cv-studio venv python "
            "(has ruamel.yaml) or `pip install pyyaml`."
        )


def _dump_yaml(obj: dict[str, Any], path: Path) -> None:
    # Order MUST be preserved (section order is ATS-load-bearing).
    try:
        from ruamel.yaml import YAML

        y = YAML()
        y.default_flow_style = False
        y.allow_unicode = True
        with path.open("w", encoding="utf-8") as fh:
            y.dump(obj, fh)
        return
    except ImportError:
        pass
    import yaml

    path.write_text(
        yaml.safe_dump(obj, sort_keys=False, allow_unicode=True, width=100),
        encoding="utf-8",
    )


def _s(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, dict):  # an unquoted "Key: value" YAML line parsed as a mapping
        return "; ".join(f"{k}: {_s(val)}" for k, val in v.items())
    if isinstance(v, list):
        return ", ".join(_s(x) for x in v)
    return str(v).strip()


# --------------------------------------------------------------------------- #
# Engine resolution (isolated first, never assume global)                     #
# --------------------------------------------------------------------------- #
def find_rendercv() -> str | None:
    """Locate a rendercv executable: env override -> cv-studio venv -> PATH."""
    env = os.environ.get("CV_STUDIO_RENDERCV")
    if env and Path(env).exists():
        return env
    home = Path.home()
    for cand in (
        home / ".local/share/cv-studio/venv/Scripts/rendercv.exe",  # Windows
        home / ".local/share/cv-studio/venv/bin/rendercv",  # POSIX
        home / ".local/bin/rendercv",  # pipx
    ):
        if cand.exists():
            return str(cand)
    return shutil.which("rendercv")


# --------------------------------------------------------------------------- #
# profile.yaml (JSON Resume superset) -> RenderCV YAML                         #
# --------------------------------------------------------------------------- #
def _social_networks(
    profiles: list[dict[str, Any]],
) -> tuple[list[dict[str, str]], list[str]]:
    out: list[dict[str, str]] = []
    warns: list[str] = []
    for p in profiles or []:
        raw = _s(p.get("network")).lower()
        canon = _NETWORKS.get(raw)
        user = _s(p.get("username")) or _s(p.get("url")).rstrip("/").rsplit("/", 1)[-1]
        if not canon:
            warns.append(
                f"social network '{p.get('network')}' is not one of RenderCV's "
                f"supported networks; skipped (add it to the contact line manually)."
            )
            continue
        if not user:
            warns.append(f"social network '{canon}' has no username; skipped.")
            continue
        out.append({"network": canon, "username": user})
    return out, warns


def _link(name: str, url: str) -> str:
    name, url = _s(name), _s(url)
    return f"[{name}]({url})" if url else name


def _date_range(item: dict[str, Any]) -> dict[str, str]:
    start, end = _s(item.get("startDate")), _s(item.get("endDate"))
    out: dict[str, str] = {}
    if start:
        out["start_date"] = start
        out["end_date"] = end or "present"
    elif end:
        out["date"] = end
    return out


def _experience(work: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for w in work or []:
        row: dict[str, Any] = {
            "company": _s(w.get("name") or w.get("company")),
            "position": _s(w.get("position")),
        }
        if _s(w.get("location")):
            row["location"] = _s(w.get("location"))
        row.update(_date_range(w))
        if _s(w.get("summary")):
            row["summary"] = _s(w.get("summary"))
        hl = [_s(h) for h in (w.get("highlights") or []) if _s(h)]
        if hl:
            row["highlights"] = hl
        rows.append(row)
    return rows


def _education(edu: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for e in edu or []:
        row: dict[str, Any] = {"institution": _s(e.get("institution"))}
        if _s(e.get("area")):
            row["area"] = _s(e.get("area"))
        if _s(e.get("studyType") or e.get("degree")):
            row["degree"] = _s(e.get("studyType") or e.get("degree"))
        if _s(e.get("location")):
            row["location"] = _s(e.get("location"))
        row.update(_date_range(e))
        hl = [_s(h) for h in (e.get("highlights") or []) if _s(h)]
        if _s(e.get("score")):
            hl.insert(0, f"GPA: {_s(e.get('score'))}")
        courses = [_s(c) for c in (e.get("courses") or []) if _s(c)]
        if courses:
            hl.append("Coursework: " + ", ".join(courses))
        if hl:
            row["highlights"] = hl
        rows.append(row)
    return rows


def _projects(projs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for p in projs or []:
        row: dict[str, Any] = {"name": _link(p.get("name"), p.get("url"))}
        row.update(_date_range(p))
        if _s(p.get("description")):
            row["summary"] = _s(p.get("description"))
        hl = [_s(h) for h in (p.get("highlights") or []) if _s(h)]
        if hl:
            row["highlights"] = hl
        rows.append(row)
    return rows


def _skills(skills: list[dict[str, Any]]) -> list[dict[str, str]]:
    rows, loose = [], []
    for s in skills or []:
        name = _s(s.get("name"))
        kw = [_s(k) for k in (s.get("keywords") or []) if _s(k)]
        details = ", ".join(kw) if kw else _s(s.get("level"))
        if details:
            rows.append({"label": name, "details": details})
        elif name:
            loose.append(name)
    if loose:
        rows.append({"label": "Additional", "details": ", ".join(loose)})
    return rows


def _publications(pubs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for p in pubs or []:
        row: dict[str, Any] = {"title": _s(p.get("name") or p.get("title"))}
        authors = [_s(a) for a in (p.get("authors") or []) if _s(a)]
        if authors:
            row["authors"] = authors
        if _s(p.get("publisher") or p.get("journal")):
            row["journal"] = _s(p.get("publisher") or p.get("journal"))
        if _s(p.get("doi")):
            row["doi"] = _s(p.get("doi"))
        if _s(p.get("url")):
            row["url"] = _s(p.get("url"))
        date = _s(p.get("releaseDate") or p.get("date"))
        if date:
            row["date"] = date
        rows.append(row)
    return rows


def _awards(awards: list[dict[str, Any]]) -> list[dict[str, str]]:
    rows = []
    for a in awards or []:
        bits = [_s(a.get("title"))]
        if _s(a.get("awarder")):
            bits.append(_s(a.get("awarder")))
        if _s(a.get("date")):
            bits[-1] = (
                f"{bits[-1]} ({_s(a.get('date'))})"
                if len(bits) > 1
                else f"{bits[0]} ({_s(a.get('date'))})"
            )
        rows.append({"bullet": " — ".join(b for b in bits if b)})
    return rows


def _certificates(certs: list[dict[str, Any]]) -> list[dict[str, str]]:
    rows = []
    for c in certs or []:
        det = ", ".join(x for x in (_s(c.get("issuer")), _s(c.get("date"))) if x)
        rows.append(
            {"label": _link(c.get("name"), c.get("url")), "details": det or "—"}
        )
    return rows


def _one_line_langs(langs: list[dict[str, Any]]) -> list[dict[str, str]]:
    return [
        {"label": _s(lang.get("language")), "details": _s(lang.get("fluency")) or "—"}
        for lang in (langs or [])
        if _s(lang.get("language"))
    ]


def _text_list(v: Any) -> list[str]:
    if isinstance(v, list):
        return [_s(x) for x in v if _s(x)]
    return [_s(v)] if _s(v) else []


def profile_to_rendercv(
    profile: dict[str, Any], theme: str, section_order: tuple[str, ...]
) -> tuple[dict[str, Any], list[str]]:
    basics = profile.get("basics") or {}
    loc = basics.get("location") or {}
    location = ", ".join(
        x
        for x in (_s(loc.get("city")), _s(loc.get("region") or loc.get("countryCode")))
        if x
    )
    nets, warns = _social_networks(basics.get("profiles") or [])

    cv: dict[str, Any] = {"name": _s(basics.get("name"))}
    if _s(basics.get("label")):
        cv["headline"] = _s(basics.get("label"))
    if location:
        cv["location"] = location
    if _s(basics.get("email")):
        cv["email"] = _s(basics.get("email"))
    if _s(basics.get("phone")):
        cv["phone"] = _s(basics.get("phone"))
    if _s(basics.get("url")):
        cv["website"] = _s(basics.get("url"))
    if nets:
        cv["social_networks"] = nets

    builders = {
        "summary": lambda: _text_list(basics.get("summary")),
        "skills": lambda: _skills(profile.get("skills")),
        "experience": lambda: _experience(profile.get("work")),
        "education": lambda: _education(profile.get("education")),
        "projects": lambda: _projects(profile.get("projects")),
        "certificates": lambda: _certificates(profile.get("certificates")),
        "publications": lambda: _publications(profile.get("publications")),
        "awards": lambda: _awards(profile.get("awards")),
        "languages": lambda: _one_line_langs(profile.get("languages")),
        "volunteer": lambda: _experience(
            [
                {**v, "company": v.get("organization"), "position": v.get("position")}
                for v in (profile.get("volunteer") or [])
            ]
        ),
        "interests": lambda: _text_list(
            [i.get("name") for i in (profile.get("interests") or [])]
        ),
        "references": lambda: [
            f"{_s(r.get('reference'))} — {_s(r.get('name'))}"
            for r in (profile.get("references") or [])
            if _s(r.get("name"))
        ],
    }
    sections: dict[str, Any] = {}
    for key in section_order:
        entries = builders.get(key, lambda: [])()
        if entries:
            sections[SECTION_TITLES.get(key, key.title())] = entries
    cv["sections"] = sections
    return {"cv": cv, "design": {"theme": theme}}, warns


# --------------------------------------------------------------------------- #
# Validation + zero-fabrication lint                                          #
# --------------------------------------------------------------------------- #
def _flag_metrics(text: str) -> list[str]:
    out = []
    for m in _METRIC_RE.findall(text):
        norm = m.strip()
        bare = norm.replace(",", "").rstrip("+")
        if bare.isdigit() and (len(bare) == 4 and 1900 <= int(bare) <= 2099):
            continue  # a year, not a metric
        out.append(norm)
    return out


def _metric_haystack(profile: dict[str, Any]) -> str:
    xm = profile.get("x_metrics")
    if isinstance(xm, dict):
        xm = list(xm.values())
    parts = [str(v) for v in (xm or [])]
    return re.sub(r"[,\s]", "", " ".join(parts)).lower()


def validate(profile: dict[str, Any]) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    basics = profile.get("basics") or {}
    if not _s(basics.get("name")):
        errors.append("basics.name is required.")
    email = _s(basics.get("email"))
    if not email:
        errors.append("basics.email is required (ATS + recruiter contact).")
    elif not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        errors.append(f"basics.email '{email}' is not a valid email.")

    haystack = _metric_haystack(profile)
    master = profile.get("x_master") or {}
    for i, w in enumerate(profile.get("work") or []):
        who = _s(w.get("name") or w.get("company")) or f"work[{i}]"
        if not _s(w.get("name") or w.get("company")):
            errors.append(f"work[{i}] missing company/name.")
        if not _s(w.get("position")):
            errors.append(f"work[{i}] ({who}) missing position.")
        role_key = f"{_s(w.get('name') or w.get('company'))}|{_s(w.get('position'))}"
        if master and role_key not in master and who not in master:
            warnings.append(
                f"[zero-fab] role '{who}' has no x_master achievement bank "
                f"(key '{role_key}'); bullets are unsourced."
            )
        for h in w.get("highlights") or []:
            for tok in _flag_metrics(_s(h)):
                digits = re.sub(r"[,\s]", "", tok).lower().rstrip("+").lstrip("$")
                core = re.sub(r"[%xkmb]", "", digits)
                if haystack and core and core not in haystack:
                    warnings.append(
                        f"[zero-fab] metric '{tok}' in {who} not found in "
                        f"x_metrics — verify or add it."
                    )
    for i, e in enumerate(profile.get("education") or []):
        if not _s(e.get("institution")):
            errors.append(f"education[{i}] missing institution.")
    return errors, warnings


# --------------------------------------------------------------------------- #
# ATS self-check (PyMuPDF text-layer assertion, the smoke gate)               #
# --------------------------------------------------------------------------- #
def _extract_pdf_text(pdf: Path) -> tuple[str, int]:
    try:
        import fitz  # PyMuPDF

        doc = fitz.open(pdf)
        return "".join(p.get_text() for p in doc), doc.page_count
    except ImportError:
        pass
    try:
        from pdfminer.high_level import extract_text  # fallback

        return extract_text(str(pdf)), -1
    except ImportError:  # pragma: no cover
        sys.exit("FAILED: no PDF text extractor (need pymupdf or pdfminer.six).")


def selfcheck(pdf: Path, profile: dict[str, Any]) -> tuple[bool, list[str], int]:
    text, pages = _extract_pdf_text(pdf)
    norm = re.sub(r"\s+", " ", text).lower()
    basics = profile.get("basics") or {}
    checks: list[tuple[str, str]] = [
        ("name", _s(basics.get("name"))),
        ("email", _s(basics.get("email"))),
    ]
    for w in (profile.get("work") or [])[:6]:
        checks.append(("company", _s(w.get("name") or w.get("company"))))
    for e in (profile.get("education") or [])[:3]:
        checks.append(("institution", _s(e.get("institution"))))
    missing = []
    for label, val in checks:
        if not val:
            continue
        probe = re.sub(r"\s+", " ", val).lower()
        head = probe.split(",")[0][:24]  # tolerate truncation/wrapping
        if probe not in norm and head not in norm:
            missing.append(f"{label}: {val!r}")
    return (len(missing) == 0 and len(norm) > 200), missing, pages


# --------------------------------------------------------------------------- #
# Tailoring (mechanical keyword match; content placement is the agent's job)  #
# --------------------------------------------------------------------------- #
_STOP = set(
    """a an the and or but of to in for on with at by from as is are was were be been being
this that these those you your we our they their it its his her he she i me my will would can could
should may might must shall have has had do does did not no yes if then else than so such into over
under about above below up down out off again further once here there all any both each few more most
other some who whom which what when where why how per via etc using use used work role team years year
experience strong ability skills knowledge including include working across able we're join looking
hiring hire seeking candidate candidates ideal you'll help build building built develop developing
developed create creating maintain maintaining design designing lead leading led manage managing
mentor mentoring mentored perform performing integrate integrating analyze analyzing analysis review
reviews responsibilities requirements qualifications preferred plus bonus nice must-have required
excellent strong deep solid proven demonstrated familiarity familiar comfortable proficient expertise
understanding communication written verbal collaborate collaboration cross-functional stakeholders
partners partner drive driving deliver delivering ensure ensuring support supporting improve improving
company mission role position opportunity opportunities apps applications app software product products
platform platforms system systems solution solutions tools tooling environment environments teams
junior senior staff principal engineer engineers researcher researchers new great world class""".split()
)


def _keywords(text: str) -> dict[str, int]:
    freq: dict[str, int] = {}
    for tok in re.findall(r"[A-Za-z][A-Za-z0-9+#.\-]{1,}", text.lower()):
        tok = tok.strip(".-")
        if len(tok) < 2 or tok in _STOP or tok.isdigit():
            continue
        freq[tok] = freq.get(tok, 0) + 1
    return freq


def _profile_text(profile: dict[str, Any]) -> str:
    parts: list[str] = []
    b = profile.get("basics") or {}
    parts += [_s(b.get("label")), _s(b.get("summary"))]
    for s in profile.get("skills") or []:
        parts.append(_s(s.get("name")))
        parts += [_s(k) for k in (s.get("keywords") or [])]
    for w in profile.get("work") or []:
        parts.append(_s(w.get("position")))
        parts += [_s(h) for h in (w.get("highlights") or [])]
    for p in profile.get("projects") or []:
        parts += [_s(p.get("description"))] + [
            _s(h) for h in (p.get("highlights") or [])
        ]
    return " ".join(parts)


def tailor(profile: dict[str, Any], job_text: str) -> str:
    job_kw = _keywords(job_text)
    have = set(_keywords(_profile_text(profile)))
    ranked = sorted(job_kw.items(), key=lambda kv: (-kv[1], kv[0]))
    top = [k for k, _ in ranked][:40]
    hit = [k for k in top if k in have]
    miss = [k for k in top if k not in have][:25]
    pct = round(100 * len(hit) / len(top)) if top else 0
    out = [
        "# Tailor report",
        "",
        f"**Keyword match: {pct}%** ({len(hit)}/{len(top)} of the JD's top terms "
        f"already appear in your profile).",
        "",
        "> 2026 ATS is semantic + skills-graph: place each MISSING term where it is *true* "
        "(a real skill, a real bullet). Do NOT keyword-stuff — it is penalised.",
        "",
        "## Already covered",
        "",
        ", ".join(hit) or "_(none)_",
        "",
        "## Missing — add only where truthful (3-place rule: Skills / a title line / a proving bullet)",
        "",
    ]
    for k in miss:
        out.append(
            f"- [ ] **{k}** — add to Skills if a real skill; work it into a bullet "
            f"that proves it; mirror the JD's exact wording."
        )
    if not miss:
        out.append("_Strong coverage — focus on quantifying existing bullets instead._")
    return "\n".join(out) + "\n"


# --------------------------------------------------------------------------- #
# JSON Resume export (strip x_ extensions -> portable resume.json)            #
# --------------------------------------------------------------------------- #
def to_json_resume(profile: dict[str, Any]) -> dict[str, Any]:
    clean = {k: v for k, v in profile.items() if not k.startswith("x_")}
    clean.setdefault("meta", {})["canonical"] = "https://jsonresume.org/schema/"
    return clean


# --------------------------------------------------------------------------- #
# Commands                                                                     #
# --------------------------------------------------------------------------- #
def _report(errors: list[str], warnings: list[str]) -> None:
    for w in warnings:
        print(f"  WARN  {w}")
    for e in errors:
        print(f"  ERROR {e}")


def cmd_validate(args: argparse.Namespace) -> int:
    profile = _load_yaml(Path(args.profile))
    errors, warnings = validate(profile)
    _report(errors, warnings)
    if errors:
        print(
            f"FAILED: validate {args.profile} ({len(errors)} errors, {len(warnings)} warnings)"
        )
        return 2
    print(f"SUCCESS: validate {args.profile} (0 errors, {len(warnings)} warnings)")
    return 0


def cmd_build(args: argparse.Namespace) -> int:
    profile_path = Path(args.profile)
    profile = _load_yaml(profile_path)
    theme = args.theme
    if theme not in KNOWN_THEMES:
        print(
            f"FAILED: unknown theme '{theme}'. Choose one of {', '.join(KNOWN_THEMES)}."
        )
        return 2
    errors, warnings = validate(profile)
    _report(errors, warnings)
    if errors and not args.force:
        print(
            f"FAILED: build blocked by {len(errors)} validation errors (use --force to override)."
        )
        return 2

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    rcv, net_warns = profile_to_rendercv(profile, theme, DEFAULT_SECTION_ORDER)
    for w in net_warns:
        print(f"  WARN  {w}")
    name = re.sub(
        r"[^A-Za-z0-9]+", "_", _s((profile.get("basics") or {}).get("name")) or "cv"
    )
    rcv_yaml = out_dir / f"{name}.rendercv.yaml"
    _dump_yaml(rcv, rcv_yaml)

    engine = find_rendercv()
    if not engine:
        print(
            "FAILED: rendercv engine not found. See INSTALL.md "
            '(`pipx install "rendercv[full]"` or the bundled setup script).'
        )
        print(
            f"  (Mapped RenderCV YAML written to {rcv_yaml} — you can render it manually.)"
        )
        return 3
    pdf = out_dir / f"{name}_CV.pdf"
    cmd = [
        engine,
        "render",
        str(rcv_yaml),
        "-o",
        str(out_dir),
        "-pdf",
        pdf.name,
        "-nopng",
        "-q",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        print(proc.stdout)
        print(proc.stderr, file=sys.stderr)
        print(f"FAILED: rendercv render exited {proc.returncode}.")
        return 3
    if not pdf.exists():
        cands = list(out_dir.glob("*.pdf"))
        pdf = cands[0] if cands else pdf
    ok, missing, pages = selfcheck(pdf, profile)
    print(f"  RENDER {pdf}  ({pages} page(s))")
    print(
        f"  AUDIT  {rcv_yaml} + {pdf.with_suffix('.typ').name} (auditable Typst source)"
    )
    if not ok:
        print("  SELF-CHECK MISSING: " + "; ".join(missing))
        print("FAILED: ATS self-check — the PDF text layer is missing facts above.")
        return 4
    print(
        f"SUCCESS: build {profile_path.name} -> {pdf.name} "
        f"(ATS self-check passed; {len(warnings)} zero-fab warnings to review)"
    )
    return 0


def cmd_tailor(args: argparse.Namespace) -> int:
    profile = _load_yaml(Path(args.profile))
    job_text = Path(args.job).read_text(encoding="utf-8")
    report = tailor(profile, job_text)
    out = (
        Path(args.out) if args.out else Path(args.profile).with_name("tailor-report.md")
    )
    out.write_text(report, encoding="utf-8")
    print(report)
    print(f"SUCCESS: tailor -> {out}")
    return 0


def cmd_selfcheck(args: argparse.Namespace) -> int:
    profile = _load_yaml(Path(args.profile))
    ok, missing, pages = selfcheck(Path(args.pdf), profile)
    if ok:
        print(f"SUCCESS: selfcheck {args.pdf} ({pages} page(s); all key facts present)")
        return 0
    print("  MISSING: " + "; ".join(missing))
    print(f"FAILED: selfcheck {args.pdf}")
    return 4


def cmd_json(args: argparse.Namespace) -> int:
    profile = _load_yaml(Path(args.profile))
    out = Path(args.out) if args.out else Path(args.profile).with_suffix(".resume.json")
    out.write_text(json.dumps(to_json_resume(profile), indent=2), encoding="utf-8")
    print(f"SUCCESS: json -> {out}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="cvstudio", description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("validate", help="schema + zero-fabrication lint")
    p.add_argument("profile")
    p.set_defaults(func=cmd_validate)

    p = sub.add_parser(
        "build", help="profile -> rendercv.yaml -> PDF -> ATS self-check"
    )
    p.add_argument("profile")
    p.add_argument(
        "--theme", default=DEFAULT_ATS_THEME, help=f"one of {', '.join(KNOWN_THEMES)}"
    )
    p.add_argument("--out", default="out", help="output folder (default: out)")
    p.add_argument(
        "--force", action="store_true", help="render despite validation errors"
    )
    p.set_defaults(func=cmd_build)

    p = sub.add_parser("tailor", help="keyword-match report vs a job description")
    p.add_argument("profile")
    p.add_argument("job")
    p.add_argument("--out", default=None)
    p.set_defaults(func=cmd_tailor)

    p = sub.add_parser("selfcheck", help="assert a PDF's text layer contains key facts")
    p.add_argument("pdf")
    p.add_argument("profile")
    p.set_defaults(func=cmd_selfcheck)

    p = sub.add_parser("json", help="export a clean JSON Resume (x_ stripped)")
    p.add_argument("profile")
    p.add_argument("--out", default=None)
    p.set_defaults(func=cmd_json)

    args = ap.parse_args(argv)
    try:
        return args.func(args)
    except FileNotFoundError as exc:
        print(f"FAILED: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
