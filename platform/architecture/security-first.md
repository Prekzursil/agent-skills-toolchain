---
title: security-first
type: note
permalink: dqverify-repo-20261013/platform/architecture/security-first
---

# Architecture Candidate: SECURITY-FIRST

**Phase 3 — Architecture Tournament.** Advocate's brief, argued honestly.
Spec authority: `_USER-PROMPTS.md:10769-10796` ("security-first architecture" is item 7 of the 9
mandated candidates). Mechanism namespace: `MECH-NN` per `13-ARCHITECTURE-CANDIDATES.md:1007`.

Measured against the working tree at `git rev-parse HEAD` = **`9f2dac7a`**, not the brief's pinned
`dc90d64a`. The pin is three commits stale (`9f2dac7a` / `b68815fd` / `833fb1ea`); every number below
was re-measured at `9f2dac7a` by `platform/architecture/_secfirst_measure{,2,3}.py` and
`_secfirst_probe_denydefault.py`, whose JSON outputs sit beside this file.

**Drift disclosure (the tree moved while this was written, and I checked rather than assumed).** HEAD
advanced to `edcf9f5b` — **1 commit**, an unrelated LF-normalisation of a register hash — and
concurrent sibling units added ~67 untracked `.py` files under `platform/lib/`, moving the
working-tree `.py` count 64 → 131 and the untracked total 369 → 532. **None of the five files this
architecture modifies changed**: `git diff --name-only 9f2dac7a..HEAD --
platform/schema/receipt.schema.json platform/schema/work-unit.normative.schema.json
platform/lib/wfdsl/semantics.py platform/lib/completion_predicate.py
.github/workflows/quality.yml command-center/WORK-UNIT-CATALOG.json` returns **empty**, and tracked
`platform/lib/**/*.py` is **44 at both revisions**. So §3's design and every schema/catalog figure
below remain current; only the three volatile working-tree counts drifted, and the self-audit (§10)
classifies them as drift rather than silently passing or silently failing on them.

---

## 0. REUSE vs REPLACE — stated first, as required

**This architecture replaces nothing. It deletes zero Wave 1 files and rewrites zero Wave 1
control planes.** It is additive over the substrate and it inherits, rather than re-invents, the
evidence discipline Wave 1 shipped.

The Wave-1-plus-substrate primary artifact set is **431 files**: 9 `platform/schema/*.schema.json` +
64 `platform/lib/**/*.py` + 117 `platform/council/**/*.councilspec.json` (48 protocol + 69 preset) +
7 `platform/registry/*` + 233 `command-center/schema/` shims + 1 `WORK-UNIT-CATALOG.json`
(2,007 `work_units[]`). Against that set:

| disposition | count | what |
|---|---|---|
| **REUSED UNCHANGED** | **427 of 431** | all 117 councilspecs · all 7 registry files · all 233 shims · the catalog · 7 of 9 platform schemas · 62 of 64 lib modules |
| **MODIFIED, additively and backward-compatibly** | **4 of 431**, +1 outside it | `platform/schema/receipt.schema.json` (+1 optional `$def`, no new `required`) · `platform/schema/work-unit.normative.schema.json` (+1 `$def`) · `platform/lib/wfdsl/semantics.py` (+3 rules in `check_work_units`) · `platform/lib/completion_predicate.py` (+2 `PredicateOptions` flags, no new condition). Outside the set: `.github/workflows/quality.yml` (per-job `permissions:` + scanners) |
| **ADDED NEW** | **6** | `platform/schema/unit-tool-policy.schema.json` · `platform/policy/unit-tool-policy.json` · `platform/lib/unit_authz.py` · `platform/lib/test_unit_authz.py` · `platform/lib/witness_join.py` · `platform/lib/test_witness_join.py` |
| **DELETED** | **0** | — |

The reuse ratio is deliberate and it is the candidate's main claim to cheapness: **Wave 1 already
built roughly two-thirds of a security-first architecture without calling it that.** The measurement
that proves it, and the four gaps that prove it is only two-thirds, are §1 and §2.

Counts are from `_secfirst_measure.out.json` → `wave1_inventory` (`schemas_platform_n: 9`,
`council_protocol_n: 48`, `council_preset_n: 69`, `lib_py_n: 64`, `cc_schema_n: 233`) and
`_secfirst_measure2.out.json` → `git_scope`.

Three brief-vs-disk discrepancies, disclosed rather than smoothed over:
- brief says **8** schemas, disk has **9** — `artifact-class-profiles.schema.json` (189,910 B) was
  added by the substrate sibling after the pin. Not a defect; the pin moved.
- brief says **5 lib packages**; disk has **4** package directories (`wfdsl`, `councilspec`,
  `council_protocols`, `workflows`) plus 3 top-level modules (`completion_predicate.py`,
  `receipt_schema_gate.py`, `schema_resolver.py`). `workflows/` is a *sibling's* in-flight work, not
  Wave 1. The brief's "5" counts modules and packages together; both descriptions name the same code.
- brief says protocols 48 / presets 69 — **CONFIRMED exactly**, 117 total.

---

## 1. What Wave 1 already shipped that is a security control (measured)

This is the load-bearing inventory. Every row is a security mechanism that exists **today** in
`platform/schema/receipt.schema.json` (37,715 B, 39 `$defs`) or the gates that read it. None of it
is proposed; all of it is on disk.

| existing artifact | security property it already enforces | anchor |
|---|---|---|
| `$defs/negative_control.required` = `[id, kind, description, fired_on_bad_state, silent_on_good_state]` | **the both-states test is a schema requirement.** A receipt cannot claim a control without asserting it fires on bad state *and* is silent on good state | `receipt.schema.json`, `_secfirst_measure.out.json:receipt.negative_control_required` |
| `$defs/probe.required` = `[role, method, command, raw_output, fingerprint]` | **two-independent-signal is mechanized.** A probe must carry its literal command and raw output, so a re-run of the same probe is detectable by fingerprint | same |
| `$defs/artifact.required` = `[path, bytes, sha256, exists]` | content addressing of every claimed artifact | same |
| `$defs/security_report.report.findings[].credential_redacted` = `{"const": true}` | **deny-by-default redaction as a schema constant.** A security finding is structurally unable to omit the redaction assertion. Referenced by **24 units** | `receipt.schema.json` `$comment`; `_secfirst_measure2.out.json:output_schema.security_report_fragment_users = 24` |
| `$defs/security_report.report.scanners` `minItems: 1`, each requiring `{name, version, installed}` | **MECH-04 (fail-open dependency receipts) already shipped.** A scanner that was not installed must say `installed: false` rather than vanish | same |
| `completion_predicate.py` `Outcome.NOT_CHECKED` on absent reviewer / uncomputable severity | **MECH-03 (typed silence) already shipped** for the predicate: *"absence of a review is NOT-CHECKED, never a pass"* | `platform/lib/completion_predicate.py:898`, `:930` |
| `receipt_schema_gate.py` and `completion_predicate.py` both recompute `sha256` from disk bytes | artifact **integrity** is verified, not trusted | `_secfirst_measure2.out.json:forgeability.*.recomputes_artifact_sha256 = true` |
| `wfdsl/semantics.py` `DSL-SEM-011` — *"every tool a stage or role requests is permitted by `tool_policy` (deny by default)"*, severity `violation` | a real **deny-by-default capability gate**, with a killed mutation (`mutations.py:88-93` appends `mcp__cloud-hub__modal_sandbox_exec` to a researcher role and requires SEM-011 to fire) | `platform/lib/wfdsl/semantics.py:479-506` |
| `work-unit.normative.schema.json` `$defs/tool_token` pattern | a real tool-token grammar covering native, scoped (`Write(path/**)`), sub-shell (`Bash:python`) and `mcp__server__method` forms, with `_` forbidden in `<server>` **specifically so two comma-packed ids cannot match** | `platform/schema/work-unit.normative.schema.json` |
| `.gitleaks.toml` (11,159 B) · `.quality/opengrep/{general,python,javascript}-security.yaml` · `osv-scanner.toml` · `.semgrepignore` · `SECURITY.md` · `QUALITY-CHARTER.md` | a real static supply-chain plane, wired into `quality.yml` (`gitleaks` ×34, `opengrep` ×15, `osv-scanner` ×10, `semgrep` ×3 mentions) | `_secfirst_measure.out.json:existing_security_planes`, `quality_yml.scanner_mentions` |
| 4 security-named councilspecs | `C-H55-security-secret-exposure-blastradius`, `C-H56-security-untrusted-repo-admission`, `c-d32-deep-security-threat-model-10`, `c-m09-micro-security-smell` | `_secfirst_measure2.out.json:council_detector_forensics.filename_has_security` |

**Executable proof that the one shipped authorization control actually works.** I ran a four-state
discrimination probe against `DSL-SEM-011` rather than asserting it:

```
$ python platform/architecture/_secfirst_probe_denydefault.py
S1_absent_policy     viol=2 checked=2 ok=True     <- fails CLOSED
S2_allowlisted       viol=0 checked=2 ok=True     <- no false positive
S3_explicit_deny     viol=1 checked=2 ok=True
S4_default_allow     viol=0 checked=2 ok=True
all_four_as_expected: True | discriminating: True
SUCCESS:secfirst-denydefault
```
S1's actual violation text: `"/stages/0": "tool 'Read' is not in tool_policy.allow and the policy
default is deny"`. `tool_policy` is **not** in `workflow-dsl.schema.json`'s `required`
(`['dsl_version','id','name','version','stages']`), yet `semantics.py:476` reads
`str(policy.get("default","deny")) == "deny"` — so an omitted policy denies everything rather than
allowing everything. **That is a correct fail-closed default and it is the single best piece of
security engineering in Wave 1.** This architecture's core move is to give the other two planes the
same property.

---

## 2. The four gaps that make it only two-thirds

Two are *design* gaps in the substrate (GAP-1 authorization, GAP-2 trust root) and two are
*hygiene* gaps in the surrounding repo (GAP-3 version control, GAP-4 CI depth). All four are
CONFIRMED with the detector caveats stated inline.

### GAP-1 — the authorization plane covers one plane out of three (CONFIRMED, mechanically)

Wave 1's deny-by-default gate governs **workflow-DSL documents**. It does not govern the
**work-unit catalog**, which is where all 2,007 units and every tool grant actually live.

```
workflow-DSL plane : 14 semantic rules, 1 authorization rule  (DSL-SEM-011, severity=violation)
work-unit  plane   :  7 semantic rules, 0 authorization rules (SEM-001 .. SEM-007)
```
(`_secfirst_probe_denydefault.out.json:plane_asymmetry`; the work-unit rule list is literally
`['SEM-001','SEM-002','SEM-003','SEM-004','SEM-005','SEM-006','SEM-007']` and
`work_unit_authz_rules` is `[]`.)

Meanwhile every one of the 2,007 units *declares* an authorization posture:

| declared field | coverage | distinct values | consumed as a constraint? |
|---|---|---|---|
| `tool_permissions` | 2007/2007 | **151** distinct sets; top is `["Read","Grep","Glob","Bash"]` ×266 | **no** — validated as *shape* (`minItems:1`, `tool_token` pattern), never against a policy |
| `owner_approval_required` | 2007/2007 | `False` ×1863, `True` ×144 | **no runtime reader found** |
| `execution_substrate` | 2007/2007 | `local-parallel` 784, `local-serialized` 565, `worktree-isolated` 456, `cloud-batch` 202 | **no runtime reader found** |
| `reviewer_requirement` | 2007/2007 | 479 distinct prose strings | **no runtime reader found** |

(`_secfirst_measure2.out.json:authorization_surface`.)

`work-unit.schema.json` *requires* `tool_permissions` with `minItems: 1` and the comment *"At least
one — an empty list is indistinguishable from 'unspecified'"* — good instinct — but
`has_enum_allowlist: False` on all three profiles (`work-unit`, `.normative`, `.strict`). The grammar
constrains the *shape* of a token; nothing constrains the *set*. A unit may declare
`mcp__cloud-hub__modal_sandbox_exec` (paid GPU + arbitrary egress) or
`mcp__cloud-hub__dbx_secret_get` (a secret read) and pass every gate in the repo today.

**144 units declare `owner_approval_required: true` and nothing on disk stops any of them.** That is
the sharpest single sentence in this document, and it is measured, not inferred.

*Detector honesty, inline.* My enforcement classifier is **asymmetric**: `reading > 0` proves a
consumer exists; `reading = 0` does **not** prove absence. Control run: `spec_anchor` — which
`receipt_core` genuinely requires — also scored `reading = 0`, because the classifier only matches
`.get("f")` / `["f"]` and misses attribute and destructured access. So the four `no` rows above are
**PARTIAL, not CONFIRMED-absent**; the settling experiment is a call-graph pass (e.g. `ast`
`Attribute`/`Subscript` resolution) over the 29-file runtime surface. The *positive* findings are
CONFIRMED: `tool_permissions` **is** read, by `wfdsl/mutations.py` and `wfdsl/semantics.py` — i.e.
only inside the DSL plane, which is exactly the asymmetry claimed.
`control_verdict: DETECTOR-OK` (`min_bytes_threshold` and `negative_controls` both scored
`reading = 2`, so the classifier does find real consumers).

### GAP-2 — the trust root is self-attested (CONFIRMED)

The receipt is a superb *evidence* protocol with **no authenticity layer at all**. Token counts over
the entire 37,715-byte schema:

```
signature 0 · signed 0 · attestation 0 · attest 0 · provenance 0
generated_by 0 · source_ref 0 · actor 0 · identity 0 · authz 0
capability 0 · sbom 0 · supply 0        (sha256: 3)
```
(`_secfirst_measure.out.json:receipt.mentions_*`.)

`produced_by` requires exactly `["vendor", "model"]` — two free-text strings, `maxLength` 64 and 128
— and is **not** in `receipt_core.required` at all
(`_secfirst_measure3.out.json:receipt_authz_binding.core_requires_produced_by: false`). The receipt
never references `tool_permissions` or `owner_approval` (`mentions_tool_permissions: 0`,
`mentions_owner_approval: 0`), so nothing joins what a unit was *allowed* to do to what its receipt
*claims* it did.

The concrete consequence is predicate condition 9. Its 12 conditions are enumerated at
`completion_predicate.py:69-82`; condition 9 is *"independent reviewer status is PASS"*, and
`_c9_reviewer` (`:890-951`) does real work — it requires `verdict == "PASS"`, requires
`independent is True` (*"self-review is not review"*), and under
`opts.require_cross_vendor_review` it compares `reviewer.vendor` to `produced_by.vendor` and rejects
equality with the exactly-right reason *"a same-vendor reviewer inherits the executor's blind
spots"*. **But both sides of that comparison are strings the producing agent writes into its own
receipt.** A single agent that emits

```json
"produced_by": {"vendor": "anthropic", "model": "..."},
"reviewer":    {"reviewer_id": "codex-1", "verdict": "PASS",
                "independent": true, "fresh_context": true, "vendor": "openai"}
```

satisfies condition 9 in full without any second process, any Codex thread, or any review ever
existing. `mentions_separation: 0` in all three gates confirms nothing checks for it.

This is **not** a criticism of Wave 1. Wave 1 built the protocol. The protocol's own docstring
states the intent correctly. What is missing is the mechanism that makes the assertion *cost*
something.

### GAP-3 — the substrate that every receipt resolves through is not in version control (CONFIRMED)

```
tracked_cc_schema      : 0
untracked_cc_schema    : 233
gitignore_mentions_cc_schema : false
untracked_total        : 369   (129 under platform/)
```
(`_secfirst_measure2.out.json:git_scope`.) All 233 files of the shim tree that closed the Wave-1 P1
— the plane through which all 2,007 `output_schema` references resolve — exist only in one working
tree, are not ignored on purpose, and would be lost by any `git clean`. Under §9b that is a
blast-radius question, not a housekeeping one: the integrity root of every receipt in the program is
currently a set of unversioned local files.

### GAP-4 — the CI admission plane is one job deep (CONFIRMED)

`.github/workflows/quality.yml` (98,826 B, 1,427 lines) has **7** jobs — `lint`, `types`,
`test-node`, `test-python`, `sast`, `secrets`, `deps` — a top-level `permissions:` block, and
**exactly 1 of 7** jobs narrows its own permissions (`secrets`, L1331). Absent entirely:

```
bandit · trivy · codeql · syft · cosign · sigstore · sbom
actionlint · zizmor · checkov · pip-audit · npm audit
```
(`_secfirst_measure2.out.json:ci_permissions`, `ci_absent_scanners`.) `pull_request_target` count is
**0**, which is correct and worth crediting.

*Detector disagreement, disclosed:* my first pass counted 10 jobs with a bare
`^  name:$` regex; pass 2, scoped to inside `jobs:`, counted 7. **Pass 2 is the better detector**
(pass 1 matched top-level YAML keys such as `on:`/`env:` siblings). I report 7.

---

## 3. DESIGN

**Thesis.** *The receipt is the security boundary, and a boundary is only a boundary if crossing it
requires a capability you were granted and produces evidence you could not have written alone.*

Wave 1 made the receipt **honest-by-schema**. Security-first makes it **authorized-by-policy** and
**witnessed-by-a-second-process**. Three planes, each fail-closed, each riding a file that already
exists.

### Plane A — Authorization (pre-execution, catalog-scoped)

Lift `DSL-SEM-011`'s proven pattern from the DSL plane onto the work-unit plane. This is a *port*,
not an invention: same deny-by-default semantics, same `tool_token` grammar, same `violation`
severity, same fail-closed-on-absent-policy default that the four-state probe just confirmed.

**New:** `platform/policy/unit-tool-policy.json` — the allowlist, **derived from the corpus** so day
one is not a wall of false positives. The token space is small enough to enumerate exhaustively:
**85 distinct tokens** across all 2,007 units, of which **78 are non-ambient**. Measured partition:

- `allow` — the ambient read/analysis set (`Read`, `Grep`, `Glob`, `Write`, `Edit`, `Bash`,
  `PowerShell`). **1,435 of 2,007 units (71.5%) declare only-ambient tokens**, so a correctly-derived
  allowlist leaves 71.5% of the corpus untouched on day one. (The top-8 *sets* cover 1,012 units =
  50.4%; the 71.5% figure is the one that matters, because it counts units whose entire declared set
  is ambient regardless of which permutation they used.)
- `require_owner_approval` — tokens implying spend, egress, or credential access. **261 units (13.0%)
  hold at least one `mcp__` token.** From the measured space: `mcp__cloud-hub__modal_sandbox_*`,
  `mcp__cloud-hub__compute_*`, `mcp__cloud-hub__dbx_secret_*`, `mcp__cloud-hub__*_account_*`,
  `mcp__github__merge_pull_request`, `mcp__github__push_files`, plus every wildcard family form —
  **120 units carry a wildcard token**.
- `deny` — tokens no unit in this program may hold under any policy.

**A measured limitation of the existing grammar, and Plane A must not paper over it.** The
`tool_token` pattern ends `(?:\s*\([^)]*\))?$`, i.e. a parenthesised scope whose contents are
*unconstrained*. The corpus exploits this with **English prose scopes** that no machine can enforce.
Real tokens on disk:

```
Bash(git read-only: ls-tree/cat-file/show/log/diff/worktree list; NO add/commit/push/reset)
Bash(python analysis only; no network, no git write)
Bash(gh read-only: gh api GET, gh search, gh release list; NO write subcommands)
Bash(torsocks curl, sandboxed + egress-logged)
PowerShell(read-only: Get-ChildItem/Get-Content/Get-Command/Get-FileHash)
```

These are *intentions*, not *permissions*. `SEM-008` can check that `Bash(...)` is an allowed
**family**; it cannot enforce "NO add/commit/push". So Plane A's honest scope is
**family-level authorization**, and the sub-command restriction stays advisory prose until someone
writes an argv-level interceptor — which this candidate does **not** propose.

The partition of all 78 non-ambient tokens, measured (one token is counted in two rows, so the
column sums to 79 for 78 distinct values — `mcp__search-hub__* (read-only retrieval)` is both
`mcp__` and paren-scoped):

| convention | n | machine-checkable? |
|---|---|---|
| `mcp__server__method` | 48 | **yes** — exact or family match |
| paren-scoped `Tool(...)` | 16 | **mixed**: 6 are single-command (`Bash(curl)`, `Bash(pytest)`, `Bash(osv-scanner)`, `Bash(netstat)`, `Bash(python)`) or a real path glob (`Write(command-center/research/**)`) → checkable; **10 are prose** → not |
| colon form `Bash:x` | 10 | **yes** — `Bash:codex`, `Bash:gh-readonly`, `Bash:git-readonly`, `Bash:gitleaks`, `Bash:pwsh`, `Bash:pwsh-readonly`, `Bash:pytest`, `Bash:python`, `Bash:semgrep`, `Bash:uv` |
| plain native | 5 | **yes** — `AskUserQuestion`, `Monitor`, `Task`, `WebFetch`, `WebSearch` |

So **68 of 78 non-ambient tokens are already machine-checkable** and exactly **10 are prose**. That
is a far better starting position than the grammar's permissiveness suggested, and it makes the
migration concrete rather than open-ended: rewrite 10 token strings into the colon form the corpus
*already* uses elsewhere (`Bash(git read-only: …)` → `Bash:git-readonly`, which literally already
exists as a token). This supersedes the "unmeasured size" hedge I would otherwise have left here.

Two tokens in the plain-native row deserve naming as authorization concerns in their own right:
**`Task`** is subagent spawning — a unit holding it can create a child whose permissions this policy
never reviewed, which is the one genuine privilege-escalation path in the token space — and
**`WebFetch`/`WebSearch`** are egress. `Task` therefore belongs in `require_owner_approval`, not
`allow`, and §6.3's egress limitation applies to `WebFetch` exactly as it does to `Bash`.

**New:** `platform/schema/unit-tool-policy.schema.json` — draft-2020-12, so the policy file is
itself schema-checked by the existing `wfdsl` harness rather than by new bespoke code.

**New:** `platform/lib/unit_authz.py` + **3 rules appended to `wfdsl/semantics.py:check_work_units`**,
continuing the existing numbering (`SEM-001..007` → `SEM-008..010`):

- **SEM-008** — every token in a unit's `tool_permissions` is permitted by
  `unit-tool-policy.json`, deny by default. *Exact port of `check_tools` at `semantics.py:485-499`.*
- **SEM-009** — **capability/approval coherence.** If any declared token falls in
  `require_owner_approval`, the unit's `owner_approval_required` must be `true`. This is the rule
  that turns the 144 `true` declarations from decoration into a constraint, and it is
  bidirectional: a unit holding a spend token with `owner_approval_required: false` is the violation.
- **SEM-010** — **substrate/capability coherence.** A unit whose `execution_substrate` is
  `cloud-batch` (202 units) may not hold a local filesystem-mutating token, and a unit whose
  substrate is `local-*` may not hold a cloud-provisioning token. Cross-plane confusion is the
  cheapest real escalation path in a 2,007-unit fan-out.

**Enforcement point.** `SEM-008..010` run wherever `check_work_units` already runs — i.e. inside
the existing 214-test suite via `platform/lib/wfdsl/test_catalog_conformance.py`, and in
`quality.yml`'s `test-python` job. **No new runtime, no new dispatcher, no second control plane.**

### Plane B — Attestation (post-execution) — *witness-based, NOT signature-based*

This plane was redesigned in response to my own §8 refutation, and I am flagging that inline rather
than presenting the survivor as if it were the first draft. **Signature-based attestation is
REJECTED by this document** (see §8, "the killing argument"): an HMAC over a receipt, keyed by a
secret the producing agent can read, authenticates nothing an agent could not already forge, and it
would violate §9 by putting a credential on the receipt path.

What survives is the mechanism the estate's own rules already prescribe — *mechanically independent*
corroboration, not cryptography.

**Additive `$def` in `receipt.schema.json`** (optional, so all existing receipts stay valid):

```
$defs/attestation
  required: [source_ref, generated_by, built_at, witness]
  source_ref   : the git rev the unit executed against   (MECH-11 — ref-pinning)
  generated_by : the producing tool/script path          (MECH-38 — provenance stamp)
  built_at     : iso_timestamp (reuses $defs/iso_timestamp)
  witness      : { witness_id, vendor, method, artifact_sha256, verdict, raw_output_fingerprint }
```

**New:** `platform/lib/witness_join.py`. It does exactly one thing, deterministically and with no
model in the loop: given a unit's receipt and a witness receipt, it asserts

1. `witness.artifact_sha256` equals the sha256 the gate **recomputes from disk** — not the sha the
   receipt claims. The join is anchored to bytes, not to assertions.
2. `witness.vendor != produced_by.vendor` — the check condition 9 already wants, now performed
   against a *separately-produced file* rather than two fields of one file.
3. `witness.raw_output_fingerprint != probe.fingerprint` for the corresponding probe — a witness
   that re-ran the *same* probe is rejected. This is `single-signal-verification.md` §2 made
   executable, and it is the part a signature could never give you.

**Two new `PredicateOptions` flags** (`require_witnessed_review`, `require_pinned_source_ref`),
default **off**. Turned on only for the 132 security-bearing units (measured by keyword over
id/title/description) and the 144 `owner_approval_required: true` units. **Condition 9 is not
modified and no thirteenth condition is added** — the predicate's 12-condition contract and its
`completion-predicate-result.schema.json` stay byte-stable.

Cost note stated up front: a witness costs a second process per gated unit. At 132 + 144 units
(union, so ≤276 of 2,007 = **≤13.8%**) that is bounded, and `MECH-30`'s eight
`cross-vendor-dispatch.md` rules apply in full — blocking dispatch, prompt-by-file,
`--ignore-user-config`, never `sonnet`, always a terminal state.

### Plane C — Admission (pre-merge)

Release mode is **PR-ONLY** (binding owner decision), so the PR gate is the *only* place a
program-wide invariant can be enforced without a daemon. Concretely, in
`.github/workflows/quality.yml`:

1. **Per-job least privilege.** Add `permissions:` to the 6 jobs that lack it. Today 1 of 7 narrows
   its own; a top-level block is a ceiling, not a grant per job.
2. **Add the absent scanners that fit this repo's languages**: `bandit` (Python SAST — the repo is
   overwhelmingly Python and `bandit` is named in the project's own routing guidance yet appears 0
   times in the gate), `pip-audit`, `actionlint` + `zizmor` (the gate is 1,427 lines of YAML with
   zero workflow-linting), and `trivy` for filesystem/secret scanning as a second signal to
   `gitleaks`. `codeql`/`sbom`/`cosign` are **deliberately not proposed** — see §4 cost.
3. **A tracked-substrate invariant.** A new `no-untracked-substrate` step asserting
   `git ls-files command-center/schema/ | wc -l` equals the on-disk count. Today that is `0 == 233`
   → **RED**, which is the correct first result and is the both-states proof that the check works.
4. **`SEM-008..010` as a required context**, gated on merge like the existing `sast`/`secrets` jobs.

### Control-plane count (the tournament's singularity test)

| plane | file that IS the plane | new runtime? |
|---|---|---|
| authorization | `platform/policy/unit-tool-policy.json` | no — runs inside `wfdsl.check_work_units` |
| attestation | `platform/schema/receipt.schema.json` `$defs/attestation` | no — runs inside `completion_predicate` |
| admission | `.github/workflows/quality.yml` | no — GitHub Actions, already the release gate |

Three planes, three files, **zero** new runtimes. Anchor compliance (`13-ARCHITECTURE-CANDIDATES.md`
§1): rides the existing bus; introduces no second orchestration runtime, no vector-DB/KG memory, no
durable-execution engine, no trained critic, no observability SaaS, no guardrail framework. The
witness is a `codex mcp-server` call on the rail that is already mounted. **PASS.**

### MECH composition

**Adopted and already partly present:** MECH-03 (typed silence — present in the predicate, extended
to `SEM-008..010`) · MECH-04 (fail-open dependency receipts — already shipped in
`security_report.scanners[].installed`) · MECH-06 (content-addressed manifest — `artifact.sha256`
recomputed from disk; Plane C item 3 extends it to the substrate tree) · MECH-24 (detector-self-test
— already shipped as `negative_control.{fired_on_bad_state,silent_on_good_state}`).

**Adopted and genuinely new here:** MECH-11 (ref-pinning → `attestation.source_ref`) · MECH-30
(cross-vendor verification → `witness`) · MECH-38 (provenance stamp → `attestation.generated_by`) ·
MECH-27 (marketplace/admission governance → Plane C).

**Explicitly NOT adopted, with reasons:** MECH-32 (junction-aware traversal) and MECH-07
(`install.py` merge-not-replace) target the *live harness deploy* plane, which this repo does not
own — they belong to whichever candidate takes the deployment axis (A11). MECH-29 (role→model-tier
routing) contradicts a standing owner preference and is an owner call, not an architecture choice.

### Hazard coverage vs `13-ARCHITECTURE-CANDIDATES.md` §0.3

● fixes · ◐ partial · ○ no effect

| hazard | this candidate | why |
|---|---|---|
| H-h untyped silence | ◐ | inherits the predicate's `NOT-CHECKED`; adds it to `SEM-008..010`. Does not touch the live hook aggregator — that is A10's axis and A10 does it better |
| H-i catalogue tax / untrusted hook surface | ● | Plane C item 4 + `C-H56-security-untrusted-repo-admission` becomes enforceable |
| H-b `install.py` hooks-key wipe | ○ | different repo plane; A11/A2 own it |
| H-e `-Report json` writes | ○ | same |
| H-f ~470 unversioned security lines | ● *by analogy* | Plane C item 3 is the identical defect class (233 unversioned files) in *this* repo, and closes it here |
| H-g INV-3 junction fail-open | ○ | live-tree hazard, not a repo-plane hazard |
| **new: unenforced capability grants** | ● | Plane A. Not in doc 13's hazard table because doc 13 has no security-first candidate to surface it |
| **new: self-attested trust root** | ● | Plane B |

---

## 4. COST AND COMPLEXITY ANALYSIS

### Build cost

| item | size | basis for the estimate |
|---|---|---|
| `unit-tool-policy.json` + schema | **XS** | derived mechanically from the 151 measured sets; a script, not a design |
| `SEM-008` | **XS** | line-for-line port of `semantics.py:485-499`, a 15-line function |
| `SEM-009`, `SEM-010` | **S** | new cross-field logic, ~40 lines each, both pure functions over a unit dict |
| `unit_authz.py` + tests | **S** | must include a both-states fixture per rule (3 fire cases + 3 silent cases) |
| `$defs/attestation` | **XS** | additive, optional; reuses `iso_timestamp` and `sha256` |
| `witness_join.py` + tests | **M** | the only genuinely new logic; the fingerprint-inequality check is the subtle part |
| 2 `PredicateOptions` flags | **XS** | the options plumbing already exists for `require_cross_vendor_review` |
| `quality.yml` per-job permissions | **XS** | 6 blocks of 2-4 lines |
| 5 new scanners in CI | **S** | each is a pinned action or `uvx` invocation; `zizmor` will have findings on a 1,427-line workflow |
| `no-untracked-substrate` step | **XS** | 3 lines; RED on first run by design |

Total: one **S/M** work unit. Nothing here is BUILD-LARGE, because nothing here is new
infrastructure — it is policy over infrastructure that exists.

### Recurring cost, honestly

1. **Policy maintenance is permanent.** An allowlist derived from 151 sets today needs an amendment
   every time a legitimately new tool appears. That is a real tax on velocity and it never ends. The
   mitigation is that the *derivation* is scripted, so an amendment is a re-run plus a diff review,
   not an audit.
2. **The witness roughly doubles wall-time on gated units.** Bounded to ≤276 of 2,007 (≤13.8%), but
   on those it is a second full agent turn, plus `cross-vendor-dispatch.md`'s mandatory 30-minute
   timeout and `longrun` wrapper. If the whole program were gated this way the cost would be
   unacceptable; the scoping is what makes it affordable, and the scoping is a judgement that could
   be wrong in either direction.
3. **CI minutes.** `bandit` + `pip-audit` + `actionlint` + `zizmor` + `trivy` on top of a
   1,427-line workflow. `codeql` is **excluded specifically on this axis** — it is the single most
   expensive scanner available and it duplicates `opengrep`/`semgrep` coverage on a
   Python-dominant repo. `sbom`/`cosign`/`sigstore` are excluded because a PR-only, single-owner,
   non-distributed repo has no downstream consumer to verify a signature; adding them would be
   ceremony. Naming what I am *not* buying is part of the cost analysis.
4. **False-positive tax at switch-on.** 151 distinct permission sets against a fresh allowlist will
   produce violations. Mitigated by SHADOW-first (§6 M2), not by hoping.

### Complexity delta

Cyclomatic: three pure functions and one join. No new state, no new process supervision, no new
network listener, no new credential. The witness rides an already-mounted MCP.
**The honest complexity cost is not code — it is one more thing that can say NO,** and every
blocking gate on a 2,007-unit program is a potential program-wide stall. That is the real price.

---

## 5. FAILURE-MODE ANALYSIS

| # | failure | trigger | blast radius | detection | mitigation |
|---|---|---|---|---|---|
| F1 | **Allowlist too tight → mass false positives** | switch-on with a policy derived from a subset of the corpus | all 2,007 units fail `SEM-008`; program stalls | the switch-on run itself; violation count >> 0 | SHADOW mode first (log, never fail); derive from the **union** of all 151 sets; ratchet only after a clean shadow run |
| F2 | **Allowlist too loose → gate certifies everything** | `allow` becomes the union of every token ever seen, including spend tokens | worse than no gate: manufactures false confidence | **both-states test is mandatory** — a fixture unit holding `mcp__cloud-hub__modal_sandbox_exec` with `owner_approval_required: false` must FAIL; if it passes, the policy is void | the fixture is a test, so it cannot rot silently |
| F3 | **`SEM-009` inverted** — reads `owner_approval_required` as *permission granted* rather than *approval required* | a subtle boolean-polarity bug | 144 units silently exempted | polarity fixture in both directions | two tests per rule, asserting the *opposite* direction fires |
| F4 | **Witness is the same process wearing a different name** | agent writes a witness receipt itself | Plane B becomes theatre — exactly GAP-2 relocated | `witness_join` requires `raw_output_fingerprint != probe.fingerprint` **and** `artifact_sha256` matching a gate-recomputed hash | this is why the join is byte-anchored; a self-witness must produce a *different* probe fingerprint, which requires actually re-probing |
| F5 | **Witness join fails open on a missing witness** | `attestation` absent, flag on | a gated unit passes unwitnessed | must return `NOT-CHECKED`, never `SATISFIED` — the pattern `_c9_reviewer:897` already uses | reuse `Outcome.NOT_CHECKED`; test the absent-field direction explicitly (this is precisely the hole `single-signal-verification.md` documents in `claim_gate.py`, where a missing `source_probe` normalised to empty and trivially "differed") |
| F6 | **`source_ref` pinned to a stale rev** | unit executes at `9f2dac7a`, stamps an older ref | verdicts survive their evidence — the measured class where **5 of 12** re-checked verdicts flipped | compare `attestation.source_ref` to `git rev-parse HEAD` at gate time | MECH-11's own check; a mismatch is `NOT-CHECKED`, not a failure, because a legitimate re-run at an older ref exists |
| F7 | **Per-job `permissions:` too narrow → CI red for the wrong reason** | a job needs `contents: read` it no longer has | all PRs blocked | first PR after the change | land the 6 permission blocks in **one** PR, alone, so a red is unambiguous |
| F8 | **`no-untracked-substrate` gets "fixed" by ignoring the tree** | someone adds `command-center/schema/` to `.gitignore` to make the red go away | GAP-3 becomes permanent and invisible | assert **`.gitignore` does not mention the path** as part of the same check | the check must fail on the workaround, not just on the symptom |
| F9 | **Policy file itself is unversioned or unvalidated** | the fate of the 233 shims | the security plane is the least-protected file in the repo | `unit-tool-policy.schema.json` validates it; Plane C item 3 covers tracking | the plane must be subject to its own admission gate |
| F10 | **Scanner added but not installed → silent skip** | `bandit` step with `continue-on-error` | a green gate that scanned nothing | `security_report.scanners[].installed` **already** models this correctly | reuse the existing shape; never `continue-on-error` on a security step |

F2, F4 and F5 are the three that would make this architecture *worse than nothing*, because each
converts an absent control into a false green — the estate's documented dominant failure class. All
three are answered by the same discipline: **every rule ships a fixture that must fire, and the
fixture is a test.**

---

## 6. SECURITY REVIEW (of this architecture, adversarially)

**Assets.** (1) The owner's credentials reachable from any agent process — `HF_TOKEN`,
`OPENAI_API_KEY`, `GH_TOKEN`, Databricks PATs, and the Chrome/Edge `User Data` stores. (2) Cloud
spend on `cloud-hub` (Modal / RunPod / Databricks / OVH). (3) Repo write and merge authority.
(4) The integrity of the 2,007 receipts, which is what the owner will make decisions from.

**Trust boundaries this design draws.** Unit declaration → policy (Plane A). Execution → receipt
(Plane B). Repo → main (Plane C).

**Threat model, and where it is honest about itself.** The credible adversary here is **not** a
human attacker. It is (a) a *confabulating agent* that asserts what it did not do, (b) a
*prompt-injected* agent that read hostile content from a fetched page, an MCP result, or a cloned
repo (§9, CVE-2026-47751-class), and (c) *mechanical error at 2,007-unit scale*. Plane A is aimed at
(b) and (c) — an injected agent that tries to reach `dbx_secret_get` is stopped by a policy it
cannot edit from inside its own turn, because the policy lives in a file its `tool_permissions` does
not grant it. Plane B is aimed at (a). **Plane B is largely useless against (b)**, because an
injected agent can fabricate a witness stanza as easily as a reviewer stanza — which is precisely
why the join is anchored to a gate-recomputed sha256 and a probe-fingerprint inequality rather than
to any field the agent controls.

**§9 compliance, explicitly.** This architecture **introduces no credential**. That is a deliberate
constraint and it is the reason signature-based attestation was rejected: a signing key on the
receipt path would be a new secret, on disk, readable by the process it is meant to authenticate,
and rotating it would be an owner-only action per §9. `witness_join.py` needs no key. The
`security_report.findings[].credential_redacted: {"const": true}` shape already in the schema is
the right primitive and this design leans on it rather than adding a second redaction path.

**Where this design is weak, stated plainly.**
1. **Policy-file integrity is the whole ballgame.** Anything that can write
   `platform/policy/unit-tool-policy.json` owns the authorization plane. In a repo where 369 files
   are currently untracked, that is not a hypothetical. Mitigation: F9 + Plane C item 3; residual
   risk remains until the substrate tree is tracked.
2. **`tool_token` wildcards and prose scopes.** The grammar admits `mcp__<server>__*`; **120 units
   carry a wildcard token**, so a single grant can silently include a future dangerous method.
   Mitigation: wildcard families go in `require_owner_approval`, never in `allow`. Separately,
   **10 of the 78 non-ambient tokens encode their restriction as English prose** (§3 Plane A), so
   for those 10 the gate authorizes a *family* while the *stated* restriction remains unenforced.
   That is a real residual and it is why Plane A claims family-level authorization only.
   **UNVERIFIED** whether rewriting those 10 into the colon form breaks any unit's intent; the
   settling experiment is the rewrite plus a `check_work_units` re-run, which I did not perform.
3. **Egress is not modelled at all.** `tool_permissions` gates *which tool*, never *which host*. An
   allowed `Bash` can `curl` anywhere, and 5 units hold `WebFetch`/`WebSearch` families outright.
   This architecture does **not** close exfiltration, and a candidate that claimed to would be
   lying. Windows has no native OS-level process sandbox; the sandbox ladder (WSL2 / docker /
   `modal_sandbox`) is the real answer and it belongs to the distributed-runtime candidate, not to
   this one.
3b. **`Task` is an escalation path this policy cannot close by itself — and it is live today.**
   A unit holding `Task` spawns a child whose `tool_permissions` are set by the *prompt*, not by the
   catalog, so Plane A governs the parent and not the child. **Measured: 25 units hold `Task` and
   only 2 declare `owner_approval_required: true` — 23 units can spawn unreviewed children with no
   approval gate.** Putting `Task` in `require_owner_approval` is a mitigation, not a fix; the fix is
   propagating the parent's policy into the spawn, which requires an orchestrator change outside this
   candidate's scope. Comparable exposure on the egress axis: **122 units hold `WebFetch`/`WebSearch`
   without approval**, which §6.3 concedes this architecture does not close.
4. **`execution_substrate: cloud-batch` (202 units) is a trust extension** to a shared, in some cases
   production, environment. `SEM-010` reduces confusion but does not isolate.
5. **The witness rides `codex mcp-server`.** That is a second vendor's process with the same
   filesystem access as the first. Cross-vendor independence buys **uncorrelated blind spots**, not
   *containment*. Saying otherwise would be an overclaim.

**What this design fixes that nothing else in the tournament does.** 144 units that declare they
need owner approval and get none; 151 unconstrained capability sets; a reviewer field that costs
nothing to assert. No other candidate in `13-ARCHITECTURE-CANDIDATES.md` touches the
authorization axis at all — measured: `work_unit_authz_rules == []`.

---

## 7. MIGRATION DESIGN FROM TODAY'S STATE

Today = `9f2dac7a`, working tree carrying 369 untracked files including all 233 substrate shims and
a modified `platform/schema/SUBSTRATE-RESOLUTION-STATUS.json`. Five stages, each independently
revertible, each with a stated first-result expectation. **The first result of M0 and M1 is RED, and
a green there would mean the check is broken.**

**M0 — Track the substrate (prerequisite, blocks everything else).**
Commit `command-center/schema/**` (233 files) and the `platform/` work. Add the
`no-untracked-substrate` step. Expected first result: **RED at `0 == 233`**, going green on the
commit. *Rationale: this mirrors A11's migration rule — you cannot build an integrity plane on top
of a tree that is not in git. Doing Plane A before M0 would put the policy file itself in the
untracked set (F9).* Not my commit to make: the orchestrator commits.

**M1 — Derive the policy, land it in SHADOW.**
Script the union of the 151 `tool_permissions` sets; partition into
`allow` / `require_owner_approval` / `deny`; land `unit-tool-policy.json` + its schema. Add
`SEM-008..010` with severity **`advisory`**, not `violation`. Run over all 2,007 units and publish
the violation census. Expected first result: **a non-zero count**, and if it is zero the allowlist
is too loose (F2) and must be tightened until a known-bad fixture fails.

**M2 — Ratchet SHADOW → violation, per rule, in three PRs.**
`SEM-008` first (pure port, lowest risk), then `SEM-009` (the 144-unit approval coherence), then
`SEM-010` (substrate coherence). One rule per PR so a red is attributable. Each PR carries its
both-states fixtures. Any unit that legitimately needs a `require_owner_approval` token gets its
`owner_approval_required` flipped to `true` in the catalog — that is a **catalog data fix**, and it
is the point of the exercise, not a workaround.

**M3 — `$defs/attestation` + `witness_join.py`, flags default OFF.**
Additive schema change; all 2,007 existing receipt shapes stay valid (the `$def` adds no `required`
to `receipt_core`). Verify by re-running the substrate sibling's `_probe_substrate_receipts.py`,
whose 4 positive / 4 negative receipts must return exactly the same verdicts. **This is the
byte-stability control**: if any existing receipt changes verdict, M3 is wrong.

**M4 — Turn the flags on for the gated subset.**
Enumerate the union of the 132 security-bearing units and the 144 `owner_approval_required: true`
units (≤276). Enable `require_witnessed_review` + `require_pinned_source_ref` for that set only.
Expected first result: **every one of them `NOT-CHECKED`**, because no witness receipts exist yet.
`NOT-CHECKED` is the correct state — it is the whole point of MECH-03 — and it must not be read as
a pass or as a failure.

**M5 — CI hardening, two PRs.**
PR-1: the 6 per-job `permissions:` blocks, alone, nothing else (F7). PR-2: `bandit`, `pip-audit`,
`actionlint`, `zizmor`, `trivy`. Expect `zizmor` findings on a 1,427-line workflow; triage, do not
suppress.

**Rollback.** M1/M2: set severity back to `advisory` or delete the policy file (rules fail closed on
a *missing token*, but a *missing policy file* must be a hard error, not a silent allow — an
explicit design decision, and the inverse of `DSL-SEM-011`'s convenient default, because a
catalog-wide silent allow is worse than a loud stop). M3: the `$def` is additive; old consumers
ignore it. M4: flip two booleans. M5: revert the workflow.

**Stopping condition 13 ("release/canary succeeds") is UNSATISFIABLE as literally written** under
the binding PR-ONLY decision. Treated here as: **a merged PR plus a local rollback rehearsal** — for
this candidate, that rehearsal is M2-revert (set `SEM-008` back to `advisory`, re-run
`check_work_units`, confirm the 2,007-unit census returns to its pre-M2 value). I am saying so
explicitly rather than claiming a canary.

---

## 8. TEST DESIGN

Baseline: **214 named test functions** across the 8 **Wave 1** test files under `platform/lib/`
(`test_completion_predicate` 42, `councilspec/test_councilspec` 48, `test_receipt_schema_gate` 30,
`wfdsl/test_schemas_and_examples` 27, `council_protocols/test_protocols_25_36` 23,
`test_schema_resolver` 20, `wfdsl/test_expr` 13, `wfdsl/test_catalog_conformance` 11). Static count
via `re.findall(r'^\s*def test_')`, independent of pytest. The substrate sibling reports **475
passed**; parametrization accounts for the difference and the two numbers are **not** in conflict.

*Concurrency disclosure, because it bit this unit.* The tree is **moving while this document is
being written**. A parallel unit is adding `platform/lib/workflows/test_*.py`; my first count read
214 across 8 files, a re-run 20 minutes later read **457 across 23 files** — 15 new files whose
`st_mtime_ns` values (`1786323348…`-`1786324057…`) all postdate my first measurement
(`1786319616…`). So **457 is not a Wave 1 number and 214 is not a current-tree number**; each is
correct for its scope. The baseline this candidate's tests add to is the 8-file, 214-function Wave 1
set. Three of the sibling's new files — `test_secret_exposure_blast_radius_trace.py`,
`test_security_review_scanner_fix_loop.py`, `test_scanner_detector_integrity_probe.py` — are
**security-adjacent to Plane C** and the orchestrator should reconcile them against §3 rather than
assume this document accounts for them; it does not.

**T1 — `SEM-008..010`, both states per rule (6 fixtures minimum).** For each rule, one unit that
MUST fire and one that MUST be silent. `SEM-008` fire fixture: a unit declaring
`mcp__cloud-hub__modal_sandbox_exec` against a policy that does not allow it — the *exact* token
`wfdsl/mutations.py:91-93` already uses for the DSL plane, so the two planes share a known-bad
value. `SEM-009` fire fixture: a spend token with `owner_approval_required: false`. `SEM-010` fire
fixture: `cloud-batch` substrate holding `Edit`.

**T2 — Policy-void detection (the F2 killer).** A test that loads the *real*
`unit-tool-policy.json` and asserts a hardcoded known-bad token set is rejected by it. This test
fails if anyone ever loosens the policy to make CI green. Without T2 the entire plane can be
neutralised by a one-line edit.

**T3 — Missing-policy is a hard error.** Point `unit_authz` at a non-existent policy path and require
a raised error, **not** an empty allowlist and **not** a silent pass. This is the direction the
`claim_gate.py` hole documented in `single-signal-verification.md` §6 got wrong (an absent
`source_probe` normalised to empty and therefore trivially "differed"), so it is tested first-class.

**T4 — Witness join, four states.** (i) valid witness → SATISFIED. (ii) same-vendor witness →
UNSATISFIED. (iii) witness whose `raw_output_fingerprint` equals the original probe's → UNSATISFIED
*with the reason naming re-run, not merely "invalid"*. (iv) absent `attestation` with the flag on →
**NOT-CHECKED**, never SATISFIED.

**T5 — sha256 anchoring.** A witness whose `artifact_sha256` matches the receipt's *claimed* hash
but not the gate's *recomputed* hash must be rejected. This is the test that distinguishes a
byte-anchored join from a field-comparison one, and it is the reason Plane B is not theatre.

**T6 — Backward compatibility (byte-stability control).** Re-run the substrate sibling's
`_probe_substrate_receipts.py` and `_probe_substrate_selfaudit.py` after the `$defs/attestation`
addition; require identical output — `all_positives_accepted=True`,
`all_negatives_rejected=True`, `all_gate_a_12_of_12=True`.

**T7 — Mutation battery, extended.** Wave 1 killed 12/12 predicate mutations with an independent
control. Add 3: (i) invert `SEM-009`'s polarity, (ii) change `witness_join`'s vendor comparison from
`!=` to `==`, (iii) make the fingerprint check compare lengths instead of values. All three must be
killed. **Expected result is 3/3, and I will treat a surviving mutant as the finding rather than
patching the test to hide it** — `single-signal-verification.md` records that 1 of 6 mutations
surviving *was* the useful result.

**T8 — Detector control for T1-T7 (meta).** Run the new gates against the *unmodified* corpus and
require the violation count to be reproducible across two runs, and against a deliberately-corrupted
policy and require a different count. A gate that returns the same number in both states measures
nothing.

**T9 — CI both-states.** `no-untracked-substrate` must be RED at `0 == 233` before M0 and GREEN
after. Capturing the RED is mandatory; a check only ever observed green has not been shown to work.

**T10 — Prose-scope classifier.** A test that partitions the corpus token space and asserts exactly
**10 prose-scoped tokens** remain, failing when the count rises. Without it, the next authored unit
reintroduces `Bash(python analysis only; no network)` and the family-level-only limitation silently
widens. This test *ratchets down*: it should be edited only to lower the number.

**T11 — `Task` containment.** Assert that no unit holds `Task` while `owner_approval_required` is not
`true`, once `Task` is in `require_owner_approval`. This is `SEM-009` applied to the one measured
escalation path (§6.3b). **It fires today on 23 units**: 25 units hold `Task` and only 2 of them
declare `owner_approval_required: true` (sample: `TST-0257`…`TST-0276`). That is the fixture and the
finding in one — no synthetic input needed.

**What I did NOT test, and would need to.** I have not run the full 475-case suite in this unit
(the sibling's 111 s run is the last measurement; I did not re-run it), so **NOT-CHECKED** on
whether the suite is green at `9f2dac7a` as opposed to at the sibling's tree state. I have not
enumerated wildcard `tool_token` usage across the 151 sets, so the §6.2 narrowability claim stays
**UNVERIFIED**. And my enforcement classifier's asymmetry (§2 GAP-1) means the four "no runtime
reader" rows are PARTIAL; an `ast`-based call-graph pass would settle them.

---

## 9. THE STRONGEST ADVERSARIAL REFUTATION OF THIS ARCHITECTURE

I owe the tournament the argument that would kill this design. There are three, in ascending order
of force. The third one lands.

### R1 — "You are optimising for 6.6% of the program." *(Rejected.)*

132 of 2,007 units are security-bearing by keyword — 6.6%. Building the program's architecture
around them is the tail wagging the dog; A6's 9,255-agent workflow corpus and A7's dark council
deliver capability, while this delivers paperwork.

**Why it fails.** It confuses the *subject* of security-bearing units with the *scope* of the
authorization plane. Plane A governs **2007/2007** units, because all 2,007 declare
`tool_permissions` and all 2,007 currently have it unenforced. The 6.6% figure applies only to
Plane B's witness scope, which is bounded *on purpose* for cost. R1 measures the wrong denominator.

### R2 — "A blocking gate is the wrong instrument on this estate." *(Partly lands; the design already answers it.)*

The estate's documented dominant failure is the **false green**, not the false red. Adding a gate
that can halt a 2,007-unit program trades a known failure mode for a worse one: 151 distinct
permission sets against a fresh allowlist means day-one mass rejection, and the pressure will be to
loosen the policy until CI is green — at which point the plane certifies everything (F2) and the
program is *worse off than before*, because it now has documented, false assurance.

**Why it partly lands.** This is a real and likely dynamic; I rate it *likely* (55-80%) that a
naive switch-on produces exactly that pressure. It is why M1 lands in SHADOW, why M2 ratchets one
rule per PR, and above all why **T2 exists** — a test that fails if the policy is ever loosened past
a hardcoded known-bad set. R2 is a reason to sequence carefully, not a reason the architecture is
wrong. But it correctly identifies the failure mode that would kill it in practice, and if T2 were
ever deleted the refutation would become decisive.

### R3 — THE KILLING ARGUMENT: "Attestation cannot fix a self-attested system, because the attester is the subject." *(This one lands, and it forced a redesign.)*

Here is the argument in full, made as strongly as I can make it against myself.

Plane B's entire premise is that GAP-2 — an agent can write `reviewer.vendor: "openai"` without any
Codex process existing — is a *security* defect fixable by a *security* mechanism. **It is not.** It
is an honesty defect, and honesty defects are not fixable by attestation, because **every
attestation mechanism available inside a single-owner, single-filesystem, agent-driven system is
produced by the same class of process it is meant to authenticate.**

Walk the options. A **signature** requires a key; the key must live where the producing agent can
read it, or the agent cannot sign; therefore the signature proves only that *something with the key*
signed, which is exactly what `produced_by.vendor` already claims — and it adds a credential to the
receipt path in violation of §9. A **second-party counter-signature** requires an independent
identity; there is no identity provider on this box, and a `witness_id` string is as forgeable as
the `reviewer_id` string it replaces. A **cross-vendor witness** requires that a Codex process
really ran; nothing in a receipt can prove a process ran, because the receipt is written by whoever
claims it ran. Even my byte-anchored sha256 join is only as good as the *gate* being an independent
reader — and the gate runs on the same machine, invoked by the same orchestrator, with the same
filesystem.

**So the honest conclusion: Plane B, in its naive signature form, is security theatre and I have
rejected it in §3 on exactly this basis.** An advocate who shipped `$defs/signature` here would be
adding ceremony that raises confidence without raising assurance — the worst outcome available,
because false assurance is the estate's own documented dominant failure class. The refutation is
**TRUE as stated against signature-based attestation.**

**Does it kill the architecture? No — but it does not merely wound it either, and I will not
pretend it costs nothing.** Three things survive R3, and one thing dies.

*What dies.* Any claim that this architecture makes receipts *unforgeable*, *tamper-proof*, or
*attested* in the cryptographic sense. I make none. `$defs/attestation` is a **provenance record**
(MECH-38) and a **corroboration record** (MECH-30), not a proof of authorship. If the tournament
judge reads Plane B as cryptographic assurance, the judge has read it wrong and I would rather lose
the tournament than let that reading stand.

*What survives, first:* **Plane A does not depend on attestation at all.** A tool token is either in
the policy file or it is not. That is a set-membership test over data the agent did not author,
evaluated by code the agent did not write, and it is *exactly* the kind of question
`fan-out-contract` §C4 says must be answered by an algorithm rather than by judgement. R3 has no
purchase on Plane A. 144 units asking for approval that nothing enforces is a real defect with a
real, mechanical fix, and it stays fixed.

*What survives, second:* the witness is worth building **not as proof but as cost**. R3 is right
that a witness stanza is forgeable. It is wrong that forging it is free. `witness_join` demands a
probe fingerprint that *differs* from the original and an artifact hash that matches a
*gate-recomputed* value; to fabricate that pair an agent must actually re-read the artifact and
produce genuinely different raw output. That is not a proof, it is a **cost floor** — and against
confabulation (the actual failure mode, per `fan-out-contract` §C2 where 5 of 8 refutations were
overclaims rather than broken code) a cost floor is the correct instrument. The estate's own rule
says the two signals must be *mechanically independent*, and it never says *cryptographically
signed*. I am implementing the rule as written.

*What survives, third:* GAP-3 and GAP-4 are untouched by R3. 233 unversioned files that every
receipt resolves through, and 1 of 7 CI jobs with least privilege, are plain integrity defects with
plain fixes and no epistemics involved.

**Net verdict on my own candidate.** R3 reduces this architecture from *"security-first: the receipt
becomes trustworthy"* to *"authorization-first, with provenance and a corroboration cost floor
bolted onto a receipt that remains, in the last analysis, self-reported."* That is a materially
weaker claim than the one the candidate's name advertises, and I am stating it in the advocacy
document rather than letting a reviewer discover it. It is still, on the measured evidence, the only
candidate in the tournament that closes the authorization axis at all — and the axis is real: 2,007
units, 151 unconstrained capability sets, 144 unenforced approval requirements, 0 rules.

**Evidence that would make a different candidate win.** (i) If an `ast`-based call-graph pass shows
that `owner_approval_required` and `execution_substrate` *are* consumed somewhere I did not find,
GAP-1 shrinks from "unenforced" to "under-enforced" and Plane A's value drops sharply — this is the
single measurement most likely to overturn me, and my own detector is admittedly asymmetric. (ii) If
a both-states audit of the estate's gates finds untyped silence to be the far larger loss, **A10
(falsification-plane first) should win**, and I would say so: A10 is cheaper, has no policy-
maintenance tax, and R3 does not apply to it because A10 never claims authenticity in the first
place. (iii) If the owner's real threat model is exfiltration rather than misauthorization, this
candidate is close to worthless — §6.3 concedes it does not model egress — and the sandbox-ladder
candidate wins outright.

---

## 10. Provenance of this document

`generated_by` `platform/architecture/security-first.md` (hand-authored) ·
`source_ref` `9f2dac7a6b6d14cfdf5e4c21894c893c4372b7c3` · measured 2026-08-10.

Probes, all re-runnable, outputs on disk beside them:
`platform/architecture/_secfirst_measure.py` → `.out.json` (Wave 1 inventory, receipt surface,
catalog, CI, existing security planes) · `_secfirst_measure2.py` → `.out.json` (detector forensics,
authorization surface, enforcement search, CI per-job permissions, forgeability, git scope) ·
`_secfirst_measure3.py` → `.out.json` (enforcement classifier with detector control, work-unit
schema constraints, receipt authz binding) · `_secfirst_probe_denydefault.py` → `.out.json`
(four-state discrimination on `DSL-SEM-011` + plane asymmetry) · `_secfirst_selfaudit.py` →
`.out.json` (re-derives every load-bearing figure in this document from the probe outputs and from
disk).

**This document is self-audited.** `_secfirst_selfaudit.py` carries **61** checks, of which **2 are
deliberately-wrong injected controls**; it reports `auditor_valid` only when both are caught, so a
green run is not vacuous. It separates **STABLE** claims (fixed by the pin — these are errors if they
mismatch) from **VOLATILE** working-tree counts (moved by concurrent siblings — these are reported as
drift), and it independently re-checks that no file this design modifies has changed since the pin:

```
$ python platform/architecture/_secfirst_selfaudit.py
checks=61 controls=2 controls_caught=2
auditor_valid=True  (if False, every verdict below is meaningless)
commits since pin 9f2dac7a: 1
design-touched files changed since pin: NONE -> design section is current
STABLE mismatches (errors)  = 0
VOLATILE drift (tree moved) = 3
  DRIFT {'claim': 'HEAD', 'doc': '9f2dac7a', 'derived': 'edcf9f5b'}
  DRIFT {'claim': 'lib py', 'doc': 64, 'derived': 131}
  DRIFT {'claim': 'untracked total', 'doc': 369, 'derived': 532}
figures missing from doc text: []
SUCCESS:secfirst-selfaudit
```

Collapsing that stable/volatile distinction was the auditor's own first bug: it initially reported
the three drifted counts as document errors, which would have sent me chasing a moving tree instead
of checking whether anything load-bearing had actually changed. It had not.

It also asserts that each headline figure literally appears in this file's text, so a number cannot
be silently dropped during editing. Two probe scripts were themselves wrong before they were right
and both corrections are recorded in the body rather than hidden: the council security-keyword
detector reported a meaningless **117/117** (`secret`/`redact` are boilerplate in every councilspec —
a use-vs-mention artifact, real signal is 4 security-named specs), and the first `DSL-SEM-011` probe
was **silent in all four states** because it called a non-existent entry point (`semantics.check`
instead of `check_workflow`) — a probe silent in both states measures nothing, and it was fixed
before any verdict was drawn from it.

**Spec-gap finding, reported because the tournament needs to know.**
`13-ARCHITECTURE-CANDIDATES.md` contains **no security-first candidate**. It enumerates A1-A11 and
`grep -i "security-first\|security first"` returns **zero** hits. Mapping the spec's 9 mandated
candidates onto doc 13: config-first→A1, generated-SSOT→A2, marketplace-first→A3,
gateway/lazy→A4, distributed-runtime→A5, cross-vendor→A8, maximal-hybrid→A9 — and
**security-first and UX/product-first have no counterpart** (`grep -i "ux/product\|product-first\|
UX-first"` also returns zero). A10 (falsification-plane) and A11 (immutable deploy) are the nearest
neighbours and both carry *"Security model"* paragraphs, but neither takes security as its
organising principle and neither touches the authorization axis. **So this document is a synthesis
from the MECH-NN menu, not a consumption of a prior design**, and any judge expecting it to match a
doc-13 card should know that card does not exist. Whoever owns UX/product-first should be told the
same thing about theirs.