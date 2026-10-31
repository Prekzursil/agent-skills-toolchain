---
title: CANONICAL-CLAIMS
type: note
permalink: dqverify-repo-20261013/platform/corpus/canonical-claims
---

# CANONICAL CLAIMS — Phase 1 corpus normalization and mechanism-level deduplication

Corpus root: `C:/Users/Prekzursil/.claude/harness-restore-20260806`  ·  schema `1.0.0`  ·  status **MEASURED**

## Counts

| field | value |
|---|---|
| **raw records in** | **1291** |
| raw records in the claim set (bookkeeping sections excluded) | 1282 |
| excluded as bookkeeping (`lane_section`) | 9 |
| **canonical records out** | **909** |
| **compression ratio (raw in : canonical out)** | **1.4202x** |
| compression ratio over the claim set only | 1.4103x |
| records collapsed | 373 |
| collapse rate | 29.1% |
| merge edges by rule | {'D1': 283, 'D2': 55, 'D3': 11, 'D5': 24} |
| refused merges by reason | {'D3-complete-linkage-refused': 141, 'D4-veto': 18} |
| max cluster size | 6 |
| singleton claims | 606 |
| multi-member clusters | 303 |
| thin-signature multi-member clusters (must be 0) | **0** |

### Raw records by class

| record class | n |
|---|---|
| `option_lane` | 341 |
| `option_universe` | 283 |
| `verify_doc` | 121 |
| `blueprint` | 108 |
| `lane_finding` | 103 |
| `preset` | 72 |
| `council_card` | 59 |
| `protocol` | 58 |
| `mechanism_card` | 38 |
| `decision` | 24 |
| `grill` | 20 |
| `unknown` | 16 |
| `archaeology` | 14 |
| `arch_candidate` | 11 |
| `lane_section` | 9 |
| `probe_finding` | 7 |
| `invariant` | 7 |

Six of these counts independently reproduce a total the corpus declares about itself, which is the extractor's detector control: `option_lane`=341 vs "Pre-dedup total across the five lanes: 341"; `option_universe`=283 vs "Final distinct options: 283"; `preset`=72; `protocol`=58; `mechanism_card`=38; and the authored dedup ledger parses to 50 rows / 55 absorbed ids vs "50 canonical options absorbed 55 sibling cards".

**Correction to the orchestrator brief (measured, three independent signals).** The brief pins `09-WORKFLOW-BLUEPRINT-LIBRARY.md` at "96 blueprint DESIGNS". It holds **108**: 108 `### \`BP-*\`` headings, a `by_family` histogram whose 20 rows sum to 108, and the document's own prose "Anti-overfit anchor - applied to all 108". `96` is REFUTED.

## Dedup rule

Deduplicate at the MECHANISM level, not the wording level. A mechanism is the triple (verb_set, locus, artifact_set): WHAT the record does, WHERE the change lands, and WHICH concrete named things it operates on. Two records describing the same triple in different words are duplicates; two records sharing wording but differing in the triple are not.

- **D1_identity** — Same local id across a document and a document that DECLARES itself that document's consolidation (07-OPTION-UNIVERSE.md over the five 07-OPTIONS-*.md lane docs) => same record. Exact, no judgement.
- **D2_authored_absorption** — 07-OPTION-UNIVERSE.md section 3 publishes a dedup ledger of (canonical <- absorbed) edges. Those 55 edges are INHERITED and tagged authored-ledger. They are NOT evidence that D3 works -- they are the positive control D3 is measured against.
- **D3_mechanism_signature** — verb agreement (jaccard(verbs) >= 0.50 OR |verbs cap| >= 3) AND locus COMPATIBILITY (top-2 locus sets intersect) AND artifact agreement (both name concrete artifacts -> jaccard(hard) >= 0.25 OR |hard cap| >= 2; otherwise jaccard(soft_concepts) >= 0.60). A record that names no concrete artifact cannot DISAGREE about one, so the asymmetric case falls through to the concept path instead of being rejected.
- **D4_authored_distinction_veto** — If either record's own 'not a duplicate:' field names the other's id, they are NEVER merged whatever D3 says. A lexical signature does not overrule an authored distinction. This is the precision guard.
- **D5_verify_document_target_identity** — Two adversarial verification documents re-verifying ONE finding collapse when TWO signals derived from DIFFERENT parts of the document agree: (a) BODY -- the concrete artifact paths named in the document head intersect, AND (b) NAME -- topic-slug token jaccard >= 0.60 after stripping the ADV/VERIFY/Vn scaffolding, which encodes only which PASS ran, never what was verified. Requiring both is what stops D5 degrading into a filename-similarity rule. 24 merges fired on this corpus and all 24 were hand-audited as genuine re-verifications; that audit is author judgement, not a mechanical control, and the settling experiment is an independent reviewer re-adjudicating the same 24.
- **error_direction** — Tuned for PRECISION, not recall. A false MERGE destroys a distinct mechanism invisibly; an under-merge leaves the duplicate pair sitting in the output where it is auditable. Operating point chosen by a criterion fixed before the sweep: maximise recall subject to false_merge_rate <= 0.02.

### Dedup rule — measured, in both states

| control | pairs | D3 fired | rate |
|---|---|---|---|
| POSITIVE (authored ledger absorptions, D2 off) — must fire | 55 | 14 | recall **0.2545** |
| NEGATIVE-1 (authored `not a duplicate:` pairs, D4 off) — must NOT fire | 616 | 11 | false-merge **0.0179** |
| NEGATIVE-2 (intra-document declared-distinct pairs) — must NOT fire | 17399 | 12 | false-merge **0.00069** |

**NEGATIVE-2 exists because NEGATIVE-1 was not enough, and that is the sharpest lesson in this unit.** NEG-1 scored an earlier operating point clean at 1.62% while the build that point produced merged 15 records on the single shared word "gate" and 10 on "index". All 616 NEG-1 pairs live in the option families, which carry rich hand-written mechanism prose; the failure lives in the classes that carry NO mechanism field at all (blueprints, presets, protocols, archaeology, verify docs). A control measured on a population that structurally excludes the failure mode is a weak control — the same defect class as a probe that is silent in both states, one level up. The signature-richness and absolute-intersection floors are the fix; `controls.py` is the measurement.

**A pairwise false-merge rate does not bound CLUSTER quality either.** Single-linkage D3 produced 427 edges whose transitive closure collapsed 461 records — a third of the corpus — into one claim, with every individual edge inside the audited budget, because chaining a-b, b-c never has to justify a-c. D3 therefore runs with COMPLETE linkage: a record joins a cluster only if it matches every member, and an over-budget linkage check is refused rather than approximated.

A detector that is silent in both states measures nothing, so both extremes were also run: impossible thresholds fire 0/55 and permissive thresholds fire 52/55 (`DEDUP-VALIDATION.json.detector_controls`).

**The honest headline: a lexical mechanism signature does NOT reproduce human mechanism-level dedup at acceptable precision — 23.6% recall at a 1.6% false-merge budget.** So `canonical_records_out` is an UPPER BOUND on distinct mechanisms: under-merged by a measured margin, never over-merged past the audited 1.6%.

## Worked examples — 4 merges (3 required)

### Merge 1 — rule `D5` → claim `CLM-a4697592829d` (cluster size 6)

- **A** `ADV-V-dup-guard-cp1252-verify.md:1` [verify_doc] — ADVERSARIAL VERIFY — dup-guard cp1252 decode (BROKEN-FIRING / behaviour)
  - mechanism: ADVERSARIAL VERIFY — dup-guard cp1252 decode (BROKEN-FIRING / behaviour)
- **B** `ADV-VERIFY-dup-guard-cp1252.md:1` [verify_doc] — ADV-VERIFY — dup-guard cp1252 decode finding (encoding half only)
  - mechanism: ADV-VERIFY — dup-guard cp1252 decode finding (encoding half only)
- **why this is ONE mechanism:** Two adversarial verification documents re-verifying ONE finding on ONE artifact, under different pass names. A re-verification is the same claim measured again -- it is NOT independent evidence for a second claim, which is exactly why collapsing it matters for a ranking that refuses to count repetition.
- match detail: `{"shared_target_paths": ["users/prekzursil/.claude/hooks/dup-guard/guard.py"], "slug_jaccard": 0.75, "slug_a": ["cp1252", "dup", "guard", "v"], "slug_b": ["cp1252", "dup", "guard"], "body_signal": true, "name_signal": true}`

### Merge 2 — rule `D1` → claim `CLM-95c429aa7f97` (cluster size 4)

- **A** `07-OPTION-UNIVERSE.md:875` [option_universe] — Owner-controlled marketplace index (local directory and/or private git), replacing file-copy deployment
  - mechanism: One owner marketplace (a real on-disk directory and/or a private git repo with marketplace.json) consumed by the native plugin channel at user scope; deployment becomes install+enable+version, drift becomes a visible version mismatch, and the dangling registra
- **B** `07-OPTIONS-AB.md:599` [option_lane] — Static Git-backed owner index (no server)
  - mechanism: one repo containing `marketplace.json` (an index of packages, versions, source refs) plus the packages. Consumers add it by URL. No server, no API, no auth
-
- **why this is ONE mechanism:** SAME option id in a lane document and in the document that declares itself that lane document's consolidation. One record, written down twice. No judgement is exercised and none is needed -- this is the single largest source of apparent duplication in the corpus (283 of 353 collapses).

### Merge 3 — rule `D2` → claim `CLM-95c429aa7f97` (cluster size 4)

- **A** `07-OPTION-UNIVERSE.md:875` [option_universe] — Owner-controlled marketplace index (local directory and/or private git), replacing file-copy deployment
  - mechanism: One owner marketplace (a real on-disk directory and/or a private git repo with marketplace.json) consumed by the native plugin channel at user scope; deployment becomes install+enable+version, drift becomes a visible version mismatch, and the dangling registra
- **B** `07-OPTIONS-AB.md:648` [option_lane] — Private local-directory marketplace for owner-authored packages
  - mechanism: a real directory marketplace, present on disk, registered in both surfaces, holding owner packages. Zero network
-
- **why this is ONE mechanism:** The corpus's OWN dedup ledger says these are one mechanism, and names the surviving canonical wording. Inherited on the author's authority and tagged as such; it is the positive control D3 is measured against, never evidence that D3 works.

### Merge 4 — rule `D3` → claim `CLM-753414957218` (cluster size 4)

- **A** `07-OPTION-UNIVERSE.md:1703` [option_universe] — Deploy claim-verify-gate and close its certifies-nothing hole
  - mechanism: Deploy from the mirror AFTER applying the fix: require a non-empty source probe for any CONFIRMED/REFUTED verdict BEFORE fingerprint comparison, and add the missing-source regression case.
-
- **B** `13-ARCHITECTURE-CANDIDATES.md:1196` [mechanism_card] — Deploy `claim-verify-gate` AND close its documented hole first.
  - mechanism: `rules/common/single-signal-verification.md` cites
`.agents/skills/claim-verify-gate/scripts/claim_gate.py` by `file:line` and documents that a
CONFIRMED claim with **no `source_probe`** returns `violations: []`, `ok: true`, exit 0 — and that
path **does not e
- **why this is ONE mechanism:** Different words, same mechanism triple: the verb classes agree, the loci are compatible, and both records name the SAME concrete artifacts. This is the only rule that exercises mechanism-level judgement, and it is the one held to a measured false-merge budget.
- match detail: `{"verb_jaccard": 1.0, "verb_overlap": 4, "hard_jaccard": 0.0, "hard_overlap": 0, "soft_jaccard": 0.5, "soft_overlap": 3, "locus_compatible": true, "locus_a": "evidence-gates", "locus_b": "skills-rules", "path": "concept", "signatures_rich": true, "blocked_by": []}`

## Worked examples — 4 deliberate non-merges (3 required)

### Non-merge 1 — refused by `D3-complete-linkage-refused`

- **A** `07-OPTION-UNIVERSE.md:964` [option_universe] — Trust tiers that gate what a package may register
- **B** `07-OPTION-UNIVERSE.md:1124` [option_universe] — Cross-vendor two-person review for anything that registers a hook
- **why these are TWO mechanisms:** This pair matched, but merging their two CLUSTERS would have put records together that do NOT match each other. Single linkage would have accepted it and chained; on the real corpus that produced one 461-member cluster from 427 in-budget edges. Refusing here is the difference between a pairwise budget and an actual bound on cluster quality.
- detail: `{"verb_jaccard": 0.5, "verb_overlap": 3, "hard_jaccard": 1.0, "hard_overlap": 0, "soft_jaccard": 0.4, "soft_overlap": 2, "locus_compatible": true, "locus_a": "corpus-claims", "locus_b": "corpus-claims", "path": "concept-both-empty", "signatures_rich": true, "blocked_by": ["artifact"]}`

### Non-merge 2 — refused by `D4-veto`

- **A** `07-OPTION-UNIVERSE.md:1834` [option_universe] — Hook-stdin fuzz corpus
- **B** `07-OPTIONS-EFG.md:261` [option_lane] — Differential replay of hooks against a recorded real-payload corpus
- **why these are TWO mechanisms:** The signature matched, and the merge was refused anyway: one of these records names the other in its own `not a duplicate:` field. The author separated them deliberately -- A-01 is the merge OPERATION, A-02 is the ownership IDENTITY that operation needs. A lexical signature does not get to overrule an authored distinction.
- detail: `{"verb_jaccard": 0.5, "verb_overlap": 2, "hard_jaccard": 0.0, "hard_overlap": 0, "soft_jaccard": 0.5, "soft_overlap": 2, "locus_compatible": true, "locus_a": "evidence-gates", "locus_b": "corpus-claims", "path": "concept", "signatures_rich": true, "blocked_by": []}`

### Non-merge 3 — refused by `D3-blocked-on-richness`

- **A** `07-OPTION-UNIVERSE.md:596` [option_universe] — Merge-not-replace hook installer
- **B** `07-OPTION-UNIVERSE.md:605` [option_universe] — Ownership-tagged registration groups
- **why these are TWO mechanisms:** Both signatures are too thin to be mechanisms: fewer than two verb classes and no concrete artifact between them. Merging on that is a WORDING match -- it is how 15 records once collapsed because they all contained the word "gate". Same words, no shared mechanism, so: two records.
- detail: `{"verb_jaccard": 0.2, "verb_overlap": 1, "hard_jaccard": 1.0, "hard_overlap": 0, "soft_jaccard": 0.0, "soft_overlap": 0, "locus_compatible": true, "locus_a": "installer", "locus_b": "settings-registration", "path": "concept-both-empty", "signatures_rich": false, "blocked_by": ["richness", "verb", "artifact"]}`

### Non-merge 4 — refused by `D3-blocked-on-artifact`

- **A** `07-OPTION-UNIVERSE.md:643` [option_universe] — Runtime host-event capability probe (observed-events ledger)
- **B** `07-OPTION-UNIVERSE.md:1905` [option_universe] — Silence is a FAILURE: per-check verdict accounting emitted as a durable, diffable dispatch decision
- **why these are TWO mechanisms:** Same operation, same neighbourhood, DIFFERENT things operated on. The verb classes agree and the loci are compatible, but the concrete artifact sets do not overlap enough, so these are two mechanisms that happen to be described in similar language.
- detail: `{"verb_jaccard": 0.429, "verb_overlap": 3, "hard_jaccard": 0.0, "hard_overlap": 0, "soft_jaccard": 0.0, "soft_overlap": 0, "locus_compatible": true, "locus_a": "hook-dispatch", "locus_b": "hook-dispatch", "path": "concept", "signatures_rich": true, "blocked_by": ["artifact"]}`

## Ranking rule

Rank by independent evidence, cross-domain convergence, severity and decision impact. repetition_count is COMPUTED and PUBLISHED but carries WEIGHT ZERO.

Weights: `{'independent_evidence': 3, 'cross_domain_convergence': 2, 'severity': 2, 'decision_impact': 3}` · repetition weight **0**.

- All records from ONE source document collapse to ONE lineage.
- A declared consolidation of another document does NOT count as a second lineage -- that is the same authors re-reading their own output.
- Evidence is counted once per KIND (executed output / file:line / both-states control / second independent probe), never once per record asserting it.

Proof: test_corpusnorm.py::test_repetition_has_zero_weight clones a cluster's supporting records 10x and asserts the composite score is bit-identical.

## Known limits (inline, not a trailing disclaimer)

- UNDER-MERGED, measured: D3 recovers 25.45% (14/55) of the authored dedup ledger's merges, at an authored-pair false-merge rate of 1.79% (11/616) and an intra-document rate of 0.069% (12/17399). ~75% of the author's own mechanism merges are paraphrases sharing no verb+artifact vocabulary, so canonical_records_out is an UPPER BOUND on the number of distinct mechanisms in the corpus. Settling experiment: have an independent reviewer adjudicate the 41 D3-missed ledger pairs listed in DEDUP-VALIDATION.json; if they are genuine paraphrase merges the residual is SEMANTIC and not closable by any threshold change -- it would need an embedding or an LLM adjudicator, which this unit does not ship.
- The superseded sweep-v1 numbers quoted in dedup.py (recall 0.2364 / false-merge 0.0162) are a HISTORICAL console measurement and are NOT reproducible from the code as it now stands: the D3 predicate itself changed afterwards (signature-richness floors, absolute-intersection floors, locus compatibility, complete linkage). Re-running _probe_dedup_sweep.py today measures the CURRENT predicate over the v1 grid and will not reprint the v1 figures. They are retained only to record WHY the criterion was revised, not as a live result.
- D5 precision (24/24 merges judged correct) was established by the author reading all 24 pairs, NOT by an independent control set -- there is no authored ground truth for verify-document identity in the corpus. Treat it as author judgement. Settling experiment: an independent reviewer re-adjudicates the same 24 pairs listed under merge rule D5 in CANONICAL-CLAIMS.json.
- The two negative controls bound FALSE merges. Neither bounds false SPLITS beyond the positive control's 55 pairs, and the positive control covers only the option families. For the blueprint / preset / protocol / verify-doc classes there is no authored merge ground truth at all, so D3 recall in those classes is NOT-CHECKED rather than measured.
- COVERAGE: extraction targets the 16 STRUCTURAL record classes enumerated in extract.py. Measured ground truth stated in PROSE (rather than under a labelled heading) in 07-OPTIONS-CD/HIJK/LM is NOT extracted -- only 07-OPTIONS-AB.md carries labelled '### P1 -' probe sections, so probe_finding=7 is the honest full count of that class, not of all measured facts in the corpus.
- COVERAGE: the corpus holds 5,338 .md and 2,746 .json files; this pass reads the ~180 top-level report documents. Per-run scratch artifacts under the ~80 _adv*/verify*/wave* subdirectories are NOT normalised. NOT-CHECKED, not clean.
- The 07-OPTION-UNIVERSE.md dedup ledger is INHERITED as D2, not independently re-derived. Its 55 edges are the corpus author's judgement; this artifact reuses it and says so.

## Ranked canonical claims

Top 60 by composite. Full set in `CANONICAL-CLAIMS.json`.

| # | claim id | score | ev | conv | sev | imp | status | locus | mechanism | reps |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | `CLM-d4f004a1c4ee` | 28/30 | 3 | 2 | 3 | 3 | CONFIRMED | evidence-gates | **measured still open today** `[M]`: two live junctions into the real Chrome/Edge `User Data`, and INV-3's `ok` expression has no `junctions` term | 2 |
| 2 | `CLM-bdbcc4cacda2` | 25/30 | 2 | 2 | 3 | 3 | DESIGN-ONLY | evidence-gates | Builder and verifier are different vendors; the verifier re-derives the load-bearing properties from the mirror with a both-states control. Transport  | 3 |
| 3 | `CLM-1ee6b8c16325` | 24/30 | 3 | 3 | 3 | 1 | CONFIRMED | vcs-repo | ADVERSARIAL VERIFY — "Six live paths carrying real behaviour are unversioned in BOTH repo harness trees" | 3 |
| 4 | `CLM-21258ea15f64` | 24/30 | 3 | 3 | 3 | 1 | CONFIRMED | unknown | Lane 15b — ADVERSARIAL VERIFY of the `modules.py` LIVE-STALE bundle finding | 3 |
| 5 | `CLM-fcaf436f6179` | 24/30 | 3 | 3 | 3 | 1 | CONFIRMED | hook-dispatch | Adversarial verification — `~/.agents/harness/dispatcher.py` DIVERGED / behaviour | 3 |
| 6 | `CLM-2292061a6a7a` | 23/30 | 3 | 1 | 3 | 2 | REFUTED | evidence-gates | ADV lane 9 — VERDICT: **REFUTED** (finding: "origin/main's deny.py is the PRE-#260 file") | 1 |
| 7 | `CLM-2d687815fe37` | 23/30 | 3 | 2 | 2 | 2 | CONFIRMED | hook-dispatch | `path:C:/Users/Prekzursil/.claude/hooks` · klass:IMPROVEMENT · claimed sev:medium **Verdict: CONFIRMED on facts — SEVERITY DOWNGRADED to `info`.** The | 2 |
| 8 | `CLM-333ee7efe0cc` | 23/30 | 3 | 2 | 2 | 2 | REFUTED | evidence-gates | ADVERSARIAL VERIFY — "INV-5 / INV-3 detector controls are wired to artifacts under repair" | 2 |
| 9 | `CLM-585183caef5e` | 23/30 | 3 | 1 | 3 | 2 | REFUTED | evidence-gates | Lane 14 — NO-REGRESSION CONTRACT · ADVERSARIAL RE-DERIVE | 1 |
| 10 | `CLM-69efe033a2bd` | 23/30 | 3 | 1 | 3 | 2 | NOT-CHECKED | security-credentials | CRCP stays quarantined | 1 |
| 11 | `CLM-97f174300a47` | 22/30 | 3 | 2 | 3 | 1 | CONFIRMED | vcs-repo | ADVERSARIAL VERIFY — `scripts/sync-from-live.ps1` has no `~/.agents/harness` mapping | 2 |
| 12 | `CLM-b0af08c36125` | 22/30 | 3 | 3 | 2 | 1 | CONFIRMED | recall-memory | `C:/Users/Prekzursil/.claude/hooks/event-ledger/ledger.py`, DIVERGED / bof:formatting, claimed sev=medium tier=hold-for-owner.  **VERDICT: CONFIRMED** | 3 |
| 13 | `CLM-b546d7b3bc34` | 22/30 | 3 | 2 | 3 | 1 | REFUTED | security-credentials | ADV4 — ADVERSARIAL VERIFY: deny-credential-reads/deny.py "do-not-touch" finding | 2 |
| 14 | `CLM-52d0230322a3` | 22/30 | 2 | 2 | 3 | 2 | DESIGN-ONLY | installer | Replace the whole-key assignment with a per-event, per-group merge: harness-owned groups replaced, every other group carried through untouched; the ti | 2 |
| 15 | `CLM-59eea6a4f8e8` | 22/30 | 2 | 2 | 3 | 2 | DESIGN-ONLY | corpus-claims | One register combining a scan (file, line, claim text, tag, is-in-final-15-percent, does-a-recommendation-depend-on-it) with authored records (what, w | 3 |
| 16 | `CLM-7825ecdc359d` | 22/30 | 2 | 2 | 3 | 2 | DESIGN-ONLY | security-credentials | A third state that evaluates the guard and records would-be denials to the detector ledger without denying anything; the default stays OFF. - | 2 |
| 17 | `CLM-2fd1a1edb350` | 22/30 | 1 | 2 | 3 | 3 | DESIGN-ONLY | corpus-claims | Extend the existing corpus tool with two sources - run records and agent journals - parsed into one append-only index keyed by run and agent id, strea | 3 |
| 18 | `CLM-69dedb87d291` | 22/30 | 1 | 2 | 3 | 3 | DESIGN-ONLY | vcs-repo | Run the existing cache reaper: retain installed + N-1 for enabled packages, delete temp clones older than X days, clean orphaned state siblings keepin | 3 |
| 19 | `CLM-6a2ce28eb30d` | 22/30 | 1 | 2 | 3 | 3 | DESIGN-ONLY | hook-dispatch | Each hook declares its required event; a test asserts that event is in the generator's list or in one of the four measured registration channels. No n | 2 |
| 20 | `CLM-7cf43b1a5873` | 22/30 | 1 | 2 | 3 | 3 | DESIGN-ONLY | hook-dispatch | Extend the existing PreToolUse deny guard so a call attributable to a package is checked against its declaration; undeclared access denied with a name | 2 |
| 21 | `CLM-86554dab7030` | 22/30 | 1 | 2 | 3 | 3 | DESIGN-ONLY | routing-models | Manifest entries gain a when: predicate over tool, path and cwd; non-matching checks never spawn. - | 2 |
| 22 | `CLM-94c7eb28e7fb` | 22/30 | 1 | 2 | 3 | 3 | DESIGN-ONLY | marketplace-plugins | TTL plus last-used plus declared-retired scan produces a PROPOSAL list; retirement moves to an attic (the pattern already used), never deletes. - | 2 |
| 23 | `CLM-9b260c4ae04f` | 22/30 | 1 | 2 | 3 | 3 | DESIGN-ONLY | security-credentials | ONE stdlib predicate module (is-force-push-to-protected, contains-live-secret, and so on) called by the existing checks. - | 2 |
| 24 | `CLM-aefcaf12ca0d` | 22/30 | 1 | 2 | 3 | 3 | DESIGN-ONLY | corpus-claims | At launch resolve and record every declared source ref as a full 40-char sha plus tool versions, model ids, prompt bytes hash, grounding-pack hash and | 4 |
| 25 | `CLM-a4697592829d` | 21/30 | 3 | 3 | 3 | 0 | CONFIRMED | unknown | ADVERSARIAL VERIFY — dup-guard cp1252 decode (BROKEN-FIRING / behaviour) | 6 |
| 26 | `CLM-048b2bb00de4` | 20/30 | 3 | 1 | 3 | 1 | CONFIRMED | hook-dispatch | ADVERSARIAL VERIFY — dispatcher.py DIVERGED / do-not-touch | 1 |
| 27 | `CLM-1800613c9dbf` | 20/30 | 3 | 1 | 3 | 1 | CONFIRMED | security-credentials | ADVERSARIAL VERIFY — CRCP quarantine profile-junctions (SECURITY / medium) | 1 |
| 28 | `CLM-1d105f1fc1bc` | 20/30 | 3 | 1 | 3 | 1 | REFUTED | unknown | Lane: harness-tree-reconcile — ADVERSARIAL RE-DERIVE | 1 |
| 29 | `CLM-3243e4bdf106` | 20/30 | 3 | 1 | 3 | 1 | DESIGN-ONLY | routing-models | CROSS-VENDOR CAPABILITY-GRAPH | 1 |
| 30 | `CLM-5157b27a701d` | 20/30 | 3 | 1 | 3 | 1 | CONFIRMED | hook-dispatch | ADVERSARIAL VERIFY (pass 2, independent) — dispatcher.py DIVERGED finding | 1 |
| 31 | `CLM-5e00401810e4` | 20/30 | 3 | 1 | 3 | 1 | REFUTED | corpus-claims | Adversarial verification — "recall-index.json 103.8h stale, PULL broken, sev:high" | 1 |
| 32 | `CLM-70fab21f8648` | 20/30 | 3 | 1 | 3 | 1 | REFUTED | unknown | ADVERSARIAL VERIFY — modules.py "LIVE-STALE, safe to deploy" — **REFUTED** | 1 |
| 33 | `CLM-8698dbdceb51` | 20/30 | 3 | 1 | 3 | 1 | NOT-CHECKED | hook-dispatch | The whole live hook tree: known-red baseline is **26 failed / 1 error / 861 passed** | 1 |
| 34 | `CLM-898471a74d4b` | 20/30 | 3 | 1 | 3 | 1 | REFUTED | unknown | ADV3 — adversarial verification of the `modules.py LIVE-STALE / auto-low-risk` finding | 1 |
| 35 | `CLM-900a052ac174` | 20/30 | 3 | 1 | 3 | 1 | CONFIRMED | hook-dispatch | ADVERSARIAL VERIFY — "136 is the deny dir only; the whole live hook tree is 861/26/1" | 1 |
| 36 | `CLM-a19b5b0488d2` | 20/30 | 3 | 1 | 3 | 1 | NOT-CHECKED | security-credentials | Security: 4 native Read denies present AND credential guard stays opt-in-OFF | 1 |
| 37 | `CLM-a7a37546179c` | 20/30 | 3 | 1 | 3 | 1 | CONFIRMED | corpus-claims | ADVERSARIAL VERIFY — `~/.agents/harness/ledger.py` LIVE-AHEAD claim | 1 |
| 38 | `CLM-adb63a174eba` | 20/30 | 3 | 1 | 3 | 1 | CONFIRMED | hook-dispatch | ADVERSARIAL VERIFY — dispatcher.py DIVERGED finding | 1 |
| 39 | `CLM-bb942d3a3b64` | 20/30 | 3 | 1 | 3 | 1 | CONFIRMED | installer | ADV-VERIFY — install.py whole-key hooks replace (MISWIRED / behaviour) | 1 |
| 40 | `CLM-e7d638f9c82e` | 20/30 | 3 | 1 | 3 | 1 | REFUTED | unknown | ADVERSARIAL VERIFY — `modules.py` LIVE-STALE / safe-to-deploy finding | 1 |
| 41 | `CLM-f34fdacd6508` | 20/30 | 3 | 1 | 3 | 1 | REFUTED | unknown | ADVERSARIAL VERIFY — `check_no_regression.py` deliverable (lane 14) | 1 |
| 42 | `CLM-f6af0645c60e` | 20/30 | 3 | 1 | 3 | 1 | REFUTED | hook-dispatch | lane hooks-reconcile — ADVERSARIAL RE-DERIVE (default REFUTED) | 1 |
| 43 | `CLM-5fb105f6f251` | 20/30 | 2 | 2 | 2 | 2 | CONFIRMED | evidence-gates | ADVERSARIAL VERIFY — INV-3 junction gate is fail-open (check_no_regression.py:233) | 2 |
| 44 | `CLM-7753b8e0ffc8` | 20/30 | 2 | 1 | 3 | 2 | NOT-CHECKED | installer | Is `install.py`'s hooks-key wipe still reproducible on the CURRENT settings.json? | 1 |
| 45 | `CLM-7aee62ae6d50` | 20/30 | 2 | 1 | 3 | 2 | NOT-CHECKED | corpus-claims | Adversarial verification — HarnessRecallRefresh / recall-index staleness | 1 |
| 46 | `CLM-c815350f71fb` | 20/30 | 2 | 1 | 3 | 2 | DESIGN-ONLY | marketplace-plugins | IMMUTABLE / CONTENT-ADDRESSED DEPLOY (release channels, no marketplace) | 1 |
| 47 | `CLM-d4b364401127` | 20/30 | 2 | 1 | 3 | 2 | DESIGN-ONLY | corpus-claims | Claim-Decomposition Verification Pass | 1 |
| 48 | `CLM-6b5bee3ed02a` | 20/30 | 1 | 1 | 3 | 3 | NOT-CHECKED | security-credentials | Remove the two CRCP profile junctions, and close INV-3's fail-open? | 1 |
| 49 | `CLM-798b6f04d757` | 20/30 | 1 | 1 | 3 | 3 | DESIGN-ONLY | hook-dispatch | Hook Event-Reachability Conformance Test | 1 |
| 50 | `CLM-ff8de708ee6c` | 19/30 | 3 | 2 | 0 | 2 | DESIGN-ONLY | evidence-gates | A typed VERIFY-REPORT with exactly two re-derived booleans, each carrying its own probe and a both-states control; the verifier may not read the autho | 2 |
| 51 | `CLM-17e32da19e91` | 19/30 | 2 | 2 | 3 | 1 | CONFIRMED | hook-dispatch | Adversarial re-verification — dispatch.py / manifest.json LIVE-AHEAD finding | 2 |
| 52 | `CLM-d1f6148a7de3` | 19/30 | 2 | 2 | 3 | 1 | DESIGN-ONLY | security-credentials | A pre-write deny when a write targets a protected path held by another session's lease, or when the writer cannot prove it read the current hash first | 2 |
| 53 | `CLM-196a0068569e` | 19/30 | 1 | 2 | 3 | 2 | DESIGN-ONLY | corpus-claims | probes/<claim-id> - exit 0 means the defect is absent, exit 1 means present, one terminal line; a CONFIRMED defect with no probe downgrades to PLAUSIB | 2 |
| 54 | `CLM-2843892f2c2a` | 19/30 | 1 | 2 | 3 | 2 | DESIGN-ONLY | workflow-runtime | Hash the body at launch, store sha->body, stamp the run record; wf diff renders a semantic diff (stages, agent counts, required-list deltas, model bin | 2 |
| 55 | `CLM-47d91c9ad1f6` | 19/30 | 1 | 2 | 3 | 2 | DESIGN-ONLY | corpus-claims | One generated export - program, refs, claims, decisions, contradictions, unknowns, probes, retained artifacts - produced FROM the ledger so it cannot  | 2 |
| 56 | `CLM-52538227732e` | 19/30 | 1 | 2 | 3 | 2 | DESIGN-ONLY | workflow-runtime | Each stage writes its artifact as its FIRST act (skeleton with every claim marked unknown plus a coverage line), rewrites at each milestone, and recor | 3 |
| 57 | `CLM-5811f0315077` | 19/30 | 1 | 2 | 3 | 2 | DESIGN-ONLY | corpus-claims | Extend the corpus tool to emit bounded, redacted real payloads; replay old code and new code over the same N and diff exit, verdict and wall time. Off | 3 |
| 58 | `CLM-6777da867894` | 19/30 | 1 | 2 | 3 | 2 | DESIGN-ONLY | corpus-claims | A per-detector fires/silent fixture pair with a one-line statement of what makes it broken, plus a harvest step that turns each recorded incident into | 3 |
| 59 | `CLM-6b613709cd99` | 19/30 | 1 | 2 | 3 | 2 | DESIGN-ONLY | evidence-gates | About 30 adversarial payloads (truncated JSON, BOM, cp1252, embedded control bytes, 5 MB body, null tool input, surrogates); every hook must exit 0 AN | 4 |
| 60 | `CLM-753dd65f4612` | 19/30 | 1 | 2 | 3 | 2 | DESIGN-ONLY | evidence-gates | Copy the cited span plus context to an evidence store keyed by sha256, recording path, file sha, line range and span sha at CLAIM time, not after the  | 2 |

`reps` is the repetition count. It is published so a reader can see it was measured and NOT used: two claims with the same score and different `reps` are adjacent in this table by construction.