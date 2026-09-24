#!/usr/bin/env python3
"""cv/tools/build.py — render a named VIEW of profile.yaml into a document.

One master profile -> many audience-specific documents. A *view* (declared under
``x_views`` in profile.yaml) says WHAT is selected, in WHAT order, which sections
render, the locale, the page size, and the page budget. This script applies the
view, emits the renderer's intermediate file, and invokes the renderer.

Pipeline order (this order is the point — the gate runs BEFORE the renderer, so a
fabricated figure can never reach a PDF):

    load profile -> resolve view -> apply selection/order
      -> ZEROFAB GATE (fail-closed: a missing/failing gate refuses the render)
      -> emit intermediate (<slug>.rendercv.yaml)
      -> invoke renderer (rendercv -> Typst -> PDF)
      -> no-regression contract (tools/verify.py)
      -> print SUCCESS:<view> | FAILED:<view>

Usage
-----
    PY=~/.agents/cv/.venv/Scripts/python          # POSIX venv: .venv/bin/python
    $PY tools/build.py --list-views
    $PY tools/build.py --view research-profile
    $PY tools/build.py --view engineering-resume --out out --theme engineeringresumes
    $PY tools/build.py --view ro-eJobs --emit-only      # stop after the intermediate

Exit codes: 0 ok · 2 usage/profile/view error · 3 zerofab gate refused · 4 render
failed · 5 no-regression contract failed.

NO LLM here. This file is mechanics only: selection, mapping, invocation, gating.
The content (every bullet, every number) comes from profile.yaml, which is the
single source of truth and is itself gated by tools/zerofab.py.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

# Windows consoles default to cp1252 on Python 3.14; one em dash in a log line
# would otherwise raise UnicodeEncodeError and lose the terminal SUCCESS/FAILED.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:                                          # pragma: no cover
        pass

ROOT = Path(__file__).resolve().parent.parent          # ~/.agents/cv
TOOLS = ROOT / "tools"
DEFAULT_PROFILE = ROOT / "profile.yaml"
DEFAULT_OUT = ROOT / "out"
DEFAULT_GATE = TOOLS / "zerofab.py"

# --------------------------------------------------------------------------- #
# RenderCV 2.8 ground truth (probed from the installed package, not guessed).  #
#   design/classic_theme.py:24  PageSize = Literal["a4","a5","us-letter",...]  #
#   locale/other_locales/       has no Romanian -> we override English fields. #
# --------------------------------------------------------------------------- #
KNOWN_THEMES = (
    "classic",
    "engineeringresumes",
    "sb2nov",
    "engineeringclassic",
    "moderncv",
)
PAGE_SIZES = {"a4": "a4", "A4": "a4", "a5": "a5", "us-letter": "us-letter",
              "letter": "us-letter", "us-executive": "us-executive"}
DEFAULT_THEME = "engineeringresumes"   # most minimal / colourless -> strictest ATS

# RenderCV's strict SocialNetwork enum. An unknown name is a hard Pydantic error.
_NETWORKS = {
    "linkedin": "LinkedIn", "github": "GitHub", "gitlab": "GitLab", "imdb": "IMDB",
    "instagram": "Instagram", "orcid": "ORCID", "mastodon": "Mastodon",
    "stackoverflow": "StackOverflow", "stack overflow": "StackOverflow",
    "researchgate": "ResearchGate", "youtube": "YouTube",
    "google scholar": "Google Scholar", "scholar": "Google Scholar",
    "telegram": "Telegram", "whatsapp": "WhatsApp", "leetcode": "Leetcode",
    "x": "X", "twitter": "X", "bluesky": "Bluesky", "reddit": "Reddit",
}

# Blocks a view can select/order, and how an item in each is keyed.
BLOCK_KEYS = {
    "work": ("id", "{name}|{position}"),
    "education": ("id", "{institution}"),
    "projects": ("id", "{name}"),
    "publications": ("id", "{name}"),
    "awards": ("id", "{title}"),
    "certificates": ("id", "{name}"),
    "skills": ("id", "{name}"),
    "volunteer": ("id", "{organization}|{position}"),
    "x_data_and_software": ("id", "{name}"),
    "languages": ("id", "{language}"),
    "interests": ("id", "{name}"),
    "references": ("id", "{name}"),
}

DEFAULT_SECTION_ORDER = (
    "summary", "skills", "experience", "education", "projects",
    "publications", "data_software", "awards", "certificates", "languages",
    "volunteer", "interests", "references",
)

# The profile declares views in EDITORIAL vocabulary (`id`, `language`,
# `page_size`, `section_order` as prose headings). build.py owns the render
# contract, so it normalises that vocabulary rather than demanding the data file
# be rewritten. A prose heading is matched to a data block by keyword; anything
# unmatched is WARNed and skipped — never invented.
TITLE_TO_BLOCK: tuple[tuple[str, str], ...] = (
    ("data and software", "data_software"),
    ("zenodo", "data_software"),
    ("research output", "publications"),
    ("publication", "publications"),
    ("publicatii", "publications"),
    ("preprint", "publications"),
    ("research summary", "summary"),
    ("summary", "summary"),
    ("profil", "summary"),
    ("experience", "experience"),
    ("experienta", "experience"),
    ("employment", "experience"),
    ("education", "education"),
    ("educatie", "education"),
    ("research engineering", "projects"),
    ("selected software", "projects"),
    ("project", "projects"),
    ("proiecte", "projects"),
    ("software", "projects"),
    ("honor", "awards"),
    ("award", "awards"),
    ("distinctii", "awards"),
    ("pbinfo", "awards"),
    ("skill", "skills"),
    ("competente", "skills"),
    ("certific", "certificates"),
    ("language", "languages"),
    ("limbi", "languages"),
    ("volunteer", "volunteer"),
    ("voluntariat", "volunteer"),
    ("interest", "interests"),
    ("reference", "references"),
    ("referinte", "references"),
)

SECTION_TITLES = {
    "en": {
        "summary": "Summary", "skills": "Skills", "experience": "Experience",
        "education": "Education", "projects": "Projects",
        "publications": "Publications & Preprints", "awards": "Honors & Awards",
        "data_software": "Data and Software",
        "certificates": "Certifications", "languages": "Languages",
        "volunteer": "Volunteering", "interests": "Interests",
        "references": "References",
    },
    "ro": {
        "summary": "Profil", "skills": "Competente", "experience": "Experienta",
        "education": "Educatie", "projects": "Proiecte",
        "publications": "Publicatii si preprinturi", "awards": "Distinctii",
        "data_software": "Date si software",
        "certificates": "Certificari", "languages": "Limbi straine",
        "volunteer": "Voluntariat", "interests": "Interese",
        "references": "Referinte",
    },
}

# No Romanian locale ships with RenderCV 2.8 (probed: other_locales/ has 21 files,
# none Romanian). EnglishLocale permits per-field overrides while `language`
# stays "english", so a locale pack is a field-override dict. Diacritic-free by
# design: the profile's canonical name is unaccented and PDF text layers that mix
# encodings are the classic ATS mangling source.
LOCALE_PACKS: dict[str, dict[str, Any]] = {
    "en": {"language": "english"},
    "ro": {
        "language": "english",
        "present": "prezent",
        "last_updated": "Actualizat in",
        "month": "luna", "months": "luni", "year": "an", "years": "ani",
        "phrases": {"degree_with_area": "DEGREE in AREA"},
        "month_abbreviations": ["ian", "feb", "mar", "apr", "mai", "iun",
                                "iul", "aug", "sep", "oct", "noi", "dec"],
        "month_names": ["ianuarie", "februarie", "martie", "aprilie", "mai",
                        "iunie", "iulie", "august", "septembrie", "octombrie",
                        "noiembrie", "decembrie"],
    },
}

# Fields that must NEVER reach a machine-parsed document (EU/ATS hygiene).
PERSONAL_DATA_KEYS = (
    "photo", "image", "picture", "birthDate", "birthdate", "dob",
    "dateOfBirth", "nationality", "citizenship", "maritalStatus",
    "marital_status", "gender", "address", "street", "streetAddress",
    "postalCode", "x_private", "x_privacy",
)

TODO_MARKER = "TODO-CONFIRM"

VIEW_DEFAULTS: dict[str, Any] = {
    "renderer": "rendercv",
    "theme": DEFAULT_THEME,
    "locale": "en",
    "page": "A4",
    "parsed": True,          # machine-parsed -> single column + no personal data
    "page_budget": [1, 3],
    "sections": list(DEFAULT_SECTION_ORDER),
    "section_titles": {},    # per-view override, e.g. {awards: "Distinctii"}
    "select": {},            # {block: {include:[keys], exclude:[keys]}}
    "order": {},             # {block: [keys in render order]}
    "tags": {},              # {any:[...], all:[...], none:[...]} matched on x_tags
    "max_highlights": {},    # {block: int}
    "todo_policy": "annotate",   # annotate | omit | fail
    "headline": None,        # override basics.label for this audience
    "summary": None,         # key into x_summaries, else basics.summary
    "design": {},            # raw RenderCV design overrides, merged last
    "slug": None,            # output file stem; default <Name>_<view>
}


# --------------------------------------------------------------------------- #
# IO helpers                                                                   #
# --------------------------------------------------------------------------- #
def load_yaml(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    try:
        from ruamel.yaml import YAML

        y = YAML(typ="safe")
        data = y.load(text)
    except ImportError:
        import yaml as pyyaml

        data = pyyaml.safe_load(text)
    if not isinstance(data, dict):
        raise ValueError(f"{path} did not parse to a mapping")
    return data


def dump_yaml(obj: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        from ruamel.yaml import YAML

        y = YAML()
        y.default_flow_style = False
        y.width = 4096
        y.allow_unicode = True
        with path.open("w", encoding="utf-8", newline="\n") as fh:
            y.dump(obj, fh)
    except ImportError:
        import yaml as pyyaml

        path.write_text(
            pyyaml.safe_dump(obj, sort_keys=False, allow_unicode=True, width=4096),
            encoding="utf-8",
        )


def s(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, bool):
        return ""
    return str(v).strip()


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def log(msg: str) -> None:
    print(msg, flush=True)


# --------------------------------------------------------------------------- #
# View resolution + selection                                                  #
# --------------------------------------------------------------------------- #
def _views_map(profile: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """x_views may be a mapping {name: spec} or a list of specs carrying `id`."""
    raw = profile.get("x_views") or {}
    if isinstance(raw, dict):
        return {str(k): (v if isinstance(v, dict) else {}) for k, v in raw.items()}
    if isinstance(raw, list):
        out: dict[str, dict[str, Any]] = {}
        for i, spec in enumerate(raw):
            if not isinstance(spec, dict):
                continue
            key = s(spec.get("id")) or s(spec.get("name")) or f"view{i}"
            out[key] = spec
        return out
    raise ValueError("x_views must be a mapping or a list of specs")


def _fold(text: str) -> str:
    """Lowercase, strip diacritics and any parenthesised qualifier."""
    import unicodedata

    text = re.sub(r"\(.*?\)", " ", s(text))
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", text).strip().lower()


def title_to_block(title: str) -> str | None:
    folded = _fold(title)
    for needle, block in TITLE_TO_BLOCK:
        if needle in folded:
            return block
    return None


def normalize_view_spec(spec: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Translate the profile's editorial view vocabulary into a render spec.

    Recognised editorial keys: language, page_size, photo, headline,
    section_order (prose headings), include_ubb, engine, outputs, structure,
    max_pages / page_budget. Keys already in render vocabulary pass through.
    """
    out: dict[str, Any] = {}
    warns: list[str] = []
    for k, v in spec.items():
        if k in VIEW_DEFAULTS or k == "extends":
            out[k] = v

    if s(spec.get("language")):
        out["locale"] = s(spec.get("language")).lower()[:2]
    if s(spec.get("page_size")):
        out["page"] = s(spec.get("page_size"))
    if s(spec.get("headline")):
        out["headline"] = re.sub(r"\s+", " ", s(spec.get("headline")))

    budget = spec.get("page_budget") or spec.get("pages")
    if isinstance(spec.get("max_pages"), int):
        budget = [1, spec["max_pages"]]
    if isinstance(budget, (list, tuple)) and budget:
        out["page_budget"] = [int(budget[0]), int(budget[-1])]

    # A view that only declares text outputs (cover letter, LinkedIn copy,
    # platform snippets) is not a document this renderer produces.
    engine = _fold(spec.get("engine"))
    if spec.get("outputs") or spec.get("structure"):
        out["renderer"] = "none"
        out["renderer_reason"] = "view declares text outputs, not a rendered document"
    elif "design" in engine and "rendercv" not in engine:
        out["renderer"] = "design"
        out["renderer_reason"] = f"view routes to the design pipeline (engine: {engine})"

    order = spec.get("section_order")
    if isinstance(order, list) and order:
        blocks: list[str] = []
        titles: dict[str, str] = {}
        for raw_title in order:
            title = re.sub(r"\s+", " ", s(raw_title))
            block = title_to_block(title)
            if block is None:
                warns.append(
                    f"section_order entry {title!r} matches no data block; skipped "
                    f"(nothing is invented to fill it)"
                )
                continue
            if block in blocks:
                warns.append(
                    f"section_order entry {title!r} maps to block {block!r}, already "
                    f"rendered as {titles[block]!r}; merged (its items render there)"
                )
                continue
            blocks.append(block)
            titles[block] = title
        if blocks:
            out["sections"] = blocks
            out["section_titles"] = {**titles, **(out.get("section_titles") or {})}

    if spec.get("include_ubb") is False:
        sel = dict(out.get("select") or {})
        edu = dict(sel.get("education") or {})
        edu["exclude_matching"] = [*(edu.get("exclude_matching") or []), "babes-bolyai"]
        sel["education"] = edu
        out["select"] = sel
    return out, warns


def list_views(profile: dict[str, Any]) -> list[str]:
    try:
        return list(_views_map(profile))
    except ValueError:
        return []


def resolve_view(profile: dict[str, Any], name: str) -> dict[str, Any]:
    """Merge a named x_views entry over VIEW_DEFAULTS. Supports `extends`."""
    views = _views_map(profile)

    if name not in views:
        if name == "default" and not views:
            # A profile with no x_views still builds: render everything, once.
            return copy.deepcopy(VIEW_DEFAULTS) | {"name": "default",
                                                   "_synthesized": True}
        raise KeyError(
            f"view {name!r} not found. Available: "
            f"{', '.join(list_views(profile)) or '(none — x_views is empty)'}"
        )

    chain: list[dict[str, Any]] = []
    warns: list[str] = []
    seen: set[str] = set()
    cur = name
    while cur:
        if cur in seen:
            raise ValueError(f"circular `extends` in x_views at {cur!r}")
        seen.add(cur)
        spec = views.get(cur)
        if not isinstance(spec, dict):
            raise ValueError(f"x_views.{cur} must be a mapping")
        norm, w = normalize_view_spec(spec)
        warns.extend(w)
        chain.append(norm)
        cur = s(spec.get("extends")) or ""

    out = copy.deepcopy(VIEW_DEFAULTS)
    declared_budget = False
    for spec in reversed(chain):            # base first, most-derived last
        for k, v in spec.items():
            if k == "extends":
                continue
            if k == "page_budget":
                declared_budget = True
            if isinstance(v, dict) and isinstance(out.get(k), dict):
                out[k] = {**out[k], **v}
            else:
                out[k] = copy.deepcopy(v)
    if not declared_budget:
        warns.append(
            f"view {name!r} declares no page_budget; using the default "
            f"{VIEW_DEFAULTS['page_budget']} (override with --page-budget LO-HI)"
        )
    out["name"] = name
    out["_synthesized"] = False
    out["_warnings"] = warns
    return out


def item_key(block: str, item: Any) -> str:
    """Stable identity for a profile item, for include/exclude/order lists."""
    if not isinstance(item, dict):
        return s(item)
    id_field, template = BLOCK_KEYS.get(block, ("id", "{name}"))
    if s(item.get(id_field)):
        return s(item.get(id_field))
    fields = re.findall(r"\{(\w+)\}", template)
    vals = [s(item.get(f)) for f in fields]
    return "|".join(v for v in vals if v) if any(vals) else s(item.get("name"))


def _tag_ok(item: Any, tags: dict[str, Any]) -> bool:
    if not tags:
        return True
    have = set()
    if isinstance(item, dict):
        have = {s(t).lower() for t in (item.get("x_tags") or []) if s(t)}
    any_ = {s(t).lower() for t in (tags.get("any") or [])}
    all_ = {s(t).lower() for t in (tags.get("all") or [])}
    none_ = {s(t).lower() for t in (tags.get("none") or [])}
    if none_ and (have & none_):
        return False
    if all_ and not all_.issubset(have):
        return False
    if any_ and not (have & any_):
        return False
    return True


def apply_selection(profile: dict[str, Any], view: dict[str, Any]) -> dict[str, Any]:
    """Filter + order every selectable block according to the view."""
    out = copy.deepcopy(profile)
    select = view.get("select") or {}
    order = view.get("order") or {}
    tags = view.get("tags") or {}
    caps = view.get("max_highlights") or {}

    for block in BLOCK_KEYS:
        items = out.get(block)
        if not isinstance(items, list):
            continue
        rule = select.get(block) or {}
        include = [s(x) for x in (rule.get("include") or []) if s(x)]
        exclude = {s(x) for x in (rule.get("exclude") or []) if s(x)}
        # Substring form, diacritic-insensitive: the editorial `include_ubb: false`
        # switch becomes exclude_matching: ["babes-bolyai"].
        exclude_sub = [_fold(x) for x in (rule.get("exclude_matching") or []) if s(x)]
        block_tags = rule.get("tags") if isinstance(rule.get("tags"), dict) else tags

        kept = []
        for it in items:
            key = item_key(block, it)
            if include and key not in include:
                continue
            if key in exclude:
                continue
            if exclude_sub and any(sub in _fold(key) for sub in exclude_sub):
                continue
            if not include and not _tag_ok(it, block_tags):
                continue
            kept.append(it)

        seq = [s(x) for x in (order.get(block) or include) if s(x)]
        if seq:
            rank = {k: i for i, k in enumerate(seq)}
            kept.sort(key=lambda it: rank.get(item_key(block, it), len(rank)))

        cap = caps.get(block)
        if isinstance(cap, int) and cap > 0:
            for it in kept:
                if isinstance(it, dict) and isinstance(it.get("highlights"), list):
                    it["highlights"] = it["highlights"][:cap]
        out[block] = kept
    return out


def strip_personal_data(profile: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Remove DOB / nationality / marital status / street address / photo.

    Enforced on every parsed view: these are illegal-to-require or
    discrimination-risk fields in the EU and pure noise to an ATS parser.
    """
    removed: list[str] = []

    def scrub(node: Any, path: str) -> Any:
        if isinstance(node, dict):
            clean = {}
            for k, v in node.items():
                if k in PERSONAL_DATA_KEYS:
                    removed.append(f"{path}.{k}" if path else k)
                    continue
                clean[k] = scrub(v, f"{path}.{k}" if path else k)
            return clean
        if isinstance(node, list):
            return [scrub(x, path) for x in node]
        return node

    return scrub(profile, ""), removed


def apply_todo_policy(profile: dict[str, Any], policy: str) -> tuple[dict[str, Any], list[str]]:
    """TODO-CONFIRM markers must never silently ship.

    annotate (default) — leave the marker visible in the PDF, so an unreviewed
                         draft is obvious on sight.
    omit               — drop any string carrying the marker.
    fail               — refuse to build while any marker remains.
    """
    hits: list[str] = []

    def walk(node: Any, path: str) -> Any:
        if isinstance(node, dict):
            return {k: walk(v, f"{path}.{k}" if path else k) for k, v in node.items()}
        if isinstance(node, list):
            out = []
            for i, x in enumerate(node):
                w = walk(x, f"{path}[{i}]")
                if w is not None:
                    out.append(w)
            return out
        if isinstance(node, str) and TODO_MARKER in node:
            hits.append(path)
            if policy == "omit":
                return None
        return node

    if policy not in ("annotate", "omit", "fail"):
        raise ValueError(f"todo_policy must be annotate|omit|fail, got {policy!r}")
    scrubbed = walk(profile, "")
    return (scrubbed if policy == "omit" else profile), hits


# --------------------------------------------------------------------------- #
# profile.yaml (JSON Resume superset) -> RenderCV intermediate                 #
# --------------------------------------------------------------------------- #
def _social(profiles: list[dict[str, Any]]) -> tuple[list[dict[str, str]], list[str]]:
    out, warns = [], []
    for p in profiles or []:
        canon = _NETWORKS.get(s(p.get("network")).lower())
        user = s(p.get("username")) or s(p.get("url")).rstrip("/").rsplit("/", 1)[-1]
        if not canon:
            warns.append(f"social network {p.get('network')!r} unsupported by RenderCV; skipped")
            continue
        if not user:
            warns.append(f"social network {canon} has no username; skipped")
            continue
        out.append({"network": canon, "username": user})
    return out, warns


def _md_link(name: Any, url: Any) -> str:
    name, url = s(name), s(url)
    return f"[{name}]({url})" if url and name else (name or url)


_DATE_SHAPE = re.compile(r"^\d{4}(-\d{2}(-\d{2})?)?$")


def _is_date(value: str, present: str) -> bool:
    v = s(value)
    return bool(_DATE_SHAPE.match(v)) or v.lower() in {"present", present.lower()}


def _dates(item: dict[str, Any], present: str) -> tuple[dict[str, str], str]:
    """Map dates onto RenderCV's TYPED date fields — and refuse to guess.

    RenderCV rejects anything that is not YYYY[-MM[-DD]] or the present token,
    so an unresolved "TODO-CONFIRM" end date would break the render. Silently
    substituting `present` would instead ASSERT an ongoing engagement that is
    not established. So an unparseable date is pulled out of the typed field
    and rendered as a visible note, and the uncertainty survives into the PDF.
    """
    start, end = s(item.get("startDate")), s(item.get("endDate"))
    single = s(item.get("date"))

    if start and _is_date(start, present) and (not end or _is_date(end, present)):
        return {"start_date": start, "end_date": end or present}, ""
    if not start and single and _is_date(single, present):
        return {"date": single}, ""
    if not start and end and _is_date(end, present):
        return {"date": end}, ""

    raw = " to ".join(x for x in (start, end or single) if x)
    return ({}, f"Dates: {raw}") if raw else ({}, "")


def _highlights(item: dict[str, Any]) -> list[str]:
    return [s(h) for h in (item.get("highlights") or []) if s(h)]


def _experience(rows: list[dict[str, Any]], present: str) -> list[dict[str, Any]]:
    out = []
    for w in rows or []:
        row: dict[str, Any] = {
            "company": s(w.get("name") or w.get("company") or w.get("organization")),
            "position": s(w.get("position")),
        }
        if s(w.get("location")):
            row["location"] = s(w.get("location"))
        fields, note = _dates(w, present)
        row.update(fields)
        if s(w.get("summary")):
            row["summary"] = s(w.get("summary"))
        hl = _highlights(w)
        if note:
            hl.insert(0, note)
        if hl:
            row["highlights"] = hl
        out.append(row)
    return out


def _education(rows: list[dict[str, Any]], present: str) -> list[dict[str, Any]]:
    out = []
    for e in rows or []:
        row: dict[str, Any] = {"institution": s(e.get("institution"))}
        if s(e.get("area")):
            row["area"] = s(e.get("area"))
        if s(e.get("studyType") or e.get("degree")):
            row["degree"] = s(e.get("studyType") or e.get("degree"))
        if s(e.get("location")):
            row["location"] = s(e.get("location"))
        fields, note = _dates(e, present)
        row.update(fields)
        hl = _highlights(e)
        if note:
            hl.insert(0, note)
        if s(e.get("score")):
            hl.insert(0, f"GPA: {s(e.get('score'))}")
        courses = [s(c) for c in (e.get("courses") or []) if s(c)]
        if courses:
            hl.append("Coursework: " + ", ".join(courses))
        if hl:
            row["highlights"] = hl
        out.append(row)
    return out


def _projects(rows: list[dict[str, Any]], present: str) -> list[dict[str, Any]]:
    out = []
    for p in rows or []:
        row: dict[str, Any] = {"name": _md_link(p.get("name"), p.get("url"))}
        fields, note = _dates(p, present)
        row.update(fields)
        if s(p.get("description")):
            row["summary"] = s(p.get("description"))
        hl = _highlights(p)
        if note:
            hl.insert(0, note)
        if hl:
            row["highlights"] = hl
        out.append(row)
    return out


def _skills(rows: list[dict[str, Any]]) -> list[dict[str, str]]:
    out, loose = [], []
    for sk in rows or []:
        name = s(sk.get("name"))
        kw = [s(k) for k in (sk.get("keywords") or []) if s(k)]
        details = ", ".join(kw) if kw else s(sk.get("level"))
        if details:
            out.append({"label": name, "details": details})
        elif name:
            loose.append(name)
    if loose:
        out.append({"label": "Additional", "details": ", ".join(loose)})
    return out


def _publications(rows: list[dict[str, Any]], owner: str = "",
                  warns: list[str] | None = None) -> list[dict[str, Any]]:
    """RenderCV's PublicationEntry REQUIRES `authors` (no default), and a whole
    section must be one entry type — so an author-less entry would break the
    render. Rather than drop the entry silently, fall back to the CV owner and
    say so out loud."""
    out = []
    for p in rows or []:
        row: dict[str, Any] = {"title": s(p.get("name") or p.get("title"))}
        authors = [s(a) for a in (p.get("authors") or []) if s(a)]
        if not authors and owner:
            authors = [owner]
            if warns is not None:
                warns.append(
                    f"publication {row['title'][:48]!r} declares no authors; "
                    f"rendered as {owner!r} (RenderCV requires the field) — "
                    f"add an explicit authors list to profile.yaml"
                )
        if authors:
            row["authors"] = authors
        if s(p.get("publisher") or p.get("journal")):
            row["journal"] = s(p.get("publisher") or p.get("journal"))
        if s(p.get("doi")):
            row["doi"] = s(p.get("doi"))
        if s(p.get("url")):
            row["url"] = s(p.get("url"))
        pub_date = s(p.get("releaseDate") or p.get("date"))
        if pub_date and _is_date(pub_date, "present"):
            row["date"] = pub_date
        elif pub_date:
            row["summary"] = " ".join(x for x in (s(row.get("summary")), f"Date: {pub_date}") if x)
        out.append(row)
    return out


def _awards(rows: list[dict[str, Any]]) -> list[dict[str, str]]:
    out = []
    for a in rows or []:
        title = s(a.get("title"))
        awarder = s(a.get("awarder"))
        date = s(a.get("date"))
        summary = s(a.get("summary"))
        head = " — ".join(x for x in (title, awarder) if x)
        if date:
            head = f"{head} ({date})"
        out.append({"bullet": f"{head}. {summary}".strip() if summary else head})
    return out


def _certificates(rows: list[dict[str, Any]]) -> list[dict[str, str]]:
    return [
        {"label": _md_link(c.get("name"), c.get("url")),
         "details": ", ".join(x for x in (s(c.get("issuer")), s(c.get("date"))) if x) or "—"}
        for c in rows or []
    ]


def _languages(rows: list[dict[str, Any]]) -> list[dict[str, str]]:
    return [
        {"label": s(row.get("language")), "details": s(row.get("fluency")) or "—"}
        for row in rows or [] if s(row.get("language"))
    ]


def _data_software(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """`x_data_and_software` — data deposits and released software.

    A deliberately SEPARATE section: filing a data deposit under Publications is
    exactly the inflation an academic reviewer looks for (profile x_style lock).
    """
    out = []
    for d in rows or []:
        row: dict[str, Any] = {"name": _md_link(d.get("name"), d.get("url"))}
        bits = [s(d.get("repository")), s(d.get("doi")), s(d.get("version"))]
        detail = ", ".join(b for b in bits if b)
        summary = s(d.get("description"))
        if detail and summary:
            row["summary"] = f"{summary} ({detail})"
        elif summary or detail:
            row["summary"] = summary or detail
        fields, note = _dates(d, "present")
        row.update(fields)
        hl = _highlights(d)
        if note:
            hl.insert(0, note)
        if hl:
            row["highlights"] = hl
        out.append(row)
    return out


def _texts(v: Any) -> list[str]:
    if isinstance(v, list):
        return [s(x) for x in v if s(x)]
    return [s(v)] if s(v) else []


def profile_to_rendercv(
    profile: dict[str, Any], view: dict[str, Any]
) -> tuple[dict[str, Any], list[str]]:
    basics = profile.get("basics") or {}
    loc = basics.get("location") or {}
    locale_key = s(view.get("locale")) or "en"
    pack = LOCALE_PACKS.get(locale_key) or LOCALE_PACKS["en"]
    present = s(pack.get("present")) or "present"
    titles = {**SECTION_TITLES.get(locale_key, SECTION_TITLES["en"]),
              **(view.get("section_titles") or {})}

    # City/region only — never a street address, on any view.
    location = ", ".join(
        x for x in (s(loc.get("city")), s(loc.get("region") or loc.get("countryCode"))) if x
    )
    nets, warns = _social(basics.get("profiles") or [])

    cv: dict[str, Any] = {"name": s(basics.get("name"))}
    headline = s(view.get("headline")) or s(basics.get("label"))
    if headline:
        cv["headline"] = headline
    if location:
        cv["location"] = location
    for key, field in (("email", "email"), ("phone", "phone"), ("website", "url")):
        if s(basics.get(field)):
            cv[key] = s(basics.get(field))
    if nets:
        cv["social_networks"] = nets

    summary_key = s(view.get("summary"))
    summaries = profile.get("x_summaries") or {}
    summary_text = (
        summaries.get(summary_key) if summary_key and isinstance(summaries, dict) else None
    ) or basics.get("summary")
    if summary_key and isinstance(summaries, dict) and summary_key not in summaries:
        warns.append(f"view.summary {summary_key!r} not in x_summaries; used basics.summary")

    builders = {
        "summary": lambda: _texts(summary_text),
        "skills": lambda: _skills(profile.get("skills")),
        "experience": lambda: _experience(profile.get("work"), present),
        "education": lambda: _education(profile.get("education"), present),
        "projects": lambda: _projects(profile.get("projects"), present),
        "publications": lambda: _publications(
            profile.get("publications"), s(basics.get("name")), warns
        ),
        "data_software": lambda: _data_software(
            profile.get("x_data_and_software") or profile.get("data_software")
        ),
        "awards": lambda: _awards(profile.get("awards")),
        "certificates": lambda: _certificates(profile.get("certificates")),
        "languages": lambda: _languages(profile.get("languages")),
        "volunteer": lambda: _experience(profile.get("volunteer"), present),
        "interests": lambda: _texts([i.get("name") for i in (profile.get("interests") or [])]),
        "references": lambda: [
            f"{s(r.get('reference'))} — {s(r.get('name'))}"
            for r in (profile.get("references") or []) if s(r.get("name"))
        ],
    }

    sections: dict[str, Any] = {}
    for key in view.get("sections") or DEFAULT_SECTION_ORDER:
        build = builders.get(key)
        if build is None:
            warns.append(f"view section {key!r} is not a known block; skipped")
            continue
        entries = build()
        if entries:
            sections[titles.get(key, key.title())] = entries
    cv["sections"] = sections

    theme = s(view.get("theme")) or DEFAULT_THEME
    if theme not in KNOWN_THEMES:
        raise ValueError(f"unknown theme {theme!r}; choose from {', '.join(KNOWN_THEMES)}")
    page_size = PAGE_SIZES.get(s(view.get("page")) or "A4")
    if not page_size:
        raise ValueError(f"unknown page size {view.get('page')!r}; use A4/a5/us-letter")

    design: dict[str, Any] = {"theme": theme, "page": {"size": page_size}}
    if view.get("parsed"):
        # Typst hyphenates justified text, and a soft hyphen in the text layer
        # splits a keyword an ATS matches exactly ("infra-structure" != the
        # search term). Measured: the default justified setting put 3 U+00AD
        # into this profile's 2-page render. Off by default on parsed views.
        design["typography"] = {"alignment": "justified-with-no-hyphenation"}
    for k, v in (view.get("design") or {}).items():
        if isinstance(v, dict) and isinstance(design.get(k), dict):
            design[k] = {**design[k], **v}
        else:
            design[k] = v

    doc: dict[str, Any] = {"cv": cv, "design": design, "locale": copy.deepcopy(pack)}
    return doc, warns


# --------------------------------------------------------------------------- #
# The zero-fabrication gate — FAIL CLOSED                                      #
# --------------------------------------------------------------------------- #
def run_zerofab_gate(
    gate: Path, profile_path: Path, view_name: str, python: str
) -> tuple[bool, str]:
    """Run tools/zerofab.py. Exit 0 = pass. Anything else (including a MISSING
    gate, a crash, or a timeout) = refuse to render.

    The gate's own CLI is probed rather than assumed: if `--help` advertises
    `--view`, the view name is passed through so the gate can scope its lint.
    """
    if not gate.exists():
        return False, (
            f"zerofab gate not found at {gate}. Fail-closed: refusing to render "
            f"without the zero-fabrication gate. (Point at it with --gate PATH.)"
        )
    try:
        helptext = subprocess.run(
            [python, str(gate), "--help"], capture_output=True, text=True, check=False,
            timeout=120, encoding="utf-8", errors="replace",
        )
        advertised = (helptext.stdout or "") + (helptext.stderr or "")
    except Exception:
        advertised = ""
    view_flag = ["--view", view_name] if "--view" in advertised else []

    # Candidate CLIs, most likely first. A gate that rejects its argv with
    # argparse's exit-2 "unrecognized/required arguments" is retried with the
    # other shape; any OTHER non-zero exit is a real gate FAILURE and is final.
    candidates = [
        [python, str(gate), str(profile_path), *view_flag],
        [python, str(gate), "--profile", str(profile_path), *view_flag],
    ]
    if "--profile" in advertised:
        candidates.reverse()

    proc = None
    for i, argv in enumerate(candidates):
        try:
            proc = subprocess.run(argv, capture_output=True, text=True, timeout=600,
                                  check=False, encoding="utf-8", errors="replace")
        except subprocess.TimeoutExpired:
            return False, "zerofab gate timed out after 600s — treated as FAIL (fail-closed)"
        except Exception as exc:                               # pragma: no cover
            return False, f"zerofab gate could not be executed: {exc!r} (fail-closed)"
        argparse_reject = proc.returncode == 2 and re.search(
            r"unrecognized arguments|the following arguments are required|invalid choice",
            (proc.stderr or "") + (proc.stdout or ""),
        )
        if not (argparse_reject and i + 1 < len(candidates)):
            break

    assert proc is not None
    for line in (proc.stdout or "").rstrip().splitlines():
        log(f"  | {line}")
    for line in (proc.stderr or "").rstrip().splitlines()[:40]:
        log(f"  | {line}")
    if proc.returncode != 0:
        return False, f"zerofab gate exited {proc.returncode} — render refused"
    return True, "zerofab gate passed"


# --------------------------------------------------------------------------- #
# Renderer                                                                     #
# --------------------------------------------------------------------------- #
def find_rendercv() -> str | None:
    import os

    env = os.environ.get("CV_RENDERCV") or os.environ.get("CV_STUDIO_RENDERCV")
    if env and Path(env).exists():
        return env
    here = Path(sys.executable).parent                 # the venv running us
    for cand in (here / "rendercv.exe", here / "rendercv",
                 ROOT / ".venv/Scripts/rendercv.exe", ROOT / ".venv/bin/rendercv",
                 Path.home() / ".local/share/cv-studio/venv/Scripts/rendercv.exe",
                 Path.home() / ".local/share/cv-studio/venv/bin/rendercv",
                 Path.home() / ".local/bin/rendercv"):
        if cand.exists():
            return str(cand)
    return shutil.which("rendercv")


def render_rendercv(intermediate: Path, out_dir: Path, pdf_name: str) -> tuple[bool, str, Path]:
    engine = find_rendercv()
    if not engine:
        return False, (
            "rendercv engine not found. Create the venv:\n"
            f"  C:/Python314/python.exe -m venv {ROOT / '.venv'}\n"
            f"  {ROOT / '.venv/Scripts/python.exe'} -m pip install 'rendercv[full]' pymupdf ruamel.yaml"
        ), out_dir / pdf_name
    cmd = [engine, "render", str(intermediate), "-o", str(out_dir),
           "-pdf", pdf_name, "-nopng", "-nomd", "-nohtml", "-q"]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False,
                          encoding="utf-8", errors="replace")
    pdf = out_dir / pdf_name
    if proc.returncode != 0:
        tail = ((proc.stdout or "") + "\n" + (proc.stderr or "")).strip().splitlines()
        for line in tail[-30:]:
            log(f"  | {line}")
        return False, f"rendercv render exited {proc.returncode}", pdf
    if not pdf.exists():
        cands = sorted(out_dir.glob("*.pdf"))
        if not cands:
            return False, "rendercv reported success but produced no PDF", pdf
        pdf = cands[0]
    return True, f"rendered {pdf.name}", pdf


RENDERERS = {"rendercv": render_rendercv}


# --------------------------------------------------------------------------- #
# Driver                                                                       #
# --------------------------------------------------------------------------- #
def slugify(text: str) -> str:
    return re.sub(r"_+", "_", re.sub(r"[^A-Za-z0-9]+", "_", text)).strip("_") or "cv"


def build(args: argparse.Namespace) -> int:
    view_name = args.view
    profile_path = Path(args.profile).resolve()
    if not profile_path.exists():
        log(f"  ERROR profile not found: {profile_path}")
        log(f"FAILED:{view_name}")
        return 2

    try:
        profile = load_yaml(profile_path)
    except Exception as exc:
        log(f"  ERROR could not parse {profile_path}: {exc}")
        log(f"FAILED:{view_name}")
        return 2

    try:
        view = resolve_view(profile, view_name)
    except (KeyError, ValueError) as exc:
        log(f"  ERROR {exc}")
        log(f"FAILED:{view_name}")
        return 2

    if args.theme:
        view["theme"] = args.theme
    if args.page_budget:
        m = re.fullmatch(r"(\d+)\s*[-:]\s*(\d+)", args.page_budget.strip())
        if not m:
            log(f"  ERROR --page-budget must look like 1-2, got {args.page_budget!r}")
            log(f"FAILED:{view_name}")
            return 2
        view["page_budget"] = [int(m.group(1)), int(m.group(2))]
    if view.get("_synthesized"):
        log("  WARN  profile has no x_views; using the synthesized 'default' view")
    for w in view.get("_warnings") or []:
        log(f"  WARN  {w}")

    log(f"  VIEW   {view_name}  (renderer={view['renderer']} theme={view['theme']} "
        f"locale={view['locale']} page={view['page']} parsed={view['parsed']} "
        f"budget={view['page_budget']})")

    renderer = s(view.get("renderer")) or "rendercv"
    if renderer in ("none", "design"):
        log(f"  SKIP   {view.get('renderer_reason') or f'renderer {renderer!r} is not a PDF path'}")
        log("  NOTE   this view produces text/designed output elsewhere; "
            "build.py renders documents only.")
        log(f"SKIPPED:{view_name}")
        return 0
    if renderer not in RENDERERS:
        log(f"  ERROR renderer {renderer!r} not implemented (have: {', '.join(RENDERERS)})")
        log(f"FAILED:{view_name}")
        return 2

    # ---- 1. zerofab gate, BEFORE anything is rendered ---------------------- #
    if args.skip_gate:
        # Deliberately loud: this exists only for engine smoke-tests on fixtures.
        log("  GATE   SKIPPED via --skip-gate — output is NOT gate-approved and "
            "must not be sent to anyone.")
    else:
        gate = Path(args.gate).resolve() if args.gate else DEFAULT_GATE
        ok, msg = run_zerofab_gate(gate, profile_path, view_name, sys.executable)
        log(f"  GATE   {msg}")
        if not ok:
            log(f"FAILED:{view_name}")
            return 3

    # ---- 2. apply the view ------------------------------------------------- #
    selected = apply_selection(profile, view)
    try:
        selected, todo_hits = apply_todo_policy(selected, s(view.get("todo_policy")) or "annotate")
    except ValueError as exc:
        log(f"  ERROR {exc}")
        log(f"FAILED:{view_name}")
        return 2
    if todo_hits:
        policy = view.get("todo_policy")
        log(f"  TODO   {len(todo_hits)} TODO-CONFIRM marker(s) (policy={policy}): "
            + ", ".join(todo_hits[:6]) + (" …" if len(todo_hits) > 6 else ""))
        if policy == "fail":
            log("  ERROR todo_policy=fail and unresolved TODO-CONFIRM markers remain")
            log(f"FAILED:{view_name}")
            return 2

    removed: list[str] = []
    if view.get("parsed"):
        selected, removed = strip_personal_data(selected)
        if removed:
            log(f"  PRIVACY stripped for parsed view: {', '.join(sorted(set(removed))[:8])}")

    # ---- 3. emit the intermediate ------------------------------------------ #
    basics = selected.get("basics") or {}
    name = s(basics.get("name")) or "cv"
    stem = s(view.get("slug")) or f"{slugify(name)}_{slugify(view_name)}"
    out_dir = Path(args.out).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        doc, warns = profile_to_rendercv(selected, view)
    except ValueError as exc:
        log(f"  ERROR {exc}")
        log(f"FAILED:{view_name}")
        return 2
    for w in warns:
        log(f"  WARN  {w}")

    intermediate = out_dir / f"{stem}.rendercv.yaml"
    dump_yaml(doc, intermediate)
    log(f"  EMIT   {intermediate}  ({intermediate.stat().st_size} bytes)")

    # C1's expectation is scoped to the sections this view actually RENDERS.
    # A research profile that deliberately omits Experience must not be failed
    # for "missing" an employer it was never asked to print.
    rendered_sections = set(view.get("sections") or DEFAULT_SECTION_ORDER)
    employers = ([s(w.get("name") or w.get("company")) for w in (selected.get("work") or [])]
                 if "experience" in rendered_sections else [])
    institutions = ([s(e.get("institution")) for e in (selected.get("education") or [])]
                    if "education" in rendered_sections else [])
    manifest = {
        "view": view_name,
        "renderer": renderer,
        "theme": view["theme"],
        "locale": view["locale"],
        "page": view["page"],
        "parsed": bool(view.get("parsed")),
        "page_budget": list(view.get("page_budget") or [1, 3]),
        "sections": list(view.get("sections") or []),
        "name": name,
        "employers": [e for e in employers if e],
        "institutions": [i for i in institutions if i],
        "personal_fields_stripped": sorted(set(removed)),
        "todo_markers": todo_hits,
        "profile": str(profile_path),
        "profile_sha256": sha256(profile_path),
        "intermediate": str(intermediate),
        "gate_skipped": bool(args.skip_gate),
    }
    manifest_path = out_dir / f"{stem}.manifest.json"

    if args.emit_only:
        manifest["pdf"] = None
        manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
                                 encoding="utf-8")
        log(f"  EMIT   {manifest_path}")
        log("  NOTE   --emit-only: stopped before rendering")
        log(f"SUCCESS:{view_name}")
        return 0

    # ---- 4. render ---------------------------------------------------------- #
    ok, msg, pdf = RENDERERS[renderer](intermediate, out_dir, f"{stem}.pdf")
    log(f"  RENDER {msg}")
    if not ok:
        log(f"FAILED:{view_name}")
        return 4
    manifest["pdf"] = str(pdf)
    manifest["pdf_bytes"] = pdf.stat().st_size
    manifest["pdf_sha256"] = sha256(pdf)
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
                             encoding="utf-8")
    log(f"  PDF    {pdf}  ({pdf.stat().st_size} bytes)")
    log(f"  EMIT   {manifest_path}")

    # ---- 5. no-regression contract ------------------------------------------ #
    if args.no_verify:
        log("  VERIFY skipped via --no-verify")
        log(f"SUCCESS:{view_name}")
        return 0
    try:
        sys.path.insert(0, str(TOOLS))
        import verify as verify_mod

        # The ORIGINAL profile, not the stripped one: C6 checks that the
        # values build.py held back are genuinely absent from the PDF, and
        # they are no longer present in `selected` to check against.
        vok, findings = verify_mod.verify_pdf(pdf, manifest, profile)
    except Exception as exc:
        log(f"  VERIFY could not run tools/verify.py: {exc!r}")
        log(f"FAILED:{view_name}")
        return 5
    for f in findings:
        log(f"  {f}")
    if not vok:
        log(f"FAILED:{view_name}")
        return 5
    log(f"SUCCESS:{view_name}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="build.py", description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--view", help="named view from x_views (default: 'default')",
                    default="default")
    ap.add_argument("--profile", default=str(DEFAULT_PROFILE))
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--gate", help=f"zerofab gate script (default: {DEFAULT_GATE})")
    ap.add_argument("--theme", choices=KNOWN_THEMES, help="override the view's theme")
    ap.add_argument("--page-budget", metavar="LO-HI",
                    help="override the view's page budget, e.g. 1-2")
    ap.add_argument("--list-views", action="store_true")
    ap.add_argument("--emit-only", action="store_true",
                    help="stop after the intermediate (no render)")
    ap.add_argument("--no-verify", action="store_true",
                    help="skip the no-regression contract (tools/verify.py)")
    ap.add_argument("--skip-gate", action="store_true",
                    help="ENGINE SMOKE-TEST ONLY: bypass the zerofab gate. Output is "
                         "not gate-approved and must never be sent to anyone.")
    ap.add_argument("--all", action="store_true", help="build every view in x_views")
    args = ap.parse_args(argv)

    if args.list_views:
        try:
            profile = load_yaml(Path(args.profile))
        except Exception as exc:
            print(f"  ERROR {exc}")
            print("FAILED:--list-views")
            return 2
        specs = _views_map(profile)
        if not specs:
            print("  (no x_views in this profile — 'default' renders everything)")
        for v, spec in specs.items():
            try:
                resolved = resolve_view(profile, v)
                kind = s(resolved.get("renderer"))
                extra = (f"{kind}, {resolved['locale']}, {resolved['page']}, "
                         f"pages {resolved['page_budget'][0]}-{resolved['page_budget'][-1]}")
            except (KeyError, ValueError) as exc:
                extra = f"UNRESOLVABLE: {exc}"
            note = re.sub(r"\s+", " ", s(spec.get("audience")) or s(spec.get("description")))
            print(f"  {v:<18} [{extra}]  {note[:70]}")
        print("SUCCESS:--list-views")
        return 0

    if args.all:
        try:
            profile = load_yaml(Path(args.profile))
        except Exception as exc:
            print(f"  ERROR {exc}")
            print("FAILED:--all")
            return 2
        views = list_views(profile) or ["default"]
        worst = 0
        for v in views:
            args.view = v
            print(f"--- {v} ---")
            worst = max(worst, build(args))
        print("SUCCESS:--all" if worst == 0 else "FAILED:--all")
        return worst

    return build(args)


if __name__ == "__main__":
    raise SystemExit(main())
