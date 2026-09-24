# `templates/` — the academic CV and the auxiliary views

One command renders an A4 academic CV and every auxiliary surface from
`../profile.yaml`. Nothing here holds facts; `profile.yaml` holds the facts and
these files decide their shape. If a claim is wrong, fix `profile.yaml` — never a
template.

```bash
cd ~/.agents/cv
.venv/Scripts/python.exe templates/emit.py --list
.venv/Scripts/python.exe templates/emit.py --all                 # working copies
.venv/Scripts/python.exe templates/emit.py --all --todo omit \
    --out out/templates-clean                                    # copies for a reader
.venv/Scripts/python.exe templates/killlist.py --self-test       # prove the gate fires
.venv/Scripts/python.exe -m pytest templates/test_templates.py -q
```

## What gets produced

| view | output | notes |
|---|---|---|
| `academic` | `academic_cv.rendercv.yaml` + `academic_cv.pdf` | A4, education-first, researcher-leading, **no summary block**, no page cap, running footer with page numbers |
| `cover-en` | `cover_letter_en.md` | hook / proof / close |
| `cover-ro` | `cover_letter_ro.md` | same structure, same identity block |
| `linkedin` | `linkedin.md` | headline ≤ 220 chars, About ≤ 2600 with a strong pre-fold 300 |
| `pack-ejobs` | `pack_ejobs.md` | field-sized snippets |
| `pack-bestjobs` | `pack_bestjobs.md` | field-sized snippets |
| `pack-hipo` | `pack_hipo.md` | field-sized snippets |
| `europass` | `europass.md` | Europass model; DOB / nationality / gender / address **empty** |
| `europass-yaml` | `europass.yaml` | the same emission as structured data |

## `--todo annotate` vs `--todo omit`

`annotate` (the default) prints `[TODO-CONFIRM] …` markers wherever the record has
a gap. That is the **working copy**: the gaps are the to-do list.

`omit` drops the markers and prints only what is verified. That is the copy that
goes to a supervisor or an employer. It never fills a gap in — it leaves it out.
Measured on this box: annotate renders 3 pages with 24 markers, omit renders 2
pages with 0.

## The two rules that shape everything here

**1. A gap is printed as a gap; a guess is never printed at all.**

- A `TODO-CONFIRM` date renders as no date. DINUPLAST's end date contradicts
  itself across the owner's two 2023 CVs, so the entry prints `May 2021 –
  [TODO-CONFIRM]`, never `May 2021 – present`. "Present" is a claim that an
  engagement is still running, and nothing supports it.
- A bare year stays a bare year. RenderCV reads a quoted `"2022"` as a full date
  and prints `Jan 2022` — a month nobody verified — so `emit.py` passes bare years
  as integers. Verified against RenderCV 2.8 on this machine.
- English renders as "Advanced" with no CEFR code. An unevidenced C2 in front of a
  doctoral committee is a fabricated credential.
- `tracelines`, `llm-anthology` and Babeș-Bolyai render on no view, because
  `profile.yaml` says so.
- The **Presentations** section omits itself: no presentation is verified, and a
  hollow heading is worse than no heading. Add a top-level `x_presentations:` list
  to `profile.yaml` and the section appears on its own.
- **References** prints "Available on request." — a statement of willingness, not
  a claim of fact. A doctoral application normally wants *named* referees; that is
  a real, open gap. Add `x_references:` and named referees replace the line.

**2. Every artefact is scanned before it is written, and the gate fails closed.**

`killlist.py` is the output-side gate (`tools/zerofab.py` guards the input side).
23 claim rules + 2 privacy line-rules + 7 two-sided wording locks. A hit means the
file is **not written** — there is no "warn and ship".

It is two-sided on purpose: a lock fires when an artefact *mentions* ChemRxiv and
*fails to say* "preprint", so a lock cannot be silently dropped by deleting a word.

`--self-test` proves both states: the clean fixture scores zero, and one
deliberately defective fixture per rule is caught by that rule. A gate that has
only ever seen a clean input has not been shown to work.

### Use vs. mention

A template's own "never write X" guidance has to quote X, and a blunt gate reads
the quotation as the claim. The fix is a narrow, audited region, not a softer rule:

```
<!-- killlist:allow-mentions -->
 … guidance that has to quote the forbidden phrasing …
<!-- killlist:end -->
```

Three things stop it becoming a loophole: the region is opened and closed
explicitly in the template source; every exemption is reported as a visible `NOTE`
finding; and the **privacy** rules still apply inside it, because the file ships as
it stands.

## Privacy, and why Europass is the interesting case

No photo, date of birth, nationality, marital status or street address on any
view — city and country only. Europass is where this has to be deliberate, because
the form *invites* those fields. They are emitted **present and empty**: present so
nobody thinks the form was answered wrongly, empty so nothing protected is
disclosed. The gate enforces it — a label followed by a value is an error and the
file is not written. A label followed by nothing, by `""`, or by an empty table
cell passes.

ORCID is deliberately **not linked** anywhere. The record currently has zero
registered works and an education entry crediting the bachelor's degree to the
wrong university. A reviewer who clicks it today sees an empty, factually wrong
record. `emit.py` prints that warning on every academic render until it is fixed.

## Files

```
templates/
  emit.py                          the renderer/CLI
  killlist.py                      the output gate (self-testing)
  test_templates.py                70 contract tests
  _shared/identity.j2              one identity block, shared by both cover letters
  _shared/blurbs.j2                the snippets the three platform packs share
  academic/academic.sections.yaml  THE SECTION CONTRACT — edit this to reshape the CV
  academic/academic.design.yaml    A4, margins, running footer, page numbers
  academic/academic.view.yaml      drop-in x_views patch for tools/build.py
  cover-letter/cover_{en,ro}.md.j2
  linkedin/linkedin.md.j2
  platform-packs/{ejobs,bestjobs,hipo}.md.j2
  europass/europass.{md,yaml}.j2
```

## Two declared deviations from the brief

1. **A `Professional experience` section was added** to the academic CV, between
   Research experience and Publications. The brief's section list omits it, but
   G-5 rules momentstudio.ro paid client work into Experience and an unbounded
   academic CV pays no page cost to carry it. Turn it off with
   `emit.py --view academic --no-experience` for the brief's list exactly.
2. **The "running header" is a running footer.** RenderCV's repeating per-page
   element is the footer; its `top_note` renders on the first page only. The footer
   carries `NAME — Curriculum Vitae — page N of M` on every page, which is the
   identification a reader needs when pages get separated. Calling it a header
   would be a claim the renderer does not support.

## Relationship to `tools/build.py`

Both read the same `profile.yaml`, so the facts are identical either way.
`build.py` renders the whole view family (ats-en, ro, research-profile, europass,
academic). `emit.py` renders the academic CV plus the text views that `build.py`
skips by design, and does four things `build.py` cannot: two separate project
sections, a running footer with page numbers, per-item publication status labels,
and the platform/LinkedIn length checks. `academic/academic.view.yaml` documents
that boundary and patches what *can* be fixed inside `build.py`.
