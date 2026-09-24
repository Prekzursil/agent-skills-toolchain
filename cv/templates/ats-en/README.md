# `ats-en` — the English ATS resume

One PDF: **A4, single column, real text, two pages, engineering identity first.**
Everything it says comes from `../../profile.yaml`; this directory decides only the
*shape* and what the finished PDF has to satisfy.

```bash
cd ~/.agents/cv
.venv/Scripts/python.exe templates/render_template.py --template ats-en
```

Output (`out/templates/ats-en/`):

| File | What it is |
|---|---|
| `Andrei-Mihai_Visalon_ATS_EN.pdf` | the document |
| `…​.resolved.yaml` | the exact profile the PDF was built from, after the template's transforms — inspectable, and what the gates were run against |
| `…​.rendercv.yaml` | the RenderCV intermediate, after the document-level patches |
| `…​.manifest.json` | build provenance: profile sha256, sections, TODO markers, PDF sha256 |
| `…​.docgate.json` | the output-gate summary, including `status` |
| `…​.template-manifest.json` | the whole chain in one file: template sha256 → profile sha256 → PDF sha256 |

## Why it looks the way it does

An applicant-tracking system does not read a page, it reads a text layer. So:

- **One column.** A two-column CV parses as interleaved nonsense. `tools/verify.py`
  check C2 looks for a real column gutter and fails the render if it finds one.
- **No icons.** `header.connections.show_icons: false`. Icon fonts put private-use
  codepoints in the text layer; check D7 fails on any of them.
- **Left-aligned, never justified.** Typst hyphenates justified text, and a soft
  hyphen inside a keyword breaks exact ATS matching ("infra&shy;structure" is not
  "infrastructure"). Checks C5 and D7 both look for that damage.
- **A hyphen bullet**, not `●`. One less symbol glyph for a parser to mangle.
- **No photo, no date of birth, no nationality, no address.** Stripped by
  `build.py` on every `parsed` view and re-checked on the PDF by C6.
- **Two pages, and page 1 stands alone.** Check D6 requires the identity, a way to
  make contact, the summary, both employers and the first project on page 1, and
  fails if page 1 ends on an orphaned section heading.

## The two judgement calls in this template

**ORCID is not printed.** `profile.yaml` says the record today has zero registered
works and credits the bachelor's to the wrong university. A reviewer who clicks it
sees an empty, wrong record. It stays in `profile.yaml`; it is stripped from this
document until `TODO-CONFIRM.md` item 2 is closed.

**Two project stubs are not printed.** `tracelines` and `llm-anthology` exist in
`profile.yaml` with a `TODO-CONFIRM` description and nothing else. A project name
followed by "no verified description exists yet" advertises a gap without
describing anything, so they are excluded here and stay on the TODO list.

Everything else that is unknown IS printed as a visible `TODO-CONFIRM` marker —
the DINUPLAST title and dates, and the English CEFR level. That is deliberate:

> **The document's status is `DRAFT` while any marker is visible.** `docgate`
> prints it (`STATUS DRAFT`) and records it in `…​.docgate.json`. It becomes
> `SEND-READY` when the owner answers the questions in `../../TODO-CONFIRM.md` —
> not when someone deletes the markers.

## Known divergence from `profile.yaml: x_views[ats-en]`

The renderer reports it on every run (`DRIFT view contract: …`) rather than
silently picking a winner:

| | this template | `x_views[ats-en]` |
|---|---|---|
| section order | Summary · Experience · Projects · **Skills · Education** · Languages · Honors | Summary · Experience · Projects · **Education · Skills** · Honors · Languages |
| page budget | 1–2 | 1–3 |

The template's order is the one this lane was asked for; the editorial view is the
one recorded in the profile. They are a decision apart, not a bug — pick one and
make the other match.
