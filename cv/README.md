# The CV data model, in plain language

Everything in this folder renders from **one file**: `profile.yaml`.

There is no second copy of the facts. A resume, a research profile, a Romanian CV, a cover
letter and a LinkedIn About are all *views* of that one file. If a fact is wrong on three
documents, it is wrong in one place here, and fixing it here fixes all three.

---

## 1. What `profile.yaml` is

It is a [JSON Resume](https://jsonresume.org/schema/) document — a widely used open standard
for CV data — plus a set of extra blocks whose names start with `x_`. The standard blocks
(`basics`, `education`, `work`, `projects`, `publications`, `awards`, `skills`, `languages`)
hold the ordinary CV content. The `x_` blocks are the honesty machinery. They are stripped
out when the file is exported as portable JSON Resume, so they never leak into a document.

Two of the `x_` blocks (`x_master`, `x_metrics`) come from the existing `cv-studio` skill.
The rest (`x_views`, `x_forbidden`, `x_style`, `x_privacy`, `x_decisions`,
`x_data_and_software`) are additions for this profile.

---

## 2. The three layers, and why they exist

### Layer 1 — the facts (standard blocks)

`basics`, `education`, `work`, `projects`, `publications`, `awards`, `skills`, `languages`.
Ordinary CV content. Every entry carries an `x_provenance` label:

| Label | Meaning |
|---|---|
| `VERIFIED` | Checked this session against a source that can be re-checked. |
| `INFERRED` | A reasonable reading of verified material, not itself verified. Must be re-checked before it is treated as fact. |
| `TODO-CONFIRM` | Unknown. The owner must supply it. It is never guessed, and in the worst cases it deliberately blocks a render. |

Entries also carry `x_todo` lists (the specific questions), `x_note` (context a writer needs),
`x_link_gate` (why a URL must not be published yet) and `x_forbidden_here` (claims that are
banned for that specific entry).

### Layer 2 — the achievement bank (`x_master`)

`x_master` is the **only sanctioned source for bullets**. It holds long-form notes about each
role, project, award and output — more detail than any document will use, written out in full.
When a document needs a bullet, the bullet is *compressed out of* `x_master`; it is never
composed from memory or from a general impression of the person.

Work entries are keyed exactly `"<company>|<position>"` (that exact spelling is what the
`cv-studio` lint looks for). Projects, awards, publications and data deposits use
`project:`, `award:`, `publication:` and `data:` prefixes.

If a role has no bank, it gets no bullets. That is the rule, and it is the entire point.

### Layer 3 — the numbers (`x_metrics`)

**A number may appear in a document if, and only if, it appears in `x_metrics`.**

Each metric is a small record:

```yaml
- id: grace-ensemble-f1
  value: "0.743 dev strict macro-F1 (softmax-averaging ensemble)"
  provenance: M
  renderable: true
  how_known: Public technical report; dev split, strict matching.
```

`provenance` is the load-bearing field:

| Code | Meaning | Renders? |
|---|---|---|
| `M` | **Measured** — directly observed or counted, and re-checkable. | yes |
| `E` | **Estimated** — approximate. Must render with a hedge word ("roughly", "about", "~"). | yes, hedged |
| `B` | **Borrowed** — second-hand, someone else's measurement. | **never** |
| `U` | **Unknown** — no traceable source. | **never** |

`how_known` is a sentence saying *how* the figure was obtained, so a future reader (or the owner
in an interview) can reproduce it. `renderable: false` marks a figure that is real and measured
but is **not CV content** — for example the 63,363 branches in the momentstudio repository, or
the trade-registry record for DINUPLAST. Those are internal facts that explain a decision
(why a link is withheld), not achievements.

Today `x_metrics` holds 38 entries: 31 that may render and 7 held back as internal or
unresolved-scope. There are no `B` or `U` entries, and none may be added without a
`how_known`.

---

## 3. The guardrails

### `x_forbidden` — the kill list

A flat list of claims that must never appear on any surface, in any language: inflated PR and
contribution counts, "40+ MCP servers", "peer-reviewed publication", "Reframe v1.4.2", any
adoption figure for Reframe / tracelines / llm-anthology, and the highest-severity item,
"finished 4th overall at GRACE" — which traces to a fabricated document and would end a
doctoral candidacy on its own. A renderer or lint that encounters any of these must **fail
closed**, not warn.

### `x_style` — the provenance verbs

Not stylistic taste. Each rule is the difference between a true and a false sentence:

- *ships*, not *passing* — "ships 8,000 test functions", never "8,000 passing tests".
- *curates* vs *authored* — a **415-skill tree curated**, of which **~140 authored**.
- *operates* vs *wrote* — multiplexers are operated; the 18 MCP servers were written.
- Every ChemRxiv mention carries the word **preprint**. The second manuscript is **in
  preparation** — never "submitted", never "under review".
- The Zenodo deposit files under **Data and software**, never under Publications.
- **open-source** is used only for a repository that actually has a LICENSE file.
- The GRACE metric sentence renders **in full or not at all**.

### `x_privacy`

No photo, date of birth, nationality, marital status or street address on any machine-parsed
view. City and country only. A4 everywhere.

### `x_decisions`

The owner's decisions (G-1, G-2, G-3, G-5, G-6, G-10, G-18) recorded so a later renderer does
not silently re-open them: the doctorate is committed; the research identity leads the academic
documents while the engineering resume leads with engineering; pbinfo goes in Honors, named as
Romania's national **high-school** judge, with the full numbers and an "as of September 2026"
date; momentstudio is paid client work and belongs in Experience; the research profile is built
first; Personal-Finance-Management stays on the CV with honest derivation wording; SemEval-2027
is skipped.

---

## 4. The outputs (`x_views`)

Nine named views, each a different audience reading the same facts:

| View | Audience | Leads with |
|---|---|---|
| `research-profile` | Doctoral supervisors (**built first**, December deadline) | researcher |
| `ats-en` | English ATS and recruiter keyword search | engineering |
| `ro` | eJobs, BestJobs, Hipo, Romanian public competitions | engineering |
| `academic` | Committees, scholarships, grants | researcher |
| `designed` | A human reading a portfolio PDF | engineering |
| `cover` | Per-application cover letters | — |
| `linkedin` | LinkedIn headline / About / skills | — |
| `europass` | EU applications requiring Europass | — |
| `platform-packs` | Field-sized snippets per job platform | — |

Each view declares its section order, whether the incomplete Babes-Bolyai year is included
(`include_ubb`, currently `false` everywhere pending the owner's decision), page size and
privacy rules. `x_targets` lists the five role families the profile is aimed at, so a tailored
version can be generated per family.

The one hard technical rule: the **submitted** CV is typeset single-column with real text
(the `ats-en` path). A multi-column designed graphic parses into interleaved nonsense in an
applicant-tracking system. Design is for the `designed` view only.

---

## 5. How to change something

1. **A new fact** → add it to the right standard block with an `x_provenance` label, and add a
   long-form note to `x_master`.
2. **A new number** → add an `x_metrics` entry first, with `provenance` and `how_known`. Only
   then may a bullet cite it.
3. **Something unknown** → write a `TODO-CONFIRM` marker and add the question to
   `TODO-CONFIRM.md`. Never fill the gap with a plausible guess.
4. **A claim you cannot trace** → delete it. An untraceable claim on a document that goes to
   employers and to a doctoral committee is the single worst failure mode of this system.

## 6. Validating

```bash
# parse check (PyYAML, global Python)
C:/Python314/python.exe -c "import yaml;yaml.safe_load(open(r'C:\Users\prekzursil\.agents\cv\profile.yaml',encoding='utf-8'))"

# cv-studio schema + zero-fabrication lint
C:/Python314/python.exe C:/Users/prekzursil/.agents/skills/cv-studio/scripts/cvstudio.py validate profile.yaml
```

**Known caveat — the shipped lint fails OPEN.** On 2026-09-24 `cvstudio.py validate` reported
`SUCCESS: 0 errors, 0 warnings` on this file *even though* the DINUPLAST entry has the literal
string `TODO-CONFIRM` as its end date and the momentstudio entry has two empty date fields.
The shipped lint only scans `work[].highlights` for unsourced figures, never
`projects`/`education`/`summary`/`publications`, and its warnings never change the exit code.
Do not read a green `validate` as permission to ship. A replacement fail-closed lint is a
separate work item; until it lands, the guardrails in this file are enforced by the writer,
not by the tool.

## 7. Files here

| File | What it is |
|---|---|
| `profile.yaml` | The master profile. The only place facts live. |
| `README.md` | This file. |
| `TODO-CONFIRM.md` | Every gap the owner must fill, ordered by how much it blocks. |
