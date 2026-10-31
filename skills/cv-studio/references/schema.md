---
title: schema
type: note
permalink: dqverify-repo-20261013/skills/cv-studio/references/schema
---

# profile.yaml schema — JSON Resume superset + x_ extensions

`profile.yaml` is a [JSON Resume](https://jsonresume.org/schema/) document (MIT open standard)
plus three `x_` extensions. `cvstudio.py` maps it onto RenderCV's YAML (ground-truth schema
below). `cvstudio.py json` exports a clean JSON Resume with the `x_` blocks stripped, so your
data stays portable to any of the 400+ `jsonresume-theme-*` renderers.

## Standard JSON Resume blocks (what cv-studio consumes)

| Block | Key fields | Renders as (RenderCV) |
|-------|-----------|-----------------------|
| `basics` | `name, label, email, phone, url, summary, location{city,region,countryCode}, profiles[{network,username,url}]` | header + Summary |
| `work[]` | `name`(company), `position, location, startDate, endDate, summary, highlights[]` | Experience entries |
| `education[]` | `institution, area, studyType, location, startDate, endDate, score, courses[], highlights[]` | Education entries |
| `skills[]` | `name`(category), `keywords[]`, `level` | Skills one-liners `Category: kw, kw` |
| `projects[]` | `name, url, description, startDate, endDate, highlights[]` | Projects (name links to url) |
| `publications[]` | `name`(title), `publisher`(journal), `releaseDate, url, doi, authors[]` | Publications entries |
| `awards[]` | `title, awarder, date` | bulleted Awards & Honors |
| `certificates[]` | `name, issuer, date, url` | Certifications one-liners |
| `languages[]` | `language, fluency` | Languages one-liners |
| `volunteer[]` | `organization, position, startDate, endDate, highlights[]` | Volunteering (like Experience) |
| `interests[]`, `references[]` | `name` / `name, reference` | text |

## x_ extensions (the zero-fabrication guardrail — stripped on JSON export)

```yaml
x_master:                        # per-role achievement bank — the ONLY bullet source
  "Company Name|Position Title": # key MUST equal "<work.name>|<work.position>"
    - long-form achievement note 1
    - long-form achievement note 2
x_metrics:                       # verified figures only; a bullet may cite a number iff listed
  - "12,000+ players (telemetry 2023-Q4)"
  - "3 days -> 40 minutes (measured over 6 versions)"
x_targets:                       # optional saved JDs for `tailor`
  - id: some-role
    file: some-job.md
```

`validate` checks: every `work` role has a matching `x_master` key (else WARN: unsourced); every
numeric figure in a highlight traces to `x_metrics` (else WARN: verify). Resolve all warnings.

## RenderCV target schema (ground truth, v2.8, from the installed package)

- `cv:` → `name, headline, location, email, phone, website, social_networks[{network,username}]`,
  `sections:{Title: [entries]}`.
- **Supported `network` values** (strict enum — others fail the render): LinkedIn, GitHub,
  GitLab, IMDB, Instagram, ORCID, Mastodon, StackOverflow, ResearchGate, YouTube, Google Scholar,
  Telegram, WhatsApp, Leetcode, X, Bluesky, Reddit. cv-studio canonicalises case and skips
  unknown networks with a warning. Format rules: ORCID `XXXX-XXXX-XXXX-XXX`, StackOverflow
  `id/name`, Mastodon `@user@domain`, YouTube no leading `@`.
- `design.theme` ∈ `classic, engineeringresumes, sb2nov, engineeringclassic, moderncv`.
- Dates: `YYYY-MM` or `YYYY` or ISO; empty end → `present`.

## YAML gotchas
- **Quote any string that starts with `Word:`** — a bare leading colon parses as a YAML mapping
  (`- Capstone: foo` becomes `{Capstone: foo}`). cv-studio recovers it, but quote it to be safe.
- Use `>-` for multi-line summaries. Keep dates as `YYYY-MM` strings.

---
JSON Resume: jsonresume.org/schema (MIT). RenderCV schema: docs.rendercv.com +
`rendercv/schema/models/` in the installed package.