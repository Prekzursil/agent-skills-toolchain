# Verified academic / research position — independent check of harvest-academic.md

Checker: research-lane subagent. Date of checks: 2026-09-23 (all network calls made this session).
Scope: the research output only — ChemRxiv preprint, Zenodo deposit, FAERS analysis, GRACE @ IberLEF 2026.
**Education claims in harvest-academic.md §7 are WRONG and were ignored** (corrected ground truth: BSc =
Titu Maiorescu 2022-2025; UB = Master's 2025-2027, in progress; UBB 2021-2022 incomplete). The ORCID
education entry naming UB as the bachelor's awarder is a live, public defect — see §6.

Every line is tagged VERIFIED (I fetched/ran it myself this session), INFERRED, or COULD NOT DETERMINE.
Raw evidence files are in this scratchpad and are re-checkable.

---

## 0. What I did differently from the harvest

The harvest is mostly accurate but I found **three material errors** by going to the evidence:

1. **"Public leaderboard NOT retrievable / login-gated" (harvest row 22) is FALSE.** The GRACE
   final-evaluation leaderboard is public and unauthenticated at
   `https://www.codabench.org/api/phases/26223/get_leaderboard/` (HTTP 200, 28 rows, 25 KB).
   I pulled it. It changes the whole GRACE assessment — see §4.
2. **Commit count wrong.** Harvest says 16 commits; the API returns **36** on `master`
   (`gh_commits.json`). All human commits are his (`Prekzursil` / `Andrei Mihai Visalon`); the rest are
   dependabot. No second human contributor in git history.
3. **The deposit's headline reproducibility claim does not survive a third-party run.** I downloaded the
   archive and ran the verifier exactly as its README instructs. It fails immediately. See §3.

---

## 1. ChemRxiv preprint — VERIFIED, the single strongest research asset

Source I checked: `https://api.crossref.org/works/10.26434/chemrxiv.15009306/v1` -> `cx_chemrxiv.json`.

| Field | Value | Tag |
|---|---|---|
| DOI | 10.26434/chemrxiv.15009306/v1 | VERIFIED |
| Type | `posted-content` / subtype `preprint` (NOT a journal article) | VERIFIED |
| Title | "Computational corroboration, at the sign level, that R-phenibut is the GABA-B eutomer: a two-sided alchemical transfer free-energy validation" | VERIFIED |
| Author | Andrei Mihai Visalon, **sole author**, `authenticated-orcid: true` for 0009-0001-8776-8498 | VERIFIED |
| Affiliation on record | "Faculty of Mathematics and Computer Science" + "University of Bucharest" — correct for a current UB master's student | VERIFIED |
| Posted / deposited | posted 2026-09-22; Crossref created + deposited 2026-09-23T05:39:42Z; indexed 06:09Z | VERIFIED |
| Peer review | none. No `relation` block, no journal version, `is-referenced-by-count` = 0, `reference-count` = 0 | VERIFIED |
| Licence | Crossref carries **no licence field** | VERIFIED |
| Crossref author sweep | `query.author=Visalon` -> 9 works; 8 are **Ioana / Ioana Octavia Visalon** (theatre and voice studies, Univ. Galati) = a different person; exactly **1** is his | VERIFIED |

**Link reachability caveat (matters for a CV that prints the DOI).** `doi.org` resolves correctly (302 to
chemrxiv.org). But chemrxiv.org returns **HTTP 403 "Just a moment..." (Cloudflare)** to every automated
client I tried — plain curl, browser-UA curl, the public engage API, and headless Chromium via Playwright.
Control test: **chemrxiv.org's own homepage and two unrelated ChemRxiv items also 403**, so this is a
site-wide bot block, not something wrong with his item. INFERRED (high, ~90%): a human in a normal browser
sees the page fine. **He should confirm in 10 seconds by opening his own DOI while logged out**, because the
CV depends on that link working for a stranger.

**Indexing status today — VERIFIED absences.** OpenAlex `works/doi:...` -> **404** (not ingested).
Europe PMC `AUTH:"Visalon"` -> **hitCount 0**. arXiv `all:Visalon` -> **0 entries**. ORCID `/works` ->
**zero work groups**. So today the preprint exists in Crossref and on ChemRxiv, and nowhere else.
Expect OpenAlex / Europe PMC ingestion within weeks; nothing to do but wait and re-check.

## 2. Zenodo data/code deposit — VERIFIED

Sources: `zenodo.org/api/records/{22819601,22836690,22836832}` -> `zen_*.json`; the archive itself.

- Concept DOI **10.5281/zenodo.22819600** resolves (302 to zenodo.org). Record page HTTP 200, public.
- Three versions: v1 2026-09-17 (21.9 MB), v2 2026-09-18 (24.7 MB), v3 2026-09-18T19:25:18Z (35.5 MB).
- Title: "Data and code for two studies of the phenibut GABA-B axis: alchemical transfer free energies,
  and KCTD-subunit genetics with FAERS pharmacovigilance". Type **dataset**, licence **CC-BY-4.0**, open.
- Creator "Visalon, Andrei Mihai", ORCID attached, affiliation "University of Bucharest, Faculty of
  Mathematics and **Informatics**" — inconsistent with the ChemRxiv string ("Mathematics and Computer
  Science"). Minor, but a reviewer who cross-checks sees two faculty names. Fix on the next version.
- **Usage stats are tiny and public: 11 views / 2 downloads.** Never put a "used by" or "impact" claim on this.
- OpenAlex holds 4 works for him, **all four are these Zenodo dataset DOIs**, 0 citations, h-index 0, and his
  author record is **split across two OpenAlex IDs** (A5151992415, A5152109704).

**Integrity check I ran myself (strong, third-party repeatable):** downloaded
`phenibut_deposit_2026-09-18_v3.zip`, MD5 = `3501eeacf141c955eb9626a4135f72e4` (matches the Zenodo-recorded
checksum). 634 entries. Recomputed SHA-256 for **every one of the 630 files listed in `MANIFEST.sha256`:
630 match, 0 mismatches, 0 missing.** All six production edges carry their per-replica data
(`atm_drains/{seed1,seed2,seed3,validation_R-phenibut_to_arbaclofen,a2d1_h2cl_...,a2d1_gpn_control_...}`,
22-23 `.out` files each). Two stored `uwham_result.json` files reproduce published numbers exactly
(seed2 ddG 0.63325 vs published 0.633; gabapentin->pregabalin 12.8464 vs 12.846).

## 3. The "self-verifying archive" claim — OVERSTATED, and I can prove it

The deposit README says the published free energies "can be **re-derived from it alone**... That is verified
rather than asserted", instructs `python scripts/verify_deposit_selfsufficient.py`, and claims reproduction
of all six edges "to within 0.0004 kcal/mol".

I extracted the archive and ran exactly that command with a clean Python 3.14:

```
ModuleNotFoundError: No module named 'atom_openmm'
```

Root cause, read from the shipped source (`zen_x/scripts/verify_deposit_selfsufficient.py`):

- `VENDOR = r"D:\Research\projects\phenibut\compute\scaleway\_vendor"` — an absolute path on **his** machine;
  `atom_openmm` is **not** in the archive and there is **no requirements / environment / pyproject file**
  anywhere in it.
- `STAGE = r"D:\Research\projects\phenibut\deposit_stage\atm_drains"` — also absolute to his machine. Nothing
  resolves relative to the script. No env-var or CLI override exists.

To isolate the second fault I stubbed the missing import and re-ran. Output:

```
seed1    *** NOT IN DEPOSIT
... (all six edges) ...
DEPOSIT NOT SELF-SUFFICIENT: 6 edge(s) failed to reproduce.
```

i.e. **run from inside the deposit, the deposit's own verifier declares the deposit not self-sufficient.**

Fair reading: the **data** genuinely is there (see §2), so this is a packaging bug, not a data or honesty
problem, and it is a ~10-line fix (resolve `STAGE` from `__file__`, pin or vendor `atom_openmm`, add a
requirements file). But **until it is fixed, "anyone can re-derive the published free energies from the
archive" is false**, and it is exactly the claim a reproducibility-minded reviewer would test first. This is
the highest-value thing he can fix today: it converts an overstated line into his most distinctive one.

## 4. GRACE @ IberLEF 2026 — the real status, including the official leaderboard

### 4a. Competition structure — VERIFIED live
`https://www.codabench.org/api/competitions/13280/` (`cb_comp.json`): "GRACE @ IberLEF 2026: Granular
Recognition of Argumentative Clinical Evidence", created 2026-01-28 by `idelaiglesia004`, published.
**Exactly three phases, all closed, and there is no post-evaluation or open phase:**

| Phase | Window (UTC) | Status |
|---|---|---|
| Pre-Release | 2026-02-21 -> 2026-03-24 | Previous |
| Development | 2026-03-24 -> 2026-04-22 | Previous |
| **Final Evaluation** | **2026-04-22 22:00 -> 2026-05-17 21:55** | Previous |

### 4b. The official leaderboard IS public — I retrieved it
`https://www.codabench.org/api/phases/26223/get_leaderboard/` -> 200, 28 rows, both tracks, with each
submission's **fact-sheet team name**. Track 1 ("GRACE@IberLEF2026 Final Evaluation - Track 1", task 32158)
contains four teams. Best row per team:

| Team (Codabench account) | Overall | Subtask 1 | Subtask 2 |
|---|---|---|---|
| SINAI (`lucasinai`) | 0.264 | **0.369** | 0.160 |
| Verbanex AI (`andre08`) | 0.192 | 0.313 | 0.070 |
| **bionlp (`alexcristea72`)** | **0.184** | **0.368** | **0.000** |
| UMUTeam (`ronghaopan`) | 0.146 | 0.278 | 0.015 |

Nine of the 28 rows belong to `alexcristea72`, team name **"bionlp"** (one row "BIONLP"), pipeline names
`MRBERT_SOLO`, `MRBERT_SOLO_e4`, `deb`, `quad`, `x`, `y`, `z`, `a`, `b`; subtask-2 score 0.000 on every one
(components only, no relations). Track 2 is a separate task (32159) with VicomNLP, UMUTeam, FranRodrigo.

### 4c. Is "bionlp" him? — strong circumstantial link, identity NOT closed
Evidence **for**: his GitHub repo's README literally opens `# bionlp — ToolUniverse Workspace` and the GRACE
work lives inside that workspace; the harvest records his local working dir as `...\Downloads\bionlp\`; the
pipeline names match his model lineup exactly (MrBERT, deberta, a 4-model "quad" ensemble — the vault records
a "geometric 4-model ensemble" in the early paper draft); subtask-2 = 0 matches a components-only system;
and the best Subtask-1 score **0.368** matches the "**36.83**" figure his own notes flag as appearing only in
a draft PDF and on "an external leaderboard".
Evidence **complicating it**: his Kaggle handle is `prekzursil` (verified in
`FINAL/kaggle_runs/*/kernel-metadata.json`, e.g. `"id": "prekzursil/gt1-mdb-s42"`), while the Kaggle dataset
those kernels attach is `alexcristea72/iberlef-grace` — so **`alexcristea72` is a different handle**, either
a second account of his or a collaborator who hosted the data and made the submissions.
Codabench exposes no public user lookup (404) and both Kaggle profiles are JS shells with no readable name.

**COULD NOT DETERMINE from public evidence.** One question to him settles it: *"Is the Codabench account
`alexcristea72` / team `bionlp` yours, or a teammate's, and were you a registered member of that team?"*
Until answered, **no leaderboard result may appear on the CV**, and the CV must not say "solo" either.

### 4d. What the leaderboard does and does not support
- "**2nd on Subtask 1**" — the number is right *if* the team is his: bionlp 0.368 vs SINAI 0.369, second by
  **0.001**, out of **four** teams. Honest form: "2nd of 4 teams on Track-1 Subtask 1 (0.368 vs 0.369)".
  Omitting "of four" is the kind of thing that dies badly in an interview.
- "**4th overall**" — **unsupported by the public leaderboard on any reading**: by Track-1 overall score
  bionlp is **3rd of 4**; across the whole competition (both tracks, 6 teams) it is **6th of 6**. Drop it.
- **The June all-9 system cannot be the officially scored one.** Final Evaluation closed 2026-05-17 21:55 UTC;
  there is no later phase; the entire Modal 27-cell sweep, the 0.7434 ensemble and every
  `blind_submission_*.json` were produced on **2026-06-06/07** (commit "add Modal 27-cell sweep, ensemble, and
  Track-1 report deliverables", 2026-06-07). So the scored entry was the earlier, weaker system — consistent
  with a 0.368 test score — and the strong number is a **post-hoc dev result**, not a ranked one.
  The harvest's guess that the June work "went to a post-evaluation/open phase" is **refuted**: no such phase exists.

### 4e. The technical numbers — VERIFIED from machine-readable source
I pulled `FINAL/ensemble_results.json` raw from the repo rather than trusting the report, and confirmed the
local report copies are byte-identical to the repo blobs (git-blob SHA-1 match, both PDF and DOCX).

- 27 runs = 9 backbones x 3 seeds (42/100/2026); all 27 have a dev score. VERIFIED.
- All-9 softmax-mean ensemble, official scorer, **dev strict macro-F1 = 0.7434**; top-3 0.7416; greedy 0.7426. VERIFIED.
- Best backbone by 3-seed mean: mDeBERTa-v3-base **0.7046 (sd 0.035)**. VERIFIED.
- **Best single run: mDeBERTa-v3 seed 42 = 0.7368.** VERIFIED — and this is the trap. The report's
  "**+3.9-point gain**" compares the ensemble against the best backbone's *seed mean*. Against the best
  individual checkpoint the gain is **+0.7 points**. The report's defence ("no selection bias") is legitimate,
  but the bare phrase "+3.9 points over the best single model" invites a reviewer to open the JSON and find 0.737.
- Blind-test artefact: 2,474 abstracts, 26,640 sentences, **11,752 predicted components** (Premise 7,872 /
  Claim 3,717 / MajorClaim 163), **0 offset mismatches** after trimming (135 raw). VERIFIED in the JSON.
- Scale caveat worth knowing before quoting any of it: dev is **50 abstracts** and the ensemble's MajorClaim
  cell is **tp=4, fp=4, fn=5**. The 0.743-vs-0.737 difference is a handful of spans.
- Repo hygiene: `grace-iberlef-2026` is public, 0 stars, **no licence**, 3 open issues, last push 2026-08-02,
  and its front-page README is the *ToolUniverse workspace* readme, not a GRACE readme. A supervisor who
  clicks it does not land on the work. **No `main.tex`, no `paper/` directory, no PDF other than the technical
  report** — 400 blobs scanned. The report itself carries **no author line, no affiliation, no team name and
  no official score** (grepped: zero matches for visalon / andrei / author / bucharest / team / bionlp).

### 4f. Working notes / system paper — VERIFIED ABSENT today
ceur-ws.org index fetched (5.5 MB): IberLEF volumes exist for 2019-2025, **none for 2026**; latest volume is
Vol-4270. No CEUR paper under his name. No evidence anywhere of a submitted, accepted or presented system
paper. Re-check CEUR after ~Oct-Nov 2026.

## 5. FAERS pharmacovigilance — VERIFIED as a public artefact, not as a publication
The receipts are **inside the public Zenodo deposit**, so for the first time these numbers are third-party
checkable rather than vault-only. From `zen_x/receipts/faers_v2_2026-09-15/RESULT.md` (read by me):
openFDA FAERS queried 2026-09-15, **grand total N = 20,692,690**; phenibut n = 49; loss-of-consciousness
**PRR 23.36, ROR 27.09 (12.17-60.30)** reproducing a prior run; drug-role (suspect) restriction collapses the
baclofen-Depression signal (ROR 2.64 -> bracket [0.96, 1.50]) via an **exact census of 87.1% of baclofen
reports plus a monotonicity bound**; withdrawal signals strengthen; de-duplication shown negligible;
MedDRA version found populated per-record 17.0-26.0, correcting the manuscript's own SI wording.
Status: a **component of the unposted Paper B**, not a standalone publication. The phenibut cell is a=7/n=49
— small numbers; never present it as a safety conclusion.

## 6. Paper B, ORCID and the two things to fix before any supervisor sees this
- **Paper B (KCTD16/KCTD12 MR + coloc + FAERS): DRAFTED, NOT POSTED.** VERIFIED absence in Crossref
  (only 1 work under his name), DataCite (4 DOIs, all the Zenodo versions), OpenAlex, Europe PMC, arXiv.
  The deposit README names **medRxiv** as its intended venue. On a CV it is at most
  "manuscript in preparation"; it is not citable.
- **ORCID has ZERO works** (verified live today: `/works` -> 0 groups) while a Crossref auto-update permission
  request for his own preprint sits unactioned in the inbox. A supervisor who clicks the ORCID on the preprint
  byline sees an empty record.
- **ORCID's education entry says the BSc was awarded by the University of Bucharest 2022-2025. That is wrong**
  (Titu Maiorescu awarded it; UB is the master's). It is self-asserted, public, and attached to the identifier
  his preprint carries — so it is a cross-checkable inconsistency against any honest CV. His action, not a
  drafting choice.
- 10-minute fix list, in order: (1) grant the pending ORCID-Crossref permission; (2) add the Zenodo concept
  DOI to ORCID; (3) correct the ORCID education entries; (4) fix the deposit verifier paths and publish a
  v4; (5) add a GRACE-specific README and a licence to the repo, or move GRACE into its own repo.

## 7. Which artefact opens a doctoral-supervisor conversation
The binding gate is a **supervisor's written agreement**, not a publication count, so the question is not
"which line scores highest" but "which artefact makes a busy academic reply to a cold email".

**Lead with the ChemRxiv preprint.** Reasons, all evidence-backed: it is the only object that carries his
name, a DOI and a date (VERIFIED); it is **sole-authored**, so nothing about it is shared credit; and its
actual subject is the thing supervisors screen for — it reports a **licensed regime and a documented failure
regime side by side**, withdraws a mechanism it could not defend ("did not survive a direct test... and is
withdrawn"), refuses to claim a magnitude it cannot support ("the claim is the sign, not the magnitude"), and
names the seed that did not replicate. A prospective supervisor reads that as *this student will not hand me
a fabricated result* — which is the risk they actually carry. Pair it with the deposit: 630/630 files
hash-verified against a shipped manifest is concrete and checkable (once §3 is fixed it becomes strong).

**Use GRACE second, and only as domain proof** if the supervisor is in NLP/ML: a 27-run controlled benchmark
with seed variance reported and a bias-free ensemble is legible to that audience, and the code is public. But
it has no paper, no byline, a repo whose front page is about something else, and an official result that is
not yet attributable to him — so it cannot be the opener without inviting the questions he cannot yet answer.

**Do not open with FAERS / Paper B.** It is the most *interesting* methodological work (an exact-census bound
to prove a non-signal is genuinely nice), but there is nothing a supervisor can read: no preprint, no paper,
only receipts inside a dataset archive. It is the right answer to "what are you working on now", not to
"who are you".

One tactical point: three UB doctoral scholarship places in 2026 and a July 2027 registration means the useful
move is not more output — it is getting **one named academic to read one artefact**. The preprint is the only
artefact that survives being read cold by a stranger, so everything in §6 that makes it check out (ORCID works,
ORCID education, a working verifier) is worth more right now than a fourth project.

---

## Appendix — evidence files produced this session (all in this scratchpad)

| File | What it is |
|---|---|
| `cx_chemrxiv.json` | Crossref record for the preprint |
| `orcid_works.json` | ORCID /works — zero work groups |
| `zen_22819601.json`, `zen_22836690.json`, `zen_22836832.json` | Zenodo version records |
| `zen_v3.zip`, `zen_x/` | the deposit archive + extraction used for the manifest check and verifier run |
| `gh_grace.json`, `gh_commits.json`, `gh_tree.json`, `gh_readme.md` | GitHub repo metadata, 36 commits, 400-blob tree, README |
| `gh_ensemble.json`, `gh_reportdata.json` | machine-readable GRACE results pulled raw from the repo |
| `cb_comp.json`, `cb_ph_26223.json`, `cb_ph_24943.json`, `cb_ph_22513.json` | Codabench competition + the three phase leaderboards |
| `ceur_index.html` | CEUR-WS index (no IberLEF 2026 volume) |
| `chemrxiv_full.html` | the Cloudflare interstitial returned for the preprint page |
