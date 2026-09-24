#!/usr/bin/env python
"""Render the ONE-PAGE RESEARCH PROFILE (deliverable #1).

    C:/Users/prekzursil/.agents/cv/.venv/Scripts/python.exe \
        templates/research-profile/render.py

This EXTENDS cv-studio. It does not replace tools/build.py - it imports it and
reuses the verified components (view resolution, selection, TODO policy, personal
-data stripping, the RenderCV mapping, the zero-fabrication gate, the renderer and
the PDF verifier). The only thing this file owns is SECTION ASSEMBLY: interleaving
the four narrative sections the research profile needs (which build.py has no data
block for) with the data-driven Education / Honors / Languages blocks.

FAIL-CLOSED, in this order. Any single failure stops the render:

  T1 trace        every narrative line names an x_master key that EXISTS in
                  profile.yaml; `trace: TODO-CONFIRM` is the only exemption
  T2 todo shape   a TODO-CONFIRM-traced line must carry the literal marker and
                  must contain NO digits (an unsourced number is the failure mode
                  this whole exercise exists to prevent)
  T3 zerofab      the narrative is written into an augmented copy of profile.yaml
                  and tools/zerofab.py lints THAT - so template prose is gated by
                  the same fail-closed lint as the profile, not exempt from it
  T4 locks        wording_locks.require_present / require_absent, checked against
                  the assembled document text
  T5 verify       tools/verify.py against the rendered PDF, page_budget [1, 1]

Outputs, into ../../out/ :
  Andrei-Mihai_Visalon_research_profile_onepage.rendercv.yaml
  Andrei-Mihai_Visalon_research_profile_onepage.pdf
  Andrei-Mihai_Visalon_research_profile_onepage.md        (fallback rendering)
  Andrei-Mihai_Visalon_research_profile_onepage.manifest.json

The markdown rendering is written BEFORE the PDF is attempted, so a box without a
working Typst still leaves the owner a usable document.
"""

from __future__ import annotations

import argparse
import copy
import json
import re
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent                       # ~/.agents/cv
TOOLS = ROOT / "tools"
OUT = ROOT / "out"
PROFILE = ROOT / "profile.yaml"
TEMPLATE = HERE / "template.yaml"
GATE = TOOLS / "zerofab.py"
STEM = "Andrei-Mihai_Visalon_research_profile_onepage"

sys.path.insert(0, str(TOOLS))
import build as B  # noqa: E402  (sys.path must be set first: cv-studio is not a package)


def log(msg: str) -> None:
    print(msg, flush=True)


def s(v: Any) -> str:
    return B.s(v)


# --------------------------------------------------------------------------- #
# T1 / T2 - the trace contract                                                 #
# --------------------------------------------------------------------------- #
TODO = "TODO-CONFIRM"

# Where the narrative is parked in the augmented profile the gate lints. MUST NOT start
# with "x_" - zerofab's walk_strings skips those. See gate_narrative().
RENDERED_NARRATIVE_KEY = "rendered_narrative"


def check_traces(profile: dict[str, Any], tpl: dict[str, Any]) -> list[str]:
    """Every narrative line must name a real x_master key, or be an explicit TODO."""
    master = profile.get("x_master") or {}
    if not isinstance(master, dict) or not master:
        return ["profile.yaml has no x_master block - nothing to trace narrative against"]

    errs: list[str] = []
    for sec_id, sec in (tpl.get("narrative") or {}).items():
        for i, line in enumerate(sec.get("lines") or []):
            where = f"narrative.{sec_id}.lines[{i}]"
            text = s(line.get("text"))
            trace = s(line.get("trace"))
            if not text:
                errs.append(f"{where}: empty text")
                continue
            if not trace:
                errs.append(f"{where}: no `trace:` - every line must name its source")
                continue
            if trace == TODO:
                # T2. An unsourced line may exist, but it must ADMIT it and must
                # not smuggle a number in.
                if TODO not in text:
                    errs.append(
                        f"{where}: trace is {TODO} but the rendered text does not "
                        f"carry the {TODO} marker - a reader would read it as fact"
                    )
                digits = re.findall(r"\d", text)
                if digits:
                    errs.append(
                        f"{where}: trace is {TODO} but the text contains digits "
                        f"({''.join(digits[:12])}...) - an unsourced number is exactly "
                        f"the failure this gate exists to stop"
                    )
                continue
            if trace not in master:
                near = [k for k in master if trace.split(":")[-1][:12].lower() in k.lower()]
                errs.append(
                    f"{where}: trace {trace!r} is not a key in profile.yaml x_master"
                    + (f" (did you mean {near[0]!r}?)" if near else "")
                )
    return errs


# --------------------------------------------------------------------------- #
# T3 - lint the narrative with the SAME fail-closed gate as the profile        #
# --------------------------------------------------------------------------- #
def gate_narrative(profile: dict[str, Any], tpl: dict[str, Any], out_dir: Path) -> tuple[bool, str]:
    """Lint the narrative with the profile's own fail-closed gate.

    The key name matters and is NOT decorative. zerofab's walk_strings SKIPS every
    `x_`-prefixed key by design - those are the evidence bank, not rendered output.
    A first version of this function parked the narrative under `x_narrative` and the
    lint silently saw nothing: a fabricated "4,821 stars" with no x_metrics entry
    rendered clean. The narrative is RENDERED OUTPUT, so it goes under a plain key and
    is scanned like any other rendered string.
    """
    augmented = copy.deepcopy(profile)
    assert not RENDERED_NARRATIVE_KEY.startswith("x_"), (
        "the narrative key must NOT start with 'x_' or zerofab will skip it"
    )
    augmented[RENDERED_NARRATIVE_KEY] = {
        "headline": s((tpl.get("view") or {}).get("headline")),
        **{sec_id: [s(ln.get("text")) for ln in (sec.get("lines") or [])]
           for sec_id, sec in (tpl.get("narrative") or {}).items()},
    }
    tmp = out_dir / f"{STEM}.gated-profile.yaml"
    B.dump_yaml(augmented, tmp)
    ok, msg = B.run_zerofab_gate(GATE, tmp, "research-profile-onepage", sys.executable)
    return ok, f"{msg}  (narrative-augmented profile: {tmp.name})"


# --------------------------------------------------------------------------- #
# View resolution - template view merged over build.VIEW_DEFAULTS              #
# --------------------------------------------------------------------------- #
def resolve_view(tpl: dict[str, Any]) -> dict[str, Any]:
    view = copy.deepcopy(B.VIEW_DEFAULTS)
    for k, v in (tpl.get("view") or {}).items():
        if isinstance(v, dict) and isinstance(view.get(k), dict):
            view[k] = {**view[k], **v}
        else:
            view[k] = copy.deepcopy(v)
    view["name"] = s((tpl.get("meta") or {}).get("id")) or "research-profile-onepage"
    view["headline"] = re.sub(r"\s+", " ", s(view.get("headline")))
    return view


_YEAR = re.compile(r"^\d{4}$")


def fix_bare_year_dates(doc: dict[str, Any]) -> list[str]:
    """A bare YYYY must not render as 'Jan YYYY'.

    profile.yaml records the Titu Maiorescu BSc as 2022-2025 - years, no months.
    RenderCV's TYPED start_date/end_date fields default a bare year to January, so
    the PDF ends up asserting 'Jan 2022 - Jan 2025', a month nobody verified. Where
    BOTH endpoints are bare years, collapse them into RenderCV's free-text `date`
    field so the document says exactly what the record says.
    """
    notes: list[str] = []
    for entries in (doc["cv"].get("sections") or {}).values():
        for e in entries if isinstance(entries, list) else []:
            if not isinstance(e, dict):
                continue
            start, end = s(e.get("start_date")), s(e.get("end_date"))
            if _YEAR.match(start) and _YEAR.match(end):
                e.pop("start_date", None)
                e.pop("end_date", None)
                e["date"] = start if start == end else f"{start} – {end}"
                notes.append(f"{s(e.get('institution') or e.get('name'))}: {e['date']} "
                             f"(bare years kept as-is; no month invented)")
    return notes


def suppress_networks(doc: dict[str, Any], tpl: dict[str, Any]) -> list[str]:
    rules = tpl.get("suppress_networks") or []
    drop = {s(r.get("network")).lower() for r in rules if s(r.get("network"))}
    if not drop:
        return []
    nets = doc["cv"].get("social_networks") or []
    kept = [n for n in nets if s(n.get("network")).lower() not in drop]
    removed = [s(n.get("network")) for n in nets if s(n.get("network")).lower() in drop]
    if kept:
        doc["cv"]["social_networks"] = kept
    else:
        doc["cv"].pop("social_networks", None)
    return removed


# --------------------------------------------------------------------------- #
# Section assembly - the one thing this template owns                          #
# --------------------------------------------------------------------------- #
def assemble(doc: dict[str, Any], tpl: dict[str, Any], view: dict[str, Any]) -> list[str]:
    """Rebuild cv.sections in `layout` order, interleaving narrative and blocks."""
    titles = {**B.SECTION_TITLES["en"], **(view.get("section_titles") or {})}
    built = doc["cv"].get("sections") or {}
    narrative = tpl.get("narrative") or {}

    ordered: dict[str, Any] = {}
    warns: list[str] = []
    for step in tpl.get("layout") or []:
        if s(step.get("narrative")):
            sec_id = s(step["narrative"])
            sec = narrative.get(sec_id)
            if not sec:
                warns.append(f"layout names narrative {sec_id!r} which template.yaml "
                             f"does not define; skipped (nothing is invented to fill it)")
                continue
            lines = [re.sub(r"\s+", " ", s(ln.get("text")))
                     for ln in (sec.get("lines") or []) if s(ln.get("text"))]
            if lines:
                ordered[s(sec.get("title")) or sec_id.replace("_", " ").title()] = lines
        elif s(step.get("block")):
            block = s(step["block"])
            title = titles.get(block, block.title())
            if title in built:
                ordered[title] = built[title]
            else:
                warns.append(f"layout names block {block!r} but it rendered empty; "
                             f"omitted rather than faked")
    doc["cv"]["sections"] = ordered
    return warns


# --------------------------------------------------------------------------- #
# T4 - wording locks over the assembled document                               #
# --------------------------------------------------------------------------- #
def _doc_text(doc: dict[str, Any]) -> str:
    chunks: list[str] = []

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)
        elif isinstance(node, str):
            chunks.append(node)

    walk(doc.get("cv"))
    return re.sub(r"\s+", " ", " ".join(chunks))


def check_locks(doc: dict[str, Any], tpl: dict[str, Any]) -> list[str]:
    text = _doc_text(doc)
    low = text.lower()
    errs: list[str] = []
    locks = tpl.get("wording_locks") or {}
    for needle in locks.get("require_present") or []:
        if s(needle).lower() not in low:
            errs.append(f"wording lock: required phrase {needle!r} is ABSENT from the document")
    for needle in locks.get("require_absent") or []:
        if s(needle).lower() in low:
            errs.append(f"KILL LIST: forbidden phrase {needle!r} is PRESENT in the document")
    return errs


# --------------------------------------------------------------------------- #
# Markdown rendering - written before the PDF, so there is always a document   #
# --------------------------------------------------------------------------- #
def to_markdown(doc: dict[str, Any], tpl: dict[str, Any], dropped: list[str]) -> str:
    cv = doc["cv"]
    out: list[str] = [f"# {cv.get('name')}", ""]
    if cv.get("headline"):
        out += [f"**{cv['headline']}**", ""]
    contact = [s(cv.get("location")), s(cv.get("email")), s(cv.get("phone"))]
    for n in cv.get("social_networks") or []:
        contact.append(f"{s(n.get('network'))}: {s(n.get('username'))}")
    out += [" · ".join(c for c in contact if c), ""]
    out += ["*One-page research profile. This is not a CV and must not be sent as one.*", ""]

    for title, entries in (cv.get("sections") or {}).items():
        out += [f"## {title}", ""]
        for e in entries:
            if isinstance(e, str):
                out += [f"- {e}", ""]
            elif isinstance(e, dict) and e.get("bullet"):
                out += [f"- {e['bullet']}", ""]
            elif isinstance(e, dict) and e.get("institution"):
                dates = s(e.get("date")) or " – ".join(
                    x for x in (s(e.get("start_date")), s(e.get("end_date"))) if x)
                head = ", ".join(x for x in (s(e.get("degree")), s(e.get("area"))) if x)
                out += [f"- **{e['institution']}** — {head} ({dates})", ""]
            elif isinstance(e, dict) and e.get("label"):
                out += [f"- **{e['label']}**: {s(e.get('details'))}", ""]
            else:
                out += [f"- {json.dumps(e, ensure_ascii=False)}", ""]

    if dropped:
        note = (f"*Suppressed contact link(s): {', '.join(dropped)}. See template.yaml "
                f"`suppress_networks` for why and for the unblock condition.*")
        out += ["---", "", note, ""]
    return "\n".join(out)


# --------------------------------------------------------------------------- #
# Driver                                                                       #
# --------------------------------------------------------------------------- #
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--profile", default=str(PROFILE))
    ap.add_argument("--template", default=str(TEMPLATE))
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--emit-only", action="store_true",
                    help="stop after the intermediate + markdown; do not call rendercv")
    args = ap.parse_args(argv)

    profile_path = Path(args.profile).resolve()
    tpl_path = Path(args.template).resolve()
    out_dir = Path(args.out).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    log(f"  TEMPLATE {tpl_path}")
    log(f"  PROFILE  {profile_path}")
    for p in (profile_path, tpl_path):
        if not p.exists():
            log(f"  ERROR not found: {p}")
            log(f"FAILED:{STEM}")
            return 2

    profile = B.load_yaml(profile_path)
    tpl = B.load_yaml(tpl_path)
    view = resolve_view(tpl)
    log(f"  VIEW     {view['name']}  theme={view['theme']} page={view['page']} "
        f"budget={view['page_budget']} parsed={view['parsed']}")

    # ---- T1 / T2 -------------------------------------------------------- #
    errs = check_traces(profile, tpl)
    for e in errs:
        log(f"  ERROR T1/T2 {e}")
    if errs:
        log("  NOTE   every narrative line must trace to profile.yaml x_master, or "
            "declare trace: TODO-CONFIRM and carry the marker with no digits.")
        log(f"FAILED:{STEM}")
        return 2
    n_lines = sum(len(sec.get("lines") or []) for sec in (tpl.get("narrative") or {}).values())
    n_todo = sum(1 for sec in (tpl.get("narrative") or {}).values()
                 for ln in (sec.get("lines") or []) if s(ln.get("trace")) == TODO)
    log(f"  TRACE    {n_lines} narrative line(s) traced; {n_todo} declared {TODO}")

    # ---- T3 -------------------------------------------------------------- #
    ok, msg = gate_narrative(profile, tpl, out_dir)
    log(f"  GATE     {msg}")
    if not ok:
        log(f"FAILED:{STEM}")
        return 3

    # ---- build the document ---------------------------------------------- #
    selected = B.apply_selection(profile, view)
    selected, todo_hits = B.apply_todo_policy(selected, s(view.get("todo_policy")) or "annotate")
    removed_personal: list[str] = []
    if view.get("parsed"):
        selected, removed_personal = B.strip_personal_data(selected)
        if removed_personal:
            log(f"  PRIVACY  stripped: {', '.join(sorted(set(removed_personal))[:8])}")

    doc, warns = B.profile_to_rendercv(selected, view)
    for w in warns:
        log(f"  WARN     {w}")
    dropped = suppress_networks(doc, tpl)
    for net in dropped:
        log(f"  SUPPRESS {net} link withheld - see template.yaml suppress_networks")
    for n in fix_bare_year_dates(doc):
        log(f"  DATES    {n}")
    for w in assemble(doc, tpl, view):
        log(f"  WARN     {w}")
    log(f"  SECTIONS {' | '.join(doc['cv'].get('sections') or {})}")

    # ---- T4 -------------------------------------------------------------- #
    lock_errs = check_locks(doc, tpl)
    for e in lock_errs:
        log(f"  ERROR T4 {e}")
    if lock_errs:
        log(f"FAILED:{STEM}")
        return 2
    log(f"  LOCKS    {len((tpl.get('wording_locks') or {}).get('require_present') or [])} "
        f"required phrase(s) present, "
        f"{len((tpl.get('wording_locks') or {}).get('require_absent') or [])} "
        f"kill-list phrase(s) absent")

    # ---- emit -------------------------------------------------------------- #
    intermediate = out_dir / f"{STEM}.rendercv.yaml"
    B.dump_yaml(doc, intermediate)
    log(f"  EMIT     {intermediate}  ({intermediate.stat().st_size} bytes)")

    md_path = out_dir / f"{STEM}.md"
    md_path.write_text(to_markdown(doc, tpl, dropped), encoding="utf-8")
    log(f"  EMIT     {md_path}  ({md_path.stat().st_size} bytes)")

    manifest: dict[str, Any] = {
        "template": str(tpl_path),
        "view": view["name"],
        "renderer": "rendercv",
        "theme": view["theme"],
        "locale": view["locale"],
        "page": view["page"],
        "parsed": bool(view.get("parsed")),
        "page_budget": list(view.get("page_budget") or [1, 1]),
        "sections": list(doc["cv"].get("sections") or {}),
        "name": s((selected.get("basics") or {}).get("name")),
        "employers": [],                       # this view renders no Experience block
        "institutions": [s(e.get("institution")) for e in (selected.get("education") or [])],
        "personal_fields_stripped": sorted(set(removed_personal)),
        "networks_suppressed": dropped,
        "todo_markers": todo_hits,
        "narrative_lines": n_lines,
        "narrative_todo_lines": n_todo,
        "profile": str(profile_path),
        "profile_sha256": B.sha256(profile_path),
        "template_sha256": B.sha256(tpl_path),
        "intermediate": str(intermediate),
        "markdown": str(md_path),
        "gate_skipped": False,
    }
    manifest_path = out_dir / f"{STEM}.manifest.json"

    if args.emit_only:
        manifest["pdf"] = None
        manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
                                 encoding="utf-8")
        log(f"  EMIT     {manifest_path}")
        log("  NOTE     --emit-only: stopped before rendercv")
        log(f"SUCCESS:{STEM}")
        return 0

    # ---- render ------------------------------------------------------------ #
    ok, msg, pdf = B.render_rendercv(intermediate, out_dir, f"{STEM}.pdf")
    log(f"  RENDER   {msg}")
    if not ok:
        log(f"  NOTE     markdown rendering is on disk at {md_path} - the owner has a "
            f"usable document even with the PDF engine down.")
        log(f"FAILED:{STEM}")
        return 4
    manifest["pdf"] = str(pdf)
    manifest["pdf_bytes"] = pdf.stat().st_size
    manifest["pdf_sha256"] = B.sha256(pdf)
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
                             encoding="utf-8")
    log(f"  PDF      {pdf}  ({pdf.stat().st_size} bytes)")
    log(f"  EMIT     {manifest_path}")

    # ---- T5 ---------------------------------------------------------------- #
    try:
        import verify as V
        vok, findings = V.verify_pdf(pdf, manifest, profile)
    except Exception as exc:                                   # pragma: no cover
        log(f"  VERIFY   could not run tools/verify.py: {exc!r}")
        log(f"FAILED:{STEM}")
        return 5
    for f in findings:
        log(f"  {f}")
    if not vok:
        log(f"FAILED:{STEM}")
        return 5
    log(f"SUCCESS:{STEM}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
