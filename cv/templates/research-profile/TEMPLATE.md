# One-page research profile — template

**Deliverable #1.** Due for the December supervisor outreach (decision G-6: this view is
built first, ahead of the rest of the system).

**Audience.** A prospective doctoral supervisor at the University of Bucharest Doctoral
School of Informatics who has never heard of Andrei-Mihai Visalon and is reading cold.

> **This is not a CV and must never be sent as one.** The engineering resume (`ats-en`)
> is the CV. This document leads with the researcher identity (decision G-2); the resume
> leads with engineering. That split is deliberate and per-audience.

---

## Files

| File | What it is |
|---|---|
| `template.yaml` | The template. View spec, narrative text with per-line `trace:`, wording locks, density knobs. |
| `render.py` | The renderer. Imports `tools/build.py` and reuses it; owns section assembly only. |
| `OUTREACH.md` | How to approach a supervisor with this document (decision G-16). |
| `TEMPLATE.md` | This file. |

## Render it

```bash
cd ~/.agents/cv
.venv/Scripts/python.exe templates/research-profile/render.py
```

Outputs land in `~/.agents/cv/out/`:

- `Andrei-Mihai_Visalon_research_profile_onepage.pdf` — the document
- `…onepage.md` — a full markdown rendering of the same content, written **before** the
  PDF is attempted, so a box with a broken Typst still leaves a usable document
- `…onepage.rendercv.yaml` — the RenderCV intermediate
- `…onepage.manifest.json` — provenance: profile SHA-256, template SHA-256, PDF SHA-256,
  sections rendered, TODO markers, suppressed links
- `…onepage.gated-profile.yaml` — the narrative-augmented profile the lint actually ran on

`--emit-only` stops before RenderCV. `--profile` / `--template` / `--out` override paths.

---

## The document answers four questions, in this order

1. **What questions does he work on?** — `narrative.questions`
2. **What has he actually done?** — `narrative.work_to_date` (GRACE with the complete
   metric wording; the FAERS/phenibut line; the ChemRxiv preprint; the Zenodo deposit
   with its SHA-256 manifest)
3. **What can he bring to a group?** — `narrative.what_i_bring`
4. **What does he want to do next?** — `narrative.next`

Then, small and at the bottom: **Education**, **Honors** (pbinfo), **Languages**.

pbinfo is in Honors, never the headline (decision G-3), always named as *Romania's
national **high-school** competitive-programming judge*, always with the full numbers,
always dated *as of September 2026* because the ranking can move.

---

## The five fail-closed gates in `render.py`

Any one of them stops the render. In order:

| Gate | What it enforces |
|---|---|
| **T1 trace** | Every narrative line names a key that **exists** in `profile.yaml`'s `x_master`. A dangling trace is a hard error — no line may assert something the record does not hold. |
| **T2 todo shape** | `trace: TODO-CONFIRM` is the only exemption from T1. Such a line **must** carry the literal `TODO-CONFIRM` marker in its rendered text and **must contain no digits**. An unsourced number is precisely the failure this whole exercise exists to prevent. |
| **T3 zerofab** | The narrative is written into an augmented copy of `profile.yaml` under the plain key `rendered_narrative`, and `tools/zerofab.py` lints *that*. Template prose is gated by the same fail-closed lint as the profile — every number in it must resolve to an `x_metrics` entry with provenance `M`/`E`. |
| **T4 wording locks** | `require_present` (e.g. the complete GRACE metric wording, `SHA-256`, `preprint`, `high-school`, `as of September 2026`) and `require_absent` (the kill list) checked against the assembled document text. |
| **T5 verify** | `tools/verify.py` over the rendered PDF: identity, single-column reading order, **page count against a `[1, 1]` budget**, A4 MediaBox, no ligature/soft-hyphen damage, no DOB/nationality/marital-status/street-address leak, real selectable text layer. |

Each gate was verified in **both** states — the real template passes, and a deliberately
broken copy is rejected:

| Control | Injected | Result |
|---|---|---|
| N1 | `trace: "project:DoesNotExist"` | `ERROR T1/T2 … is not a key in profile.yaml x_master` |
| N2 | the words "widely used" | `ERROR T4 KILL LIST … is PRESENT` |
| N3 | a figure inside the `TODO-CONFIRM` line | `ERROR T1/T2 … text contains digits` |
| N4 | `page_budget: [3, 3]` | `FAIL C3 page count 1 (budget 3-3)` |
| N5 | "open-source" with no LICENSE | `ERROR ZF008 rendered_narrative.what_i_bring[3]` |
| N6 | "1,590 merged pull requests" | `ERROR T4 KILL LIST '1,590' is PRESENT` |
| N7 | an invented "4,821 stars" | `ERROR ZF001 … figure '4,821' resolves to no x_metrics entry` |

Two of these were real defects found by running the controls, not decoration:

- **T4** rejected a first draft containing "there is no peer-reviewed publication" — a
  negation, but still the banned string on the page, and a skimming reader does not
  parse negations.
- **T3 was originally a no-op.** The narrative was first parked under `x_narrative`, and
  `zerofab.walk_strings` **skips every `x_`-prefixed key by design** (they are the
  evidence bank, not rendered output). N7's fabricated "4,821 stars" rendered completely
  clean. The key is now the plain `rendered_narrative`, and N5/N7 both fail as they
  should. **Anyone adding rendered content to a profile must not park it under an `x_`
  key** — it will not be linted.

---

## Editorial decisions baked in

- **ORCID is suppressed on this view.** `profile.yaml` states that ORCID
  0009-0001-8776-8498 currently has zero registered works and credits the bachelor's to
  the wrong university. A supervisor *will* click it. `template.yaml`
  `suppress_networks` withholds the link with the unblock condition recorded
  (`TODO-CONFIRM.md` item 2). **Re-enable it the moment both are fixed** — an ORCID iD is
  expected on a research profile and its absence is a small cost of its own.
- **Babes-Bolyai is excluded** (`include_ubb: false`). The 2021–22 Cluj year is
  incomplete with no degree and the listing decision is still pending.
- **No Experience section.** momentstudio and DINUPLAST are real and paid, and they
  belong on the engineering resume. On a one-page research profile aimed at a supervisor
  they cost more space than they earn. Nothing is hidden — the resume carries them.
- **Bare years stay bare.** `profile.yaml` records the Titu Maiorescu BSc as 2022–2025,
  years only. RenderCV's typed date fields silently default a bare year to January, so
  the PDF would have asserted "Jan 2022 – Jan 2025" — a month nobody verified.
  `render.py::fix_bare_year_dates` collapses such a pair into RenderCV's free-text `date`
  field instead. *(This is a general `tools/build.py` fidelity bug, not specific to this
  view; it affects every view that renders a bare-year entry.)*
- **Density knobs are part of the template.** Measured on this box: at RenderCV 2.8
  defaults (0.7in margins, 10pt body, 0.7cm header gaps) this content renders on **two**
  pages. The template sets 1.1/1.3cm margins, 9.4pt body and tightened header and
  section spacing. Current render fills to y≈763pt of 842pt — roughly 80pt of slack, so
  a few more lines fit before the budget breaks. **If T5 ever fails on page count, cut
  prose first; do not shrink the font below 9pt.**

---

## Before this is sent to anyone

The document currently renders **three visible `TODO-CONFIRM` markers**. That is by
design — they are unresolved facts, and the alternative is inventing them. But a
document with visible TODO markers is a *draft*, not a send.

Resolve or delete, in this order:

1. **The FAERS/phenibut line.** `profile.yaml` holds **no** verified material on this
   work at all — no cohort definition, no de-duplication or drug-role rules, no
   disproportionality measures, and no statement of whether it is the subject of the
   ChemRxiv preprint or of the manuscript in preparation. The line is currently a
   number-free TODO placeholder held open by T2. **Supply the facts into
   `profile.yaml` `x_master` + `x_metrics` and re-point the trace, or delete the line.**
2. **The ChemRxiv preprint's title, DOI and posting date** (`TODO-CONFIRM.md`).
3. **The Zenodo deposit DOI** (`TODO-CONFIRM.md`).
4. **The exact CEFR level for English** (C1 or C2) — do not guess it.
5. **ORCID**: register the works, fix the bachelor's institution, then remove the
   `suppress_networks` entry and re-render.
6. **The dissertation topic line**, which is deliberately open: see `OUTREACH.md`.

## Changing the document

Edit `template.yaml`, never the generated files in `out/`. A new claim needs a real
source in `profile.yaml` first — add it to `x_master` (and any number to `x_metrics`
with provenance `M` or `E` and `renderable: true`), *then* write the line and point
`trace:` at it. If you find yourself wanting to relax a gate to make a line fit, the
line is the problem.
