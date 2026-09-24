---
name: cv-studio
description: Generate an ATS-clean PDF resume AND a visually-designed CV from ONE structured profile, plus tailored cover letters and an optimised LinkedIn profile. Use when the user wants to create, redesign, tailor, or ATS-optimise a resume/CV, write a cover letter, or rewrite their LinkedIn headline/About. Zero-fabrication, enforced by a fail-closed lint. ATS PDF via RenderCV; visual CV via JSON Resume or figma.
license: "MIT (skill). Engines: RenderCV + JSON Resume are MIT. Reference content is paraphrased from MIT-licensed repos (credited in references/); no unlicensed text vendored."
---
# cv-studio — one profile → N documents, behind two fail-closed gates

A CV is **two artifacts with opposite constraints** (this is the load-bearing insight):

1. **The ATS-submitted PDF** is a *data input, not a design piece*. It must be **single-column,
   real selectable text, tagged**. A multi-column Figma graphic parses into interleaved garbage —
   the extractor reads *across* columns, so "Skills … SQL Senior PM Python" becomes one mangled
   job title and you drop out of keyword search. → Typeset it with **RenderCV**.
2. **The human/portfolio version** (personal site, a PDF handed to a person) is where design
   shines. → Route that to the owner's **design-studio / figma / ui-ux-pro-max** pipeline.

Never design the *submitted* CV as a graphic. Typeset it; design the portfolio variant only.

## ⚠ Two implementations — know which one you are in

| | `skills/cv-studio/scripts/cvstudio.py` (legacy, shipped) | `~/.agents/cv/` (hardened, **canonical**) |
|---|---|---|
| Scope | one script, one document | one profile → 10 PDFs + 15 markdown packs |
| Zero-fab lint | **FAILS OPEN — do not trust it** | `tools/zerofab.py`, fail-closed, 36 tests |
| Output check | text-layer presence | 7-check PDF contract + 10-check document gate |
| Status | kept for the generic/other-person case | what the owner actually ships |

**The shipped `cvstudio.py validate` is not a gate.** Measured: it returns
`SUCCESS: validate (0 errors, 0 warnings)` on a profile containing a literal `TODO-CONFIRM`
date and two empty date fields. Three defects, each independently confirmed:

- with no `x_metrics` block it **short-circuits**, so every fabricated figure passes silently;
- it scans **only `work[].highlights`** — `projects`, `education`, `publications`, `summary`,
  `volunteer` are never read;
- its warnings **never change the exit code**, so a caller cannot gate on it.

A green `cvstudio.py validate` is **not** permission to ship. Use `tools/zerofab.py`.
If you are building for someone other than the owner, copy `~/.agents/cv/tools/` rather than
falling back to the legacy lint.

## The one input: `profile.yaml` (JSON Resume superset)

A [JSON Resume](https://jsonresume.org/schema/) document plus `x_` extensions that enforce
honesty. `references/schema.md` has the field map; `~/.agents/cv/README.md` documents the
owner's live instance.

- Standard blocks: `basics, work, education, skills, projects, publications, awards,
  certificates, languages, volunteer, interests, references`.
- `x_master` — per-role achievement bank, keyed `"Company|Position"`. **The ONLY sanctioned
  source for bullets.** You rewrite these long-form notes into punchy bullets; you never invent.
- `x_metrics` — verified figures only, as **mappings**: `{id, value, provenance, renderable,
  how_known}`. A figure may render **iff** it resolves to an entry with provenance `M` or `E`
  **and** a non-empty `how_known`. `B`/`U` provenance and `renderable: false` license nothing.
- `x_views` — the named outputs (see the table below).
- `x_targets` — saved job descriptions for `tailor` mode.
- `x_forbidden` — per-profile kill list: claims that must never appear on any surface.

## The pipeline (deterministic; scripts do the mechanics, you do the content)

The scripts contain **no LLM**. YOU do the writing (bullets, headline, About, cover letter),
guided by `references/`. Facts flow one way and are gated twice:

```
profile.yaml
  ├─ tools/zerofab.py        GATE 1 (input)  fail-closed, BEFORE any render
  ├─ view / template resolution (selection, order, locale, A4, page budget)
  ├─ <slug>.rendercv.yaml    inspectable intermediate
  ├─ RenderCV → Typst → PDF
  ├─ tools/verify.py         GATE 2 (output) 7 checks on the produced PDF
  └─ templates/docgate.py    GATE 3 (document) 10 checks on the text layer
```

Gate 1 runs **before** the renderer, so a fabricated figure can never reach a PDF. A missing or
failing gate **refuses the render** (exit 3, no PDF, no intermediate written).

## Exact commands — verified on this box 2026-09-24

```powershell
cd ~/.agents/cv
./build.ps1 preflight          # Python 3.14.6 · RenderCV 2.8 · PyMuPDF 1.28.2 · Typst 0.15.0
./build.ps1 all                # gate → documents → verify → test        [SUCCESS:all, exit 0]
./build.ps1 view research-profile
./build.ps1 list               # what the drivers expose + Makefile parity check
```

POSIX box: `make all` — same target names, and `./build.ps1 list` asserts that parity
automatically. **Caveat, stated plainly: `make` is not installed on this box, so the Makefile
was never executed.** Its structure was checked (tab-indented recipes, no CRLF, matching
targets) and every command it wraps was verified individually, but it is unproven as a whole.
`build.ps1` is the driver with end-to-end evidence behind it.

Under the drivers, these are the real entry points — all four run green:

```
PY=~/.agents/cv/.venv/Scripts/python.exe          # POSIX: .venv/bin/python

$PY tools/zerofab.py profile.yaml                 # SUCCESS:zerofab (0 errors, 14 warnings)
$PY tools/build.py --all                          # 5 PDFs, 4 SKIPPED (no renderer)
$PY templates/render_template.py --all            # ats-en + ro, each through docgate
$PY templates/emit.py --all                       # academic CV + 8 text packs
$PY templates/research-profile/render.py          # the one-page research profile
```

Tests and gate self-tests (all green, 2026-09-24):

```
$PY -m pytest tools/test_zerofab.py tools/test_build.py templates/test_templates.py -q
                                        # 122 passed in 15.5s
$PY tools/verify.py --selftest          # SUCCESS:selftest (11 cases)
$PY templates/docgate.py --selftest     # SUCCESS:selftest 29 checks
$PY templates/killlist.py --self-test   # SUCCESS:killlist-self-test
```

Every self-test proves its checks in **both** states — each check is shown to go RED on a
deliberately broken fixture and GREEN when clean. A gate that only ever passes is not evidence.

## What renders today

**10 PDFs and 17 text artifacts, all produced and gate-approved on 2026-09-24**
(`gate_skipped: false` in every manifest). Page counts are measured, not estimated.

| Output | Driver | Result |
|---|---|---|
| `research_profile_onepage.pdf` | `templates/research-profile/render.py` | **1 page**, 5 extra gates |
| `ats_en.pdf` / `ATS_EN.pdf` | `build.py` / `render_template.py` | 2 pages |
| `ro.pdf` / `CV_RO.pdf` | `build.py` / `render_template.py` | 2 pages, Romanian |
| `academic.pdf` (view) / `academic_cv.pdf` (template) | `build.py` / `emit.py` | 2 / 3 pages |
| `research_profile.pdf` (multi-page variant) | `build.py` | 2 pages |
| `europass.pdf` | `build.py` | 3 pages |
| `academic_cv.pdf` (reader copy, TODOs omitted) | `emit.py --todo omit` | 2 pages |
| cover letters EN+RO, LinkedIn pack, eJobs/BestJobs/Hipo packs, Europass md+yaml | `emit.py` | markdown/yaml |

`build.py` prints **SKIPPED** for `designed`, `cover`, `linkedin`, `platform-packs` — those
views declare no renderer. `cover`, `linkedin` and `platform-packs` are produced as **text** by
`emit.py`. **`designed` has no producer at all** — it routes to `design-studio` / `figma` by
hand. That is a real gap, not an oversight to paper over.

## Adding a view

1. **Declare it** in `profile.yaml` under `x_views`: `id`, `language`, `page_size: a4`,
   `section_order` (prose headings), `include_ubb`, `engine`, `outputs`, and — do this, the
   default is only a warning — `page_budget: [lo, hi]`.
2. **Check it resolves**: `./build.ps1 list` then `$PY tools/build.py --view <id> --emit-only`
   and read the `.rendercv.yaml`. `build.py` matches prose headings to data blocks by keyword and
   **WARNs on anything unmatched — it never invents a section to fill a heading.**
3. **Render**: `./build.ps1 view <id>`. Gate 1 must pass or nothing is written.
4. **For a delivered document**, add `templates/<id>/template.yaml` with a `render:` block
   (render contract, document-level `transform`s, and the `checks` the finished PDF must satisfy)
   and drive it with `render_template.py`, which chains template→profile→PDF sha256 in a manifest.
5. **Never park rendered prose under an `x_`-prefixed key.** `zerofab.walk_strings` skips `x_`
   keys by design (they are the evidence bank, not output), so content stored there is
   **unlinted**. This was caught by a negative control after a fabricated figure rendered clean.

## The zero-fabrication discipline (non-negotiable)

1. Draft bullets **only** from `x_master`. No bank → fill the bank; do not invent.
2. A figure may render **only** if it resolves to an `x_metrics` entry with provenance `M`/`E`
   and a `how_known`. `zerofab` enforces this comma-insensitively, so `1,590` and `1590` are
   the same claim.
3. A value containing `TODO-CONFIRM` is a **render-blocker, not text**. Dates are deliberately
   left as the literal string so a render **fails closed** rather than shipping a guessed month.
   A hard failure there is correct behaviour, not a bug to patch.
4. Kill-list phrases and the words `passing`, `all gates green`, `widely used`, and
   `open-source` on a repo with no declared LICENSE are refused outright.
5. `zerofab` warnings ≠ permission to ship — they are a review queue. It currently reports
   **14 `ZF010` warnings**: verified evidence in `x_metrics` that renders on no surface. Each
   needs a per-item decision (surface it, or drop it from `x_metrics`).

## Honest status — what is NOT automated

- **`designed` view.** No producer. Hand-routed to `design-studio`/`figma`.
- **`tailor` mode.** Only the legacy `cvstudio.py tailor` exists; it is not wired into the
  hardened pipeline and not covered by the 122 tests.
- **Legacy `cvstudio.py` is un-gated.** `build.py` calls `zerofab.py` as a subprocess gate;
  any *other* caller of `cvstudio.py validate`/`build` is still running the fail-open lint.
  It was deliberately **not** modified (no lane owned it). Either make its `validate` delegate
  to `zerofab`, or delete its zero-fab block so it cannot be mistaken for a gate.
- **Two template systems coexist** under `templates/`: `render_template.py` + `docgate.py`
  (ats-en, ro) and `emit.py` + `killlist.py` (academic + aux). Both read the same
  `profile.yaml`, so the facts agree, but they are two renderers and two READMEs. Reconciling
  them is open work.
- **`--skip-gate` is a real bypass.** It stamps `gate_skipped: true` into the manifest and
  prints a warning, but it exists. Never ship an artifact whose manifest says `true`.
- **Bare-year dates.** `profile.yaml` knows only `2022`/`2025` for the BSc; RenderCV expands a
  bare year to January. `emit.py` and the research-profile renderer work around it; **the fix
  belongs in `tools/build.py::_dates`** and is not yet applied there.
- **No CI.** Everything is local and manual. Nothing re-runs these gates on a change.
- **ORCID is suppressed on every view** while the record has zero works and credits the BSc to
  the wrong university. Unblocking it is an owner action, not a code change.

## What still needs the owner's content

Blocking, and tracked in full in `~/.agents/cv/TODO-CONFIRM.md` (27 items, four tiers). The
ones that block a *send*, not just a field:

1. **DINUPLAST** — job title, end date (Jul 2022 vs Jun 2023), location. Two 2023 CVs
   contradict each other; the profile refuses to pick one and renders `TODO-CONFIRM`.
2. **ChemRxiv preprint** — exact title, DOI, posting date, author order.
   `publications[0].name` is still a literal placeholder.
3. **Zenodo deposit** — DOI, URL, title, license.
4. **English CEFR level** — C1 or C2. Renders as `Advanced — TODO-CONFIRM exact CEFR level`.
5. **ORCID record** — register works; correct the BSc to Titu Maiorescu University.
6. **LICENSE status** for ZHMModSDK, Reframe, the GRACE code repo — the word "open-source"
   is kill-listed without one.
7. **Named referees** for the academic CV (it currently prints "Available on request.").
8. **No FAERS/phenibut material exists in `profile.yaml`.** The research profile renders a
   number-free `TODO-CONFIRM` placeholder for it rather than importing figures from memory.

Every document therefore renders as **DRAFT** with visible `TODO-CONFIRM` markers. That is
deliberate: `--todo omit` produces a clean reader copy, but the gaps do not stop existing
because they stopped printing.

## Cover-letter · LinkedIn · visual

- **Cover letter** — 3 paragraphs: hook, proof (2–3 achievements from `x_master` mapped to the
  JD), close. Same zero-fab rule. EN+RO emitted by `emit.py`.
- **LinkedIn** — headline ≤220 chars, About ≤2,600 with the strongest keyword-rich sentence in
  the first ~300 (what shows before "See more"). `emit.py` **measures** these limits and
  refuses to write an over-long field. **Writing to the live profile is DEFERRED** — automating
  a real profile can breach LinkedIn ToS. Output is copy-paste; never auto-write.
- **Visual** — route to `ui-ux-pro-max` → `design-studio`/`figma`. Or a JSON Resume HTML theme
  via `cvstudio.py json`. Keep the *submitted* CV on the typeset path regardless.

## Acceptance

`./build.ps1 all` prints `SUCCESS:all` and exits 0, having produced 10 PDFs that each pass the
7-check contract, 17 text artifacts, 122 passing tests and three both-states gate self-tests.
Reproducing from a bare clone: `~/.agents/cv/REPRODUCE.md`.

## References (pulled on demand — do not inline)

`references/ats-rules.md` · `references/bullets.md` · `references/linkedin.md` ·
`references/regional-formats.md` · `references/schema.md` · `INSTALL.md` (legacy engine setup) ·
`~/.agents/cv/README.md` (data model) · `~/.agents/cv/REPRODUCE.md` (second machine) ·
`~/.agents/cv/TODO-CONFIRM.md` (the 27 open facts).
