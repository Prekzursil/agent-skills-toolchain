#!/usr/bin/env python3
"""cv/tools/verify.py — the no-regression contract for a produced PDF.

A CV that renders is not a CV that works. This file asserts the properties an
applicant-tracking system, a doctoral committee's PDF reader, and EU hiring
hygiene actually depend on. It reads the PDF that was produced, not the data
that went in, so a mis-render is caught before the document is sent.

Seven checks, each independently PASS/FAIL:

  C1 IDENTITY   the text layer contains the name, every institution and every
                employer that this view selected (a picture of a CV, a broken
                font, or a dropped section all fail here)
  C2 COLUMNS    single-column reading order on parsed views — detects a real
                column gutter (a vertical band that body text never crosses),
                which is what makes an ATS interleave two columns into garbage
  C3 PAGES      page count inside the view's budget
  C4 A4         every page's MediaBox is A4 (595.276 x 841.890 pt, +/- 2pt)
  C5 GLYPHS     no ligature / soft-hyphen / zero-width damage in the text layer
                (a U+FB01 "fi" ligature makes "certification" unsearchable)
  C6 PRIVACY    no date of birth, nationality, marital status or street address
                leaks into a parsed view
  C7 TEXT       a real selectable text layer exists (not a scan/image)

Usage
-----
    PY=~/.agents/cv/.venv/Scripts/python
    $PY tools/verify.py --pdf out/Name_view.pdf                       # manifest auto-found
    $PY tools/verify.py --pdf out/X.pdf --manifest out/X.manifest.json
    $PY tools/verify.py --pdf out/X.pdf --profile profile.yaml --view research-profile
    $PY tools/verify.py --selftest          # prove each check fires (both states)

Last line is SUCCESS:<pdf-name> or FAILED:<pdf-name>. Exit 0 = contract held.
build.py imports verify_pdf() directly, so the contract runs on every build.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent

# Windows consoles default to cp1252 on Python 3.14; a single em dash or ligature
# in a finding would otherwise raise UnicodeEncodeError and lose the whole report.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:                                          # pragma: no cover
        pass

A4_PT = (595.276, 841.890)
A4_TOL = 2.0

# Glyph damage that silently breaks ATS keyword search.
# Codepoints are written with chr() so this source file stays pure ASCII: a
# literal ligature or zero-width character in the checker itself is exactly the
# kind of invisible damage the checker exists to find.
LIGATURES = {
    chr(0xFB00): "ff", chr(0xFB01): "fi", chr(0xFB02): "fl", chr(0xFB03): "ffi",
    chr(0xFB04): "ffl", chr(0xFB05): "st", chr(0xFB06): "st",
}
INVISIBLES = {
    chr(0x00AD): "SOFT HYPHEN", chr(0x200B): "ZERO WIDTH SPACE",
    chr(0x200C): "ZERO WIDTH NON-JOINER", chr(0x200D): "ZERO WIDTH JOINER",
    chr(0xFEFF): "BOM/ZWNBSP", chr(0x2028): "LINE SEPARATOR",
    chr(0xFFFD): "REPLACEMENT CHAR",
}

# C6. Personal-data shapes that must not appear on a machine-parsed view.
PRIVACY_PATTERNS: list[tuple[str, str]] = [
    ("date of birth", r"\b(date\s+of\s+birth|d\.?o\.?b\.?|born\s+on|birth\s*date|"
                      r"data\s+na[sș]terii|n[aă]scut(?:[aă])?\s+la)\b"),
    ("nationality",   r"\b(nationality|citizenship|na[tț]ionalitate|cet[aă][tț]enie)\b"),
    ("marital status", r"\b(marital\s+status|civil\s+status|stare\s+civil[aă]|"
                       r"married|unmarried|divorced|c[aă]s[aă]torit)\b"),
    ("street address", r"\b(str\.|strada|bd\.|bulevardul|[ș]os\.|"
                       r"\d{1,4}\s+[A-Z][a-z]+\s+(street|st\.|road|rd\.|avenue|ave\.|lane|ln\.)|"
                       r"apt\.?\s*\d|bl\.\s*\w+\s*,?\s*sc\.|nr\.\s*\d+)"),
    ("gender",        r"\b(gender|sex)\s*[:\-]\s*(m|f|male|female)\b"),
]


# --------------------------------------------------------------------------- #
# PDF access                                                                   #
# --------------------------------------------------------------------------- #
def _open(pdf: Path):
    try:
        import pymupdf
    except ImportError:                                        # pragma: no cover
        try:
            import fitz as pymupdf                             # older wheels
        except ImportError:
            raise SystemExit(
                "verify.py needs PyMuPDF: "
                f"{ROOT / '.venv/Scripts/python.exe'} -m pip install pymupdf"
            ) from None
    return pymupdf.open(pdf)


def _norm(text: str) -> str:
    """Collapse whitespace and undo ligatures for CONTAINMENT tests only.

    C5 still sees the raw text, so this never hides glyph damage — it stops a
    ligature from also producing a spurious C1 failure.
    """
    for lig, plain in LIGATURES.items():
        text = text.replace(lig, plain)
    text = unicodedata.normalize("NFKC", text)
    text = "".join(ch for ch in text if ch not in INVISIBLES)
    return re.sub(r"\s+", " ", text).lower()


def glyph_damage(raw: str) -> list[str]:
    """C5 as a pure function over a text layer: ligature / invisible-char damage.

    A U+FB01 "fi" ligature makes "certification" unfindable by an exact ATS keyword
    search; a soft hyphen splits a word the same way. Both are invisible to a
    human reading the PDF, which is exactly why they need a machine check.
    """
    found: list[str] = []
    for ch, plain in LIGATURES.items():
        n = raw.count(ch)
        if n:
            found.append(f"{n}x U+{ord(ch):04X} ligature (breaks '{plain}' search)")
    for ch, label in INVISIBLES.items():
        n = raw.count(ch)
        if n:
            found.append(f"{n}x {label} (U+{ord(ch):04X})")
    return found


def _contains(haystack: str, needle: str) -> bool:
    """Tolerate line-wrapping and a trailing ', Location' on an entry heading."""
    probe = re.sub(r"\s+", " ", needle).strip().lower()
    if not probe:
        return True
    if probe in haystack:
        return True
    head = probe.split(",")[0].strip()
    if len(head) >= 6 and head in haystack:
        return True
    # last resort: all words present, in order, within a short window
    words = [w for w in re.split(r"\W+", probe) if len(w) > 2]
    if not words:
        return False
    pos = 0
    for w in words:
        idx = haystack.find(w, pos)
        if idx < 0:
            return False
        pos = idx + len(w)
    return True


# --------------------------------------------------------------------------- #
# C2 — single-column reading order                                             #
# --------------------------------------------------------------------------- #
def column_gutters(doc, min_side_share: float = 0.20,
                   max_cross_share: float = 0.05) -> list[tuple[int, float]]:
    """Find x positions that split a page into two non-interacting text columns.

    A genuinely two-column CV has a vertical band that NO line of body text
    crosses: everything is wholly left of it or wholly right of it. A
    single-column CV with right-aligned dates looks two-column line-by-line,
    but its bullets and summary span the full width and cross the band
    constantly — so `cross_share` discriminates the two.

    Returns [(page_index, x)] for each offending page.
    """
    hits: list[tuple[int, float]] = []
    for pno, page in enumerate(doc):
        rects = []
        for block in page.get_text("dict").get("blocks", []):
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                text = "".join(sp.get("text", "") for sp in line.get("spans", []))
                if not text.strip():
                    continue
                x0, _y0, x1, _y1 = line["bbox"]
                if x1 - x0 > 1:
                    rects.append((x0, x1))
        if len(rects) < 8:
            continue
        left_edge = min(r[0] for r in rects)
        right_edge = max(r[1] for r in rects)
        span = right_edge - left_edge
        if span <= 0:
            continue
        total = len(rects)
        # Scan the middle 60% of the text band in 2pt steps.
        x = left_edge + 0.20 * span
        stop = left_edge + 0.80 * span
        while x <= stop:
            cross = sum(1 for x0, x1 in rects if x0 < x - 0.5 and x1 > x + 0.5)
            left = sum(1 for _x0, x1 in rects if x1 <= x)
            right = sum(1 for x0, _x1 in rects if x0 >= x)
            if (cross / total <= max_cross_share
                    and left / total >= min_side_share
                    and right / total >= min_side_share):
                hits.append((pno, round(x, 1)))
                break
            x += 2.0
    return hits


# --------------------------------------------------------------------------- #
# The contract                                                                 #
# --------------------------------------------------------------------------- #
def verify_pdf(
    pdf: Path,
    manifest: dict[str, Any] | None = None,
    profile: dict[str, Any] | None = None,
) -> tuple[bool, list[str]]:
    """Run all seven checks. Returns (all_passed, ['PASS  C1 …', 'FAIL  C2 …'])."""
    findings: list[str] = []
    ok = True

    def record(passed: bool, code: str, msg: str) -> None:
        nonlocal ok
        findings.append(f"{'PASS' if passed else 'FAIL'}  {code} {msg}")
        if not passed:
            ok = False

    pdf = Path(pdf)
    if not pdf.exists():
        return False, [f"FAIL  C0 pdf not found: {pdf}"]

    manifest = manifest or {}
    profile = profile or {}
    basics = profile.get("basics") or {}

    name = manifest.get("name") or basics.get("name") or ""
    employers = manifest.get("employers")
    if employers is None:
        employers = [str(w.get("name") or w.get("company") or "")
                     for w in (profile.get("work") or [])]
    institutions = manifest.get("institutions")
    if institutions is None:
        institutions = [str(e.get("institution") or "")
                        for e in (profile.get("education") or [])]
    parsed = bool(manifest.get("parsed", True))
    budget = manifest.get("page_budget") or [1, 3]
    lo, hi = int(budget[0]), int(budget[-1])

    doc = _open(pdf)
    try:
        pages = doc.page_count
        raw = "".join(page.get_text() for page in doc)
        hay = _norm(raw)

        # C7 — a real text layer -------------------------------------------- #
        record(len(hay) > 200,
               "C7", f"text layer: {len(hay)} chars extracted "
                     f"({'selectable text' if len(hay) > 200 else 'NO TEXT — image-only PDF?'})")

        # C1 — identity ------------------------------------------------------ #
        missing = []
        for label, value in ([("name", name)]
                             + [("institution", i) for i in institutions if i]
                             + [("employer", e) for e in employers if e]):
            if value and not _contains(hay, str(value)):
                missing.append(f"{label}={value!r}")
        checked = 1 + len([i for i in institutions if i]) + len([e for e in employers if e])
        record(not missing,
               "C1", f"identity: {checked - len(missing)}/{checked} required strings present"
                     + (f" — MISSING {'; '.join(missing)}" if missing else ""))

        # C2 — single-column reading order ----------------------------------- #
        if parsed:
            gutters = column_gutters(doc)
            record(not gutters,
                   "C2", "single-column reading order"
                         + (f" — COLUMN GUTTER on page(s) "
                            f"{', '.join(f'{p + 1}@x={x}' for p, x in gutters)}"
                            if gutters else " (no column gutter found)"))
        else:
            findings.append("SKIP  C2 single-column check (view is not machine-parsed)")

        # C3 — page budget ---------------------------------------------------- #
        record(lo <= pages <= hi, "C3", f"page count {pages} (budget {lo}-{hi})")

        # C4 — A4 MediaBox ---------------------------------------------------- #
        bad_pages = []
        for i, page in enumerate(doc):
            box = page.mediabox
            w, h = round(box.width, 3), round(box.height, 3)
            if abs(w - A4_PT[0]) > A4_TOL or abs(h - A4_PT[1]) > A4_TOL:
                bad_pages.append(f"p{i + 1}={w}x{h}")
        record(not bad_pages,
               "C4", f"A4 MediaBox 595.276x841.890pt on all {pages} page(s)"
                     + (f" — WRONG: {', '.join(bad_pages)}" if bad_pages else ""))

        # C5 — glyph damage ---------------------------------------------------- #
        damage = glyph_damage(raw)
        record(not damage, "C5", "no ligature/soft-hyphen/zero-width damage"
                                 + (f" — FOUND {'; '.join(damage)}" if damage else ""))

        # C6 — personal-data leak ---------------------------------------------- #
        if parsed:
            leaks = []
            for label, pattern in PRIVACY_PATTERNS:
                m = re.search(pattern, hay, re.IGNORECASE)
                if m:
                    leaks.append(f"{label} ~ {m.group(0)!r}")
            # The actual held-back VALUES, not just the generic shapes: the
            # profile keeps a date of birth on file precisely so nobody
            # re-derives a wrong one, and it must render nowhere.
            for block, label in (
                (profile.get("x_private"), "x_private"),
                ((profile.get("x_privacy") or {}).get("held_but_never_rendered"),
                 "x_privacy.held_but_never_rendered"),
            ):
                for key, value in (block or {}).items():
                    literal = re.sub(r"\s+", " ", str(value)).strip().lower()
                    if len(literal) >= 4 and literal in hay:
                        leaks.append(f"{label}.{key} literal present in the PDF")
            record(not leaks, "C6", "no DOB/nationality/marital-status/street-address leak"
                                    + (f" — LEAKED {'; '.join(leaks)}" if leaks else ""))
        else:
            findings.append("SKIP  C6 personal-data check (view is not machine-parsed)")
    finally:
        doc.close()

    return ok, findings


# --------------------------------------------------------------------------- #
# Self-test — prove each check can FAIL, not just pass                         #
# --------------------------------------------------------------------------- #
def _selftest() -> int:
    """Both-states evidence: a clean synthetic PDF must PASS; a deliberately
    broken one must FAIL on the specific check that targets the defect."""
    try:
        import pymupdf
    except ImportError:                                        # pragma: no cover
        import fitz as pymupdf

    tmp = ROOT / "out" / "_selftest"
    tmp.mkdir(parents=True, exist_ok=True)
    manifest = {
        "name": "Test Person", "employers": ["Acme Widgets"],
        "institutions": ["State University"], "parsed": True, "page_budget": [1, 1],
    }
    body = ("Test Person\nSummary: builds things and writes about building them.\n"
            "Experience\nAcme Widgets — Engineer 2020-2024\n"
            + "\n".join(f"- did a measurable thing number {i} across the whole line width "
                        f"of this document so it spans the page" for i in range(12))
            + "\nEducation\nState University — BSc Computer Science 2016-2020\n")
    results: list[tuple[str, bool, str]] = []

    def make(path: Path, size, text, two_col=False, extra=""):
        d = pymupdf.open()
        page = d.new_page(width=size[0], height=size[1])
        if two_col:
            half = size[0] / 2
            for col, x in ((0, 40), (1, half + 10)):
                page.insert_textbox(pymupdf.Rect(x, 50, x + half - 50, size[1] - 50),
                                    text + f"\ncolumn {col}", fontsize=8)
        else:
            page.insert_textbox(pymupdf.Rect(40, 50, size[0] - 40, size[1] - 50),
                                text + extra, fontsize=8)
        d.save(path)
        d.close()

    # 1. clean A4 single-column -> everything passes
    p = tmp / "clean.pdf"
    make(p, A4_PT, body)
    ok, f = verify_pdf(p, manifest, {})
    results.append(("clean A4 single-column PASSES", ok, "; ".join(x for x in f if x.startswith("FAIL"))))

    # 2. US Letter -> C4 must fail
    p = tmp / "letter.pdf"
    make(p, (612.0, 792.0), body)
    ok, f = verify_pdf(p, manifest, {})
    results.append(("US-Letter FAILS C4", (not ok) and any("FAIL  C4" in x for x in f), ""))

    # 3. two columns -> C2 must fail
    p = tmp / "twocol.pdf"
    make(p, A4_PT, body, two_col=True)
    ok, f = verify_pdf(p, manifest, {})
    results.append(("two-column FAILS C2", (not ok) and any("FAIL  C2" in x for x in f), ""))

    # 4. missing employer -> C1 must fail
    p = tmp / "noemployer.pdf"
    make(p, A4_PT, body.replace("Acme Widgets", "Redacted"))
    ok, f = verify_pdf(p, manifest, {})
    results.append(("missing employer FAILS C1", (not ok) and any("FAIL  C1" in x for x in f), ""))

    # 5a. glyph damage, as a pure function (both states, font-independent)
    clean_ok = glyph_damage("certification and innovation") == []
    dirty = glyph_damage("certi\ufb01cation and in\u00adnovation\ufeff")
    results.append(("glyph_damage(): clean text -> no findings", clean_ok, ""))
    results.append(("glyph_damage(): ligature+soft-hyphen+BOM -> 3 findings",
                    len(dirty) == 3, f"got {dirty}"))

    # 5b. and end-to-end through a real PDF. The base-14 fonts PyMuPDF writes by
    # default cannot even encode U+FB01 (it becomes '?'), so this needs a TTF
    # that carries the glyph; if none is on the box the pure test above stands.
    fontfile = next((f for f in ("C:/Windows/Fonts/calibri.ttf",
                                 "C:/Windows/Fonts/times.ttf",
                                 "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf")
                     if Path(f).exists()), None)
    if fontfile:
        p = tmp / "ligature.pdf"
        d = pymupdf.open()
        page = d.new_page(width=A4_PT[0], height=A4_PT[1])
        page.insert_textbox(pymupdf.Rect(40, 50, A4_PT[0] - 40, A4_PT[1] - 50),
                            body + "\ncerti\ufb01cation", fontsize=8,
                            fontfile=fontfile, fontname="vt")
        d.save(p)
        d.close()
        ok, f = verify_pdf(p, manifest, {})
        results.append(("ligature in a real PDF FAILS C5",
                        (not ok) and any("FAIL  C5" in x for x in f), ""))
    else:                                                      # pragma: no cover
        print("  note no TTF with a U+FB01 glyph on this box; C5 proven by the pure test only")

    # 6. DOB + address leak -> C6 must fail
    p = tmp / "privacy.pdf"
    make(p, A4_PT, body, extra="\nDate of birth: 8 June 2002\nNationality: Romanian")
    ok, f = verify_pdf(p, manifest, {})
    results.append(("DOB/nationality FAILS C6", (not ok) and any("FAIL  C6" in x for x in f), ""))

    # 6b. a bare held-back VALUE with no label: the generic patterns do not see
    # it, so the literal check is what catches a real DOB slipping through.
    p = tmp / "dob_literal.pdf"
    make(p, A4_PT, body, extra=chr(10) + "1993-06-08")
    held = {"x_privacy": {"held_but_never_rendered": {"date_of_birth": "1993-06-08"}}}
    ok_lit, f_lit = verify_pdf(p, manifest, held)
    ok_ctl, f_ctl = verify_pdf(p, manifest, {})
    results.append(("bare held-back DOB literal FAILS C6",
                    (not ok_lit) and any("FAIL  C6" in x for x in f_lit), ""))
    results.append(("...and the generic patterns alone do NOT flag it (control)",
                    any("PASS  C6" in x for x in f_ctl), ""))

    # 7. page budget -> C3 must fail
    p = tmp / "pages.pdf"
    make(p, A4_PT, body)
    ok, f = verify_pdf(p, {**manifest, "page_budget": [2, 3]}, {})
    results.append(("page budget FAILS C3", (not ok) and any("FAIL  C3" in x for x in f), ""))

    failed = 0
    for label, passed, detail in results:
        print(f"  {'ok  ' if passed else 'BAD '} {label}" + (f"  [{detail}]" if detail and not passed else ""))
        failed += 0 if passed else 1
    print(f"SUCCESS:selftest ({len(results)} cases)" if not failed
          else f"FAILED:selftest ({failed}/{len(results)} cases did not behave as specified)")
    return 0 if not failed else 1


# --------------------------------------------------------------------------- #
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="verify.py", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pdf")
    ap.add_argument("--manifest", help="build.py's <stem>.manifest.json (auto-found beside the PDF)")
    ap.add_argument("--profile", help="fallback when no manifest exists")
    ap.add_argument("--view", help="view name, with --profile")
    ap.add_argument("--selftest", action="store_true",
                    help="prove every check fires on a deliberately broken PDF")
    args = ap.parse_args(argv)

    if args.selftest:
        return _selftest()
    if not args.pdf:
        ap.error("--pdf is required (or use --selftest)")

    pdf = Path(args.pdf).resolve()
    label = pdf.name
    manifest: dict[str, Any] = {}
    if args.manifest:
        mpath = Path(args.manifest)
        if not mpath.exists():
            print(f"  FAIL  C0 manifest not found: {mpath}")
            print(f"FAILED:{label}")
            return 1
    else:
        cand = pdf.parent / (pdf.stem + ".manifest.json")
        mpath = cand if cand.exists() else None
    if mpath:
        try:
            manifest = json.loads(mpath.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            print(f"  FAIL  C0 manifest {mpath} is not readable JSON: {exc}")
            print(f"FAILED:{label}")
            return 1
        if not isinstance(manifest, dict):
            print(f"  FAIL  C0 manifest {mpath} is not a JSON object")
            print(f"FAILED:{label}")
            return 1
        print(f"  MANIFEST {mpath}")

    profile: dict[str, Any] = {}
    if args.profile:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import build as build_mod

        profile = build_mod.load_yaml(Path(args.profile))
        if args.view:
            view = build_mod.resolve_view(profile, args.view)
            profile = build_mod.apply_selection(profile, view)
            if view.get("parsed"):
                profile, _ = build_mod.strip_personal_data(profile)
            manifest = manifest or {
                "name": (profile.get("basics") or {}).get("name"),
                "employers": [str(w.get("name") or w.get("company") or "")
                              for w in (profile.get("work") or [])],
                "institutions": [str(e.get("institution") or "")
                                 for e in (profile.get("education") or [])],
                "parsed": bool(view.get("parsed")),
                "page_budget": list(view.get("page_budget") or [1, 3]),
            }
            label = args.view
    elif not manifest:
        print("  WARN  no manifest and no --profile: C1 identity has nothing to assert against")

    ok, findings = verify_pdf(pdf, manifest, profile)
    for f in findings:
        print(f"  {f}")
    print(f"{'SUCCESS' if ok else 'FAILED'}:{label}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
