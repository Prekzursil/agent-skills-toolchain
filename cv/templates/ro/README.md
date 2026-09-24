# `ro` — the Romanian rendering

The same resume as `../ats-en`, in Romanian: same facts, same order, same figures,
Romanian section labels, Romanian dates, Romanian text.

```bash
cd ~/.agents/cv
.venv/Scripts/python.exe templates/render_template.py --template ats-en   # build this first
.venv/Scripts/python.exe templates/render_template.py --template ro
```

The English document is built first because the Romanian one is measured against
it (check D10, below).

## How a translation stays honest

`transform.translate` is a table of pairs: an exact string that exists in
`../../profile.yaml`, and its Romanian restatement. Nothing else may enter the
document. `render_template.py` enforces three rules before a single pair is
applied:

1. **The digits must be identical, in the same order.** A translation restates a
   verified number; it never renotates one. This caught a real defect while the
   template was being written: "Ranked **first** all-time" had been translated as
   "Locul **1** all-time", which introduces a figure `1` that no `x_metrics` entry
   licenses. The build refused it. It now reads "Locul întâi".
2. **A `TODO-CONFIRM` marker cannot be added or dropped.** An unresolved gap stays
   visible in every language.
3. **A pair whose source string is no longer in the profile is reported as
   drift.** That bullet then renders in English — visibly, in a `DRIFT` line —
   rather than silently going missing or being re-invented. Set
   `transform.on_drift: fail` to make it a hard stop instead.

### Two notation decisions

**Figures keep the source notation**: `1,016`, `32,500`, `0.743` — not the
Romanian `1.016` / `0,743`. A Romanian thousands separator reads as a decimal
point to every downstream parser (an ATS, `tools/zerofab.py`, a recruiter's
spreadsheet), and the digit-parity rule above depends on the figure staying
byte-identical to the verified one.

**Proper nouns are not translated**; institution names are. `momentstudio.ro`,
`ZHMModSDK`, `Reframe`, `FastAPI`, `Python` are identities and search keys — a
Romanian recruiter searches for them in English too. But a Romanian university has
a Romanian name, and that is the name a Romanian reader verifies:
*Universitatea din București, Facultatea de Matematică și Informatică*;
*Universitatea Titu Maiorescu*.

## Diacritics

Romanian uses **comma-below** letters — `ș` U+0219, `ț` U+021B (and `Ș` U+0218,
`Ț` U+021A) — not the cedilla look-alikes `ş` U+015F / `ţ` U+0163 that Windows
code pages and old fonts substitute. Check D8 fails the document if a cedilla form
reaches the text layer, and fails it if a Romanian rendering contains no
comma-below letter at all (the tell that a locale pack silently fell back to
ASCII). XCharter was measured on this box against the full set `Ș Ț ș ț Ă ă Î î Â
â`: all present, no substitution.

**The name never takes diacritics.** "Andrei-Mihai Visalon", hyphenated, unaccented,
on every surface — D8 fails the document otherwise.

## What the Romanian document fixes beyond translation

- **Dates.** `build.py`'s Romanian locale pack supplies the months (`ian`, `feb`,
  … `dec`) and `prezent`. The template adds what the pack leaves in English:
  `phrases.degree_with_area`, which otherwise prints "Licență **in** Informatică".
  It now reads "Licență, specializarea Informatică".
- **The DINUPLAST date line.** `build.py` refuses to guess an untypeable date and
  writes an English `Dates: …` line. `transform.date_notes` replaces it with
  `Perioada: 2021-05 – TODO-CONFIRM (datele exacte, de confirmat)`.
- **The bachelor's years.** `profile.yaml` knows only `2022` and `2025`; RenderCV
  expands a bare year into a month and prints "ian 2022 – ian 2025", asserting
  months nobody verified. `intermediate.entries` prints the years as written. A
  patch like that may only *remove* precision — `render_template.py` refuses any
  patch whose value introduces a digit the entry did not already have.

## Expansion

Romanian runs about 10% longer than English. Measured on this pair: **1.12×** the
English document's text layer, still **2 pages**. The template declares
`max_expansion: 1.20` against the English PDF, so a future edit that inflates the
Romanian text fails the build (check D10) instead of quietly spilling onto a third
page. The layout absorbs the difference through slightly tighter entry spacing
(`0.28cm` / `0.12cm` against the English `0.32cm` / `0.14cm`), not a smaller font.

## Romanian public competitions

Some of them require personal data — CNP, address — on **their own forms**. That
goes on the form. It never goes in `profile.yaml` and never in a machine-parsed CV
view (`x_privacy`, check C6).
