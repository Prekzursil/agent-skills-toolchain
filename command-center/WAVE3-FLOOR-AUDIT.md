# WAVE 3 FLOOR AUDIT — mechanical, independent

**Unit:** `verify/wave3` · **Date:** 2026-08-10 · **Baseline pin:** main `0aa6f8fa`
**Machine-readable companion:** `command-center/WAVE3-FLOOR-AUDIT.json`

Every number below was produced by a probe in this repo and read off disk or off a git blob.
No agent's self-reported figure is carried forward. Where my probe disagreed with a lane's
document, I re-derived from the raw source rather than picking a side.

> **Concurrency disclosure, load-bearing.** ~20 agents share this working tree and `HEAD` moved
> **three times** while this audit ran (`0aa6f8fa` → `72c3f1a7` → `a46ec548` → `29f4c72a`). Two
> checks were measured twice and the *later* reading is the one reported; the earlier reading is
> kept as the drift record. Any single-run count here is a snapshot, not an invariant.

## COVERAGE

| # | Check | State | Detector control |
|---|---|---|---|
| 1 | D1 cross-vendor predicate, 45 vendor pairs | **CLOSED** | FIRED (24/24 on the pre-fix gate) |
| 1 | D2 work-unit authorization census | **CLOSED** (1 disclosed residual) | FIRED (SEM-009, SEM-010) |
| 1 | D3 hand-edit an unsampled shim, run the suite | **CLOSED** | FIRED (pre-fix generator reverted it) |
| 1 | D4 duplicate workflow ids | **CLOSED** — was PARTIAL 4 h earlier | FIRED (planted duplicate) |
| 1 | D5 non-canonical `assigned_model_vendor_role` | **CLOSED** | FIRED (both instruments moved) |
| 2 | Phase 5 plugin package + full lifecycle | **PASS** | FIRED (8/8 forbidden-content detectors) |
| 3 | Phase 6 marketplace publish→install→revoke | **PASS** | FIRED (revoke, tamper, forgery, governance) |
| 4 | Phase 8 routing bytes@k + precision/recall | **MEASURED, not flooding** | FIRED (real flooding selector) |
| 5 | Phase 9 coordination degrades loudly | **CLOSED** | FIRED (silent adapter) |
| 6 | Full platform suite regression | **NO REGRESSION** — 3922 passed / 14 skipped / **0 failed** | n/a |
| 7 | Repo hygiene / untracked deliverables | **30 untracked deliverables**, 2 of them load-bearing | FIRED (seeded temp file) |

All 11 checks were probed. Nothing here is folded into a pass on the strength of an unrun probe;
the two `NOT-CHECKED` items are named explicitly at the end.

---

## 6. REGRESSION — reported first, because it is the load-bearing number

**No regression. 0 failures in every clean-tree run.**

| run | command | result | exit |
|---|---|---|---:|
| baseline, this audit, tree at `0aa6f8fa`+dirty | `python -m pytest platform -q -p no:randomly` | **3830 passed, 14 skipped, 0 failed** in 588.43 s | 0 |
| with a shim edit deliberately planted (check D3) | same | 3918 passed, 14 skipped, **4 failed** in 627.13 s | 1 |
| **final**, clean tree, `HEAD 29f4c72a` | same | **3922 passed, 14 skipped, 0 failed** in 818.63 s | **0** |

Artifacts: `command-center/wave3_audit_suite_baseline.log`, `command-center/wave3_audit_suite_final.log`
(both verbatim, with the exit code appended).

**The pinned baseline of 2,767 could not be reproduced and is stale.** Measured 3,830 then 3,922 on
a clean tree — **+1,155** against the pin. The D3 lane independently measured 2,812 at `0aa6f8fa`
and also failed to reproduce 2,767, so two lanes now disagree with the pin. Anyone quoting 2,767 is
quoting a number no run in this program has produced. `UNVERIFIED` for the exact gap — settled only
by running the command on a pristine, quiet checkout of `0aa6f8fa`, which is not possible in this
shared tree.

The two clean runs bracket the audit and both show **0 failures**, which is the claim that matters:
the +92 between them is sibling agents adding tests, not this audit changing anything.

The 4 failures in the planted run are fully accounted for and are **not** regressions:
`test_generator_output_matches_every_committed_file` and `test_shims_carry_no_constraints` are the
D3 guard firing on my planted edit (intended); `test_receipt_schema_differs_from_head_ONLY_by_the_authorized_d1_delta`
and `test_the_authorized_delta_guard_fires_on_an_unauthorized_edit` **no longer exist** — a sibling
renamed them to `…_ONLY_by_the_generated_vendor_layer` mid-run (commit `29f4c72a`, "the D1 delta
guard broke when its own anchor moved"). Re-run on the restored tree: `1 passed, 37 deselected`.

---

## 1. THE FIVE DEFECTS — re-derived independently

### D1 — cross-vendor predicate. **CLOSED**

Drove the shipped `completion_predicate._c9_reviewer` over **45** vendor pairs — 24 same-vendor
alias pairs, 8 genuinely cross-vendor, 13 not-computable.

| measurement | value |
|---|---:|
| alias pairs ACCEPTED as cross-vendor (the defect) | **0 / 24** |
| genuinely cross-vendor pairs still accepted (the good direction) | **8 / 8** |
| not-computable pairs blocked (hosting planes, placeholders, unknowns, non-strings) | **13 / 13** |
| rows disagreeing with the expected verdict | **0** |

**Detector control:** I re-implemented the pre-fix gate `str(exec or "") != str(rev or "")` and ran
the same 24 alias pairs through it — **24 / 24 accepted as cross-vendor**. The probe fires on the
known-broken state and is silent on the shipped one, so the 0/24 is a measurement.

Second, mechanically independent signal — the **schema** layer: `receipt.schema.json` `$defs.vendor_id`
carries a **130-value** enum; the same validator accepts `anthropic` and **rejects**
`totally-made-up-vendor`.

Coverage beyond the lane's 10 pairs: fullwidth NFKC (`ｏｐｅｎａｉ`), trailing/leading space, TAB,
NBSP, and four Unicode **Cf** format characters (U+200B, U+00AD, U+FEFF, U+2060).

> **An earlier reading, kept as the drift record.** At `0aa6f8fa`+dirty, 3 of my 24 alias pairs
> resolved `NOT-COMPUTABLE` rather than `SAME-VENDOR` (`Anthropic PBC`, `Mistral AI`,
> `anthropic`+U+200B) — all three in the **fail-closed** direction, so never a false green. All
> three now resolve `KNOWN`. I checked *how*: the normalizer strips Cf, and the registry contains
> **0** aliases with any non-ASCII character — so this was fixed at the normalizer, not papered
> over by registering a zero-width alias. That distinction is the difference between a fix and a
> hack, and it is the right one.

### D2 — work-unit authorization plane. **CLOSED**, one residual disclosed

My own census (not `authz_census.py`) over `work_units[]`, with BEFORE recomputed from
`git cat-file -p 0aa6f8fa:command-center/WORK-UNIT-CATALOG.json` (never `git archive`).

| measurement | BEFORE | AFTER |
|---|---:|---:|
| work units | 2,007 | 2,007 |
| `owner_approval_required: true` | 144 | **167** |
| hold `Task` | 25 | 25 |
| hold `Task` **unapproved** | **23** | **0** |
| hold an `mcp__` token | 261 | 261 |
| hold an `mcp__` token **unapproved** | 239 | **239** ← residual |
| token containing `*` anywhere | 120 | 111 |
| `*` in the token **identity** (a broadening) | **9** | **0** |
| `*` only inside a `( )` **scope** (a narrowing) | 111 | 111 |

Every figure reproduces the lane's own table exactly. `tool_policy` is present: `default: deny`,
57 allow, 19 deny, 2 `require_owner_approval` (`Task`, `AskUserQuestion`).

The shipped gate returns **SEM-008..011**, all at severity `violation`, **0 violations** on the
corpus — and, critically, each rule's `checked` population is **non-zero** (2007 / 28 / 200 / 942).
I assert the positive here rather than "nothing blocking", because a `0 violations / 0 checked`
pair is the guard-converts-a-bug-into-a-green shape this program has already paid for.

**Detector control:** a seeded unit holding `mcp__cloud-hub__modal_sandbox_exec` + `Task(anything)`
+ `Bash(*)` with `owner_approval_required: false` raised **SEM-009** and **SEM-010**; the clean
corpus raises nothing. Additional discrimination probes: an unlisted token
(`mcp__cloud-hub__compute_provision`) → SEM-008; a deny-listed token → SEM-008; an identity
wildcard → SEM-008 + SEM-011; an allowed token → silent.

**Residual, disclosed:** 239 units hold an `mcp__` token without owner approval. Unchanged from
BEFORE; the lane scopes it out in its §5. Not a regression, but it is the largest remaining
authorization surface and it is not gated.

### D3 — a test that repaired the real tree. **CLOSED**

I picked an **independent** target: `command-center/schema/injection-defence-report.schema.json`,
the alphabetical median of the **228** generated shims that the old test did not sample, and
deliberately **not** `abstraction-leak.schema.json` (the fixing lane's own control file).

The pre-fix sample set, read by AST from the pinned blob, is exactly **4** literal paths
(`audit-finding`, `receipt`, `ARTIFACT-CLASS-REGISTRY`, `artifact-class-profiles`) against **236**
generator outputs — **1.69 %**, independently confirming the lane's figure.

| state | probe | planted edit |
|---|---|---|
| **FIXED** (shipped) | full suite, `python -m pytest platform -q -p no:randomly` | **SURVIVED** — digest byte-identical to the planted bytes |
| **BROKEN** (control) | the generator run the pre-fix way: no `--out-root`, cwd = REPO | **REVERTED** to pristine |

The suite went **RED** and named the file:
`(hand-edit a generated file and it shows up here): ['command-center/schema/injection-defence-report.schema.json']`.
The AST guard (`test_no_platform_test_invokes_the_generator_against_the_real_tree`) plus the two
tree-untouched guards: `3 passed`.

Restore asserted: file returned to its original bytes, LF-digest equal to the blob at HEAD,
`git status` for the path **clean**.

### D4 — duplicate workflow ids. **CLOSED** (was PARTIAL earlier the same day)

Scope stated: `platform/workflows/**/*.json`, recursive, a file counting as a workflow doc iff it
parses as a JSON object carrying **both** `dsl_version` and `id` — so a STATUS/VALIDATION report
that merely mentions ids is not miscounted.

| state | docs | distinct ids | duplicate ids |
|---|---:|---:|---|
| `0aa6f8fa` (BEFORE) | 101 | — | **1** id over 3 files: `fused.dc5b5f0b10f7` |
| my first pass, `0aa6f8fa`+dirty | 103 | 102 | **1** id over 2 files |
| **current** | **102** | **102** | **0** |

The BEFORE collision was the dangerous shape: `REJECTED.union.cnc07-arc05.workflow.json` had
**different content** (LF-sha `84dea55761ab`) yet the **same id** as the tournament winner
(`d771debb5295`), so an id-keyed loader could load a REJECTED document as the winner. My first
pass found that half fixed and a residue: the winner and its `TOURNAMENT-WINNER` copy were
byte-identical (`f9a2338a1c31`) and still shared one id. Both are now gone; a sibling landed
`platform/lib/workflows/workflow_id_index.py` + `test_workflow_id_uniqueness.py` (still untracked —
see check 7).

**Detector control:** two temp files carrying an existing doc's id → exactly 1 duplicate reported;
delete one → 0 reported.

### D5 — non-canonical `assigned_model_vendor_role`. **CLOSED**

| measurement | `0aa6f8fa` | current |
|---|---:|---:|
| object form (canonical) | 1,879 | **2,007** |
| slash-triple **string** form (non-canonical) | **128** | **0** |
| structural key-set fingerprints | 4 | 5 |
| `items[]` register entries carrying the field | 0 | **0** |

Second, mechanically independent instrument: `jsonschema` Draft 2020-12 against
`work-unit.strict.schema.json` via the platform's own disk-only `referencing` registry —
**0** `assigned_model_vendor_role` type errors, agreeing with my hand classifier.

**Detector control:** seeding one unit with `"opus/anthropic/implementer"` moved **both**
instruments by exactly +1. A control that moved only one would have meant the two were not
independent.

The briefed "128 → 1,879 regression" is confirmed **REFUTED as a regression**: the two numbers are
complements of 2,007, i.e. a polarity-inverted detector, exactly as the D5 lane argued.

---

## 2. PHASE 5 PLUGIN — **PASS**

Built and driven through a full lifecycle in a throwaway prefix.

| measurement | value |
|---|---|
| `astplugin build` | exit **0** |
| archive | `ast-integrate-platform-1.0.0.zip` |
| **archive bytes** | **95,093** |
| **file count** | **45** members |
| uncompressed | 288,265 B |
| sha256 | `af62a8836abc4f73e2a6a529dab7ea5e09b7e0828183a7caa3a08965b3067b04` |
| deterministic rebuild (two temp dirs) | **byte-identical** |

All three independently reproduce the lane's `PACKAGE-MEASUREMENT.json` — same sha256, same 95,093
/ 45 / 288,265. Contents: 1 plugin manifest, LICENSE, allowlist + inventory, README, 1 bin, 1
command, 1 hook, 20 `lib/astplugin/*.py`, 19 `schema/*.json`.

### Does it contain `.git`, credentials, or transcripts? **No — 0 hits in every category**

| detector | hits | control fired on a seeded archive |
|---|---:|---|
| `.git` / `.gitmodules` / `.svn` / `.hg` | 0 | yes |
| `.jsonl` / `transcripts/` | 0 | yes |
| `.log` / `logs/` | 0 | yes |
| `__pycache__` / `.pyc` / `node_modules` | 0 | yes |
| credential **filenames** (`.env`, `.pem`, `auth.json`, `id_rsa`, …) | 0 | yes |
| credential **values** in content (8 patterns, all 45 members read) | 0 | yes |
| nested archives | 0 | yes |
| shipped test modules | 0 | yes |

Every detector was proven against a synthetic archive containing all eight bad shapes **before**
the 0-hit reading was taken, so the zeroes are measurements and not a silent matcher. Matched
values are never recorded — only the pattern name and a byte offset (AGENTS.md §9).

### Lifecycle, real output

| step | exit | prefix after |
|---|---:|---|
| `install --package … --prefix … --live …` | **0** | 48 files, 290,557 B |
| `update` to a built 1.0.1 | **0** | 93 files, 579,876 B |
| `rollback` | **0** | 93 files — `previous_version: 1.0.1`, active `version: 1.0.0`, `versions_retained: [1.0.0, 1.0.1]`, `userdata_untouched: true` |
| `uninstall --purge-user-data` | **0** | 1 file — `removed_versions: [1.0.0, 1.0.1]`, `removed_live: [commands/astplugin.md, hooks/plugin_health.py]` |

The single surviving file after uninstall is `state/journal.jsonl`, the transaction journal.
Retaining an audit trail across uninstall is correct, not a leak — and it is the only thing left.

**Seeded-defect control:** the same archive with `.git/config` and a `.env` carrying an
`sk-ant-…` value appended → `astplugin conform` exits **51**; on the clean archive it exits **0**.
Discriminating in both directions.

---

## 3. PHASE 6 MARKETPLACE — **PASS**. Revocation blocks.

| step | exit | note |
|---|---:|---|
| `mkt fixture --into T` | 0 | registry lands at `T/registry`, **not** `T` |
| `mkt publish` **without** `--license-basis` | **1** | refused `MKT-P05` — the governance gate |
| `mkt publish` **with** `--license-basis` | **0** | success path |
| `mkt install hello-skill@1.0.0` | **0** | 6 files land in the site |
| `mkt revoke --scope version hello-skill 1.0.0 --authority pub:registry-root` | 0 | signed revocation list written |
| `mkt install hello-skill@1.0.0` (fresh site) | **1** | **REFUSED**, `MKT-I04`, **0 files landed** |
| `mkt install hello-skill@1.1.0` (never revoked) | **0** | revocation is **scoped**, not a kill switch |

**Signature verification, cryptographic.** `mkt.crypto.verify_document` over the **manifest**
(`domain mkt.manifest.v1`, `key:e647315ae19a0667`) and the **registry index**
(`mkt.index.v1`, `key:94e9ffb6a5a7e313`): both `verified: true`, and both still true with the
expected public key **pinned** — so a doc re-signed by an arbitrary key would not pass.

**SBOM.** CycloneDX **1.5**, `serialNumber` present, **3** components, **3 of 3** carrying SHA-256
hashes, licences `[MIT]`, and `sbom_ref` present in the manifest.

**Four independent controls, all valid in both states:**

| control | good state | seeded-bad state |
|---|---|---|
| revocation | install exit 0 before | exit 1 after, `MKT-I04`, 0 files landed |
| signature forgery (1 char of the sig altered) | genuine verifies `true` | forged verifies **`false`** |
| payload tamper (+34 B appended to `hello.py`) | install exit 0 before | exit 1, **`MKT-I09`** naming both digests, 0 files landed |
| governance licence basis | with `--license-basis` exit 0 | without it exit 1, `MKT-P05` |

The lane's own battery (`mkt mutations`) declares **13** mutations, runs **13**, all **13**
`load_bearing: true` — each gate REFUSES with its expected code in the real state and the
corresponding mutant SUCCEEDS.

---

## 4. PHASE 8 ROUTING — measured; **not** achieving recall by flooding

Bytes actually injected per query (mean over the lane's own 60-query labelled set; 54 carry gold):

| k | mean **card** bytes / query | mean full-description bytes if uncarded | mean items returned | precision | recall |
|---:|---:|---:|---:|---:|---:|
| 1 | **163.1** | 211.4 | 0.85 | 0.5185 | 0.4552 |
| 3 | **386.3** | 528.7 | 2.13 | 0.3364 | 0.6512 |
| 5 | **492.4** | 672.2 | 2.78 | 0.3065 | 0.6759 |
| 10 | **537.8** | 720.6 | 3.03 | 0.2996 | 0.6759 |

Corroborates the lane's `routing budget` CLI (163.1 / 387.6 / 494.4 / 540.0) to within 0.4 %.

Per tier — an easy tier must not mask a hard one:

| tier | n | recall@1 | recall@10 | precision@10 |
|---|---:|---:|---:|---:|
| L1 (literal description) | 28 | 0.7143 | **1.0000** | 0.3560 |
| L2 (paraphrase / intent) | 21 | 0.1825 | **0.3571** | 0.2163 |
| L3 (**negative**, gold = ∅) | 6 | — | — | abstain **0.6667** |
| L4 (compositional) | 5 | 0.1500 | **0.2000** | 0.3333 |

My independent L3 abstain rate of **0.6667** matches the lane's reported 0.667.

**L2 recall@10 = 0.357 and L4 recall@10 = 0.200 are the real routing weakness** — on paraphrased
and compositional queries the router misses roughly two thirds of gold. It is honestly reported in
the lane's own `MEASUREMENTS.json`, so this is a disclosed limitation rather than a hidden one.

### Flooding: **NOT FLOODING**

| signal | value |
|---|---|
| mean items returned at k=10 | **3.03 of 10 slots** (fill ratio 0.303) |
| byte growth k=1→k=10 | 3.3× |
| recall gain k=1→k=10 | +0.2207 |

**Detector control — a real flooding selector, not a hardcoded constant.** I built one from
`Decision.candidates[:10]` (the unthresholded ranking) and measured it: **10.0 items/query,
1,792.7 card bytes/query, recall 0.7824**. My probe flags it **FLOODING** and stays silent on the
shipped router. So the shipped router trades **0.107 recall** for a **3.3× byte reduction** and
truncates below k rather than filling it — the honest reading is a deliberate precision/budget
trade, not recall-by-flooding.

> **A detector failure of my own, recorded.** My first per-tier pass divided by `len(rows)` instead
> of the gold-bearing count, which made the L3 **negative** tier (gold empty for all 6) read as
> "recall 0.0 at every k" — it looked like a routing hole and was pure arithmetic. Corrected above.

---

## 5. PHASE 9 COORDINATION — **CLOSED**. Degrades loudly, artifact preserved.

Forced **6** vendor-unsupported operations against the shipped adapters, with a real work artifact
on disk:

| adapter | capability | declared | raised | terminal | artifact |
|---|---|---|---|---|---|
| `codex-cli` | `subagent.spawn` | REFUSED | `CapabilityUnavailable` | **BLOCKED** | preserved, sha unchanged |
| `codex-cli` | `mcp.tools` | REFUSED | `CapabilityUnavailable` | BLOCKED | preserved |
| `codex-cli` | `sandbox.enforced` | REFUSED | `CapabilityUnavailable` | BLOCKED | preserved |
| `claude-code` | `schema.typed_output` | REFUSED | `CapabilityUnavailable` | BLOCKED | preserved |
| `gemini-cli` | `fs.write` | **UNMEASURED** | `CapabilityUnavailable` | BLOCKED | preserved |
| `human-owner` | `subagent.spawn` | REFUSED | `CapabilityUnavailable` | BLOCKED | preserved |
| `codex-cli` | `fs.read` | OFFERED | **did not raise** | — | — |

Sample sentinel, verbatim:
`FAILED:AUDIT-COORD-1 capability-unavailable adapter=codex-cli capability=subagent.spawn preserved=1`

`UNMEASURED` is treated as not-offered — the right direction; a never-probed capability must not
pass as available. The good direction is intact: the one OFFERED capability did **not** raise, so
the boundary is not simply refusing everything.

**Structurally incapable of reading as success:** `DegradedOutcome.ok` is a hard `False`
**property**, not a field (`"ok" not in __dataclass_fields__`), and constructing one with
`terminal_state="SUCCESS"` still yields `ok is False`.

**Detector control:** a seeded adapter whose `require()` returns `None` instead of raising is
flagged (it did not raise); all six shipped refusals raise. Both states valid.

---

## 7. REPO HYGIENE

`git status --porcelain=v1 **-uall**` over the whole repo — not `-unormal`, which collapses an
untracked directory into a single line and is how a scope-too-narrow reading went wrong earlier in
this program. Detector control: a seeded temp file under `platform/` was seen, and its removal was
seen.

| measurement | first pass (`0aa6f8fa`+dirty) | current |
|---|---:|---:|
| untracked total | 315 | **140** |
| — under `platform/` | 273 | 107 |
| — under `command-center/` | 17 | 27 |
| — elsewhere | 25 | 6 |
| modified tracked | 23 | 8 |
| **untracked DELIVERABLES** | — | **30** |
| untracked scratch (`_`-prefixed, `__pycache__`, `.pyc`) | — | 104 |

The first pass caught the Wave-2 repeat: Wave 3's entire deliverable set — all of
`platform/coordination/*`, the DEFECT docs, the lane sources — was untracked. **The orchestrator has
since committed it** (`72c3f1a7`, `a46ec548`, `29f4c72a`). What remains untracked:

**Under `platform/` (4) — these are live deliverables, not scratch:**
- `platform/lib/workflows/workflow_id_index.py` ← the D4 closure mechanism
- `platform/lib/workflows/test_workflow_id_uniqueness.py` ← the test that keeps D4 closed
- `platform/workflows/_shared/shared.pairwise-overlap-matrix.subworkflow.json`
- `platform/workflows/_shared/shared.write-as-you-go-artifact.subworkflow.json`

**The first two matter most: the gate that closes D4 is untracked, so D4's closure is not yet in
version control.** A fresh clone still has the duplicate-id hole and no test to catch it. This is
the single highest-value line in this check — everything else untracked is scratch or reporting.

**Under `command-center/` (26):** `D1-CLOSE-MATRIX.{before,after}.json`,
`D1-CLOSE-REGISTRY-GAP.md`, `D4-ID-COLLISION-CLOSE.md`, seven `WAVE4-*` probe artifacts,
`schema/_meta/json-schema-2020-12.json`, and 13 probe scripts including my own four
(`wave3_floor_audit.py`, `wave3_lifecycle_audit.py`, `wave3_marketplace_audit.py`,
`wave3_d3_audit.py`). Mine are deliberately given real names, not `_`-prefixed, because they are the
instruments behind this report; whether they are tracked is the orchestrator's call.

**Elsewhere (6):** `_f7_syncskills_probe.py`, `_refute_f1_codex_stubs.py`, `_refute_f4_atomicity.py`,
`_refute_f6_probe{,2,3}.py` — all `_`-prefixed scratch at the repo root.

---

## FINDINGS the lanes did not report

1. **`mkt revoke` accepts a non-maintainer authority and reports SUCCESS while bricking the
   registry.** Signing a revocation list with `--authority pub:security-response`
   (role `security-response`, not a maintainer key) exits **0**, but the installer then rejects the
   list — *"revocation list signature is not acceptable (key is not a maintainer key) — an
   unverifiable revocation list is treated as a refusal, never as an empty one"* — and refuses
   **every** install from that registry, including `hello-skill@1.1.0`, which was never revoked
   (measured exit 1). Fail-closed on an unverifiable list is the correct install-side behaviour; the
   gap is that `revoke` does not validate the authority against the maintainer key set before
   writing, so a legitimate operator can silently self-inflict a registry-wide denial of service.
   Severity moderate; fix is a pre-write check in `revoke`.
2. **The installed site carries no SBOM.** The registry holds a full CycloneDX 1.5 SBOM, but the
   install site receives 6 files and **0** `sbom.json`. A post-install supply-chain audit has
   nothing local to read. Mitigated — not eliminated — by `mkt-lock.json`, which does carry payload
   digests. Severity low.
3. **`mkt mutations` crashed once under concurrency**, at `mutations.py:448 scenario_wrong_platform`
   → `_resign_index` → `canon.write_json:187` `os.replace` → `PermissionError: [WinError 5]`.
   Standalone it passes **3/3** with byte-identical 3,832-byte output, so the gate is not broken —
   but `canon.write_json`'s atomic rename has no retry, and on Windows `os.replace` can transiently
   fail when any handle exists (AV, indexer, a concurrent reader). 1 crash in 4 runs. Severity low;
   fix is a bounded retry around `os.replace`.
4. **The tournament's G4 acceptance criterion is not met as literally written.** It requires that
   "a fixture unit holding `mcp__cloud-hub__modal_sandbox_exec` with `owner_approval_required: false`
   **must** fail". Measured: that unit raises **no violation**, because the shipped
   `tool_policy.allow` list *contains* `mcp__cloud-hub__modal_sandbox_exec`. The lane discloses this
   honestly and inline — `authz_census.py:218-224` records that the earlier seed used that token,
   that the allowlist permits it, that the control therefore read `bad=0` and measured nothing, and
   substitutes `mcp__cloud-hub__compute_provision`. The substance of the criterion (a
   non-allowlisted token must fail) **is** met. Flagging it because the deviation lives only in a
   code comment, not in the gate ledger, and because "the corpus may hold an unapproved
   arbitrary-remote-code-execution grant" is an owner policy decision rather than a lane decision.
5. **The 2,767 baseline pin is stale** — see check 6. Two independent lanes now fail to reproduce it.

## A COST MY OWN METHOD IMPOSED, AND A NOW-STALE ACTION ITEM

**The D3 probe transiently dirtied a tracked file in a tree twenty agents share, and a peer lane
paid for it.** `command-center/D1-CLOSE-REGISTRY-GAP.md:308-328` carries a section headed
*"OWNER / ORCHESTRATOR ACTION — a peer lane left a `DO-NOT-COMMIT` marker in a tracked file"*,
quoting my exact planted keys. That lane attributed it correctly and well — two independent signals
(the marker string existing in exactly one place, `wave3_d3_audit.py:168-169`, plus the process
table showing my PID and a matching mtime) — and correctly refused to commit it. No verdict of
theirs was contaminated.

Two things follow, and the orchestrator needs both:

1. **The marker is GONE.** Verified after the fact:
   `git status --porcelain=v1 -- command-center/schema/injection-defence-report.schema.json` is
   **empty**, the file's LF-digest equals its blob at HEAD, and a tree-wide `grep` for
   `PLANTED-BY-verify-wave3` now hits only two places — my own probe source (where it is a string
   literal) and that sibling's write-up. **So `D1-CLOSE-REGISTRY-GAP.md`'s action item is stale and
   must not be acted on.** Left unread, it invites someone to hunt a modification that no longer
   exists.
2. **The method itself deserves the criticism.** Planting a defect in a *tracked, shared* file to
   validate a guard is the correct experiment but the wrong location. A restore-on-exit `finally`
   block (which I had, and which worked) does not help a sibling who samples `git status` inside the
   ten-minute window. The right shape is to plant into a copied tree — feasible here precisely
   because the D3 fix made `REPO` `__file__`-derived and added `--out-root`. I did not do that, and
   the cost landed on someone else.

## MY OWN DETECTOR FAILURES — recorded, since an unvalidated pass is not evidence

Five, all caught by a control or a self-contradiction rather than by review:

| # | wrong reading | what caught it | correction |
|---|---|---|---|
| 1 | D2 census: `hold_Task 0`, `hold_mcp__ 0` | contradicted the shipped gate's 942-unit `checked` population | the field is `tool_permissions`, not `tools`; added a `TOKEN_FIELD_COVERAGE` assertion so the miss cannot recur silently |
| 2 | `tool_policy.require_approval = 0` vs the lane's 2 | key-name mismatch | the real key is `require_owner_approval` (= 2) |
| 3 | Marketplace: "revocation blocks install" | its own both-states control (`probe_silent_before_revocation: false`) | `--registry` must point at `<into>/registry`; publish had exited 1 and install failed with `RegistryError` in **both** states |
| 4 | Signature `verified: false` on the genuine manifest | the forgery control read false in both states | the API is `verify_document(doc, domain, *, expected_public_key)`, not `verify()` |
| 5 | Routing "L3 recall 0.0 at every k" | the lane's own doc calls L3 a negative tier | divided by `len(rows)` instead of the gold-bearing count; L3's metric is abstention (0.6667) |

## RESIDUAL / NOT-CHECKED

- **Release/canary (program stopping condition 13)** — `NOT-CHECKED`. Release mode is PR-ONLY and
  binding, so the condition is unsatisfiable as written. I read it as "a merged PR plus a local
  rollback rehearsal" and **say so**: the local rollback rehearsal is measured above
  (`astplugin rollback` exit 0, `previous_version: 1.0.1` → active `1.0.0`); the merged PR is not
  mine to make.
- **`ruff` under CI's pinned 0.15.17** — **CHECKED and clean** for all four of my scripts:
  `uvx ruff@0.15.17 check` → *"All checks passed!"*, `uvx ruff@0.15.17 format --check` → *"4 files
  already formatted"*. Two `F841` unused-variable errors were found and fixed first. Deliberately
  the pinned version, not the ambient one — a local green against a different version verifies
  nothing (`windows-shell.md` §8b). Residual: this ran against the **working tree**, not the blob,
  because these files are untracked and have no blob yet.
- **Repo-wide `ruff` / `cc-validate` / `cc-render`** — `NOT-CHECKED`. I linted only what I authored;
  the wave's own gates are the lanes' and the orchestrator's to run.
- **The 239 unapproved `mcp__` grants** — measured, not adjudicated. Owner policy call.
- **Every count is a snapshot of a tree under concurrent write by ~20 agents.** `HEAD` moved three
  times mid-audit. Reproducing any figure requires a quiet tree, which this is not.
