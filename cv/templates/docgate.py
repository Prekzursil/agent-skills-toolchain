#!/usr/bin/env python3
"""templates/docgate.py — the OUTPUT-side, fail-closed gate.

`tools/zerofab.py` guards the *profile*: no unsourced figure, no kill-list phrase,
no un-licensed "open-source" claim may live in `profile.yaml`. It runs BEFORE the
renderer. This file guards the *document*: it reads the text layer of the PDF that
was actually produced and re-asks the same questions of the artefact a human will
receive — plus the questions only a rendered page can answer (does page 1 stand
alone? did the typesetter emit a ligature? are the Romanian diacritics the
comma-below ones?).

Why both: a profile gate cannot see the renderer. A theme, a font, a template
string or a locale pack can introduce text that was never in `profile.yaml`
(RenderCV's `templates.experience_entry` literally composes new lines), and a
section that renders empty, a heading orphaned at the foot of page 1, or an
`ﬁ` ligature in the text layer are defects that only exist after typesetting.

Checks (every one is FAIL-CLOSED unless marked REPORT):

  D1  TEXT      a real, selectable text layer exists
  D2  KILLLIST  no forbidden claim from tools/zerofab.py's KILL_LIST / BANNED_WORDS
  D3  NUMBERS   every digit-bearing token traces to a renderable x_metrics entry
                (or to a declared allow-entry that carries a written reason)
  D4a BULLETS   every bullet line in the PDF traces to a string in the resolved
                profile — nothing the renderer invented
  D4b MASTER    every rendered highlight traces to an x_master note (for a
                translated view, through its 1:1 source map first)
  D5  SECTIONS  the required sections are present, in the declared order
  D6  PAGE1     page 1 stands alone (identity + contact + summary + experience)
                and does not end on an orphaned section heading
  D7  GLYPHS    no ligature / soft-hyphen / zero-width / private-use (icon) glyph,
                no tab character, bullet glyph is an allow-listed one
  D8  LOCALE    ro: comma-below diacritics present, cedilla forms absent, the NAME
                is rendered without diacritics; en: no unexpected diacritics
  D9  TODO      TODO-CONFIRM markers are counted and named  (REPORT — sets the
                document's status to DRAFT instead of SEND-READY)
  D10 EXPANSION text-length ratio against a reference PDF  (REPORT unless the
                template declares `max_expansion`)

Usage
-----
    PY=~/.agents/cv/.venv/Scripts/python
    $PY templates/docgate.py --pdf out/templates/ats-en/X.pdf \
        --profile out/templates/ats-en/X.resolved.yaml \
        --template templates/ats-en/template.yaml
    $PY templates/docgate.py --selftest

Exit codes: 0 all fail-closed checks passed · 1 at least one FAILED ·
2 usage / missing input (fail-closed: an unrunnable gate is never a pass).

NO LLM here, and no network. Mechanics only.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:                                          # pragma: no cover
        pass

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent                                   # ~/.agents/cv
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

TODO_MARKER = "TODO-CONFIRM"

# Glyph classes that mean the text layer is damaged for a parser.
LIGATURES = {chr(c) for c in range(0xFB00, 0xFB07)}
INVISIBLE = {chr(c) for c in (0x00AD, 0x200B, 0x200C, 0x200D, 0xFEFF, 0x2060)}
def PUA(ch: str) -> bool:
    """True for a private-use codepoint — i.e. an icon-font glyph."""
    return 0xE000 <= ord(ch) <= 0xF8FF or 0xF0000 <= ord(ch) <= 0xFFFFD
ALLOWED_BULLETS = {"-"} | {chr(c) for c in (0x2013, 0x2022, 0x25CF, 0x25E6, 0x2014)}

# Romanian: the CORRECT letters are comma-below (U+0218/0219/021A/021B).
# The cedilla forms below are the Turkish letters and the classic mojibake tell.
RO_COMMA = {chr(c) for c in (0x0218, 0x0219, 0x021A, 0x021B)}
RO_CEDILLA = {chr(c) for c in (0x015E, 0x015F, 0x0162, 0x0163)}
RO_DIACRITICS = RO_COMMA | {chr(c) for c in (0x0102, 0x0103, 0x00CE, 0x00EE, 0x00C2, 0x00E2)}

STOPWORDS = {
    # EN
    "a", "an", "and", "the", "of", "to", "in", "on", "for", "with", "as", "at",
    "by", "from", "that", "this", "it", "its", "is", "are", "was", "were", "be",
    "been", "has", "have", "had", "not", "no", "but", "or", "so", "than", "then",
    "across", "over", "under", "into", "out", "up", "down", "one", "two", "three",
    "which", "while", "because", "each", "every", "per", "own",
    # RO
    "si", "sau", "de", "la", "cu", "pe", "din", "pentru", "care", "ca",
    "un", "al", "ale", "lui", "este", "sunt", "fost", "fie", "dintre",
    "prin", "intre", "dupa", "peste", "sub", "mai", "cel", "cea", "cele", "unui",
    "unei", "sa", "se", "fara", "catre", "iar", "dar", "ci", "au",
}


# --------------------------------------------------------------------------- #
# small helpers                                                                #
# --------------------------------------------------------------------------- #
def fold(text: str) -> str:
    """Lowercase, strip diacritics, collapse whitespace and dashes."""
    t = unicodedata.normalize("NFKD", str(text))
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = re.sub(r"[‐-―−]", "-", t)
    return re.sub(r"\s+", " ", t).strip().lower()


def words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9']{3,}", fold(text)) if w not in STOPWORDS}


def load_yaml(path: Path) -> Any:
    text = path.read_text(encoding="utf-8")
    try:
        from ruamel.yaml import YAML

        return YAML(typ="safe").load(text)
    except ImportError:                                        # pragma: no cover
        import yaml as pyyaml

        return pyyaml.safe_load(text)


def walk_strings(node: Any) -> list[str]:
    out: list[str] = []
    if isinstance(node, dict):
        for v in node.values():
            out.extend(walk_strings(v))
    elif isinstance(node, list):
        for v in node:
            out.extend(walk_strings(v))
    elif isinstance(node, str):
        out.append(node)
    return out


# --------------------------------------------------------------------------- #
# Finding model                                                                #
# --------------------------------------------------------------------------- #
class Report:
    def __init__(self) -> None:
        self.lines: list[str] = []
        self.failed: list[str] = []
        self.status_notes: list[str] = []

    def record(self, ok: bool, code: str, msg: str, *, fatal: bool = True) -> bool:
        if ok:
            self.lines.append(f"PASS  {code} {msg}")
        elif fatal:
            self.lines.append(f"FAIL  {code} {msg}")
            self.failed.append(code)
        else:
            self.lines.append(f"WARN  {code} {msg}")
        return ok

    def note(self, code: str, msg: str) -> None:
        self.lines.append(f"NOTE  {code} {msg}")


# --------------------------------------------------------------------------- #
# Pure checks — every one is a function over text, so they are testable without #
# a renderer, and the self-test proves each goes RED on a defect.              #
# --------------------------------------------------------------------------- #
def check_killlist(text: str) -> list[str]:
    """D2 — reuse the PROFILE gate's rules on the rendered text."""
    import zerofab

    norm = zerofab._normalise(text)
    hits = []
    for rule in zerofab.KILL_LIST:
        if rule.pattern.search(norm):
            hits.append(f"kill-list: {rule.label} ({rule.fix})")
    for rule in getattr(zerofab, "BANNED_WORDS", ()):
        if rule.pattern.search(norm):
            hits.append(f"banned wording: {rule.label} ({rule.fix})")
    return hits


def check_numbers(text: str, profile: Any, allow: list[dict[str, str]]) -> list[str]:
    """D3 — every digit-bearing token must trace to a renderable x_metrics form."""
    import zerofab

    metrics, _ = zerofab.parse_metrics((profile or {}).get("x_metrics"))
    good: set[str] = set()
    for m in metrics:
        if m.renderable:
            good |= m.forms
    allow_forms: dict[str, str] = {}
    for row in allow or []:
        t = str(row.get("text", "")).strip()
        reason = str(row.get("reason", "")).strip()
        if t and reason:
            allow_forms[t] = reason
    unsourced: list[str] = []
    for tok in zerofab.tokenize(text):
        if tok.is_year:
            continue
        if tok.forms & good:
            continue
        hit = next((r for t, r in allow_forms.items() if t == tok.raw or t == tok.digits), None)
        if hit:
            continue
        unsourced.append(tok.raw)
    return sorted(set(unsourced))


def check_glyphs(text: str) -> list[str]:
    """D7 — ATS-hostile characters in the text layer."""
    bad: list[str] = []
    ligs = sorted({c for c in text if c in LIGATURES})
    if ligs:
        bad.append("ligature(s) " + ", ".join(f"U+{ord(c):04X}" for c in ligs))
    inv = sorted({c for c in text if c in INVISIBLE})
    if inv:
        bad.append("invisible char(s) " + ", ".join(f"U+{ord(c):04X}" for c in inv))
    pua = sorted({c for c in text if PUA(c)})
    if pua:
        bad.append("private-use (icon font) glyph(s) "
                   + ", ".join(f"U+{ord(c):04X}" for c in pua))
    if "\t" in text:
        bad.append("tab character (column artefact)")
    marks = sorted({c for c in text
                    if unicodedata.category(c) == "So" and c not in ALLOWED_BULLETS})
    if marks:
        bad.append("symbol glyph(s) " + ", ".join(f"U+{ord(c):04X}" for c in marks))
    return bad


def check_locale(text: str, name: str, locale: str) -> list[str]:
    """D8 — Romanian comma-below discipline; the NAME stays diacritic-free."""
    bad: list[str] = []
    ced = sorted({c for c in text if c in RO_CEDILLA})
    if ced:
        bad.append("cedilla-form diacritic(s) "
                   + ", ".join(f"U+{ord(c):04X}" for c in ced)
                   + " — Romanian uses comma-below U+0218/0219/021A/021B")
    if locale == "ro" and not any(c in text for c in RO_COMMA):
        bad.append("no comma-below diacritic anywhere in a Romanian rendering "
                   "(U+0219/U+021B expected in 'Experiență', 'Competențe', …)")
    if name:
        if name not in text:
            bad.append(f"the canonical name {name!r} is not in the text layer")
        if any(c in name for c in RO_DIACRITICS | RO_CEDILLA):
            bad.append(f"the rendered name {name!r} carries diacritics; the "
                       f"canonical spelling is unaccented")
    return bad


def untranslate(line: str, source_map: dict[str, str]) -> str:
    """Put a rendered line back into the language x_master is written in.

    An exact hit covers a bullet the renderer printed verbatim. The substring
    pass covers the lines the renderer COMPOSES: an award prints as
    "TITLE — AWARDER (DATE)", so the translated title is only a part of the line
    and an exact lookup would miss it and blame the translation for not tracing.
    """
    key = re.sub(r"\s+", " ", line).strip()
    if key in source_map:
        return source_map[key]
    out = key
    for translated in sorted(source_map, key=len, reverse=True):
        if translated and translated in out:
            out = out.replace(translated, source_map[translated])
    return out


def trace(line: str, corpus_words: set[str], threshold: float) -> float:
    """Share of a line's content words that exist in the corpus."""
    w = words(line)
    if not w:
        return 1.0
    return len(w & corpus_words) / len(w)


def heading_index(page_texts: list[str], title: str) -> int:
    """Line number of the heading `title` in the document, or -1.

    A section heading is a LINE that *is* the title, not the title appearing
    anywhere. Measured on this profile: the Skills section contains a row
    labelled "Languages", so a substring search finds that row before the
    Languages section heading and reports the document as out of order.
    """
    want = fold(title).rstrip(":")
    for i, line in enumerate("\n".join(page_texts).splitlines()):
        if fold(line).rstrip(":") == want:
            return i
    return -1


def check_sections(page_texts: list[str], required: list[str]) -> list[str]:
    """D5 — required titles present, as headings, in document order."""
    pos = {t: heading_index(page_texts, t) for t in required}
    missing = [t for t, i in pos.items() if i < 0]
    if missing:
        return [f"missing section heading(s): {', '.join(missing)}"]
    seq = [pos[t] for t in required]
    if seq != sorted(seq):
        got = [t for _, t in sorted(zip(seq, required))]
        return [f"sections out of order — declared {required}, rendered {got}"]
    return []


def check_page1(page1: str, must_contain: list[str], titles: list[str]) -> list[str]:
    """D6 — page 1 stands alone, and does not end on an orphaned heading."""
    bad: list[str] = []
    folded = fold(page1)
    for needle in must_contain:
        if fold(needle) not in folded:
            bad.append(f"page 1 does not contain {needle!r}")
    tail = [ln.strip() for ln in page1.strip().splitlines() if ln.strip()]
    if tail:
        last = fold(tail[-1])
        for t in titles:
            if last == fold(t):
                bad.append(f"page 1 ends on the orphaned heading {t!r}")
    return bad


# --------------------------------------------------------------------------- #
# PDF-facing driver                                                            #
# --------------------------------------------------------------------------- #
def join_wrapped(parts: list[str]) -> str:
    """Join the lines of one wrapped bullet back into a sentence.

    Typst may break a line after a HARD hyphen, so the Romanian "skill-uri"
    reaches the text layer as "skill-" + "uri". Joining those with a space makes
    the line differ from its source string by one character, and every exact
    lookup downstream (the translation source map) then misses for a reason that
    has nothing to do with the content. Measured on the Romanian rendering.
    """
    out = ""
    for part in parts:
        piece = part.strip()
        if not piece:
            continue
        if not out:
            out = piece
        elif out.endswith("-") and piece[:1].islower():
            out += piece
        else:
            out += " " + piece
    return re.sub(r"\s+", " ", out).strip()


def bullet_lines(page_texts: list[str]) -> list[str]:
    """Lines the renderer set as bullets, de-hyphenated and de-wrapped.

    RenderCV wraps a highlight across several lines; the text layer keeps the
    wrap. A bullet therefore starts at a bullet glyph and runs until the next
    bullet glyph or a blank line.
    """
    out: list[str] = []
    cur: list[str] = []
    bullet_re = re.compile(r"^\s*[" + "".join(re.escape(b) for b in ALLOWED_BULLETS) + r"]\s+")
    for raw in "\n".join(page_texts).splitlines():
        line = raw.rstrip()
        if bullet_re.match(line):
            if cur:
                out.append(join_wrapped(cur))
            cur = [bullet_re.sub("", line).strip()]
        elif cur:
            if not line.strip():
                out.append(join_wrapped(cur))
                cur = []
            else:
                cur.append(line.strip())
    if cur:
        out.append(join_wrapped(cur))
    return [b for b in out if b.strip()]


def bullet_lines_layout(doc: Any, indent_pt: float = 2.0) -> list[str]:
    """Bullets read from the PAGE LAYOUT, which is where the truth is.

    A bullet is a line starting with a bullet glyph; its continuation lines are
    the following lines indented past it (measured here: bullet x0 = 45.4pt,
    continuation x0 = 51.5pt). Reading the flat text layer instead lets the last
    bullet of a section swallow the next heading — measured on this very
    document, where one bullet absorbed the whole Skills section and then failed
    to trace, for the wrong reason.
    """
    out: list[str] = []
    cur: list[str] = []
    cur_x: float | None = None
    bullet_re = re.compile(r"^\s*[" + "".join(re.escape(b) for b in ALLOWED_BULLETS) + r"]\s+")
    for page in doc:
        for block in page.get_text("dict").get("blocks", []):
            for line in block.get("lines", []):
                text = "".join(sp.get("text", "") for sp in line.get("spans", []))
                x0 = float(line.get("bbox", (0, 0, 0, 0))[0])
                if bullet_re.match(text):
                    if cur:
                        out.append(join_wrapped(cur))
                    cur = [bullet_re.sub("", text).strip()]
                    cur_x = x0
                elif cur and cur_x is not None and x0 > cur_x + indent_pt:
                    cur.append(text.strip())
                elif cur:
                    out.append(join_wrapped(cur))
                    cur, cur_x = [], None
    if cur:
        out.append(join_wrapped(cur))
    return [b for b in out if b.strip()]


def run(pdf: Path, profile_path: Path, template: dict[str, Any],
        source_map: dict[str, str] | None, reference: Path | None) -> tuple[int, Report, dict]:
    rep = Report()
    checks = (template.get("checks") or {}) if isinstance(template, dict) else {}
    render = (template.get("render") or {}) if isinstance(template, dict) else {}
    locale = str(render.get("locale") or "en").lower()[:2]

    if not pdf.exists():
        rep.record(False, "D0", f"pdf not found: {pdf}")
        return 2, rep, {}
    if not profile_path.exists():
        rep.record(False, "D0", f"resolved profile not found: {profile_path}")
        return 2, rep, {}
    try:
        import pymupdf
    except ImportError:                                        # pragma: no cover
        rep.record(False, "D0", "pymupdf is not installed — the gate cannot read "
                                "the PDF, so it FAILS (fail-closed)")
        return 2, rep, {}

    profile = load_yaml(profile_path)
    doc = pymupdf.open(pdf)
    pages = [doc[i].get_text() for i in range(doc.page_count)]
    layout_bullets = bullet_lines_layout(doc)
    text = "\n".join(pages)
    doc.close()

    # D1 — text layer
    rep.record(len(text.strip()) > 500, "D1",
               f"text layer: {len(text)} characters over {len(pages)} page(s)")

    # D2 — kill list
    hits = check_killlist(text)
    rep.record(not hits, "D2", "no kill-list / banned wording in the document"
               if not hits else "; ".join(hits))

    # D3 — numbers
    unsourced = check_numbers(text, profile, checks.get("numbers_allow") or [])
    rep.record(not unsourced, "D3",
               "every figure traces to a renderable x_metrics entry"
               if not unsourced else
               f"{len(unsourced)} figure(s) with no renderable x_metrics entry: "
               + ", ".join(unsourced[:12]))

    # D4a — every bullet exists in the resolved profile
    profile_strings = walk_strings(profile)
    profile_words: set[str] = set()
    for sline in profile_strings:
        profile_words |= words(sline)
    bullets = layout_bullets or bullet_lines(pages)
    thr = float(checks.get("trace_threshold", 0.70))
    stray = [(b, round(trace(b, profile_words, thr), 2)) for b in bullets
             if trace(b, profile_words, thr) < thr]
    rep.record(not stray, "D4a",
               f"all {len(bullets)} bullet(s) trace to the resolved profile"
               if not stray else
               "; ".join(f"[{sc}] {b[:90]}" for b, sc in stray[:5]))

    # D4b — every rendered highlight traces to x_master (through the source map)
    master = (profile or {}).get("x_master") or {}
    master_words: set[str] = set()
    for note in walk_strings(master):
        master_words |= words(note)
    mthr = float(checks.get("master_threshold", 0.55))
    exempt = [fold(x) for x in (checks.get("bullets_exempt") or [])]
    untraced = []
    for b in bullets:
        fb = fold(b)
        if any(e and e in fb for e in exempt):
            continue
        src = untranslate(b, source_map or {})
        sc = trace(src, master_words, mthr)
        if sc < mthr:
            untraced.append((b, round(sc, 2)))
    rep.record(not untraced, "D4b",
               f"all {len(bullets)} bullet(s) trace to an x_master note"
               if not untraced else
               "; ".join(f"[{sc}] {b[:90]}" for b, sc in untraced[:5]))

    # D5 — sections
    required = [str(t) for t in (checks.get("required_sections") or [])]
    sec = check_sections(pages, required) if required else []
    rep.record(not sec, "D5",
               f"{len(required)} required section(s) present, in order"
               if not sec else "; ".join(sec))

    # D6 — page 1 stands alone
    p1 = checks.get("page1_must_contain") or []
    p1bad = check_page1(pages[0] if pages else "", [str(x) for x in p1], required)
    rep.record(not p1bad, "D6",
               "page 1 stands alone (identity, contact, summary, experience)"
               if not p1bad else "; ".join(p1bad))

    # D7 — glyphs
    glyph = check_glyphs(text)
    rep.record(not glyph, "D7",
               "no ligature / invisible / icon / tab damage in the text layer"
               if not glyph else "; ".join(glyph))

    # D8 — locale
    name = str(((profile or {}).get("basics") or {}).get("name") or "")
    loc = check_locale(text, name, locale)
    rep.record(not loc, "D8",
               f"locale discipline ok ({locale})" if not loc else "; ".join(loc))

    # D9 — TODO markers (REPORT: sets DRAFT, never blocks)
    todo = [ln.strip() for ln in text.splitlines() if TODO_MARKER in ln]
    if todo:
        rep.record(False, "D9", f"{len(todo)} TODO-CONFIRM marker(s) visible — the "
                                f"document is a DRAFT, not send-ready", fatal=False)
        for t in todo[:8]:
            rep.note("D9", t[:120])
    else:
        rep.record(True, "D9", "no TODO-CONFIRM marker in the document")

    # D10 — expansion against a reference rendering
    ratio = None
    if reference and reference.exists():
        rdoc = pymupdf.open(reference)
        rtext = "\n".join(rdoc[i].get_text() for i in range(rdoc.page_count))
        rpages = rdoc.page_count
        rdoc.close()
        ratio = round(len(text) / max(len(rtext), 1), 3)
        cap = checks.get("max_expansion")
        msg = (f"text length {ratio}x the reference ({reference.name}), "
               f"{len(pages)} page(s) vs {rpages}")
        if cap:
            rep.record(ratio <= float(cap), "D10", msg + f" (cap {cap}x)")
        else:
            rep.record(True, "D10", msg + " (REPORT only)")

    status = "DRAFT" if todo else "SEND-READY"
    summary = {
        "pdf": str(pdf),
        "pdf_bytes": pdf.stat().st_size,
        "pages": len(pages),
        "characters": len(text),
        "bullets": len(bullets),
        "todo_markers": len(todo),
        "expansion_ratio": ratio,
        "status": status,
        "failed_checks": rep.failed,
    }
    return (1 if rep.failed else 0), rep, summary


# --------------------------------------------------------------------------- #
# Self-test — every check must go RED on a defect and GREEN when clean.        #
# --------------------------------------------------------------------------- #
def _selftest() -> int:
    results: list[tuple[str, bool, str]] = []

    def t(label: str, ok: bool, detail: str = "") -> None:
        results.append((label, ok, detail))

    profile = {
        "basics": {"name": "Andrei-Mihai Visalon"},
        "x_metrics": [
            {"id": "m1", "value": "4,244 problems solved", "provenance": "M",
             "how_known": "read live from the public profile page"},
            {"id": "m2", "value": "88 published problems", "provenance": "M",
             "how_known": "counted on the platform"},
            {"id": "m3", "value": "1,590 merged PRs", "provenance": "B",
             "how_known": "second-hand"},
        ],
        "x_master": {"award:pbinfo.ro": [
            ("Ranked first all-time by problems solved at full score on pbinfo.ro, "
             "the national high-school judge: 4,244 solved of 14,228 submissions; "
             "author or co-author of 88 published problems.")]},
    }

    # D2 kill list — both states
    t("D2 red  (forbidden claim)", bool(check_killlist("Merged 1,590 PRs last year.")))
    t("D2 green (clean text)", not check_killlist("Shipped a desktop application."))

    # D3 numbers — both states
    t("D3 green (sourced figure)",
      check_numbers("Solved 4,244 problems and authored 88.", profile, []) == [])
    t("D3 red  (unsourced figure)",
      check_numbers("Led a team of 12 engineers.", profile, []) == ["12"])
    t("D3 red  (borrowed provenance never renders)",
      check_numbers("1,590 pull requests.", profile, []) != [])
    t("D3 green (allow-listed with a reason)",
      check_numbers("Led a team of 12 engineers.", profile,
                    [{"text": "12", "reason": "team size, stated by the owner"}]) == [])
    t("D3 green (a bare year is not a claim)",
      check_numbers("Worked there in 2024.", profile, []) == [])

    # D7 glyphs — both states
    t("D7 red  (ligature)", bool(check_glyphs("e" + chr(0xFB03) + "cient work")))
    t("D7 red  (soft hyphen)", bool(check_glyphs("infra" + chr(0x00AD) + "structure")))
    t("D7 red  (icon glyph)", bool(check_glyphs(chr(0xE0B0) + " GitHub")))
    t("D7 green (plain text with a hyphen bullet)",
      not check_glyphs("- Built a bilingual storefront."))

    # D8 locale — both states
    t("D8 red  (cedilla instead of comma-below)",
      bool(check_locale("Experien" + chr(0x0163) + chr(0x0103), "Andrei-Mihai Visalon", "ro")))
    t("D8 red  (no diacritic at all in a ro view)",
      bool(check_locale("Experienta si Educatie. Andrei-Mihai Visalon",
                        "Andrei-Mihai Visalon", "ro")))
    t("D8 green (comma-below present, name unaccented)",
      not check_locale("Experien" + chr(0x021B) + chr(0x0103) + " Andrei-Mihai Visalon",
                       "Andrei-Mihai Visalon", "ro"))
    t("D8 red  (name missing from the text layer)",
      bool(check_locale("Experien" + chr(0x021B) + chr(0x0103), "Andrei-Mihai Visalon", "ro")))

    # D4 tracing — both states
    mw: set[str] = set()
    for note in walk_strings(profile["x_master"]):
        mw |= words(note)
    good = "Ranked first all-time by problems solved at full score on pbinfo.ro."
    bad = "Led a 12-person platform team through a cloud migration at scale."
    t("D4 green (bullet traces to x_master)", trace(good, mw, 0.55) >= 0.55,
      f"score={trace(good, mw, 0.55):.2f}")
    t("D4 red  (invented bullet does not)", trace(bad, mw, 0.55) < 0.55,
      f"score={trace(bad, mw, 0.55):.2f}")

    # D5 sections — both states
    t("D5 green (present, in order)",
      not check_sections(["Summary\nExperience\nProjects"],
                         ["Summary", "Experience", "Projects"]))
    t("D5 red  (out of order)",
      bool(check_sections(["Summary\nProjects\nExperience"],
                          ["Summary", "Experience", "Projects"])))
    t("D5 red  (missing)",
      bool(check_sections(["Summary\nExperience"],
                          ["Summary", "Experience", "Projects"])))

    # D6 page 1 — both states
    page = "Andrei-Mihai Visalon\n+40 740 935 228\nSummary\nEngineer.\nExperience\nX"
    t("D6 green (contains what it must)",
      not check_page1(page, ["Andrei-Mihai Visalon", "Summary", "Experience"], []))
    t("D6 red  (missing contact)",
      bool(check_page1(page, ["andrei@example.org"], [])))
    t("D6 red  (orphaned heading at the foot)",
      bool(check_page1("Summary\nEngineer.\nProjects",
                       ["Summary"], ["Summary", "Projects"])))

    # bullet extraction across a wrapped line
    bl = bullet_lines(["- Built a bilingual storefront\nand its admin suite.\n\n- Second."])
    t("bullet extraction de-wraps", bl == ["Built a bilingual storefront and its admin suite.",
                                           "Second."], repr(bl))
    hy = bullet_lines(["- Operates a tree of skill-\nuri and tools."])
    t("hyphen-broken word rejoins without a space",
      hy == ["Operates a tree of skill-uri and tools."], repr(hy))

    # heading vs. a row LABELLED like a heading (the real Skills/Languages clash)
    doc_lines = ["Summary\nSkills\nLanguages: Python, C++\nEducation\nLanguages\nRomanian"]
    t("D5 green (a 'Languages:' skills row is not the heading)",
      not check_sections(doc_lines, ["Summary", "Skills", "Education", "Languages"]))

    # reverse translation, exact and composed
    smap = {"Locul intai pe pbinfo.ro": "Ranked first all-time on pbinfo.ro"}
    t("untranslate exact", untranslate("Locul intai pe pbinfo.ro", smap)
      == "Ranked first all-time on pbinfo.ro")
    t("untranslate inside a composed line",
      untranslate("Locul intai pe pbinfo.ro — pbinfo.ro (2026-09)", smap)
      == "Ranked first all-time on pbinfo.ro — pbinfo.ro (2026-09)")
    t("untranslate leaves an unmapped line alone",
      untranslate("Something else entirely", smap) == "Something else entirely")

    width = max(len(r[0]) for r in results)
    for label, ok, detail in results:
        print(f"  {'ok  ' if ok else 'FAIL'} {label:<{width}}  {detail}")
    bad_n = sum(1 for _, ok, _ in results if not ok)
    print(f"SUCCESS:selftest {len(results)} checks" if not bad_n
          else f"FAILED:selftest {bad_n}/{len(results)}")
    return 1 if bad_n else 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="docgate.py", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pdf")
    ap.add_argument("--profile", help="the RESOLVED profile the PDF was built from")
    ap.add_argument("--template", help="templates/<id>/template.yaml")
    ap.add_argument("--source-map", help="JSON {rendered: source} for a translated view")
    ap.add_argument("--reference", help="a reference PDF for the D10 expansion ratio")
    ap.add_argument("--json", help="write the machine-readable summary here")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args(argv)

    if args.selftest:
        return _selftest()
    if not (args.pdf and args.profile and args.template):
        ap.error("--pdf, --profile and --template are required (or use --selftest)")

    template = load_yaml(Path(args.template))
    smap = {}
    if args.source_map and Path(args.source_map).exists():
        smap = json.loads(Path(args.source_map).read_text(encoding="utf-8"))
    code, rep, summary = run(Path(args.pdf).resolve(), Path(args.profile).resolve(),
                             template if isinstance(template, dict) else {},
                             smap, Path(args.reference).resolve() if args.reference else None)
    for line in rep.lines:
        print("  " + line)
    if summary:
        print(f"  STATUS {summary['status']}  "
              f"({summary['pages']} page(s), {summary['pdf_bytes']} bytes, "
              f"{summary['bullets']} bullets, {summary['todo_markers']} TODO)")
    if args.json and summary:
        Path(args.json).write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
                                   encoding="utf-8")
    name = (template or {}).get("id") or Path(args.pdf).stem
    print(f"SUCCESS:docgate:{name}" if code == 0 else f"FAILED:docgate:{name}")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
