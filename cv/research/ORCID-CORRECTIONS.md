# ORCID-CORRECTIONS.md — ready-to-execute checklist for 0009-0001-8776-8498

**You must do this yourself.** It is your account, no agent here holds credentials for it, and none
were sought. Everything below is copy-paste-ready so the whole job is typing, not deciding.

**Record state captured:** 2026-09-24, live, unauthenticated.
`curl -H "Accept: application/json" https://pub.orcid.org/v3.0/0009-0001-8776-8498` → **HTTP 200**.
Every "current value" in section 1 is read from that response, not from any local file.

**Why it matters now:** your ChemRxiv byline carries this iD
(Crossref `authenticated-orcid: true`, verified 2026-09-24). A supervisor who clicks through from
the preprint lands on a record that today credits your bachelor's to the wrong university and lists
zero works. That is worse than no link.

---

## 1. Exact current state of the public record

Fetched 2026-09-24. Record created 2025-08-14 22:10 UTC; last modified **2026-07-21 00:46 UTC**.

### 1.1 Name

| Field (API) | Current value | Correct? |
|---|---|---|
| `given-names` | `Andrei` | NO — missing the Mihai |
| `family-name` | `Visalon` | yes |
| `credit-name` (UI: **Published name**) | **`null` — not set** | NO — nothing set |
| `other-names` (UI: **Also known as**) | **empty** | NO — nothing set |

### 1.2 Education and qualifications — exactly ONE entry

| Field (API) | Current value |
|---|---|
| put-code | `36830605` |
| organization | **University of Bucharest** — ROR `https://ror.org/02x2v6p15`, Bucharest, București, RO |
| `department-name` | `Computer Science` |
| `role-title` (UI: **Degree/title**) | `Bachelor's in Computer Science` |
| start-date | `2022-10-01` |
| end-date | `2025-06-04` |
| source | self-asserted (you), visibility public |
| created / last-modified | both 2026-05-31 09:22 UTC — never edited since |

**This single entry is the error.** It says the University of Bucharest awarded your bachelor's.
Titu Maiorescu University awarded it; UB is the master's, and the master's is not on the record at all.

### 1.3 Works

`activities-summary.works.group` = **`[]` — ZERO works registered.**
Neither the ChemRxiv preprint nor the Zenodo deposit is on the record.

### 1.4 Everything else

| Section | Current |
|---|---|
| employments · qualifications · distinctions · invited-positions · memberships · services · fundings · peer-reviews · research-resources | all **empty** (fine — not errors) |
| emails | `andrei-mihai.visalon@s.unibuc.ro` — **verified, public** (this is a Trust Marker; leave it alone) |
| addresses | `RO` |
| researcher-urls | LinkedIn (`/in/andrei-mihai-visalon-03141b170/`) + GitHub (`https://github.com/Prekzursil/`) |
| biography · keywords · external-identifiers | empty |

### 1.5 Nothing on the correction list already matches

I checked each requested correction against the live record before writing this.
**None of them is already done**, so no step is dropped. The list below is five steps, not padded.

---

## 2. The corrections

UI labels below are quoted from the live ORCID application bundle
(`https://orcid.org/main.6f13f66bcc6141fa-en.js`, downloaded and grepped 2026-09-24), so they are
the strings you will actually see. Two labels are marked `[label from general knowledge]` where the
bundle did not contain them — the path still works, the wording may differ by a word.

Start at **https://orcid.org/my-orcid** (sign in first).

---

### Step 1 — Normalise the name to "Andrei-Mihai Visalon"  ·  ~2 min

**Path:** `my-orcid` → left-hand personal card → pencil / edit icon next to your name → modal
**"Names"** → sub-heading **"Your names"**.

| Field in the modal | Type exactly this |
|---|---|
| **Given names** | `Andrei-Mihai` |
| **Family names** | `Visalon` *(unchanged — already correct)* |
| **Published name** | `Andrei-Mihai Visalon` |

The modal explains the third field as *"How you prefer your name to appear when credited."* It is
currently empty, which is why search results fall back to "Andrei Visalon".

Then click **Save changes**.

**Do this too — it costs 30 seconds and prevents a new mismatch.** Your two deposited works are
bylined **"Andrei Mihai Visalon"** (ChemRxiv) and **"Visalon, Andrei Mihai"** (Zenodo), both
unhyphenated. In the same modal, under **"Also known as"**, add:

```
Andrei Mihai Visalon
```

That way both the hyphenated and the unhyphenated form resolve to you, and the hyphenated form
(which matches your `andrei-mihai.visalon@s.unibuc.ro` institutional address) becomes the canonical
display name.

---

### Step 2 — Fix the bachelor's: University of Bucharest → Titu Maiorescu University  ·  ~3 min

**EDIT the existing entry — do not delete and re-create it.** Editing preserves put-code `36830605`
and its creation history; deleting loses them.

**Path:** `my-orcid` → **Education and qualifications** section `[label from general knowledge]` →
the row reading *"University of Bucharest: Bucharest, RO — Bachelor's in Computer Science"* →
pencil / edit icon → modal **"Education details"**.

| Field in the modal | Change to |
|---|---|
| **Organization** | `Titu Maiorescu University` — **pick the typeahead suggestion**, do not leave it as free text |
| **City** | `Bucharest` |
| **Country/Location** | `Romania` |
| **Department** | `Computer Science` *(leave as-is — see note below)* |
| **Degree/title** | `Bachelor's in Computer Science` *(unchanged — already correct)* |
| **Start date** | `2022` / `October` *(unchanged)* |
| **End date** | `2025` / `June` *(unchanged — see note below)* |

**The Organization field matters more than it looks.** As you type, ORCID offers registry matches
and shows an `Identify as:` line; if you ignore it the entry is saved as an
*"Unidentified organization"* and is not machine-readable. The correct match is:

> **Titu Maiorescu University** — ROR `https://ror.org/0367qb939` — Bucharest, Romania
> *(verified live against the ROR API, 2026-09-24: one active match, also indexed as
> "Universitatea Titu Maiorescu", "UTM", "TMU")*

Then click **Save changes**.

**Two judgement calls, both yours, neither blocking:**

- **Department.** `Computer Science` is accurate as a field of study and is the zero-risk choice.
  UTM's actual unit is the *Facultatea de Informatică* / **Faculty of Informatics** — but which
  faculty enrolled you is **not independently confirmed** in any source I can read, so I am not
  putting it in the table. Change it only if you know it first-hand.
- **End date.** The record says `2025-06-04`; `TODO-CONFIRM.md` item 6 still has your graduation
  month open, and `VERIFIED-FACTS.md` notes two old CVs disagreeing (May 2025 vs May 2024). The
  reported defect is the *institution*, not the date, so leave the date unless you know it is wrong.
  ORCID only stores year + month here anyway.

---

### Step 3 — Add the missing master's at the University of Bucharest  ·  ~3 min

**Path:** `my-orcid` → **Education and qualifications** → **+ Add** `[label from general knowledge]`
→ choose **Education** (not *Qualification*) → modal **"Education details"**.

| Field in the modal | Type exactly this |
|---|---|
| **Organization** | `University of Bucharest` — pick the ROR match **`https://ror.org/02x2v6p15`** (the record already carries this exact ROR, so it will be offered) |
| **City** | `Bucharest` |
| **Country/Location** | `Romania` |
| **Department** | `Faculty of Mathematics and Informatics` |
| **Degree/title** | `Master's in Informatics` |
| **Start date** | `2025` / **your true start month** — see below |
| **End date** | **leave blank** — a blank end date is how ORCID renders an ongoing affiliation |

Then click **Save changes**.

**On the department name.** `Faculty of Mathematics and Informatics` is the faculty's own official
English name — verified 2026-09-24 by fetching `https://fmi.unibuc.ro/en/` (HTTP 200; it is the
page `<title>` and appears 8x in the page). Use it. Note that your ChemRxiv record was deposited
with the *different* string *"Faculty of Mathematics and Computer Science"* — see section 5.

**On the two fields I will not guess for you:**

- **Degree/title.** `TODO-CONFIRM.md` item 5 has the exact programme name / specialisation open.
  `Master's in Informatics` is a safe, honest placeholder derived from `profile.yaml`
  (`area: Informatics`). Replace it with the programme's real name when you confirm it — this field
  is free text, so a later edit costs nothing. (Do **not** use LinkedIn's `MCA` label; that is a
  LinkedIn degree-type code, not the UB programme name.)
- **Start month.** `profile.yaml` carries `2025-09`, explicitly flagged **INFERRED**; the Romanian
  academic year conventionally starts **1 October**. Both are inferences. Type the real month.

---

### Step 4 — Register the ChemRxiv preprint as a work  ·  ~2 min

**Take the free route first.** ChemRxiv collected your iD through an authenticated ORCID sign-in —
Crossref's record for the DOI carries `authenticated-orcid: true` (verified live, 2026-09-24). That
means Crossref can write the work to your record itself, and it lands **source = Crossref with a
green check (a Trust Marker)** instead of self-asserted. That is strictly better than typing it in.

**4a — preferred.** `my-orcid` → **Notifications inbox** (bell icon) → find the Crossref
auto-update permission request → **Grant permissions**.

> A request for exactly this DOI was reported pending as of **2026-09-23 10:32 UTC** (from your own
> ORCID notification email). I cannot see your inbox, so **verify it is still there**. Granting it
> also auto-adds every future Crossref-registered DOI of yours — which is what you want.

**4b — fallback, if the request has expired or you would rather not grant standing permission.**
`my-orcid` → **Works** → **+ Add** → **Add DOI** `[label from general knowledge]` → paste:

```
10.26434/chemrxiv.15009306/v1
```

→ **Retrieve work details from DOI** → confirm the retrieved metadata matches the table below → add.

**Metadata you should see (verified live against the Crossref API, 2026-09-24, HTTP 200):**

| Field | Value |
|---|---|
| Title | Computational corroboration, at the sign level, that R-phenibut is the GABA-B eutomer: a two-sided alchemical transfer free-energy validation |
| Type | posted-content / **preprint** |
| Posted | 2026-09-22 |
| Publisher | American Chemical Society (ACS) — ChemRxiv |
| Author | Andrei Mihai Visalon (sole author), ORCID attached and authenticated |
| DOI | `10.26434/chemrxiv.15009306/v1` |

If anything differs from this table, stop and check the DOI before saving.

---

### Step 5 — Register the Zenodo deposit as a work  ·  ~3 min

**Add the CONCEPT DOI, not a version DOI.** The concept DOI always resolves to the newest version,
so it stays correct as you publish v4, v5, … DataCite currently holds **four** DOIs for this deposit
(concept + v1 + v2 + v3, all carrying your iD — verified live against the DataCite API, 2026-09-24).
Adding all four would put four near-identical rows on your record for one artefact.

**5a — preferred, deterministic, one clean entry.** `my-orcid` → **Works** → **+ Add** →
**Add DOI** `[label from general knowledge]` → paste:

```
10.5281/zenodo.22819600
```

→ **Retrieve work details from DOI** → confirm against the table below → add.

**Metadata you should see (verified live, Zenodo API `records/22836832`, HTTP 200 — the concept DOI
`22819600` 302-redirects there, which is correct concept-DOI behaviour):**

| Field | Value |
|---|---|
| Title | Data and code for two studies of the phenibut GABA-B axis: alchemical transfer free energies, and KCTD-subunit genetics with FAERS pharmacovigilance |
| Type | **Dataset** |
| Published | 2026-09-18 (v3) |
| Licence | CC-BY-4.0 |
| Creator | Visalon, Andrei Mihai — ORCID `0009-0001-8776-8498` attached |
| Affiliation on the deposit | University of Bucharest, Faculty of Mathematics and Informatics |
| Concept DOI | `10.5281/zenodo.22819600` · current version `10.5281/zenodo.22836832` |

**5b — optional upgrade.** `my-orcid` → **Works** → **+ Add** → **Search & link** → pick
**DataCite** from the *"Available Search & Link wizards"* list → authorise → it will find all four
DOIs by your iD. The gain is a green-check Trust Marker (source = DataCite rather than you); the
cost is that it may insist on adding every version. **If it will not let you select only the concept
DOI, back out and use 5a** — one correct self-asserted entry beats four redundant validated ones.

---

### Step 6 — Verify, from outside  ·  ~1 min

Do not trust the UI's own "saved" banner. Re-read the public API and check the four things that were
wrong:

```bash
curl -s -H "Accept: application/json" https://pub.orcid.org/v3.0/0009-0001-8776-8498 \
  | python -c "import json,sys; d=json.load(sys.stdin); \
p=d['person']['name']; print('published :', (p.get('credit-name') or {}).get('value')); \
print('given     :', p['given-names']['value']); \
[print('edu       :', s['education-summary']['organization']['name'], '|', s['education-summary']['role-title']) \
 for g in d['activities-summary']['educations']['affiliation-group'] for s in g['summaries']]; \
print('works     :', len(d['activities-summary']['works']['group']))"
```

**Pass condition — all four, or you are not done:**

- `published : Andrei-Mihai Visalon`
- `given     : Andrei-Mihai`
- two `edu` lines: **Titu Maiorescu University** (bachelor's) **and** University of Bucharest (master's)
- `works     : 2`

> The public API is cached briefly. If a change is missing, wait a few minutes and re-run before
> concluding it failed.

---

## 3. Estimated time

| Step | Estimate |
|---|---|
| 1 — name + also-known-as | 2 min |
| 2 — fix the bachelor's institution | 3 min |
| 3 — add the master's | 3 min |
| 4 — ChemRxiv preprint (4a inbox grant) | 2 min |
| 5 — Zenodo deposit (5a add by DOI) | 3 min |
| 6 — verify via the public API | 1 min |
| **Total, one sitting** | **~14 min (12–18 min realistic)** |

Add ~5 min if you take the 4b/5b routes, which involve an OAuth authorisation screen.

Nothing here is blocked on a TODO-CONFIRM answer. Two fields (the master's programme name, its
start month) would be *more precise* with answers to `TODO-CONFIRM.md` items 5 and 6, but both are
free-text/month fields you can edit later in seconds. **Do not delay the institution fix for them** —
the wrong university is the defect that actually costs you.

---

## 4. Already correct — do not touch

Leave these alone; changing them only risks breaking something that works.

- **Family name** `Visalon` — correct.
- **`andrei-mihai.visalon@s.unibuc.ro`** — verified and public. A verified institutional email
  domain is itself an ORCID Trust Marker and is the only one you have today.
- **Country** `RO`, **LinkedIn** and **GitHub** URLs — all present and correct.
- **The University of Bucharest ROR** `https://ror.org/02x2v6p15` already on the record — reuse it
  in Step 3 rather than creating a second UB organisation.
- **Empty employment / funding / peer-review sections** — empty is not an error, it is just empty.

---

## 5. Two related mismatches — flagged, NOT ORCID steps

Out of scope for this checklist, listed once because the premise is "a supervisor cross-checks".

1. **Faculty name on the preprint.** ChemRxiv/Crossref carries your affiliation as
   *"Faculty of Mathematics and Computer Science, University of Bucharest"*; the faculty's own
   official English name is *"Faculty of Mathematics and Informatics"* (verified at
   `fmi.unibuc.ro/en`, 2026-09-24), which is what Zenodo carries. Fixing a posted preprint's
   affiliation means asking ChemRxiv to revise the record — decide whether it is worth it.
2. **Babeș-Bolyai 2021–2022 (incomplete, no degree).** `TODO-CONFIRM.md` item 7 is still open and
   `x_listing_decision: PENDING` in `profile.yaml`. ORCID does allow an education entry with no
   degree awarded. **Deliberately not a step above** — it is your undecided call, and the
   "not completed, no degree awarded" wording would be mandatory if you list it.

---

## Provenance of every claim in this file

| Claim | Probe | Result |
|---|---|---|
| Live ORCID record state (§1) | `GET pub.orcid.org/v3.0/0009-0001-8776-8498` | HTTP 200, 2026-09-24 |
| Titu Maiorescu ROR = `0367qb939` | `GET api.ror.org/v2/organizations?query=Titu Maiorescu` | HTTP 200, 1 active match |
| UB faculty English name | `GET fmi.unibuc.ro/en/` | HTTP 200, page `<title>` |
| ChemRxiv metadata + `authenticated-orcid: true` | `GET api.crossref.org/works/10.26434/chemrxiv.15009306/v1` | HTTP 200 |
| Zenodo metadata, concept-to-version DOIs | `GET zenodo.org/api/records/22836832` (+ 302 from `22819600`) | HTTP 200 |
| 4 DataCite DOIs carry the iD | `GET api.datacite.org/dois?query=creators.nameIdentifiers.nameIdentifier:"0009-0001-8776-8498"` | HTTP 200, total 4 |
| ORCID UI field labels | downloaded + grepped `orcid.org/main.6f13f66bcc6141fa-en.js` | verified strings; 2 labels marked `[label from general knowledge]` |
| Crossref permission request pending 2026-09-23 | `cv/research/harvest-academic.md` row 4 (owner's own ORCID notification email) | **not re-verifiable without your login — confirm in the inbox** |
| DOIs located | `grep` over `cv/` and `cv/research/` | `harvest-academic.md`, `verified-academic.md`, `verified-programs.md` |
