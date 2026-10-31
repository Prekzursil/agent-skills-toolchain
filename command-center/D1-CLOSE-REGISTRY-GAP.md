---
title: D1-CLOSE-REGISTRY-GAP
type: note
permalink: dqverify-repo-20261013/command-center/d1-close-registry-gap
---

# D1 CLOSE - the registry gap that turned the fix into NOT-COMPUTABLE

**Unit:** `close/d1-registry-gap` · **Verdict: D1 CLOSED** — 0 incorrect rows in the audit's own
45-pair matrix (was 3), 0 in the 39 extended rows (was 22), and all **five** both-states controls
fire on their seeded defects. `platform/` is green across all six test roots: 3,922 passed /
14 skipped / 0 failed.

Every number below is read off disk from `command-center/D1-CLOSE-MATRIX.before.json` and
`...after.json`; the row tables are GENERATED from those artifacts by
`command-center/d1_close_report.py`, not hand-transcribed.

## Headline correction to the briefed premise (read this first)

The brief states *"13 of 45 tested vendor pairs cannot be evaluated"*. **That number is wrong, and
the Wave 3 artifact says so itself.** 13 is the number of rows the matrix EXPECTS to be a refusal
(hosting planes, placeholders, unregistered strings, non-string types) and all 13 were already
correctly refused. `command-center/WAVE3-FLOOR-AUDIT.json` →
`check1_D1_cross_vendor` records `not_computable_pairs_blocked` = `not_computable_pairs_tested` =
13 **and** `incorrect_rows` of length **3**.

So the over-correction was **3 rows**, not 13:

| row | executor | reviewer | normalized to | why it failed |
|---|---|---|---|---|
| 1 | `anthropic` | `Anthropic PBC` | `anthropic-pbc` | legal-entity suffix absent from the table |
| 2 | `mistral` | `Mistral AI` | `mistral-ai` | table held `mistralai`; a SPACE makes a different key |
| 3 | `anthropic` | `anthropic<U+200B>` | unchanged | U+200B is category **Cf**, and the normalizer stripped only `[\x00-\x1f\x7f]` |

Row 3 is the interesting one: `vendor_identity.py`'s own comment claimed *"Unicode categories Cc
(control) and Cf (format) are removed outright"* while the regex did not remove Cf at all. The
comment was the spec; the regex was the behaviour.

## Before / after (measured off disk)

| claim | BEFORE | AFTER |
|---|---|---|
| audit 45-row matrix: incorrect rows | **3** | **0** |
| audit 45-row matrix: same-vendor rows correctly UNSATISFIED | 21 / 24 | **24 / 24** |
| audit 45-row matrix: same-vendor rows stuck on NOT-COMPUTABLE | **3** | **0** |
| audit 45-row matrix: same-vendor rows accepted as cross-vendor (the original D1 false green) | 0 | **0** |
| audit 45-row matrix: genuine cross-vendor rows SATISFIED | 8 / 8 | **8 / 8** |
| audit 45-row matrix: refusal rows blocked | 13 / 13 | **13 / 13** |
| audit 45-row matrix: rows NOT-COMPUTABLE in total | 16 | **13** (= exactly the 13 that should be) |
| extended 39-row matrix: incorrect rows | 22 | **0** |
| extended: over-fold guard rows still refused | 15 / 15 | **15 / 15** |
| registry recognized tokens | 123 | **130** |
| `platform/lib` suite | 3,043 passed / 14 skipped / **0 failed** | **3,118 passed / 14 skipped / 0 failed** |
| `test_vendor_identity.py` alone | 173 passed | 248 passed |
| `platform/coordination` (consumes the resolver) | not measured before | **231 passed / 0 failed** |
| `platform/{plugin,marketplace,routing,corpus}` | not measured before | **573 passed / 0 failed** |

All six test roots under `platform/` (`lib` 87 files, `coordination` 13, `plugin` 6, `routing` 6,
`marketplace` 4, `corpus` 1 = 117 `test_*.py`) are green: **3,922 passed / 14 skipped / 0 failed**.

**The pinned baseline of 3,026 is stale.** Measured on the untouched tree before any edit:
`3043 passed, 14 skipped in 184.07s`. Do not quote 3,026 as current; +17 tests arrived from other
lanes between Wave 3 and this run. (`command-center/D2-WORKUNIT-AUTHZ.md:268` is itself internally
inconsistent — its captured command output reads `3023 passed` while its prose claims 3,026.)

### Measurement integrity - three runs, and why the first two do not count

1. **13:12 (pre-edit, untouched tree)** — `3043 passed, 14 skipped`. This is the real baseline.
2. **A run launched before `ruff format` touched three files was DISCARDED unread.** A baseline
   captured while the tree is being modified is exactly how the old 2,767 figure went wrong.
3. **13:19 (all edits in, guard not yet fixed)** — `2 failed, 3116 passed`. Both failures were the
   `test_schema_resolver.py` delta guards described below. Real, mine, and fixed.
4. **13:38 (guard fixed)** — `2 failed, 3116 passed`, but the two failures were now
   `test_shims_carry_no_constraints` and `test_generator_output_matches_every_committed_file`,
   caused by a **peer lane's planted defect** (next section). The same run recorded the peer file
   as planted at start and restored by the end, which is what identified the race.
5. **13:45 (final)** — `3118 passed, 14 skipped in 266.32s`. Zero failures.

`+75 = 3118 - 3043`, and all 75 are this unit's (68 from 34 new matrix rows × 2 parametrized
tests, 3 from the named Wave 3 regression rows, 4 new test functions).

## What changed

**DATA (the alias table stays data — no per-vendor branch was added):**

`platform/registry/VENDOR-REGISTRY.json` (`schema_version` 1.0.0 → 1.1.0)

* new **`normalization`** block: `legal_entity_suffix_tokens` (41 corporate forms — `inc`,
  `llc`, `l-l-c`, `ltd`, `pbc`, `p-b-c`, `gmbh`, `sas`, `oyj`, …), `descriptor_suffix_tokens`
  (`ai`, `labs`, `lab`, `research`), `domain_suffixes` (moved out of the code), and
  `punctuation_folded_to_separator`. Each list carries a `*_basis` field stating WHY, plus
  `candidate_order`, `over_fold_guard` and `what_this_does_NOT_do`.
* 7 new aliases: `anthropic-pbc`, `mistral-ai`, `meta-platforms`, `cohere-labs` on their vendors;
  `amazon-web-services` on **bedrock** and `google-cloud`/`gcp` on **vertex** — i.e. on the
  hosting planes, deliberately not on the `amazon`/`google` vendor entries.
* `alias_exclusions` gained `aws`, `amazon-web-services`, `google-cloud`, `gcp` and a new rule:
  **parent/investor relationships are NOT alias grounds.** Microsoft is OpenAI's largest investor
  and Azure hosts its models, yet `("microsoft", "openai")` is a row the matrix requires to be
  SATISFIED — folding on ownership would block a valid completion. Same reasoning bars
  `alphabet` → `google`.

**CODE (two mechanical changes, no vendor knowledge in either):**

`platform/lib/vendor_identity.py`

* `_normalize_key` now strips Unicode categories **Cc and Cf** (was `[\x00-\x1f\x7f]`), making the
  module's existing claim true. ASCII fast path retained and its equivalence stated inline.
* `_candidates(key, registry)` reads the lists above and adds two forms to the ladder: a
  punctuation-folded form and a suffix-stripped form, tried **exact-first**. Exact-first is
  load-bearing: it is why `x-ai` → `xai` rather than a bare `x`, and why `azure-ai` stays the
  Azure plane. Empty candidates are discarded.
* `load_registry` reads the block with **absent → default, present-but-empty → DISABLED**. That
  distinction is what lets a both-states control disarm the feature; if `[]` fell back to the
  defaults, a probe that emptied it would measure nothing and report a pass.

`platform/schema/receipt.schema.json` — the two generated `$defs` (`vendor_id`,
`vendor_id_canonical`) regenerated from the registry: **+7 enum entries, 0 deletions, 0 reformatted
lines.** The patcher was proven byte-identical against the unmodified registry first, so the diff
it produced is signal rather than noise.

`platform/lib/test_vendor_identity.py` — matrix 63 → **97 rows** (48 SAME / 16 CROSS / 33
REJECTED), plus 5 new tests (below). Invisible characters are written as `\uXXXX` escapes on
purpose: a literal U+200B can be deleted by a later edit without changing how the line reads.

### The guard that had to be fixed to let the parity test be satisfied

`platform/lib/test_schema_resolver.py` — **2 tests went RED on this change and they were right to
notice, but wrong to block.** `test_receipt_schema_differs_from_head_ONLY_by_the_authorized_d1_delta`
asserted *"strip the named D1 delta and the document equals HEAD"*. That anchors the invariant to
**which state HEAD happens to be in**, and it has now reddened a clean tree three times, each for a
different reason:

1. HEAD was pre-D1 and plain byte-equality fired on the authorized D1 edit;
2. D1 was committed, HEAD became post-D1, and "strip the delta, compare to HEAD" started failing
   (patched at `29f4c72a` by also accepting plain equality);
3. **this unit** — the registry legitimately gained aliases, so the GENERATED enum grew and the
   working copy stopped equalling HEAD, while `test_receipt_schema_matches_the_registry`
   simultaneously *demanded* that growth. Two shipped guards in direct contradiction: one required
   the enum to change, the other forbade any change.

Fixed by normalizing the two GENERATED blocks (and the two vendor fields) to a sentinel on **both**
sides before comparing, so the comparison is indifferent to whether HEAD is pre-D1, post-D1 or
post-extension — and moving that region's teeth to where they belong: the blocks must equal
`vendor_schema_sync.build_defs()`, i.e. the **registry**, which is a stronger claim than equality
with whatever bytes are committed. Everything outside the generated region is still compared to
HEAD exactly. Renamed to `..._ONLY_by_the_generated_vendor_layer`.

The control test gained two mutations for the region the normalization is deliberately blind to,
each stating which assertion catches it: a vendor field reverted to the pre-D1 bare string (caught
by the `$ref` assertion) and an enum member hand-added inside `vendor_id` (caught by the
registry-parity assertion). Net: 4 mutations → 6, and the guard is strictly harder to fool.

## Scope limit, stated rather than discovered later

The generated receipt enum contains **alias-table keys, not resolver candidate forms**. So
`Anthropic PBC` (a registered alias) validates at the wire, while `Microsoft Corporation` (which
only the suffix rule reaches) resolves in the predicate but is **not** in the receipt enum. This
layering is pre-existing, not new — `anthropic.com` has always resolved via the domain rule
without being an enum member — and it fails **closed** (the wire gate is stricter than the
resolver). The highest-value real-world spellings were added as explicit aliases precisely so the
wire layer accepts them too.

## Both-states controls (a probe silent in both states measures nothing)

| control | seeded defect | fired? | evidence |
|---|---|---|---|
| pre-fix gate | re-implement `str(exec or "") != str(rev or "")` | **yes** | leaks **44 / 44** same-vendor rows; the shipped gate leaks **0** |
| `normalization` block emptied | all four lists set to `[]` | **yes** | **13 rows regress** to NOT-COMPUTABLE (`Google LLC`, `Microsoft Corporation`, `Anthropic P.B.C.`, …) |
| new aliases stripped out | the 5 added aliases removed | **yes** | 2 rows regress (`Meta Platforms, Inc.`) — the rest are carried by the generic rules, which is the honest reading: the explicit aliases mostly serve the WIRE layer |
| collision sweep | a fixture vendor `acme` claiming alias `anthropic-corp` | **yes** | the sweep reports the merge; on the shipped table it reports **0** |
| pre-fix normalizer | `[\x00-\x1f\x7f]` re-implemented | **yes** | all 4 Cf spellings resolve to a key absent from the alias index |

New tests: `test_wave3_over_corrected_rows_now_return_same_vendor` (the 3 named rows),
`test_no_alias_can_reach_a_different_vendor_through_any_candidate_form` (sweeps all 130 aliases ×
every candidate form — **0** collisions; asserts the positive that ≥100 aliases and a non-empty
suffix set were actually swept), `test_collision_sweep_fires_on_a_seeded_merge`,
`test_normalization_is_data_and_an_empty_list_disables_it`,
`test_prefix_normalizer_left_format_characters_in_place`.

<!-- GENERATED:rows -->

### The Wave 3 audit's 45 rows, imported verbatim from `wave3_floor_audit.py:D1_PAIRS`

| # | executor | reviewer | expected | BEFORE | AFTER | correct |
|---|---|---|---|---|---|---|
| 1 | `anthropic` | `Anthropic` | SAME | SAME-VENDOR | SAME-VENDOR | yes |
| 2 | `anthropic` | `claude` | SAME | SAME-VENDOR | SAME-VENDOR | yes |
| 3 | `anthropic` | `ANTHROPIC` | SAME | SAME-VENDOR | SAME-VENDOR | yes |
| 4 | `anthropic` | `anthropic ` | SAME | SAME-VENDOR | SAME-VENDOR | yes |
| 5 | `anthropic` | ` anthropic` | SAME | SAME-VENDOR | SAME-VENDOR | yes |
| 6 | `anthropic` | `claude-code` | SAME | SAME-VENDOR | SAME-VENDOR | yes |
| 7 | `anthropic` | `anthropic.com` | SAME | SAME-VENDOR | SAME-VENDOR | yes |
| 8 | `anthropic` | `Anthropic PBC` | SAME | **NOT-COMPUTABLE** | **SAME-VENDOR** | yes |
| 9 | `openai` | `codex` | SAME | SAME-VENDOR | SAME-VENDOR | yes |
| 10 | `openai` | `OpenAI` | SAME | SAME-VENDOR | SAME-VENDOR | yes |
| 11 | `openai` | `open ai` | SAME | SAME-VENDOR | SAME-VENDOR | yes |
| 12 | `openai` | `open_ai` | SAME | SAME-VENDOR | SAME-VENDOR | yes |
| 13 | `openai` | `chatgpt` | SAME | SAME-VENDOR | SAME-VENDOR | yes |
| 14 | `openai` | `gpt` | SAME | SAME-VENDOR | SAME-VENDOR | yes |
| 15 | `google` | `gemini` | SAME | SAME-VENDOR | SAME-VENDOR | yes |
| 16 | `google` | `Google DeepMind` | SAME | SAME-VENDOR | SAME-VENDOR | yes |
| 17 | `google` | `google.com` | SAME | SAME-VENDOR | SAME-VENDOR | yes |
| 18 | `xai` | `grok` | SAME | SAME-VENDOR | SAME-VENDOR | yes |
| 19 | `meta` | `llama` | SAME | SAME-VENDOR | SAME-VENDOR | yes |
| 20 | `mistral` | `Mistral AI` | SAME | **NOT-COMPUTABLE** | **SAME-VENDOR** | yes |
| 21 | `anthropic` | `anthropic<U+200B>` | SAME | **NOT-COMPUTABLE** | **SAME-VENDOR** | yes |
| 22 | `anthropic` | `anthropic<U+0009>` | SAME | SAME-VENDOR | SAME-VENDOR | yes |
| 23 | `anthropic` | `ANTHROPIC<U+00A0>` | SAME | SAME-VENDOR | SAME-VENDOR | yes |
| 24 | `openai` | `<U+FF4F><U+FF50><U+FF45><U+FF4E><U+FF41><U+FF49>` | SAME | SAME-VENDOR | SAME-VENDOR | yes |
| 25 | `anthropic` | `openai` | CROSS | CROSS-VENDOR | CROSS-VENDOR | yes |
| 26 | `anthropic` | `google` | CROSS | CROSS-VENDOR | CROSS-VENDOR | yes |
| 27 | `openai` | `google` | CROSS | CROSS-VENDOR | CROSS-VENDOR | yes |
| 28 | `anthropic` | `gemini` | CROSS | CROSS-VENDOR | CROSS-VENDOR | yes |
| 29 | `claude` | `codex` | CROSS | CROSS-VENDOR | CROSS-VENDOR | yes |
| 30 | `openai` | `xai` | CROSS | CROSS-VENDOR | CROSS-VENDOR | yes |
| 31 | `anthropic` | `human` | CROSS | CROSS-VENDOR | CROSS-VENDOR | yes |
| 32 | `meta` | `mistral` | CROSS | CROSS-VENDOR | CROSS-VENDOR | yes |
| 33 | `bedrock` | `anthropic` | NC | NOT-COMPUTABLE | NOT-COMPUTABLE | yes |
| 34 | `anthropic` | `bedrock` | NC | NOT-COMPUTABLE | NOT-COMPUTABLE | yes |
| 35 | `vertex` | `openai` | NC | NOT-COMPUTABLE | NOT-COMPUTABLE | yes |
| 36 | `azure` | `anthropic` | NC | NOT-COMPUTABLE | NOT-COMPUTABLE | yes |
| 37 | `openrouter` | `google` | NC | NOT-COMPUTABLE | NOT-COMPUTABLE | yes |
| 38 | `unassigned` | `anthropic` | NC | NOT-COMPUTABLE | NOT-COMPUTABLE | yes |
| 39 | `anthropic` | `unassigned` | NC | NOT-COMPUTABLE | NOT-COMPUTABLE | yes |
| 40 | `anthropic` | `totally-made-up-vendor` | NC | NOT-COMPUTABLE | NOT-COMPUTABLE | yes |
| 41 | `<empty string>` | `anthropic` | NC | NOT-COMPUTABLE | NOT-COMPUTABLE | yes |
| 42 | `anthropic` | `<empty string>` | NC | NOT-COMPUTABLE | NOT-COMPUTABLE | yes |
| 43 | `anthropic` | `None` | NC | NOT-COMPUTABLE | NOT-COMPUTABLE | yes |
| 44 | `anthropic` | `7` | NC | NOT-COMPUTABLE | NOT-COMPUTABLE | yes |
| 45 | `anthropic` | `{'vendor': 'openai'}` | NC | NOT-COMPUTABLE | NOT-COMPUTABLE | yes |

### The 39 extended rows added by this unit (real-world spellings + over-fold guards)

| # | executor | reviewer | expected | BEFORE | AFTER | correct |
|---|---|---|---|---|---|---|
| 1 | `anthropic` | `Anthropic PBC` | SAME | **NOT-COMPUTABLE** | **SAME-VENDOR** | yes |
| 2 | `anthropic` | `Anthropic, PBC` | SAME | **NOT-COMPUTABLE** | **SAME-VENDOR** | yes |
| 3 | `anthropic` | `Anthropic P.B.C.` | SAME | **NOT-COMPUTABLE** | **SAME-VENDOR** | yes |
| 4 | `openai` | `OpenAI, Inc.` | SAME | **NOT-COMPUTABLE** | **SAME-VENDOR** | yes |
| 5 | `openai` | `OpenAI L.L.C.` | SAME | **NOT-COMPUTABLE** | **SAME-VENDOR** | yes |
| 6 | `google` | `Google LLC` | SAME | **NOT-COMPUTABLE** | **SAME-VENDOR** | yes |
| 7 | `mistral` | `Mistral AI` | SAME | **NOT-COMPUTABLE** | **SAME-VENDOR** | yes |
| 8 | `mistral` | `Mistral AI SAS` | SAME | **NOT-COMPUTABLE** | **SAME-VENDOR** | yes |
| 9 | `microsoft` | `Microsoft Corporation` | SAME | **NOT-COMPUTABLE** | **SAME-VENDOR** | yes |
| 10 | `meta` | `Meta Platforms, Inc.` | SAME | **NOT-COMPUTABLE** | **SAME-VENDOR** | yes |
| 11 | `cohere` | `Cohere Labs` | SAME | **NOT-COMPUTABLE** | **SAME-VENDOR** | yes |
| 12 | `alibaba` | `Alibaba Cloud Ltd` | SAME | **NOT-COMPUTABLE** | **SAME-VENDOR** | yes |
| 13 | `deepseek` | `DeepSeek AI Ltd.` | SAME | **NOT-COMPUTABLE** | **SAME-VENDOR** | yes |
| 14 | `xai` | `xAI Corp` | SAME | **NOT-COMPUTABLE** | **SAME-VENDOR** | yes |
| 15 | `xai` | `x.ai` | SAME | SAME-VENDOR | SAME-VENDOR | yes |
| 16 | `anthropic` | `anthropic<U+200B>` | SAME | **NOT-COMPUTABLE** | **SAME-VENDOR** | yes |
| 17 | `anthropic` | `anth<U+00AD>ropic` | SAME | **NOT-COMPUTABLE** | **SAME-VENDOR** | yes |
| 18 | `anthropic` | `<U+200E>anthropic` | SAME | **NOT-COMPUTABLE** | **SAME-VENDOR** | yes |
| 19 | `openai` | `open<U+FEFF>ai` | SAME | **NOT-COMPUTABLE** | **SAME-VENDOR** | yes |
| 20 | `anthropic` | `Anthropic<U+00A0>` | SAME | SAME-VENDOR | SAME-VENDOR | yes |
| 21 | `anthropic` | `Acme Inc` | NC | NOT-COMPUTABLE | NOT-COMPUTABLE | yes |
| 22 | `anthropic` | `Acme AI Ltd` | NC | NOT-COMPUTABLE | NOT-COMPUTABLE | yes |
| 23 | `anthropic` | `Anthropic Killer Inc` | NC | NOT-COMPUTABLE | NOT-COMPUTABLE | yes |
| 24 | `anthropic` | `Inc` | NC | NOT-COMPUTABLE | NOT-COMPUTABLE | yes |
| 25 | `anthropic` | `Ltd.` | NC | NOT-COMPUTABLE | NOT-COMPUTABLE | yes |
| 26 | `anthropic` | `AI` | NC | NOT-COMPUTABLE | NOT-COMPUTABLE | yes |
| 27 | `anthropic` | `Google Cloud` | NC | NOT-COMPUTABLE | NOT-COMPUTABLE | yes |
| 28 | `anthropic` | `AWS Bedrock Inc` | NC | NOT-COMPUTABLE | NOT-COMPUTABLE | yes |
| 29 | `anthropic` | `Amazon Web Services` | NC | NOT-COMPUTABLE | NOT-COMPUTABLE | yes |
| 30 | `anthropic` | `Azure AI` | NC | NOT-COMPUTABLE | NOT-COMPUTABLE | yes |
| 31 | `anthropic` | `openai-ish` | NC | NOT-COMPUTABLE | NOT-COMPUTABLE | yes |
| 32 | `anthropic` | `!!!` | NC | NOT-COMPUTABLE | NOT-COMPUTABLE | yes |
| 33 | `anthropic` | `...` | NC | NOT-COMPUTABLE | NOT-COMPUTABLE | yes |
| 34 | `anthropic` | `n/a` | NC | NOT-COMPUTABLE | NOT-COMPUTABLE | yes |
| 35 | `anthropic` | `unknown-vendor-inc` | NC | NOT-COMPUTABLE | NOT-COMPUTABLE | yes |
| 36 | `Anthropic PBC` | `OpenAI, Inc.` | CROSS | **NOT-COMPUTABLE** | **CROSS-VENDOR** | yes |
| 37 | `Mistral AI` | `Cohere Labs` | CROSS | **NOT-COMPUTABLE** | **CROSS-VENDOR** | yes |
| 38 | `anthropic<U+200B>` | `openai` | CROSS | **NOT-COMPUTABLE** | **CROSS-VENDOR** | yes |
| 39 | `Meta Platforms, Inc.` | `Google LLC` | CROSS | **NOT-COMPUTABLE** | **CROSS-VENDOR** | yes |

### The 28 rows that remain NOT-COMPUTABLE, and why each one does

Every one is a row whose EXPECTED outcome is a refusal. None is a same-vendor or a
cross-vendor pair that the resolver failed to classify.

| # | executor | reviewer | expected | why NOT-COMPUTABLE is the right answer |
|---|---|---|---|---|
| 1 | `bedrock` | `anthropic` | NC | hosting plane - Bedrock serves Anthropic/Meta/Mistral models |
| 2 | `anthropic` | `bedrock` | NC | hosting plane - Bedrock serves Anthropic/Meta/Mistral models |
| 3 | `vertex` | `openai` | NC | hosting plane - Vertex serves Anthropic models too |
| 4 | `azure` | `anthropic` | NC | hosting plane - Azure OpenAI Service serves OpenAI models |
| 5 | `openrouter` | `google` | NC | router - the vendor behind a routed call is unknown |
| 6 | `unassigned` | `anthropic` | NC | placeholder - the field was never filled in |
| 7 | `anthropic` | `unassigned` | NC | placeholder - the field was never filled in |
| 8 | `anthropic` | `totally-made-up-vendor` | NC | UNREGISTERED - genuinely unidentifiable |
| 9 | `<empty string>` | `anthropic` | NC | blank field |
| 10 | `anthropic` | `<empty string>` | NC | blank field |
| 11 | `anthropic` | `None` | NC | absent field |
| 12 | `anthropic` | `7` | NC | not a string |
| 13 | `anthropic` | `{'vendor': 'openai'}` | NC | not a string |
| 14 | `anthropic` | `Acme Inc` | NC | UNREGISTERED - strips to 'acme', still unknown |
| 15 | `anthropic` | `Acme AI Ltd` | NC | UNREGISTERED - strips to 'acme', still unknown |
| 16 | `anthropic` | `Anthropic Killer Inc` | NC | UNREGISTERED - strips to 'anthropic-killer', NOT anthropic |
| 17 | `anthropic` | `Inc` | NC | a bare corporate form names no vendor |
| 18 | `anthropic` | `Ltd.` | NC | a bare corporate form names no vendor |
| 19 | `anthropic` | `AI` | NC | a bare descriptor names no vendor |
| 20 | `anthropic` | `Google Cloud` | NC | hosting plane (registered alias of vertex) |
| 21 | `anthropic` | `AWS Bedrock Inc` | NC | hosting plane (strips to aws-bedrock) |
| 22 | `anthropic` | `Amazon Web Services` | NC | hosting plane (registered alias of bedrock) |
| 23 | `anthropic` | `Azure AI` | NC | hosting plane (registered alias of azure) |
| 24 | `anthropic` | `openai-ish` | NC | UNREGISTERED near-miss |
| 25 | `anthropic` | `!!!` | NC | folds to an EMPTY candidate, which never matches |
| 26 | `anthropic` | `...` | NC | folds to an EMPTY candidate, which never matches |
| 27 | `anthropic` | `n/a` | NC | placeholder |
| 28 | `anthropic` | `unknown-vendor-inc` | NC | UNREGISTERED - strips to 'unknown-vendor' |

**Rows that are NOT-COMPUTABLE but should not be: 0.** None.
<!-- /GENERATED:rows -->

## OWNER / ORCHESTRATOR ACTION - a peer lane left a `DO-NOT-COMMIT` marker in a tracked file

**Not mine, not touched, and it must not be committed.** While measuring, a tracked file showed as
modified:

```
 M command-center/schema/injection-defence-report.schema.json
     "x-catalog-reference-count": 999999,
     "x-wave3-floor-audit-marker": "PLANTED-BY-verify-wave3-DO-NOT-COMMIT"
```

Attribution, two independent signals rather than an inference:

* the marker string exists in exactly one place in the tree —
  `command-center/wave3_d3_audit.py:168-169`, which plants it as a seeded defect;
* the process table shows PID **51928 at 13:23:34** running
  `python command-center/wave3_d3_audit.py`, followed by PID **51720 at 13:23:40** running
  `python -m pytest platform -q -p no:randomly` — and the file's mtime is **13:23:40**. A third
  concurrent run (PID 37448, 13:31:40, `pytest lib/workflows/ lib/foundry/ ...`) was still live.

So a **concurrent lane is mid-probe**: it planted the defect to prove its guard fires. I did not
restore the file — doing so would corrupt a peer's in-flight both-states control, and the file
belongs to that lane. Consequences the orchestrator needs:

1. **Do not `git add -A` this wave.** `999999` is a wrong-but-schema-valid value; committing it
   ships a planted defect into main. Restore with
   `git checkout -- command-center/schema/injection-defence-report.schema.json` once that lane
   reports, or have the lane restore it.
2. **Two of my measurements were contaminated by it, and neither is a defect in this unit.** An
   isolated `pytest test_schema_resolver.py` at ~13:26 failed `test_shims_carry_no_constraints`
   and `test_generator_output_matches_every_committed_file` — both read the planted value. The
   same two tests PASSED in my 13:19-13:23 full-suite run, when the file was clean.
3. Wave 3's own hygiene census did not list this path among its 23 modified tracked files
   (`WAVE3-FLOOR-AUDIT.json:check7_repo_hygiene.modified_tracked_paths`), which is further
   evidence the mutation is from this session, not left over from Wave 3.

## Residual / what this does NOT do

* **It does not make an unknown vendor resolve.** An unregistered string is still UNKNOWN and
  still blocks. Closing the gap by treating unknown vendors as "distinct" is the original D1 false
  green; `Acme Inc` → `acme` → still a refusal.
* **13 of 45 (and 15 of 39 extended) rows remain NOT-COMPUTABLE by design.** Every one is a
  hosting plane, a placeholder, a non-string, a blank, or a genuinely unregistered vendor. The
  table above names the ground for each.
* The 41-token corporate-form list is **not exhaustive** over world jurisdictions (no `k.k.`
  variants beyond `kk`/`k-k`, no `d.o.o.`, no `pt`). A spelling outside it refuses rather than
  mis-resolves, and the fix is a one-line DATA edit. UNVERIFIED which additional forms appear in
  real receipts — settled by grepping produced receipts for `produced_by.vendor` values that
  resolve to UNKNOWN once any exist; no such corpus exists in this tree today.
* `descriptor_suffix_tokens` is deliberately 4 tokens. `cloud` is excluded because `Google Cloud`
  is a plane that serves Claude; adding it would recreate D1 in the dangerous direction. The
  asymmetry with `alibaba-cloud` (a genuine vendor name) is documented in the registry.

## Files this unit changed (and one it did not)

| path | change |
|---|---|
| `platform/registry/VENDOR-REGISTRY.json` | +`normalization` block, +7 aliases, +exclusions, version 1.1.0 |
| `platform/lib/vendor_identity.py` | Cc+Cf strip; registry-driven candidate ladder |
| `platform/schema/receipt.schema.json` | regenerated `$defs`: +7 enum entries only |
| `platform/lib/test_vendor_identity.py` | matrix 63 → 97 rows, +5 tests |
| `platform/lib/test_schema_resolver.py` | the moving-anchor guard, renamed and strengthened |
| `command-center/d1_close_matrix.py` | the 45-row re-runner (imports the audit's own table) |
| `command-center/d1_close_report.py` | renders the row tables from the JSON |
| `command-center/D1-CLOSE-MATRIX.{before,after}.json`, `D1-CLOSE-REGISTRY-GAP.md` | artifacts |

`platform/lib/_mutation_selfcheck.py` also shows as modified in this tree and is **NOT mine** — a
sibling lane taught it to copy `vendor_identity.py` + `VENDOR-REGISTRY.json` into each mutant tree,
which became necessary when `completion_predicate` started importing the resolver at module level.
Worth knowing because it is a downstream consequence of the D1 fix, correctly handled by that lane.

## COVERAGE

Measured: the 45-row audit matrix before and after (imported verbatim from the audit, not restated),
39 extended rows, 5 both-states controls each proven to fire on its seeded defect, all six
`platform/` test roots (3,922 passed / 14 skipped / 0 failed), ruff `check` + `format --check` at
CI's pinned 0.15.17 on every file touched, and an LF + ASCII-only byte check on all five changed
source files.

NOT-CHECKED, stated rather than implied: `tools/command-center/validate.py` and `render.py` were not
run (this unit made no catalog edit, so neither should be affected — that is an inference, not a
measurement). No receipt corpus exists in this tree, so the claim that the added corporate-form
tokens cover the spellings that appear in *real* receipts is UNVERIFIED. The concurrent lanes'
changes present in this working tree (`.gitignore`, `WAVE3-FLOOR-AUDIT.json`,
`_mutation_selfcheck.py`, the deleted `fused.cnc07-arc05.TOURNAMENT-WINNER.workflow.json`) were not
reviewed by this unit.