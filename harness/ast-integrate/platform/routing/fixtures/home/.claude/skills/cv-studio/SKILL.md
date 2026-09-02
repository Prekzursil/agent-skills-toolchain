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

### Modes
### The pipeline (deterministic; scripts do the mechanics, you do the content)
### The zero-fabrication discipline (non-negotiable)
### Cover-letter mode
### LinkedIn mode (folded in — a separate skill would be catalogue tax)
### Visual / design-led CV
### Acceptance
### References (pulled on demand — do not inline)
