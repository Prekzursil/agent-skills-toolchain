---
title: regional-formats
type: note
permalink: dqverify-repo-20261013/skills/cv-studio/references/regional-formats
---

# Regional CV/resume conventions

The same `profile.yaml` serves every region; adjust content + photo/personal-data per target.
Default cv-studio output is **US-style** (no photo, no personal data). Set the intended region in
your prompt when asking for a build.

## US (default) — "resume"
- 1 page (early career) → 2 pages (senior). **No photo, no DOB, no marital status, no nationality.**
- Reverse-chronological. Summary optional. Metrics-heavy. Letter page size.
- No references on the CV ("references available on request" is unnecessary — omit).

## UK — "CV"
- 2 pages standard. **No photo/DOB** (equality law). A4 page size.
- A short personal statement up top is common. Spelling: "optimise", "programme", "centre".
- Reverse-chronological; may include a brief "Interests" line.

## Australia / New Zealand
- 2-3 pages accepted (more detail than US). **No photo.** A4.
- Often include a short list of referees at the end (or "available on request"). Include
  visa/work-rights status if relevant. AU/NZ English spelling.

## Continental Europe (DE/FR/etc.) & Europass
- Photo + DOB still common in some countries (DE historically) — but increasingly optional;
  omit if unsure. A4.
- **Europass** (europass.europa.eu) is a standardised EU format (now a JSON-LD W3C Verifiable
  Credential). Adopt **only** if a specific EU public-sector/academic role requires it — it is a
  compliance format, not a design win. Low priority otherwise.

## Academic CV (any region)
- Longer, no page limit. Lead with Education, Publications, Grants, Talks, Teaching.
- Reverse-chronological within each section. Use RenderCV's `publications` entries + full author
  lists (bold your name). The `moderncv`/`classic` themes suit this.

## Page size
RenderCV defaults to US Letter. For UK/EU/AU set A4 via the design block:
`design.page.size: a4` (see `rendercv render Sample.yaml` design comments, or pass a design file).

---
Regional guidance is general best-practice (paraphrased from public career-services guidance and
jezweb/claude-skills' region-aware *idea* only — no text vendored; that repo has no licence).
Verify current local norms for a specific country before submitting.