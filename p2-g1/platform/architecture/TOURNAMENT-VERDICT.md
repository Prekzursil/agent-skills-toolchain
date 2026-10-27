# TOURNAMENT VERDICT — Nine-Architecture Judge Panel

**Unit:** `tournament/judge-panel` · Phase 3 · Spec `_USER-PROMPTS.md:10769-10796`
**Judged at** `HEAD = edcf9f5b`. The brief pinned `dc90d64a`; it is an **ancestor, 5 commits behind**
(`git merge-base --is-ancestor dc90d64a HEAD` → 0). Every candidate was read **in full** (385,399 B
across 9 files), not as a digest.
**Status:** COMPLETE. All 10 axes scored, winner named, minority report written, migration path
anchored on the real HEAD.

**Evidence classes.** `[J]` measured by this panel with a named probe and a both-states control ·
`[A]` asserted by an advocate and re-verified by `[J]` · `[A-only]` asserted by an advocate and
**not** re-verified here · `UNVERIFIED` inline with the settling experiment.
Bands: *almost certain* 90-99 · *likely* 55-80 · *roughly even* 40-60.

Panel probes (read-only, both-states controlled, `SUCCESS:`-terminated):
`platform/architecture/_judge_verify.py` · `_judge_verify2.py` · `_judge_refutation.py`

---

## 0. Two corrections to the brief the panel had to make before judging

**0.1 — "Nine architectures were committed" is FALSE.** `git ls-files platform/architecture/` → **0**.
`git status --porcelain` → `?? platform/architecture/`. 103 files on disk, 0 tracked `[J]`. The nine
documents this panel judged, and this verdict, exist only in one working tree.

**0.2 — the uncommitted surface is far larger than any single candidate measured.** Six of nine docs
independently reported "233 shims untracked". The true figure at `edcf9f5b` `[J]`:

| tree | tracked | on disk | untracked |
|---|---:|---:|---:|
| `command-center/schema` | 0 | 233 | **233** |
| `platform/lib` | 50 | 388 | **338** |
| `platform/lib/workflows` | 0 | 260 | **260** |
| `platform/lib/foundry` | 0 | 23 | **23** |
| `platform/architecture` | 0 | 103 | **103** |
| `command-center` | 75 | 492 | **417** |
| `platform/schema` | 32 | 42 | **10** |

`platform/lib/schema_resolver.py --audit` reports `references_resolving: 2007`,
`distinct_logical_files: 234/234`, `SUCCESS:schema-resolver-audit` — **but 2 of its 3
`physical_control_plane` files and the resolver itself are untracked** `[J]`. So the brief's "ONE P1
STILL OPEN" is **closed on disk and uncommitted**, and a fresh clone at `edcf9f5b` resolves **0 of
234**. Confirmed on two mechanically independent git signals (`ls-files` = 0; `status -uall` = 233)
plus `git check-ignore` returning nothing, so this is un-staged, not ignored. *Almost certain.*

**0.3 — the suite baseline every candidate cites is stale.** Docs cite 444, 475, 214 functions, 457,
and 818/1254/1912. Measured now, three consecutive runs: **2,781 collected, stable**, then
**2,767 passed / 14 skipped / 0 failed in 95.30 s** `[J]`. `maximal-hybrid`'s F4 instability finding
is CONFIRMED as a *historical* measurement of a tree under concurrent sibling writes (its readings
increase monotonically, 818→1254→1912→2781); the tree is now quiescent and green, so its conclusion
"no candidate can be judged on test counts" holds **for the numbers in the nine docs** and no longer
holds for the current tree. Its F7 (7 flagship blueprints with no dedicated test file, failing in all
three of its runs) is **REFUTED as a current-state claim** — 0 failures now.

---

## 1. The four live defects this tournament actually found, verified by the panel

The panel re-derived each with its own probe rather than trusting the advocate. All four carry
both-states controls.

| # | defect | measured by panel | closed by |
|---|---|---|---|
| **D1** | Predicate condition 9 accepts **10 of 10** same-vendor alias pairs as "cross-vendor" — `anthropic`/`Anthropic`, `anthropic`/`claude`, `openai`/`codex`, `google`/`gemini`, and trailing-whitespace variants all return `SATISFIED`. Controls valid: identical spelling → `UNSATISFIED`; distinct vendor → `SATISFIED` `[J]` | direct execution of the shipped `_c9_reviewer`; `completion_predicate.py:935` is `rev_vendor == exec_vendor`; `receipt.schema.json:261,471` type vendor as free-text `string`/`maxLength 64` with **0** vendor enums | `cross-vendor` Plane A |
| **D2** | The work-unit plane has **0 authorization rules** against the DSL plane's **14** (`check_work_units` → `SEM-001..007`; `check_workflow` → `DSL-SEM-001..014`). Meanwhile **144** units declare `owner_approval_required: true`, **25** hold `Task`, **23** of those are unapproved, **261** hold an `mcp__` token, **120** hold a wildcard token `[J]` | AST-free per-function rule extraction + catalog census | `security-first` Plane A |
| **D3** | `test_generator_is_deterministic` snapshots **4** paths against **231** generated shims (1.7%), and it runs `_gen_schema_substrate.py` with `cwd=REPO` — so it **repairs the real tree** while taking an unused `tmp_path` fixture. A hand-edit to any of the 227 unsampled shims is silently reverted by running the suite `[J]` | direct read of `test_schema_resolver.py:281-301` + `ls command-center/schema/*.schema.json` = 231. Mechanically independent of `maximal-hybrid`'s mutation probe | `maximal-hybrid` S1 |
| **D4** | The P1 closure is uncommitted; ~1,300 files across 7 trees are untracked (§0.2) `[J]` | two independent git signals + `check-ignore` | every candidate's Phase 0 |

**D1 and D3 are false greens in shipped gates. D2 is an absent gate. D4 is an absent commit.**
On this estate's own doctrine a false green outranks an absent gate, and that ordering does real
work in §3 below.

### 1.1 A defect class the panel found that no advocate did: an UNDER-claim

`security-first` §6.3 concedes *"Egress is not modelled at all"* and hands exfiltration to the
sandbox-ladder candidate. **That concession is REFUTED by the substrate** `[J]`.
`workflow-dsl.schema.json#/$defs/tool_policy` already carries:

```
default: enum[deny, allow]  default="deny"      allow[] / deny[] / require_owner_approval[]
network: enum[none, read-only, full]
source_policy: allow_domains, deny_domains, offline_only, require_provenance,
               treat_fetched_content_as_data, license_allowlist, paywalled
write_paths[] / forbid_write_paths[]
```

Two consequences, both load-bearing for the verdict:

1. **`security-first`'s proposed `platform/policy/unit-tool-policy.json` + its schema would be a
   DUPLICATE CONTROL PLANE** — the exact thing the spec's hybrid rule forbids. The shipped
   `$defs/tool_policy` already has the identical three-way `allow`/`deny`/`require_owner_approval`
   partition with `default: deny`. No advocate found this. The correction is in §3.
2. **The egress model is authored and unwired**, in precisely the same shape as the authorization
   model: all three work-unit profiles carry **0** mentions of `tool_policy`, `network`,
   `source_policy` or `require_owner_approval`; **0 of 2,007** units declare any of them; and
   `tool_policy` has **53 real readers**, every one on the DSL/foundry/blueprint side `[J]`.

This program has measured that **5 of 8 refutations were overclaims**. This is the mirror image: an
**under-claim scoped a candidate out of a capability it already had.** An under-claim is a defect
too, and it cost `security-first` an axis it should have won.

---

## 2. Per-axis scores

Scored 0-5 on the spec's objective function **in its stated order**. Weights decline with rank
(correctness ×10 → resource efficiency ×1), so "in order" is enforced without collapsing to pure
lexicographic ordering. **An architecture that wins on performance and loses on correctness loses.**
Candidates are scored on their **surviving form** — the scope each advocate defended after its own
refutation — because scoring a claim its own author withdrew would be judging a strawman.

| axis (weight) | sec-first | dist-runtime | max-hybrid | cross-vendor | gw-lazy | ux-product | gen-ssot | mkt-first | config-first |
|---|---|---|---|---|---|---|---|---|---|
| **1 correctness** ×10 | **5** | 4 | 4 | **5** | 4 | 2 | 3 | 3 | 3 |
| **2 verified improvement** ×9 | **5** | 4 | **5** | **5** | 4 | 4 | 4 | 3 | 3 |
| **3 innovation** ×8 | **5** | 4 | 3 | 3 | 4 | 4 | 4 | 3 | 3 |
| **4 robustness** ×7 | 3 | **5** | **5** | 4 | 3 | 3 | 3 | 2 | 2 |
| **5 completeness** ×6 | 4 | 4 | 3 | 2 | 3 | 3 | 3 | **5** | 3 |
| **6 usability** ×5 | 2 | 3 | 2 | 2 | 3 | **5** | 2 | 3 | 3 |
| **7 reversibility** ×4 | 4 | **5** | **5** | 4 | 4 | 4 | 4 | **5** | 3 |
| **8 maintainability** ×3 | 3 | 4 | **5** | **5** | 3 | 4 | 3 | 1 | **5** |
| **9 performance** ×2 | 3 | **5** | 2 | 3 | **5** | 3 | 2 | 1 | 2 |
| **10 resource efficiency** ×1 | 4 | 3 | **5** | **5** | 4 | 4 | 2 | 1 | **5** |
| **weighted total** | **225** | **227** | **216** | **211** | 201 | 190 | 178 | 166 | 164 |

**The top two are separated by 2 points on a 227-point scale — that is inside my own scoring noise
and I will not present it as a decisive ordering.** Re-running the weights at ×8/×7/×6… or at pure
lexicographic-on-correctness flips them. What survives every weighting I tried is the *set*
{security-first, distributed-runtime, maximal-hybrid, cross-vendor} as the top four and
{marketplace-first, config-first} as the bottom two. Confidence in the top-4 *set*: *likely* (55-80).
Confidence in the exact 1st-vs-2nd ordering: *roughly even* (40-60), and it does not matter, because
the winner is not either of them alone (§3).

**Scoring notes where a score is not obvious:**

- `config-first` scores 3 on usability despite having the best comprehension surface in the field,
  because **it measured its own justifying property and found it false**: the authored plane is
  5,607,545 B / 99,535 pretty-printed lines, so "the owner can read the whole control plane in one
  sitting" is wrong by ~3 orders of magnitude. Scoring it on the claim it withdrew would be
  dishonest in its favour.
- `marketplace-first` scores 1 on maintainability and resource efficiency on its own numbers: 40 new
  schemas at Wave-1 density ≈ 2,200 new tests, against a shipped baseline of 2,781.
- `ux-product-first` scores 2 on correctness because it concedes a naive renderer makes wrongness
  authoritative — worse than silence — and its mitigation (the `SOURCE-INTEGRITY` band) is unbuilt.
- `gateway-lazy` scores 5 on performance for measuring the **699.7 h serial-by-substrate-contract
  floor**, which no other candidate found, while explicitly disowning its own resident-byte claim.

---

## 3. WINNER

> **A HYBRID: `security-first` authorization as the spine, on a `maximal-hybrid` S0/S1 enforcement
> floor, with `cross-vendor` Plane A bolted in and `distributed-runtime` step 1-2 as the read-only
> consumer — subject to ONE mandatory correction that no advocate made.**

The tournament's own evidence forces a hybrid rather than permitting one: **the four verified live
defects sit on four different planes, and no single candidate closes more than two.** D1 → cross-vendor.
D2 → security-first. D3 → maximal-hybrid. D4 → everyone's Phase 0 and nobody's deliverable.

### 3.1 The mandatory correction

**`security-first` Plane A must consume the EXISTING `workflow-dsl.schema.json#/$defs/tool_policy`,
not author `platform/policy/unit-tool-policy.json`.** One policy plane, two consumers
(`check_workflow` — already wired via `DSL-SEM-011` — and `check_work_units`, new). Without this
correction the winner ships a duplicate authorization plane and is **inadmissible under
`_USER-PROMPTS.md:10796`**. With it, the winner also inherits `network` + `source_policy` for free,
which closes the egress axis `security-first` wrongly conceded (§1.1).

### 3.2 Control-plane enumeration, and the duplicate proof the spec demands

| # | plane | file that IS the plane | new? | duplicate check |
|---|---|---|---|---|
| **CP-1** | authorization + egress | `workflow-dsl.schema.json#/$defs/tool_policy` | **NO — exists** | Nothing else decides which tools an object may hold. Verified: `check_work_units` has 0 authz rules; 53 readers all on one side. **One plane, two consumers.** |
| **CP-2** | vendor identity | `platform/registry/VENDOR-REGISTRY.json` | **YES** | Nothing else decides canonical vendor id. Verified: **0** vendor enums in `receipt.schema.json`; both vendor fields are bare `string`. Single. |
| **CP-3** | writer authority / derived state | ONE declaration + the `--check` contract already implemented read-only in `ci/emit_hook_manifest.py` | **NO — generalised** | **See the exclusion below.** |

**EXPLICITLY EXCLUDED AS DUPLICATE CONTROL PLANES — this is the part a hybrid usually gets wrong:**

- `generated-ssot`'s `platform/spec/EMISSION-MAP.json` (path → owning emitter) and
- `config-first`'s P-1 as a third, separately-enforced writer doctrine

**both answer the same question as CP-3 — "who is allowed to write this file?"** Taking two of the
three would be exactly the duplicate control plane the spec forbids. The panel takes
`maximal-hybrid`'s form because (a) it *generalises a contract already shipped and tested*
(`ci/emit_hook_manifest.py` is read-only by design, with `--check` normalising line endings, and has
its own test), (b) its target defect D3 is panel-verified, and (c) its cost is measured at hours, not
at 350 authored lines. `config-first`'s P-1 is adopted as the hybrid's **admission criterion**, not as
a fourth mechanism — which is, by config-first's own §7.3, the contribution it should make.

`distributed-runtime` step 1-2, `ux-product-first` S0, and `gateway-lazy`'s INV gates introduce **no
plane**: the first reads existing planes and writes a report (its own §1.6 table), the second is a
`git mv`, the third is a gate over `hooks/_dispatch/manifest.json` and `agent-self/config/settings.json`.

**Three planes. Two already exist. One is new. Two candidate planes rejected as duplicates.**

### 3.3 Why this spine and not a single winner

- On **correctness** (axis 1), the two highest-scoring mechanisms fix *false greens in shipped gates*
  (D1, D3), and the spine's own contribution fixes an *absent gate* (D2). The estate's doctrine ranks
  a false green worse than an absent gate, so cross-vendor's and maximal-hybrid's fixes must be in
  the winner regardless of which spine is chosen. They are cheap (4 files/~180 LOC; hours) and
  neither adds a plane. Excluding them to preserve a single-winner narrative would be scoring
  aesthetics over correctness.
- `security-first` is the spine rather than a component because it is the only candidate that
  **governs 2007/2007 units** on an axis with literally zero existing rules, its mechanism is
  set-membership over data the agent did not author — which is immune to its own killing refutation
  (R3) — and, after §3.1, it adds **no** plane at all.
- `distributed-runtime`'s planner is included and its dispatcher is not, because its own advocate
  amputated the dispatcher and predicted (*likely*) that `plan` refuses on first contact. A read-only
  consumer that makes 4 measured defect classes blocking is worth ~500 lines; a lease protocol and a
  cloud trust boundary for a program whose release mode is PR-ONLY is not.
- **`marketplace-first` and `config-first` lose the spine** — and both said so themselves.
  marketplace-first: *"Half of it should [win]."* config-first: non-compliant at Phase 6, *"For the
  scope the spec asks for, yes [it kills the design]."* The panel agrees with both authors about
  their own candidates.

---

## 4. MINORITY REPORT — what the winner gives up, and who held the better answer

The spec requires preserved dissent. A unanimous verdict here would be a panel failure, and this
verdict is **not** unanimous: six axes were won by candidates that are not the spine.

**M1 — Deployment, licensing, and the entire spec Phase 4-6 surface. `marketplace-first` held the
better answer, and the winner is unlawful to publish without it.**
The winner scores 3/5 on completeness and closes none of Phase 5-6 (**143 units = 7.1%** of the
declared program). marketplace-first is the only candidate that engaged it, and the only one that
found the live legal defect: **no root `LICENSE`/`COPYING`/`NOTICE`; 31 Apache-2.0 payload entries
aggregated under a declared `MIT`; ≥1 CC BY-SA 4.0 share-alike entry (`trail-of-bits-re`,
`SKILL.md:15-16`) that a LICENSE-file scanner reports as clean** `[A-only]`. It also proved mutation
**M4 survives today**: 118 units declare `profile=<name>`, 0 of 30 profile names exist in the 295
`$defs`, and all 118 widen to `receipt_core` — so a publish gate that trusts "schema-valid" would
green-light receipts omitting every field their own unit declared mandatory. **Dissent: adopt
marketplace-first's Stage 0 (owner licensing decision) and the `mkt-profile` gate regardless of the
spine.** The winner's authorization plane cannot see a licensing defect.

**M2 — Whether the owner reads any of this. `ux-product-first` held the better answer and it was the
only candidate that asked the question.**
It wins usability outright (5/5) and the winner scores 2/5. Two of its findings are adopt-regardless
and cost no code: **`command-center/` is 82.3% agent debris (135 of 164 top-level files are `_*`
probes)**, and **`render.py` writes by default — `--check` is opt-in**, which is the same
write-by-default hazard class the program already catalogued. Its headline sentence is
panel-verified exactly: **1 of 2,007 declared `output_path` files exists; 29 of 32 declared output
directories are absent; `command-center/receipts/` is targeted by 1,021 units and does not exist**
`[J]`. **The winner does not print that sentence, and it is the truest sentence the tournament
produced.** ux-product-first argued for its own third place; the panel places it third on the
minority axes and adopts S0 immediately.

**M3 — The 601-unit data-loss hazard and the program's real cost. `distributed-runtime` held the
better answer, and the winner has no mitigation.**
Its planner is in the winner; its substrate binding is not — and that binding carries the only
data-loss finding in the tournament: **601 of the 784 `local-parallel` units also hold `Edit` or
`Write`**, i.e. 601 units declared to mutate one working tree and one git index concurrently
`[A-only]`. That is the exact failure this estate has already paid for. Its force-promotion
(`local-parallel ∧ mutating → worktree-isolated`, reported not edited) is the only proposed fix and
the winner drops it. It is also the only candidate that measured the economics (**2,291 declared
hours; 18.4× at concurrency 20; returns collapse after ~50 because the phase DAG serialises 21
phases and the widest holds 295 units**), corroborated from a different angle by gateway-lazy's
**699.7 h serial-by-contract floor**. **Dissent: the 601-unit promotion should be adopted as a
blocking pre-dispatch check even though the dispatcher is deferred.**

**M4 — Budget legibility in the live hook path. `gateway-lazy` held the better answer.**
It wins performance jointly (5/5) and found a live correctness defect the winner does not touch:
**`dispatch.py` still contains an `or ""` coercion, so a JSON-numeric `wall_cap: 0` is silently
discarded while the string `"0"` works** — the manifest cannot express the value that matters most
`[A-only]`. Plus **INV-GW-2 fails 4 of 4 events** (Stop 2.9×, PreToolUse 3.8×, SessionStart 2.4×,
PostToolUse 1.9× oversubscribed, `wall_cap` ABSENT on all four) and a **dual dispatcher** where 4
events carry both `hooks/_dispatch/dispatch.py` and `agent-self/harness/dispatcher.py` while 3 carry
neither. **Dissent: the `or ""` fix is one line and should land regardless of the spine.**

**M5 — Multi-writer drift on the council plane. `generated-ssot` held the better answer.**
**117 councilspecs were machine-emitted by 5 competing writer scripts, carry 0 provenance keys, and
have no drift gate** `[A-only]`; and **32 of 36 production emitters repo-wide have no drift gate at
all** (only 4 are CI-invoked, verified at `quality.yml:403,624,625` and `skill-dual-write.yml:72,79`).
Its defect-clustering result is panel-verified: **128 non-dict `assigned_model_vendor_role` values,
100% of them inside exactly 2 of 22 source slices (`IMP-4.json` 96/96, `WFA-2.json` 32/32)** `[J]` —
the defect is a property of who authored the slice, not of what the unit does. **Dissent: its
Phase 1-2 (council emitter consolidation + shim commit) should ship; its own advocate argued NO on
Phase 3 and handed the catalog to config-first, and the panel agrees with him.**

**M6 — Comprehension minimalism. `config-first` held the better answer on maintainability (5/5,
tied) and its P-1 is load-bearing for this verdict.**
config-first is last on the weighted total and still supplied the criterion that makes §3.2's
duplicate-plane exclusion statable: *"one physical definition per constraint."* Without P-1 the
hybrid has no principled way to reject `EMISSION-MAP.json`. **Dissent: the loser's contribution is
the winner's admission test.** Its own re-pitch (*"a singularity claim, not a readability claim"*) is
the correct reading and the panel adopts it.

---

## 5. Self-refutation quality — which were serious, which performative

**Methodology disclosure, because it matters.** The panel built a keyword scorer
(`_judge_refutation.py`) and it **disagreed with the full-text reading**. It scored `security-first`
**0** on "own claim REFUTED" because that document writes *"The refutation is TRUE as stated"* rather
than the token `REFUTED` — while that document in fact performed the most substantive redesign in the
field. The mechanical score clustered six candidates at 6/9 and three at 4/9, i.e. it measured
vocabulary, not substance. **"Was the self-refutation serious?" is a judgement question, not a
mechanical one, so the algorithm is reported as a prior and overridden by reasoned reading, and the
override is stated rather than hidden.** Mechanical output retained for audit:
refutation share of document ranged 14.0%-27.5% (median 18.2%), disclosed own-detector failures
0-9 per document.

**SERIOUS — the design measurably changed as a result. Ranked.**

1. **`security-first` — the gold standard, and it cost the advocate his headline.** R3 (*"attestation
   cannot fix a self-attested system, because the attester is the subject"*) forced an in-document
   redesign: signature-based attestation is **rejected in §3 on the strength of §9's own argument**,
   and the surviving Plane B is witness-based. It states what dies: *"Any claim that this
   architecture makes receipts unforgeable, tamper-proof, or attested in the cryptographic sense. I
   make none."* It names the single measurement most likely to overturn it, discloses its own
   enforcement classifier is **asymmetric** (`reading = 0` does not prove absence — its control field
   `spec_anchor` also scored 0), and ships a **61-check self-audit with 2 deliberately-wrong injected
   controls that must both be caught** or the audit reports itself invalid. It also caught two of its
   own probes being silent in all four states before drawing a verdict.
2. **`distributed-runtime` — killed its own mechanism by measurement, before shipping.** Its proposed
   bucket→`feeds_phases` join produced 246,406 edges and left **1,813 of 2,007 units unschedulable**;
   it reported that as **REFUTED** against itself and threw the mechanism away. It then amputated
   ~460 of ~1,100 production lines as *"not justified by any measurement I can produce"*, and
   predicted at *likely* (55-80) that its own `plan` would **refuse on first contact** — *"An
   advocate who predicts his own architecture will refuse to run should say so before it does."*
3. **`maximal-hybrid` — the only advocate whose refutation damaged him in both directions, and he
   said so.** He withdrew his **strongest attack point** (12 writers of the security-bearing manifest)
   after his own rebuilt detector *refused to report counts because its positive control failed* —
   use-vs-mention in his own measuring tool, the third recorded instance on this estate. Withdrawing
   it also destroyed his own **headline justification** ("consolidate 12 writers"), and he recorded
   both directions. He conceded the design is **not admissible today** against the spec's actual
   criterion, conceded his 234→3 headline is read-side and *"says nothing about writers"*, and
   **pre-committed** to declaring the candidate A2+A10 and abandoning the hybrid if S1 cannot be made
   to fire. 9 disclosed detector failures — the most in the field.
4. **`generated-ssot` — ran its own decisive test and published the failure.** The candidate's own
   stopping rule is byte-exact round-trip; measured **5.18%**, override rate **59.03%**, `exact_key:
   None` for all 11 contract fields. It declared the strong form **REFUTED**, argued **NO** on its
   own Phase 3, and handed the catalog to config-first. It also disclosed a **self-referencing key**
   in one of its own probes (a key set containing the target field) and re-measured with the
   correction.
5. **`marketplace-first` — named its own overclaim in the overclaim's own vocabulary.** *"The wide
   sentence here would have been 'marketplace-first should win'. It should not. Half of it should."*
   It conceded the deployment half on four independently sufficient grounds and disclosed that its
   own license classifier **passes all three controls and still measures the wrong input surface**
   (LICENSE files only, missing a CC BY-SA declaration in a `SKILL.md` body) — a gate whose controls
   pass can still measure the wrong thing. That is a sharper insight than the finding it qualifies.
6. **`gateway-lazy` — recorded its own framing as REFUTED and disowned its own headline number.**
   *"4.6× on 5 MB is not a reason to build anything… the original framing invited that misreading."*
   It conceded GW-2 is a sibling's deliverable and GW-4 is the status quo, and it is the **only
   document in the field that rated its central load-bearing assumption below "likely"** — *roughly
   even* (40-60) that `admit()` can stay pure — calling that *"the single biggest risk in this
   entry."* Two disclosed detector failures, one of which would have manufactured a P1 that does not
   exist.
7. **`ux-product-first` — argued for its own third place.** It conceded §7.1 as **CONFIRMED against
   its own first-mover claim**: *"it would ship five beautiful views over an empty factory, and the
   tournament should mark that down."* Every number in the paragraph attacking it is its own.
8. **`cross-vendor` — conceded the condition under which it should lose its own slot.** Plane B is
   **anchor-REJECTED in its maximal form** (*"It would be dishonest to relabel a dispatcher as a shim
   and claim anchor compliance on the strength of the label"*), and §7.4 states that if the alias
   hole is closed inline in ~15 LOC and T2 is declined, *"this architecture reduces to a two-line
   bugfix and should not win a tournament slot; the config-first candidate absorbs it."* That is the
   most self-destructive concession in the field relative to the document's own thesis — and the
   panel notes it is **correct**, which is why cross-vendor is a component of the winner and not its
   spine.

**WEAKEST — real, severe, but closest to arguing-it-away: `config-first`.**
Its §7.1 (readability false by ~3 orders of magnitude) and §7.3 (*"For the scope the spec asks for,
yes"* — fully fatal at Phase 6) are genuine and it deserves credit for both. Three things hold it
last on this criterion, none of them fatal:
- §7.4 is titled *"Three lesser objections, **answered rather than conceded**"* — the only section in
  the field framed that way.
- Its §7.2 rescue (*"the enforcement already exists and is not new"*) lets it adopt 2,033 LOC of
  committed enforcement (`completion_predicate.py` 1,301 + `receipt_schema_gate.py` 732) while
  keeping the slogan "add no new machinery." That boundary is convenient, and the document is candid
  that it *is* a rescue — but a rescue that reclassifies 2,033 LOC as free is a scope move, not an
  argument.
- Most materially, **it explicitly did not read a single sibling document** (§8: *"I did not read any
  sibling candidate's document"*), so its §7 comparisons run against `13-ARCHITECTURE-CANDIDATES.md`
  cards rather than the committed competitors. It disclosed this and instructed the panel to weight
  the siblings' own documents over its summary — which the panel did. In a *tournament*, judging
  rivals from their trading cards is a material limitation on a refutation section, however honestly
  flagged.

**No candidate wrote a performative self-refutation.** This is an unusually strong field and saying
otherwise to manufacture a villain would be the sycophantic move. Eight of nine changed a claim,
withdrew a mechanism, or argued against their own placement; the ninth measured its own justifying
property and found it false. **Two candidates additionally deserve credit the scoring cannot capture:
`security-first` and `ux-product-first` had no prior design card to consume at all** — verified: doc 13
enumerates A1-A11 and `grep -ic "security-first\|security first"` and
`grep -ic "ux/product\|product-first\|ux-first"` both return **0** `[J]`. Both are syntheses from the
MECH-NN menu, and both said so unprompted.

---

## 6. MIGRATION PATH from today's `main`

**Anchor correction first: `main` is `edcf9f5b`, not `dc90d64a`** (5 commits behind, ancestor
confirmed). Ordering below is forced by dependency, not preference: **every candidate's Phase 0 is
the same step, and until it lands every downstream gate is vacuous.**

Release mode is **PR-ONLY** (binding). Stopping condition 13 ("release/canary succeeds") is
**UNSATISFIABLE as literally written**; this panel treats it as **a merged PR plus a local rollback
rehearsal**, and says so explicitly rather than reporting a canary. Each stage below names its
rehearsal.

| stage | action | gate (first result stated; a green where RED is expected means the check is broken) | rollback rehearsal |
|---|---|---|---|
| **G0** | **Commit the untracked substrate.** `command-center/schema/**` (233), `platform/lib/schema_resolver.py`, `platform/schema/artifact-class-profiles.schema.json`, `ARTIFACT-CLASS-REGISTRY.json`, `platform/schema/examples/substrate/`, and a scoped decision on `platform/lib/{foundry,workflows}` (283 files) + `platform/architecture/` (103, incl. this verdict). **Orchestrator commits — not the panel.** | `git ls-files command-center/schema \| wc -l` = 233. Add `no-untracked-substrate` asserting tracked == on-disk **and** that `.gitignore` does not mention the path (so the check cannot be "fixed" by ignoring the tree). **Expected first result: RED at 0 == 233.** | revert the commit, re-run `schema_resolver.py --audit`, confirm it returns to 234/234 |
| **G1** | **`maximal-hybrid` S1: widen the determinism gate from 4 paths to all 231+4, emit to a temp tree, and REPORT before it REPAIRS.** Closes **D3**. Hours. | must go RED on the known-broken state `x-catalog-reference-count: 999999` in any *unsampled* shim — which today exits 0. Must stay GREEN on a clean tree. | delete the test, confirm 2,767 passed returns |
| **G2** | **`gateway-lazy` Stage 1: fix the `or ""` coercion in `dispatch.py`.** One line, precondition for any numeric budget. (M4 dissent.) | `wall_cap: 0` as a JSON **number** is honoured; control is `"0"` as a string, which already works | one-line revert |
| **G3** | **`cross-vendor` Plane A: `VENDOR-REGISTRY.json` + `vendor-identity.schema.json` + `vendor_identity.py`, then flip `completion_predicate.py:935` to `same_vendor()`.** Closes **D1**. 4 files, ~180 LOC. **Gate the consistency check (all 628 councilspec seat vendors + 2,007 catalog assignments canonicalize) BEFORE the schema `$ref` narrows**, or valid receipts start failing. | the panel's `_judge_verify.py` check 1 must go **10/10 → 0/10** with both controls still passing. It already fires in the broken state, so its later silence is meaningful. | revert the two edits; re-run `_judge_verify.py`; expect 10/10 again |
| **G4** | **Spine, corrected: wire `check_work_units` to the EXISTING `$defs/tool_policy`.** Add `SEM-008` (token permitted, deny by default — a port of `semantics.py:485-499`), `SEM-009` (approval coherence), `SEM-010` (substrate coherence). **Do NOT author `unit-tool-policy.json`** (§3.1). Land at severity **`advisory`** first. Closes **D2**. | census must be **non-zero**; a zero means the allowlist is too loose. A fixture unit holding `mcp__cloud-hub__modal_sandbox_exec` with `owner_approval_required: false` **must** fail, and a test must fail if the policy is ever loosened past a hardcoded known-bad set. | set severity back to `advisory`, re-run `check_work_units`, confirm the census returns to its pre-G4 value |
| **G5** | **Ratchet `advisory` → `violation`, one rule per PR**, so a red is attributable. Flip `owner_approval_required` to `true` on units legitimately holding a spend/`Task` token — **that is the point of the exercise, not a workaround.** Start with the **23 unapproved `Task`-holding units** (panel-verified). | `T11`: no unit holds `Task` with `owner_approval_required != true`. **Fires today on 23 units — that is the fixture and the finding in one.** | per-rule severity revert |
| **G6** | **Wire the egress vocabulary the substrate already has** (§1.1): `network` + `source_policy.{allow_domains,deny_domains,offline_only,treat_fetched_content_as_data}` onto the work-unit plane. **No new plane** — same `$defs`. This is the axis `security-first` wrongly conceded. | a unit declaring `WebFetch` with `network: none` must fail. **Fires on the 122 units holding `WebFetch`/`WebSearch` without approval** `[A-only]` — re-measure before relying on it | additive; revert the rule |
| **G7** | **`distributed-runtime` step 1-2: `state.py` + `schedule.py` + `cli.py plan\|status\|explain`.** ~500 lines, read-only, no lease, no spawn, no git write. Adopt the **601-unit force-promotion as a blocking pre-dispatch report** (M3 dissent) even though the dispatcher is deferred. | `plan` must **refuse** on the 41 family tokens and name the 68 contradictory bucket edges. Its advocate predicts refusal at *likely*; a clean pass would be the surprise and should be investigated, not celebrated | `rm -r platform/lib/runtime` |
| **G8** | **`ux-product-first` S0 + its §4.3 finding.** `git mv` 135 `_*` probes to `command-center/.probes/` (82.3% → ~0% debris); invert `render.py` so `--check` is implicit and writing requires `--write`. **Zero code for S0; adopt regardless of the spine.** | `render.py --check` still exits 0 on a clean tree and 1 on injected drift (already both-states proven). Count the CI call-sites before inverting the default — **UNVERIFIED**, settle with `grep -rn "render.py" --include=*.yml --include=*.yaml --include=*.py .` | `git mv` back |
| **G9** | **`generated-ssot` Phase 1-2** (M5 dissent): one council emitter replacing 4, `x-generated-by`/`source_ref`/`built_at` on all 117, and the shim tree into `verify.py`. **Phase 3 stays unbuilt** per its own advocate. | re-emission byte-identical to all 117 committed councilspecs. **If not byte-exact, the spec is lossy and Phase 1 stops** — the candidate's own stopping rule | delete the emitter; the 117 bytes are unchanged |
| **G10** | **`marketplace-first` Stage 0 + the `mkt-profile` gate** (M1 dissent). Stage 0 is an **owner decision, not an engineering task**: root `LICENSE`, per-entry SPDX, NOTICE for the 31 Apache-2.0 entries, and a ruling on the CC BY-SA entry. `mkt-profile` makes `parse_schema_ref` **fail** rather than widen on an unmapped `profile=`. | mutation **M4** must go from *survives* to *dies*: `profile=zzz-nonexistent` must fail rather than widen. It survives on 118 real units today | revert the strict-mode caller; the permissive path is unchanged |

**Explicitly NOT on the path**, with the reason and the author who agrees:
config-first's **step 5** (delete the 231 shims — the only irreversible step in the field; superseded
by G0 committing them, and config-first itself notes it becomes a no-op if it loses before they
land) · **catalog generation** (generated-ssot's own advocate argued NO: 5.18% round-trip, 59.03%
override rate) · **`lease.py`/`dispatch.py`/cloud-batch** (distributed-runtime amputated them) ·
**moderation, dispute process, federated mirrors, publisher reputation, collections, public channel**
(marketplace-first: *"I am not going to argue that a one-user estate needs a moderation flow"*) ·
**`EMISSION-MAP.json`** (duplicate of CP-3, §3.2) · **signature-based attestation** (security-first
rejected it on §9 grounds: it would put a credential on the receipt path).

---

## 7. Residual — what this verdict does NOT establish

- **NOT-CHECKED: no stage of the migration path was executed.** The panel judged documents and
  verified claims; it built nothing and committed nothing. G0-G10 are a design.
- **NOT-CHECKED: the 1st-vs-2nd ordering in §2** is inside my scoring noise (2 points of 227) and I
  decline to defend it. The top-4 *set* is what I defend, at *likely* (55-80). The settling
  experiment is a second, independently-weighted panel that has not read this document.
- **`[A-only]` claims the panel did NOT re-verify**, each load-bearing for a minority-report item:
  the 601 mutating `local-parallel` units · the 699.7 h serial floor · the `or ""` coercion in the
  **live** `dispatch.py` · INV-GW-2's 4-of-4 oversubscription · the 5 council writer scripts and 0
  provenance keys · the 32-of-36 ungated emitters · the licensing surface (no root LICENSE, 31
  Apache-2.0, the CC BY-SA entry) · the 118 `profile=` units and 0-of-30 profile overlap · the 122
  `WebFetch`/`WebSearch` units. Each names its own probe in its source document and should be
  re-run before it is cited as a decision input.
- **UNVERIFIED: whether `security-first`'s four "no runtime reader" rows are absences or detector
  artifacts.** Its own classifier is asymmetric and it said so. The panel's independent pass found
  **21 files mentioning `owner_approval_required`, 6 with a real read — and all 6 are
  `platform/lib/workflows/test_*.py`, i.e. tests, not runtime** `[J]`, with a control proving the
  read-matcher works (28 `tool_permissions` reads found). That *refines* the claim rather than
  settling it: an `ast`-based call-graph pass over attribute and destructured access is the settling
  experiment, and it is the single measurement most likely to reduce the spine's value.
- **A sensitive-artifact sweep fired report-only on three panel/probe files during this unit** —
  ids `sha256:99e1c4e1bfe1` and `sha256:1abff36aab85` (this panel), and previously
  `sha256:c75f24b08919` (gateway-lazy) and `sha256:8a9a00142eaa` (generated-ssot). No value was
  inspected, printed, rotated, revoked or edited; per AGENTS.md §9 credential lifecycle is the
  owner's. **Surfacing the ids is the whole of the panel's action.** That the same sweep fires on
  four independent probe files is itself worth an owner look — *likely* a pattern-shape false
  positive on probe source, **UNVERIFIED**; settling experiment is to read the sweep's matcher
  against one of the four files.
- **The panel's own detector failure, disclosed.** `_judge_verify.py` check 1 first failed with
  `TypeError: PredicateOptions.__init__() missing 1 required positional argument: 'repo_root'` — my
  API error, caught before any conclusion was drawn, fixed, re-run. And `_judge_refutation.py`
  produced a seriousness ranking that **contradicted the full-text reading** and was overridden
  (§5). A keyword scorer measuring vocabulary was the wrong instrument for a judgement question, and
  reporting its output as the verdict would have inverted the field's top entry.
- **Files this unit wrote:** `platform/architecture/TOURNAMENT-VERDICT.md` (this file),
  `_judge_verify.py`, `_judge_verify2.py`, `_judge_refutation.py`. **No repo artifact was modified.
  Nothing was committed.**
