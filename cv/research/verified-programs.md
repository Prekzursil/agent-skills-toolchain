# Verified programs — resume-claim audit of `harvest-auto-memory.md`

Auditor lane: re-verify the strongest candidate resume claims by going to primary evidence, not to the harvest file.
Date: 2026-09-23. Subject: Andrei-Mihai Visalon.

**Label discipline.** VERIFIED = I personally read the artifact named. INFERRED = my reasoning on verified facts.
COULD NOT DETERMINE = no source settles it; not filled from general knowledge.
Confidence bands (WEP): likely 55–80%, very likely 80–90%, almost certain 90–99%.

**No credential value was read or printed anywhere in this audit.**

---

## 0. Three instrument findings that change how the whole harvest should be read

These are not claims about the owner. They are facts about the evidence base, and they are load-bearing.

### 0.1 `D:\Research\` does not exist on this machine (VERIFIED)

`Get-PSDrive` + `Get-ChildItem D:\` returns exactly two directories: `basic-memory` and `npm-cache`.

The harvest cites `D:\Research\projects\phenibut\compute\faers_v2_2026-09-15\` as the location of the FAERS
receipts (`RESULT.md` + JSON) and rates that claim "verifiable yes-on-request". **That path does not resolve.**
A recursive search for `faers*` across D: returned zero files. The same applies to
`D:\Research\tools\rvc-realtime-voice-changer` (RVC note) and `D:\Research\projects\phenibut` generally.

Consequence: every claim in the harvest whose verifiability rests on "receipts under `D:\Research`" is
**COULD NOT DETERMINE on this box**, not "yes-on-request". Either the owner holds those files elsewhere
(external drive, another machine, the Zenodo zip) or they are gone. He must be asked before any such
claim is put in front of an employer. This affects FAERS most of all.

### 0.2 The workflow journals — the memory's own designated ground truth — only cover 5 days (VERIFIED)

The harvest's §2 says the three INDEX-ONLY numbers "should not go on a resume unless the owner can
re-derive them from the workflow journals (`.../subagents/workflows/wf_*/journal.jsonl`)".

I enumerated every such journal: **42 of them, all with mtimes between 2026-09-19 and 2026-09-23.**
There is no July or August 2026 journal on this machine. The designated re-derivation path for the
1000-agent audit (2026-07-30), the 97-slice audit (2026-07-13) and the 12,272-record corpus (2026-07-19)
is **empty**. Those numbers cannot be recovered here. This is stronger than the harvest's "INDEX-ONLY" —
it means the recommended remedy is unavailable, not merely unattempted.

### 0.3 The vault "hits" for the disputed numbers are tokenizer noise; the journal hits are circular (VERIFIED)

I re-ran the absence proof independently (`numscan.py`, os.walk over 774 vault files, 18 auto-memory files,
1,479 journal files, 14,094 `.agents` files). Two traps that a naive grep count would have fallen into:

- The apparent vault hits for `1582` and `12272` are all inside
  `D:\basic-memory\.hf\hub\models--*\snapshots\*\tokenizer.json` / `vocab.json` — HuggingFace vocabulary
  files, where those digit strings are token ids. **Not evidence.** Substantive vault hits: zero.
- The apparent journal hits for `1582`, `97-slice`, `1000-agent`, `12.1h`, `225 findings`, `12,272` are
  **all** in `wf_27a767d7-2c5\agent-*.jsonl` — agents of *this very résumé program*, which were fed
  `MEMORY.md` as input. The corpus is quoting the index back at itself. **Circular; not evidence.**

So the harvest's INDEX-ONLY verdicts are confirmed by an independent instrument, and confirmed *more
strongly* than the harvest stated.

---

## 1. Claim-by-claim

### 1.1 "Designed and ran a 500-unit parallel LLM research fan-out" — **OVERSTATED** (salvageable)

**What I checked.** `D:\basic-memory\projects\Program R autonomous research loop 2026-07-26.md` (read in
full); the on-disk skill at `C:\Users\prekzursil\.agents\skills\codex-databricks-fanout\` (69 files);
and the public GitHub tree of `Prekzursil/agent-skills-toolchain` (17,243 entries, not truncated).

**What "500" actually is.** In `scripts/e2e/build_research_targets.py` line 30 the literal is `BUDGET = 500`.
It is the *ceiling of a tiered plan*, spent by priority tier (`TIERS` caps: harness 99, hooks 40, mcp-tools 25,
rules 20, skills 40, …) across 8 named lenses (`DEEP`), emitted to a plan file `_R_plan.json`.
The vault note records the plan as actually funded at "harness 12×8 + hooks 38×6 = 65% of the 500"
— i.e. **324 units planned, not 500**, and 500 was never the number of units that ran.
It is a **budget**, and the plan under-spent it by ~35%.

**Attempts vs successes.** Nothing on this box records how many of those units returned. The note's only
quantitative outcome statement is "~84% of units returned HIGH", which it immediately discounts as
severity inflation. The defensible outcome is not a count of units at all — it is **three defects, each
independently reproduced before the fix**, with PR numbers (#221 camelCase payload bypassing a
destructive-command guard; #222 JSON-quoted credentials bypassing redaction; #220 cross-session
compaction-context injection), plus one finding he raised, then refuted, then corrected (#223).

**Third-party checkable: partly yes-public.** The fan-out engine is in a public repo — 158 tree entries
under `.agents/skills/codex-databricks-fanout/`, including `build_research_targets.py`, `run_research.py`,
`harness/lanes/research.py` and a test suite I counted at **230 test functions across 25 test files**.
Anyone can read the design. Nobody can verify the run.

**BLOCKING PROVENANCE FLAG (VERIFIED, existence only).** Six vault notes reference `bolt-datascience` /
`costin.ionescu`, including `decisions/Databricks account usage - OWNER AUTHORIZED no restrictions.md`.
Per the owner's standing instruction I did not open the security/access writeups. Existence is enough:
**the compute was a third-party corporate Databricks workspace under another named person.** The
workspace, the company, and "Databricks-scale" must not appear on a resume. The design is his; the
infrastructure is not his to cite.

**Safe wording:** "Designed an open-source parallel LLM research harness — tiered work-unit planner,
8 analysis lenses, sharded execution, 230-test suite — and used it to find three confirmed harness
defects, each independently reproduced before the fix (public repo: `agent-skills-toolchain`)."
Never "ran 500 agents", never "found 500 issues", never name the compute.

**Interview risk if kept as-is:** "You said 500 units — walk me through the run log." There is no run log.
He would have to say the number is a config constant. That is a bad moment; the safe wording avoids it
entirely and is stronger, because a reviewer can open the code.

---

### 1.2 "1000-agent, 12.1-hour audit; 42% of 225 findings refuted at 89% confidence" — **UNSUPPORTED → DROP IT**

**What I checked.** The string exists in exactly one place on this machine: one line of `MEMORY.md`.
Zero substantive hits across 774 vault files, zero in the 18 auto-memory detail files, zero in
`.agents` (14,094 files). No journal for 2026-07-30 exists (§0.2).

**Verdict: drop it.** It is a one-line summary written by an assistant at compaction time, describing an
audit the same line says **"died pre-synthesis"**. It is a claim about a *failure*, it has no receipt,
and the number counts *findings generated by agents*, 42% of which the line itself says were wrong.
There is no version of this that belongs on a resume.

**What survives instead (VERIFIED-VAULT, and better):** the vault holds two fully documented, smaller
instances of the same phenomenon — wave 1: 6/6 lanes self-reported SUCCESS, 15 of 18 adversarial
verdicts refuted them; wave 2: 8/8 SUCCESS, 18 of 24 refuted — with all PRs green on 100% coverage at
the moment the defects were found. Those are the measured base rates worth citing (83% / 75%), and they
are a point about his *verification discipline*, not about fan-out size.

---

### 1.3 "97-slice pure-Codex audit → 1,582 findings, 3 critical RCE" — **UNSUPPORTED → DROP IT**

**What I checked.** Same instrument as 1.2. `1582` / `1,582` / `97-slice` / `pure-CODEX`: zero substantive
hits anywhere outside the single `MEMORY.md` line. The harvest additionally noted that the vault's
`harness/Config-drift audit 2026-07-13` note wikilinks `[[Reframe codex audit 2026-07-13]]`, a note that
does not exist — a dangling link. I confirmed the target note is absent.

**Verdict: drop it.** "1,582 findings" counts *raw agent output*, which every other measurement in this
estate says is 42–83% wrong. "3 critical RCE" is the kind of claim a security-minded interviewer will
ask to see; there is nothing to show.

**What survives instead (VERIFIED-VAULT):** `projects/Reframe ultracode reconcile state 2026-07-11.md`
records "89 real findings (82 discovered, 24 false-positives dropped), 74 fixed in-tree", reconciled to a
sidecar suite at "5733 passed, 100% branch coverage". That is a *reconciled* number — findings that
survived triage — and it is the honest shape of this story.

---

### 1.4 "12,272-record corpus" — **UNSUPPORTED → DROP IT, and replace with something better**

**What I checked.** Zero substantive hits (§0.3). No July journal (§0.2).

**Verdict: drop the number.** But this is the claim where dropping costs him nothing, because the real
finding underneath it is far stronger and is fully documented.

**Replacement (VERIFIED-VAULT, measured on a live store, not estimated).**
`D:\basic-memory\projects\ai-sessions-render\...(47% of real Codex store was silently dropped).md` records
a confirmed data-loss defect in his own ingest pipeline, reproduced with a passing control:

| metric | value |
|---|---|
| rollout files in the live store | 2,024 |
| distinct session ids | 1,069 |
| ids spanning >1 file | 236 |
| **files silently dropped** | **953 = 47.1% of the store** |
| response items lost | 204,987 |
| ingest errors reported | **0**, exit 0 |
| shared ids where the survivor was a superset (i.e. harmless) | **0 of 236** |

Fixed in three commits (`7dbb99a` → `1afae7b` → `affae65`), with two follow-on defects found by
falsifying his own fix against real data after the synthetic tests were green. Session closed with four
stacks green (Python 1,342 @100% cov; TS 958; JS 418; Rust 27).

**Caveat the note states itself:** at 2026-08-08 it says "**Nothing pushed, nothing published.**" The repo
has since been renamed and pushed — see §1.12 — so the commit SHAs should be re-confirmed against the
public repo before being cited.

**Safe wording:** "Found and fixed a silent 47% data-loss defect in an ingest pipeline that reported zero
errors under a 100%-coverage gate — 953 of 2,024 files were being overwritten, measured on the real store
rather than fixtures."

---

### 1.5 "FAERS pharmacovigilance analysis at 20-million-record scale" — **OVERSTATED as phrased; supportable if re-scoped; verifiability now in doubt**

**What I checked.** `project_faers_v2_dedup_2026-09-15.md` in full (the only detail file that survives
locally); the live Zenodo record; and the cited receipts directory, which **does not exist** (§0.1).

**What the number is.** N = 20,692,690 is the **openFDA denominator** — every report in the endpoint at
lock time (2026-09-14). He did not store, download or process 20 million records. Saying "analysed 20
million adverse-event reports" is false and an interviewer with pharmacovigilance experience will know it
in one question.

**What he actually did (and it is good).** 48 keyless openFDA calls; a per-record census of
**78,592 of 90,232 baclofen reports (87.1%)**, partitioned by `receivedate` to beat the API's 25,000-skip
cap, with the partition proven exhaustive (bucket totals summed to exactly 90,232); ~6 GB paged.
Methodologically the two things worth putting in front of an academic committee are:
- a **monotonicity bound** — because ROR falls monotonically in the margin, a partial census yields a
  rigorous *upper* bound. He used it to prove a signal was absent (max possible ROR 1.50 < 2) without
  completing the census, and stopped at 87.1% deliberately.
- a **confound collapsed by drug-role restriction**: baclofen–depression ROR 2.64 → 1.31 (bracket
  [0.96, 1.50]), while the withdrawal axis strengthened (6.19 → 20.70). That is a result that changed his
  own paper's conclusion against his interest.

He also caught a nested-element overcount trap in openFDA (1.8×) by checking per record, ruled out
duplicate inflation (distinct-case == raw on every phenibut cell), and corrected a wrong MedDRA-version
statement in his own supplementary information.

**Attempts vs successes:** not applicable — this is analysis, not a fan-out. This is one of the few items
that is genuinely his own hands: the note records him re-checking the Wald arithmetic himself.

**Third-party checkable: partly, and weaker than the harvest claimed.** The Zenodo deposit (§1.13) names
a FAERS analysis in its title, so the *existence* of the work is public. The *receipts* are not on this
machine. I did not open the 33.9 MB zip to see whether the FAERS scripts are inside — **that is the single
highest-value open check left**, and it should be done before this goes on a CV.

**Safe wording:** "Ran a drug-safety disproportionality analysis against the full openFDA FAERS database
(~20.7 M reports), including an exhaustive per-record census of 78,592 reports partitioned to defeat the
API's pagination cap, and a monotonicity argument that turned a partial census into a rigorous bound.
Drug-role restriction collapsed one candidate signal (ROR 2.64 → 1.31) and strengthened another."

---

### 1.6 "A 26-repo fleet" / "nightly autonomous sweep across 26 repos" — **OVERSTATED (as a fleet), UNSUPPORTED (as an operated sweep)**

**What I checked.** The one substantive vault hit:
`D:\basic-memory\research\Autonomous Codex on GitHub - decision brief 2026-07-11.md`, read directly.

**What "26" is.** It is the *input premise* of a research brief: "18 public + 8 private" repos he owned on
2026-07-11. It is a count of his own GitHub account, not a managed fleet.

**Worse — the sweep is a proposal, not a system.** The phrase "a nightly ~26-repo sweep" appears in that
note inside **"Open decisions (to grill)"**, item 3, as a *risk to be weighed* ("can starve daytime
coding"). Independently, the owner's own `CLAUDE.md` describes the fleet runner under a **"Setup (you do
this)"** heading with four uncompleted prerequisites (merge PR #68 → #70 → #72; merge PR #270; create two
scoped PATs; uncomment line 299). **Nothing on this box shows the sweep was ever activated.**

**And the number is stale:** the account now has 68 public repos (per corrected ground truth), so "26"
describes neither today nor a fleet.

**Verdict: drop "26-repo fleet".** What is real is a security-reasoned design decision, and it is a good
one: he researched running autonomous agents on his own GitHub, found that his instinct
(`auth.json`-in-Actions) is explicitly forbidden by the vendor on public repos because the secret is the
entire account session and a fork PR can exfiltrate it, and chose the secretless path instead, propose-only,
human-merge, never auto-merge protected branches.

**Safe wording:** "Researched and designed a secretless model for running autonomous coding agents across
my own GitHub repositories after establishing that the obvious approach leaks a full account session via
fork pull requests; specified propose-only, human-merge with no self-hosted runners on public repos."
That is a judgment claim, it is true, and it is more impressive than a repo count.

---

### 1.7 Reframe — "shipped releases" — **SUPPORTED. This is his strongest engineering claim.**

**What I checked.** GitHub REST, live, 2026-09-23: `/repos/Prekzursil/Reframe/tags?per_page=100` and
`/releases?per_page=100`, plus per-asset download counts.

**Measured, exactly:**
- **17 tags**, **9 published releases** (0 drafts).
- Two product lines: `desktop-v0.1.6` / `0.1.7` / `0.1.8` (Feb–Mar 2026, 17 assets each) and
  `v0.1.0` → `v1.4.0` (2026-06-25 → 2026-07-07, 1–3 assets each).
- **Every release carries downloadable build artifacts** — this is a genuinely shipped desktop app, not
  a tagged repo.
- **1,139 total asset downloads** across all releases (largest single: `desktop-v0.1.7` at 810; `v1.4.0` at 116).
- Repo: public, Python, **4 stars, 1 fork**, created 2025-12-06, last pushed 2026-09-18.

**Counts attempts or successes?** Neither — releases are terminal artifacts. This is the cleanest number
in the whole audit.

**Third-party checkable: yes-public, one click, no login.**

**Safe wording:** "Author and maintainer of Reframe, an offline-first AI media toolkit (Python + Electron):
9 published GitHub releases across two product lines with signed installers, ~1,100 release-asset downloads."

**Do not say "7 tagged releases"** (the harvest's phrasing) — it conflates tags with releases and
under-counts. Say 9 published releases, or 17 tags, but not a blend.

---

### 1.8 Reframe "v1.4.2 SHIPPED" — **UNSUPPORTED → DROP IT**

Confirmed against the live tag list: the highest tag is **`v1.4.1`**, and `v1.4.1` exists as a **tag with
no published release**. There is no `v1.4.2` tag and no `v1.4.2` release. The vault's three `1.4.2`
mentions are local build-version strings, and the 2026-08-08 note says of the newest build that it was
"NOT installed" and that end-to-end operation through the installed app "is not proven".

"1.4.2 shipped" means *built on his laptop*. Drop it. Note also that if he wants to say "v1.4.1 released",
that is **also wrong** — v1.4.1 is a tag only. The last *released* version is **v1.4.0**.

---

### 1.9 Reframe test/coverage rigor — **SUPPORTED, and publicly checkable — but use the public numbers, not the vault's**

**What I checked.** The public repo tree (1,440 entries, not truncated) and the public
`.coverage-thresholds.json`, read raw.

**Publicly verifiable, right now, by anyone:**
- **262 TypeScript/JS test files + 264 Python test files = 526 test files** in the repo tree.
- `.coverage-thresholds.json` committed at repo root, declaring **100% lines + branches** for the Python
  sidecar (enforced by `pytest --cov-fail-under=100 --cov-branch` over two roots) and **100%
  lines/branches/functions/statements** for the renderer (vitest thresholds), each naming the CI gate that
  enforces it.
- CI workflows present: `quality.yml`, `e2e.yml`, **`mutation.yml` and `mutation-incremental.yml`**.
- Mutation-testing baselines documented *in the file itself*: `spend_ledger.py` 94 mutants → 77 killed
  = 81.9% (up from 70.2% after strengthening assertions); `timelineOps.ts` 208 mutants → 189 killed +
  1 timeout = 91.35%.

**What makes this distinctive** is not the 100% — it is that the file explicitly marks mutation testing
**non-blocking and observe-only**, scopes it to named pure-logic modules, documents the surviving mutants
as equivalent, and instructs that the target be raised "only by strengthening assertions (never by
weakening tests)". A reviewer reading that file learns more about his engineering judgment than any
bullet point could convey. **It is worth linking directly.**

**The vault's numbers, by contrast, are single-source.** "5733 passed" appears exactly once in the vault
(`Reframe ultracode reconcile state 2026-07-11.md`); "3448 tests" exactly once
(`Reframe PR #290 merge-conflict reconcile 2026-07-12.md`). Both were written by an assistant, neither is
corroborated, and I could not confirm either against CI history. **Use 526 test files (countable by anyone)
rather than 9,000 test cases (countable by nobody).**

**Safe wording:** "Maintains 100% line-and-branch coverage gates enforced in CI across a Python + TypeScript
codebase (526 test files), plus nightly mutation testing (mutmut/Stryker) kept deliberately non-blocking,
with surviving mutants documented as equivalent rather than suppressed."

---

### 1.10 WebCoder draft PR #152, "295-test suite" — **OVERSTATED, and the PR contradicts itself**

**What I checked.** The live GitHub API for `Prekzursil/WebCoder/pulls/152`, including the full body.

**State (VERIFIED):** `state=open`, **`draft=true`, `merged=false`**, 11 commits, created 2026-09-22,
last updated 2026-09-22 19:17 — **unmerged and untouched since the day it was opened.**

**What "295" is — now resolved, and the harvest's guess was wrong.** The harvest inferred 295 "may be a
subset or a stale count". The PR body states it plainly: *"295 backend tests **collected** (D2 filename
fix)"*. It is a **collection** count, not a pass count. And the same PR's own "Receipt numbers" section
says: *"Backend: 301 passed / 5 failed"* — i.e. **306 collected**. The title and the receipts section of
a single pull request disagree with each other by 11 tests. Frontend is `229/229` at ~91% coverage
(not 100%, and the PR says so honestly).

So: **295 counts neither attempts nor successes consistently.** It is a stale collection count that
survived into the title after the suite changed.

**A second trap in the same PR.** It reports `changed_files=8848`, `additions=24283`,
**`deletions=1084049`**. Those million deletions are the purge of a checked-in `venv` (8,724 paths, per
the local note). Any "over a million lines changed" claim built on this PR is false. Flagging it because
the raw API numbers are seductive and public.

**Third-party checkable: yes-public — which is exactly the problem.** A reviewer who opens the PR sees
"draft", "not merged", and a title that its own body contradicts.

**Safe wording:** "Led an AI-agent-assisted modernization of a 2023 project of mine from Create React App
to Next.js 15 (App Router, TypeScript, 14 routes), containerized the code-judging sandbox, added CI
coverage gates, and fixed a latent object-permission defect (`obj.author` → `obj.user`) that raised an
AttributeError on every submission retrieve. Backend 301 passing at 99% coverage; frontend 229/229 at ~91%.
Open as a draft PR pending my own review."

**Drop "295-test suite" entirely.** If he wants a test number, use 301 backend / 229 frontend and say
where each came from. Never present the PR as merged.

---

### 1.11 Upstream contribution: `dsifry/metaswarm` PR #51 — **SUPPORTED (with one correction). Best third-party signal in the set.**

**What I checked.** Live GitHub API for the PR and its base repo.

**Measured:** author `Prekzursil`; **`state=open`, `draft=false`, `merged=false`**; 1 commit; 1 file;
**+29 / −21**; created 2026-09-19 05:52. Base repo `dsifry/metaswarm` has **419 stars** — a real
third-party open-source project, not his own.

**The engineering behind it is real and well-argued.** The PR body shows he diagnosed that a SessionStart
hook ran an expensive plugin-cache scan *before* the cheap project check, spawning one subprocess per
`plugin.json`, with a result that is only ever consumed inside a branch gated on a file that usually does
not exist. Fix: reorder. Measured **~140 s → ~0.3 s** with behavior unchanged inside real projects, and he
tested the non-regression path explicitly.

**Correction to carry forward: two different scan counts exist in his own artifacts.** The local memory
note says **529** `plugin.json` files; the public PR body says **~350**. A third party reads 350. He must
use the public number, or state both and explain, but he cannot quote 529 next to a link to a PR that
says 350.

**Also note a sequencing artifact:** the memory note (written 02:37) says the PR was "drafted but NOT
submitted"; the same-day estate note (09:09) says it was filed; GitHub says created 05:52. The notes are
consistent once ordered — but this is a live demonstration that the memory files contain statements that
were true when written and false hours later.

**Third-party checkable: yes-public, no login.**

**Safe wording:** "Submitted an upstream performance fix to metaswarm (419-star open-source agent
framework): diagnosed a session-start hook doing an unconditional plugin-cache scan whose result was never
read outside configured projects, and reordered the check — ~140 s to ~0.3 s with identical behavior.
Open pull request (dsifry/metaswarm#51)."

**Must say "submitted"/"open", never "contributed to" or "merged".**

---

### 1.12 Repository naming: `ai-sessions-render` has been renamed — **CORRECTION to the harvest**

The harvest cites the public repo as `Prekzursil/ai-sessions-render`. A live API request to that path
**redirects to `Prekzursil/llm-anthology`** (public, Python, 0 stars, created 2026-07-19, pushed
2026-09-20). GitHub will keep the redirect working, but a CV should name the current repo. Any bullet
built on §1.4 must point at `llm-anthology`.

---

### 1.13 Zenodo data & code deposit — **SUPPORTED, with one wording trap**

**What I checked.** Live Zenodo API, record 22836832.

**Measured:** DOI **10.5281/zenodo.22836832**; concept DOI 10.5281/zenodo.22819600; published
**2026-09-18**; version v3; **resource type: dataset**; licence **CC-BY-4.0**; sole creator
"Visalon, Andrei Mihai" with ORCID 0009-0001-8776-8498 attached; one file
`phenibut_deposit_2026-09-18_v3.zip`, **33.9 MB** (the harvest said 35.5 MB — minor, use 33.9);
**11 views / 7 unique views / 2 downloads**.

**The trap:** this is a **dataset deposit, not a publication**. It has a DOI, which makes it citable and
makes it look like a paper in a CV's hands. It must sit under "Data & software" or "Research outputs",
never under "Publications". His ORCID has zero registered works and both manuscripts are unpublished; a
committee that cross-checks will notice instantly.

**Second trap, from his own record:** `reference_partial_remediation_global_claim_2026-09-18.md` states
that a **false claim shipped inside this archive** — a README asserting "All are fail-closed" when two
gates (`verify_citations.py`, `verify_typography.py`) still ended in unconditional `sys.exit(0)`.
**Whether v3 corrected that sentence is COULD NOT DETERMINE** — I did not open the zip. This is the second
of the two open checks that must happen before this is cited (the first is the FAERS receipts, §1.5).
He is linking employers and committees to an archive that may contain a documented false statement.

**Safe wording:** "Sole-author data & code deposit, CC-BY-4.0 (Zenodo, DOI 10.5281/zenodo.22836832) —
supporting two manuscripts in preparation on the phenibut GABA-B axis." Adoption (11 views / 2 downloads)
should not be quoted.

---

### 1.14 Estate MCP/TUI audit — "34 agents, 96 adversarial verifications" — **OVERSTATED; contradicted by its own journal**

**What I checked.** `project_estate_mcp_tui_audit_2026-09-19.md`, then the actual journal it names:
`.../wf_97548feb-217/journal.jsonl`, parsed event by event.

**The note says:** "Workflow run wf_97548feb-217: 34 agents, 3.9M tokens, 96 adversarial verifications
(81 CONFIRMED / 13 REFUTED)".

**The journal says:** 130 events — **80 `started`, 45 `result`, 4 `failed`**, across **65 distinct
work-unit cache keys**.

So: 80 agents were launched, 45 returned a result (56%), 4 failed outright, and **31 started with no
terminal event at all**. 15 of the 80 starts were re-runs of an already-keyed unit. **Neither 80 nor 45
is 34.** The note's headline agent count is not supported by the run it names.

This is exactly the "attempts vs successes" failure the lane was asked to look for, and it is the note's
own documented failure mode ("never state a count from recall").

**Verdict: do not use the 34, and do not use the 96.** The "96 adversarial verifications" figure counts
agent-produced verdicts, which cannot be checked. The audit is real work — the port-band root cause
(11/19 startup failures in a dead 314xx band) and closing a config-injection path (`~/.mcp.json` 34 → 0 at
HOME) are concrete and were pushed to a repo — but the numbers attached to it are not.

**Safe wording (keep the finding, drop the counts):** "Audited my own multi-agent tooling estate and
root-caused two-thirds of session-start failures to a stale port range; closed a configuration-injection
path where a project-scope config loaded automatically at the home directory."

---

### 1.15 A number that IS re-derivable, and that he currently does not claim — **SUPPORTED (new)**

Because the July/August journals are gone, I measured what *is* on disk, so he has at least one
orchestration figure he can reproduce on demand in front of an interviewer.

Across all 42 workflow journals present (2026-09-19 → 2026-09-23, a five-day window), parsed from
`journal.jsonl` event types:

| metric | value |
|---|---|
| workflow runs | **42** |
| agents started | **689** |
| agents returning a result | **498 (72.3%)** |
| agents failing explicitly | **74** |
| started with no terminal event | **117** |
| distinct work units (cache keys) | **619** |
| largest single fan-out | **80 started / 45 returned** |

Two corroborations worth noting, because they cut both ways:
- The WebCoder note's claim "wf_c8e4c79c 25 agents / wf_a58fff1f 8 / wf_4c7f6644 11, 0 errors" is
  **exactly right**: the journals show 25/25, 8/8, 11/11, zero failures. When his notes are checkable,
  they are sometimes exactly correct.
- The estate audit note's "34 agents" is **not** right (§1.14). The difference is that one note counted
  from the journal and the other counted from memory.

**Safe wording:** "Routinely orchestrate parallel agent fan-outs with on-disk run journals: 42 workflow
runs and 689 agent launches in a representative five-day window, of which 72% returned a usable result —
a gap I instrument deliberately, because a launched agent is not a finished one."

That last clause is the real differentiator and it is defensible: he is one of the few people who would
report the 72% rather than the 689.

---

## 2. Does "AI agents did it" change the honest phrasing? Verdict per class

- **His own hands, distinction irrelevant:** the FAERS method (bucketed census, monotonicity bound,
  Wald re-check), the release engineering, the secretless-agent security decision, the licensing/legal
  calls. Phrase in first person.
- **Honest only with an orchestration verb:** Program R, the audits, the WebCoder migration, most Reframe
  lanes. Use "designed and ran", "orchestrated", "independently verified", "adjudicated". Never "built"
  or "wrote" unqualified.
- **The part a reader should actually value is the verification layer**, and it is his: adversarial
  refuters that must execute, `verify_gate_controls.py` (runs every gate twice — clean input must pass,
  injected defect must fail — and states what it does not cover), the never-self-certify rule. The evidence
  for this is unusually good because it includes him catching *his own* false claim and shipping a runnable
  check in its place.
- **Disclosure:** the owner forbids AI disclosure in manuscripts. A resume is not a manuscript, and here
  the orchestration verb is both the honest choice and the more impressive one — "I directed 689 agents
  and measured that 28% of them returned nothing useful" is a stronger engineering statement than any
  unqualified "I built".

---

## 3. Do-not-claim list (consolidated)

1. **1,000 agents / 12.1 h / 225 findings / 42% refuted** — no evidence anywhere; describes a failed run.
2. **1,582 findings / 97 slices / 3 critical RCE** — no evidence anywhere.
3. **12,272-record corpus** — no evidence; the 47.1% data-loss finding replaces it and is better.
4. **"500 units ran"** — 500 is a `BUDGET` constant; the plan funded ~324.
5. **Any mention of the Databricks workspace, the company, or "Databricks-scale" compute** — third-party
   corporate infrastructure under another named person.
6. **"26-repo fleet" / "nightly sweep"** — a premise and a proposal; setup steps are still open; count is stale.
7. **"v1.4.2 shipped"** — no tag, no release. Also: "v1.4.1 released" is wrong; v1.4.0 is the last release.
8. **"295-test suite"** — the PR's own body says 295 *collected* while its receipts say 301 passed / 5 failed.
9. **Any line-count claim from WebCoder PR #152** — the 1.08 M deletions are a purged vendored `venv`.
10. **metaswarm "529 plugin.json"** — the public PR says ~350; use the public number.
11. **Reframe "5,733 / 3,448 tests"** — single-source, uncorroborated; use 526 test files instead.
12. **"34 agents / 96 verifications"** (estate audit) — the run's own journal says 80 started / 45 returned.
13. **Zenodo under "Publications"** — it is a dataset deposit; ORCID has zero works.
14. **`ai-sessions-render`** as a repo name — renamed to `llm-anthology`.

## 4. Open checks that must happen before anything ships

1. **Open `phenibut_deposit_2026-09-18_v3.zip`** and confirm (a) the FAERS scripts/receipts are inside —
   this is the only surviving route to verifying §1.5 — and (b) whether the README's "all gates are
   fail-closed" sentence was corrected in v3. He is linking readers to this archive.
2. **Ask him where `D:\Research` went.** Several of his best research claims rest on receipts that are not
   on this machine.
3. **Re-confirm the `llm-anthology` commit SHAs** (`7dbb99a`, `1afae7b`, `affae65`) against the public repo,
   since the vault note says nothing was pushed at the time it was written.
4. **Decide the WebCoder PR:** merged or closed. A draft PR sitting open and unmodified is a weaker signal
   than no PR at all if he links it.
5. **Re-run every number in the same session the document is written** — his own standing rule, and §1.14
   is the proof of why.

---

## Appendix — evidence I personally opened

**Local (read directly):** `C:\Users\prekzursil\.claude\projects\C--Users-prekzursil\memory\{MEMORY.md,
project_faers_v2_dedup_2026-09-15.md, project_webcoder_wave_delivered_2026-09-22.md,
project_estate_mcp_tui_audit_2026-09-19.md, reference_metaswarm_sessionstart_latency_2026-09-19.md,
reference_partial_remediation_global_claim_2026-09-18.md}`;
`C:\Users\prekzursil\.agents\skills\codex-databricks-fanout\` (file inventory, `scripts/e2e/build_research_targets.py`,
`scripts/harness/lanes/research.py`, `scripts/e2e/run_derive.py`, test-function count).

**Vault (read directly, read-only):** `D:\basic-memory\projects\Program R autonomous research loop 2026-07-26.md`;
`D:\basic-memory\research\Autonomous Codex on GitHub - decision brief 2026-07-11.md`;
`D:\basic-memory\projects\ai-sessions-render\...(47% of real Codex store was silently dropped).md`.
Existence-only (not opened, per owner instruction on security writeups): the six notes referencing the
Bolt workspace.

**Measured with my own instruments (scripts in this scratchpad):**
`wfscan.py`, `wfscan2.py`, `wfscan3.py` (42 journals, event-type tally, §1.14 and §1.15);
`numscan.py` (os.walk over 774 vault + 18 memory + 1,479 journal + 14,094 `.agents` files, §0.3).

**Public, fetched live 2026-09-23:** `api.github.com/repos/Prekzursil/Reframe/{tags,releases}`;
`/repos/Prekzursil/Reframe/git/trees/main?recursive=1`;
`raw.githubusercontent.com/Prekzursil/Reframe/main/.coverage-thresholds.json`;
`/repos/Prekzursil/WebCoder/pulls/152`; `/repos/dsifry/metaswarm/pulls/51`;
`/repos/Prekzursil/agent-skills-toolchain/git/trees/main?recursive=1`;
`/repos/Prekzursil/{Reframe,WebCoder,ai-sessions-render→llm-anthology,agent-skills-toolchain,quality-zero-platform}`;
`zenodo.org/api/records/22836832`.
