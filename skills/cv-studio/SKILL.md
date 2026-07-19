---
name: cv-studio
description: >
  Generate an ATS-clean PDF resume AND a visually-designed CV from ONE structured profile,
  plus tailored cover letters and an optimised LinkedIn profile. Use when the user wants to
  create, redesign, tailor, or ATS-optimise a resume or CV, write a cover letter, produce a
  job-specific version, or rewrite their LinkedIn headline / About / experience / skills.
  Zero-fabrication: every claim traces to the profile. ATS PDF via RenderCV (Typst,
  parser-verified, tagged single-column); visual CV via JSON Resume themes or the
  design-studio / figma pipeline. Triggers: "make my resume", "ATS-optimise my CV",
  "tailor my resume to this job", "write a cover letter", "optimise my LinkedIn profile",
  "rewrite my LinkedIn headline / About".
license: MIT (skill). Engines: RenderCV + JSON Resume are MIT. Reference content is
  paraphrased from MIT-licensed repos (credited in references/); no unlicensed text vendored.
---

# cv-studio — one profile → ATS PDF · visual CV · tailored letter · LinkedIn

A CV is **two artifacts with opposite constraints** (this is the load-bearing insight):

1. **The ATS-submitted PDF** is a *data input, not a design piece*. It must be **single-column,
   real selectable text, tagged**. A multi-column Figma graphic parses into interleaved garbage —
   the extractor reads *across* columns, so "Skills … SQL Senior PM Python" becomes one mangled
   job title and you drop out of keyword search. → Typeset it with **RenderCV** (below).
2. **The human/portfolio version** (personal site, a PDF handed to a person) is where design
   shines. → Route that to the owner's **design-studio / figma / ui-ux-pro-max** pipeline.

Never design the *submitted* CV as a graphic. Typeset it; design the portfolio variant only.

## The one input: `profile.yaml` (JSON Resume superset)

Everything derives from a single YAML file — a [JSON Resume](https://jsonresume.org/schema/)
document plus three `x_` extensions that enforce honesty. See `assets/sample-profile.yaml` for a
complete worked example and `references/schema.md` for the field map.

- Standard blocks: `basics, work, education, skills, projects, publications, awards,
  certificates, languages, volunteer, interests, references`.
- `x_master` — per-role achievement bank, keyed `"Company|Position"`. **The ONLY sanctioned
  source for bullets.** You rewrite these long-form notes into punchy bullets; you never invent.
- `x_metrics` — verified figures only. A bullet may cite a number **iff** it appears here.
- `x_targets` — saved job descriptions for `tailor` mode.

## Modes

| Mode | What it produces | How |
|------|------------------|-----|
| `ats` (default) | `*_CV.pdf` (tagged, single-column) + auditable `.typ` + `.rendercv.yaml` | `cvstudio.py build` |
| `tailor` | `tailor-report.md` — keyword-match % + missing terms + 3-place map | `cvstudio.py tailor` |
| `cover` | `cover-letter.md` — you write it from `x_master` + the JD (zero-fab) | agent + references |
| `linkedin` | `linkedin.md` — headline ≤220c, About (strong first 300), Skills, gaps | agent + references |
| `visual` | designed CV — **route to design-studio / figma**, or a JSON Resume HTML theme | see below |

## The pipeline (deterministic; scripts do the mechanics, you do the content)

The scripts contain **no LLM** — they map, render, lint, and self-check. YOU do the writing
(bullets, headline, About, cover letter), guided by `references/`. Run scripts with the
**cv-studio venv python** (see `INSTALL.md`; it never pollutes global Python):

```
PY=~/.local/share/cv-studio/venv/Scripts/python      # POSIX: .../venv/bin/python
$PY scripts/cvstudio.py validate profile.yaml        # schema + zero-fabrication lint
$PY scripts/cvstudio.py build    profile.yaml --out out [--theme classic]
$PY scripts/cvstudio.py tailor   profile.yaml job.md --out out/tailor-report.md
$PY scripts/cvstudio.py selfcheck out/Name_CV.pdf profile.yaml
$PY scripts/cvstudio.py json     profile.yaml        # export portable JSON Resume (x_ stripped)
```

`build` runs four gates in order and stops at the first failure:
**schema-validate → zero-fabrication lint → RenderCV render → PyMuPDF ATS self-check**
(asserts the PDF's text layer actually contains the name, email, every company, every
institution — catches a mis-render before you call it done). Terminal output is
`SUCCESS:` / `FAILED:` so a caller can gate on it.

Themes (single-column, all ATS-verified by RenderCV): `classic` (default), `engineeringresumes`
(most minimal, colourless — best for strict ATS/print), `sb2nov`, `engineeringclassic`, `moderncv`.

## The zero-fabrication discipline (non-negotiable)

1. Draft bullets **only** from `x_master`. If a role has no `x_master` bank, `validate` warns —
   fill the bank first; do not invent.
2. A bullet may cite a number **only** if it is in `x_metrics`. `validate` flags every unsourced
   figure. Resolve **every** flag (add the metric if real, or drop the number) before shipping.
3. `validate` returning warnings ≠ permission to ship. Warnings are a review queue. A clean run
   is 0 errors and every zero-fab warning consciously resolved.

## Cover-letter mode

Write 3 short paragraphs: hook (why this company/role), proof (2-3 achievements from `x_master`
mapped to the JD's needs), close (call to action). Same zero-fab rule. Mirror the JD's exact
terminology for the keywords `tailor` surfaced. Output `out/cover-letter.md`.

## LinkedIn mode (folded in — a separate skill would be catalogue tax)

Generate `out/linkedin.md` from `profile.yaml` + optional target role. See
`references/linkedin.md` for the 2026 rules. Produce:
- **Headline** (≤220 chars, use them all): role + specialisation + key tools + value. Front-load
  the exact keywords recruiters boolean-search. Offer an "Open to Work" *text* variant.
- **About** (≤2,600 chars): the first ~300 show before "See more" → front-load the strongest
  keyword-rich sentence.
- **Skills**: ranked by recruiter-search value (name exact tools).
- **Keyword-gap table** vs a target role.

**Writing to the live profile is DEFERRED.** Producing text is this skill; *applying* it rides
the **D-stream LinkedIn MCP** (read-first, official-API-first, writes consent-gated). Automating
a real profile can breach LinkedIn ToS — **flag honestly, never auto-write.** Until that MCP
lands, output is copy-paste (very likely 80-90% the correct posture).

## Visual / design-led CV

For a designed CV, do **not** hand-typeset it here. Route to the owner's standing pipeline:
`ui-ux-pro-max` (palette/font) → `design-studio` / `figma` → export. That is the human/portfolio
variant. Alternatively, a JSON Resume HTML theme: `cvstudio.py json profile.yaml` then
`npx resumed render profile.resume.json --theme jsonresume-theme-<name>` (Node; pin a
single-column theme). Keep the *submitted* CV on the `ats` path regardless.

## Acceptance

A correct run: `build` on `assets/sample-profile.yaml` prints `SUCCESS:` and produces a 2-page
`Sam_Okafor_CV.pdf` whose PyMuPDF text layer passes the self-check (name, email, both companies,
the institution all present). Verified on this machine — see `../example-output/`.

## References (pulled on demand — do not inline)

`references/ats-rules.md` · `references/bullets.md` · `references/linkedin.md` ·
`references/regional-formats.md` · `references/schema.md`.
