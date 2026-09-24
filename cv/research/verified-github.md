# verified-github.md — independent verification of GitHub resume claims

Verifier lane: re-checked `harvest-github.md` against the live GitHub API, live HTTP, package
registries and the local clones. **I did not trust the harvest file.** Every line below is tagged
VERIFIED (with the exact artifact I personally pulled), INFERRED, or COULD NOT DETERMINE.
Date of checks: 2026-09-23. All GitHub API calls unauthenticated (no Authorization header); no
credential value was read or printed.

Raw evidence written to `scratchpad/verify/` (repos_fresh.json, rel_*.json, zhm_pr241.json,
s_*.json, air_lang.json, el_repo.json, pgu_repo.json).

---

## 0. Summary

Of the harvest's strongest claims, **11 survive**, **5 are overstated**, **2 are unsupported**,
and I found **3 harvest errors** (one of them in the owner's favour).

Harvest errors corrected:

1. **npm claim reversed.** The harvest said tracelines' "live on npm" README line is FALSE because
   `@prekzursil/tracelines` 404s. Wrong package name was tested. The real package is **unscoped
   `tracelines`, maintainer `prekzursil`, v0.2.0**, whose `repository` field points at his repo.
   HTTP 200. The README is correct; the harvest's "false claim" flag should be deleted.
2. **ZHMModSDK merge date wrong.** Harvest says merged 2025-12-17. API `merged_at` =
   **2026-01-11T20:09:14Z**.
3. **Release counts overstated.** Harvest says Reframe has 10 releases and bilbo has v1.0.0 +
   v1.0.1. Unauthenticated `/releases` returns **9 for Reframe** (v1.4.1 is not publicly served)
   and **1 for bilbo, with ZERO assets** (v1.0.1 is a bare tag — it renders as a tag name in
   releases.atom, not a release title).

New evidence the harvest could not obtain (its API quota was exhausted): **release asset download
counts**. See section 2. They materially change what can be claimed.

---

## 1. Inventory — VERIFIED, matches harvest exactly

`GET /users/Prekzursil/repos?per_page=100&type=owner` -> `verify/repos_fresh.json`

- **68 public repos: 20 originals + 48 forks.** Exact match to harvest.
- Stars on originals: Reframe 4; abbyy-finereader-ocr-mcp 1; Personal-Finance-Management 1;
  Star-Wars-Galactic-Battlegrounds-Save-Game-Editor 1. **Total 7 stars. One fork received
  (Reframe).** No repo above 4 stars — matches the owner's own ground truth.
- **10 of 20 originals have no license** (`license: null`): Reframe, quality-zero-platform,
  agent-skills-toolchain, DevExtreme-Filter-Go-Language, Airline-Reservations-System,
  Star-Wars-...-Save-Game-Editor, pbinfo-scrape, WebCoder, Personal-Finance-Management,
  grace-iberlef-2026. Confirmed against the clones (Reframe carries only a `NOTICE` file).
- README present in 19/20. **WebCoder has none** — and I checked **all 38 remote branches**
  individually (`git cat-file -e <branch>:README.md`): none has one either.

INFERRED: "open-source portfolio" is the wrong frame. No license means nobody may legally reuse
Reframe or quality-zero-platform. These are *public* repos, not *open-source* ones.

---

## 2. Releases and downloads — the harvest's blind spot, now filled

`GET /repos/Prekzursil/<repo>/releases?per_page=100`

| Repo | Public releases | Total asset downloads |
|---|---|---|
| Reframe | 9 (v0.1.0–v1.4.0 + desktop-v0.1.6/0.1.7/0.1.8) | **1,139** |
| SWFOC-Mod-Menu | 3 | 22 |
| env-inspector | 2 | 13 |
| llm-anthology | 1 | 2 |
| bilbo-app | 1 | **0 (no assets at all)** |

**The 1,139 figure must not go on a resume.** Asset-level breakdown for `desktop-v0.1.7`:
aarch64 `.app.tar.gz` 113, AppImage 112, x64 `.msi` 112, `x64-setup.exe` 89, `latest.json` 87,
`.rpm` 86, `.deb` 85, x64 `.app.tar.gz` 84 — near-uniform counts across every *mutually exclusive*
platform artifact. A human downloads one platform. **That distribution is a mirror/scraper, not
users.** Corroborating: on v1.4.0 the 41-byte `latest.yml` auto-update manifest has **99**
downloads while the actual **227.9 MB Windows installer has 12**.

VERIFIED: the newest Windows installer has **12 downloads**.
INFERRED: genuine human installs across all Reframe releases are in the low tens, not thousands.

Also VERIFIED: the v1.4.0 installer is named **`media-studio-1.4.0-win-x64.exe`**, not `Reframe`.
The shipped binary carries a different product name than the repo. Anyone who downloads it sees
this, and it is the obvious "so which is it called?" interview question.

---

## 3. momentstudio — the strongest claim on the whole profile

The one item where the evidence is *stronger* than the harvest said, and it is checkable by
anyone with a browser and no login.

VERIFIED by live HTTP (no auth):

- `https://momentstudio.ro` -> HTTP 200. Angular SPA, Tailwind, critical-CSS inlining
  (`data-beasties-container`), PWA `manifest.webmanifest`, light/dark `color-scheme`.
- `https://momentstudio.ro/api/v1/health` -> **HTTP 200 `{"status":"ok"}`** — a live FastAPI backend.
- `https://momentstudio.ro/api/v1/catalog/products?limit=100` -> **HTTP 200**, real catalog:
  **16 active products**, `meta.total_items: 16`, `bounds: {min_price 12.0, max_price 90.0,
  currency "RON"}`. Romanian handmade goods (e.g. SKU `FLORIDEP-3779`, clay brooches).
- The product schema is a real commerce model, not a demo: `sku`, `base_price`, `currency`,
  `is_active`, `is_featured`, `low_stock_threshold`, `allow_backorder`, `depth_cm`/`height_cm`,
  `meta_title`/`meta_description` (SEO), `featured_collections`, `images`, `category_id`.
- `/api/v1/catalog/categories` -> HTTP 200, real taxonomy (`Brose`, ...) with `sort_order`,
  `parent_id`, `is_visible`.
- `/api/v1/openapi.json` and `/api/v1/docs` -> **404**. Interactive API docs are disabled in
  production. INFERRED: a deliberate, correct hardening choice that counts in his favour.

INFERRED: a genuine small production storefront serving a real client, deployed and running, with
a backend he can be questioned about in depth. It is the best resume line he has after pbinfo.

**Mandatory cleanup before this link goes to anyone** (VERIFIED from the clone):

- **63,363 remote branches, of which 63,116 are `cursor/*`.**
- 91 tags, **89 of them `rescue/*`**, which surface on the Releases page.

The Branches tab is unusable and reads as unattended agent runs. This is a short cleanup that
converts a liability into the profile's best asset.

---

## 4. Outside contributions — the real number is 10, not 1,590

`GET /search/issues` (4 queries, `verify/s_*.json`):

| Query | total_count |
|---|---|
| `author:Prekzursil type:pr` | **1,791** |
| `author:Prekzursil type:pr is:merged` | **1,590** |
| `author:Prekzursil type:pr -user:Prekzursil` | **18** |
| `author:Prekzursil type:pr is:merged -user:Prekzursil` | **10** |

**1,580 of the 1,590 merged PRs are on his own repositories**, where he is author, reviewer and
merger. The 10 external merges:

| Upstream | Upstream stars | His merged PRs |
|---|---|---|
| victormura/event-link | **1** | #2, #3, #7, #10, #11, #12 (6) |
| ezluci/pbinfo-get-unsolved | **6** | #11, #12, #14 (3) |
| **OrfeasZ/ZHMModSDK** | **282** | **#241 (1)** |

The harvest claimed 8 merged on event-link; the search index says **6** (`is:merged`). Of those 6,
three are housekeeping ("Sync/upstream main", "sync upstream ... into victormura/main",
"Fix/gitignore") and one is a README update. The two substantive ones are **#2 "Implementation of
Event Link MVP: core auth, event lifecycle, recommendations, email & CI"** and **#12 "Static Code
Polishing + 100% Line + Branch Coverage"**.

### ZHMModSDK #241 — VERIFIED, and it is the single best OSS line

`GET /repos/OrfeasZ/ZHMModSDK/pulls/241`:

- Title "Add TitaniumBullets mod(shoot through walls)", author `Prekzursil`
- **`merged: true`, `merged_at: 2026-01-11T20:09:14Z`, `merged_by: OrfeasZ`** (the repo owner)
- 6 commits, **+518 / −2 across 7 files**, base `master`
- Upstream repo: **282 stars, 46 forks, C++**

INFERRED: a maintainer-merged C++ feature into a 282-star project is the only contribution on the
profile that a hiring reviewer would count as real open-source work. Name it explicitly with the
PR link rather than burying it in a repo list.

### Adoption on his own repos — VERIFIED negative

No outside-authored PR or issue on any of his 20 originals. Max 4 stars. 1 fork received.
The only recurring non-owner human author is "Daria Grama" (1–5 commits in ~12 repos, all
governance-sync commits). COULD NOT DETERMINE whether that is a second person or a second account.

---

## 5. Packages and live surfaces — VERIFIED

| Target | Result |
|---|---|
| PyPI `tracelines` | **200**, v0.2.0, author `Prekzursil`, project_urls -> his repo/Pages |
| PyPI `llm-anthology` | **200**, v0.1.0, author `Prekzursil` |
| PyPI `env-inspector` | 404 (not published) |
| PyPI `svcoverage` | 404 |
| **npm `tracelines`** | **200**, v0.2.0, maintainer `prekzursil`, repo -> his GitHub |
| npm `@prekzursil/tracelines` | 404 (the name the harvest wrongly tested) |
| momentstudio.ro | 200 (see section 3) |
| prekzursil.github.io/tracelines/ | 200 |
| prekzursil.github.io/quality-zero-platform/ | 200 |

**Download reality check (pypistats):** tracelines **16/month**, llm-anthology **27/month**.
INFERRED: that is mirror and index traffic. "Published on PyPI and npm" is VERIFIED and fair; any
word implying adoption, users or popularity is not.

---

## 6. CI status a reviewer sees today — VERIFIED (live badge SVGs)

| Repo | Workflow | Status |
|---|---|---|
| Reframe | quality.yml | **passing** |
| momentstudio | backend.yml | passing |
| llm-anthology | ci.yml | passing |
| tracelines | ci.yml | passing |
| env-inspector | ci.yml | passing |
| **agent-skills-toolchain** | quality.yml | **FAILING** |
| **WebCoder** | quality.yml | **FAILING** |

The two failing repos are the two most recently pushed (2026-09-23 and 2026-09-22) — the first
things a reviewer sees when sorting the profile by recent activity.

### Reframe's coverage gate is real — VERIFIED

`.github/workflows/quality.yml` line 134: `--cov-branch --cov-fail-under=100`, over the union of
the `media_studio` and `contract` roots. `.coverage-thresholds.json` declares 100% lines+branches
for the sidecar and 100% lines/branches/functions/statements for the renderer, and — notably —
explicitly marks mutation testing **non-blocking / observe-only**, documents the measured score
(81.9% after assertion strengthening, up from 70.2%) and states that the remaining survivors are
equivalent mutants. INFERRED: genuinely rigorous, and unusually honest about what the gate does
*not* cover.

Because the gate is enforced and the badge is green, "100% line and branch coverage enforced as a
blocking CI gate" is a defensible, third-party-checkable claim **for Reframe specifically**.

Independent counts from the clone: Reframe **539 test files**, README 197 lines, 4 workflows.

---

## 7. Claims that die

### 7.1 Personal-Finance-Management — DROP IT

Independently reproduced with `git ls-tree -r` on his first commit vs the upstream clone:

- His `Initial commit` (2025-05-27, `Prekzursil <a_visalon@yahoo.com>`): **191 files in one commit**
- Upstream `preethi-sv/Thrifty-app`: 118 files, 17 commits, last 2019–2020
- **63 files byte-identical (same blob SHA at the same path)**
- **62 blob SHAs identical anywhere**; **102 of upstream's 118 paths present**
- `app/build.gradle:11` -> `applicationId "com.preethi.thrifty"` — the upstream author's name is
  still the application ID
- README line 1: "Personal Finance Management Android Application **(Thrifty)**"
- README line 5: "This project was **originally developed as a Bachelor's degree project**."
- README line 59 tells the reader to register a Firebase app "with the package name
  `com.preethi.thrifty`"
- README line 158: "No license has been declared for this project; **all rights are reserved by
  the author**."
- **Zero attribution** anywhere: grepping the whole tree for preethi / samyuktha / thrifty-app /
  "original author" returns only the inherited `applicationId` and its echo in `cline_docs/`.
- **0 test files.**

INFERRED: claiming this as "my Bachelor's project" while asserting all rights reserved, with no
credit, is the single highest-risk item on the profile. One search on `com.preethi.thrifty` finds
the upstream. For a doctoral application this is a research-integrity flag, not merely a resume
flaw. Remove it from the record, or restate as "extended an existing open-source expense tracker
(preethi-sv/Thrifty-app) with Drive backup, RO/EN localisation, theming and charting" — and fix
the README *before* anyone is pointed at it.

What he did add (VERIFIED): 36 `.java` files at his first commit vs upstream's 19 — **17 new Java
classes** (Drive backup, localisation, theming, settings, reminder/boot receivers, chart
rendering). That is a real contribution, defensible **only if attributed**.

### 7.2 bilbo-app "shipped mobile app with releases" — OVERSTATED

`/releases` returns exactly **one** release, **v1.0.0 with `assets: []`**. v1.0.1 appears in
releases.atom as a bare tag name, not a release title. **There is no downloadable APK or IPA
anywhere.** Plus **77 commits authored `Test <test@example.com>`**, which appear in the
contributor graph. Honest wording: "built a Kotlin Multiplatform Android/iOS app (tagged v1.0.1)"
— not "shipped", not "released".

### 7.3 Airline-Reservations-System — the known defect, CONFIRMED live

`GET /repos/Prekzursil/Airline-Reservations-System/languages` (fetched today):
**Python 239,129 B (43.1%), C++ 190,349 B (34.3%), JavaScript 111,726 B (20.1%)**, CMake 0.7%.
The repo description is literally **"C++ App + GUI To Manage Airline Reservations."** while
GitHub's repo-card language badge reads **Python**. The description and the badge contradict each
other on the repo's own front page. Fixable with `.gitattributes` (`linguist-vendored` /
`linguist-language`) plus a description that matches. Until then, do not call it a C++ project on
a CV — the reviewer's first click disproves the line.

### 7.4 GRACE @ IberLEF 2026 — OVERSTATED, and this one matters for the doctoral file

VERIFIED present in the clone: `FINAL/report_out/GRACE_track1_submission.json`,
`blind_submission_greedy.json`, `blind_submission_top3.json`,
`ensemble_dev_predictions_all9.json`, and `FINAL/report/` containing
`GRACE_Track1_Report.pdf`/`.docx`, `GRACE_Track1_IberLEF2026.pptx`, figures and slide PNGs.
The artifacts are real and substantial.

But the headline number is **dev-set**, not leaderboard. `FINAL/report/README.md` line 20:
"**All-9 ensemble: 0.743** (official scorer)"; line 19: "Best single model: mDeBERTa-v3-base
0.705 ± 0.028 **dev strict macro-F1**". "Official scorer" means he ran the organisers' scoring
script locally — it is not a ranked result.

COULD NOT DETERMINE: any official registration, Codabench leaderboard placement, or published
working notes. Every Codabench mention in the repo sits in **planning** documents
(`docs/superpowers/plans/...`: "Codabench quota: 3-5 submissions/day typical", "Budget at most 2
dev-phase and 3 test-phase uploads") — intent, not receipt. Consistent with the owner's own ground
truth ("research in flight, none published") and with zero registered ORCID works.

Also VERIFIED: the repo's README **title is "bionlp — ToolUniverse Workspace"**, a different
project. GRACE is described accurately, but only from the second section down.

Safe wording: "built a 27-cell transformer sweep (9 models × 3 seeds) on Modal with a
softmax-probability ensemble for IberLEF 2026 Track 1; 0.743 strict macro-F1 on the development
set under the organisers' scorer." Never "competed", never "placed", never a rank.

### 7.5 WebCoder — the project is real, the repo is not linkable

No README on main or on **any of 38 remote branches** (checked individually). No description.
`quality.yml` **failing**. Main's recent history is dependabot/CodeQL housekeeping; the real work
sits on `origin/wave/nextjs-migration` (newest ref, 2026-09-22). 34 test files exist.
Until a README lands and that branch is merged, linking this actively costs him.

### 7.6 "1,590 merged pull requests" / "6,432 contributions" — TRUE BUT SELF-DEFEATING

Both VERIFIED exactly. The logged-out contributions calendar
(`github.com/users/Prekzursil/contributions`) sums to **6,432 across 368 day-cells, 190 of them
active** — the header text and the per-day sum agree.

But section 4 shows 1,580 of 1,590 merges are self-merges, and the harvest's trailer analysis
(which I did not re-derive) reports heavy AI co-authorship. A reviewer who sees "1,590 merged PRs"
next to 7 total stars and 10 external merges will discount the entire CV. These are volume metrics
with no independent reviewer behind them; they should not be headline numbers.

---

## 8. Hygiene facts that decide "link vs describe" — VERIFIED from clones

| Repo | Finding |
|---|---|
| momentstudio | 63,363 remote branches (63,116 `cursor/*`); 91 tags, 89 `rescue/*` |
| agent-skills-toolchain | **111 tags, all `archive/` or `rescue/`**; CI failing; 237 MB (measured) |
| pbinfo-scrape | **548 MB** on disk (crawled third-party educational HTML committed) |
| SWFOC-Mod-Menu | **473 MB** (committed reverse-engineering corpus) |
| Reframe | 76 MB; no LICENSE (NOTICE only) |

`Test <test@example.com>` commits: bilbo-app 77, pbinfo-scrape 78, codeblocks 11, Airline 10,
env-inspector 9, PFM 8, quality-zero-platform 7.

Owner identity sprawl (VERIFIED, `git log --all --format='%an <%ae>' | sort -u`): at least six —
`Andrei Mihai Visalon <54636077+Prekzursil@...>`, the same with lowercase `prekzursil`,
`Andrei Mihai Visalon <andrei@users.noreply.github.com>`, `Prekzursil <a_visalon@yahoo.com>`,
`Prekzursil <noreply@prekzursil.dev>`, `Prekzursil <prekzursil1993@gmail.com>`,
`Prekzursil <prekzursil@gmail.com>`, plus `917-Andrei-Visalon` in DevExtreme.

INFERRED: none of the commit identities uses the hyphenated legal name **Andrei-Mihai Visalon**.
If the CV carries one name while the commit history shows five variants plus "Test", identity
verification during a background check takes longer than it needs to.

`agent-skills-toolchain` skill count: **378 `SKILL.md` under `skills/` + 53 under
`skills-claude-only/`**. The README's "370+ skills" claim is VERIFIED and in fact conservative.
But the repo is public while its description opens "Private platform repo", CI is red, and it is
237 MB (measured) with committed browser-profile binaries — describe in prose, do not link.

---

## 9. Portfolio-grade vs damaging — final call

**Link today (A):** Reframe (flagship engineering), momentstudio.ro (the live product — prune
branches first), llm-anthology, tracelines, env-inspector, ZHMModSDK PR #241.

**Describe in prose, do not link:** agent-skills-toolchain (red CI, 237 MB (measured)),
quality-zero-platform (no license, backup tags), SWFOC-Mod-Menu (473 MB, "game-hacking" framing),
event-link (hosted under the classmate's account).

**Actively damaging if a reviewer opens it:**

1. **Personal-Finance-Management** — unattributed upstream plus "all rights reserved". Worst item
   on the profile, and the only one with research-integrity consequences for the doctoral file.
2. **pbinfo-scrape** — 548 MB of scraped third-party educational content, public.
3. **WebCoder** — no README anywhere, red CI, and it is among the most recent activity.
4. **agent-skills-toolchain** — red CI, committed browser profiles, "Private platform repo" label
   on a public repo.
5. **Airline-Reservations-System** — description contradicts the language badge on the front page.

---

## 10. What I could not determine

- Whether "Daria Grama" is a collaborator or a second account of his.
- Whether GRACE was ever officially submitted or ranked (no public trace found).
- Whether the 4 Reframe stars are independent accounts.
- Whether DINUPLAST or any employer work appears anywhere on GitHub (no org memberships).
- The real human-vs-AI authorship split inside commits.
