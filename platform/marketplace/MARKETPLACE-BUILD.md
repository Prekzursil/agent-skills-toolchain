---
title: MARKETPLACE-BUILD
type: note
permalink: dqverify-repo-20261013/platform/marketplace/marketplace-build
---

# Phase 6 — The real marketplace (build record)

**Unit:** `build/phase6-marketplace` · **Spec:** `_USER-PROMPTS.md:10844-10871` ·
**Root:** `platform/marketplace/` · **Recorded:** 2026-08-10

Map: [`README.md`](README.md) · Governance: [`GOVERNANCE.md`](GOVERNANCE.md) +
[`governance-policy.json`](governance-policy.json) · Proof output:
[`PROOF-e2e.json`](PROOF-e2e.json)

## COVERAGE — what is measured and what is not

| section | state |
|---|---|
| Minority-report adoption (§2) | MEASURED, per finding, with the declines named |
| Contract surface — 19 schemas (§3) | MEASURED: 19/19 compile, `python -m mkt selfcheck` |
| Tooling — linter / CLI / scaffolder / validator (§4) | MEASURED: all four run, exit codes agree with markers |
| Fixture marketplace (§4) | MEASURED: 4 publish, 3 refused with the expected code |
| Required proof: publish → install → verify → revoke → refuse (§5) | MEASURED: `probe_e2e_marketplace.py` exit 0 |
| Malicious package, excessive permissions (§5) | MEASURED: refused at publish AND at install |
| Gates load-bearing (§5.3) | MEASURED: 13/13 gates by mutation, both states |
| Defects in my own installer (§5.4) | 2 found by self-review, fixed, each with a test AND a mutation |
| Suite delta (§6) | MEASURED and ATTRIBUTED: +162 is mine, +483 is concurrent sibling work |
| ruff, CI's pinned 0.15.17 (§6) | MEASURED: check + format clean |
| Loader coupling (`marketplace-first` FM-6) | **NOT-CHECKED** — see §7 |
| Whether the live 118-unit `profile=` figure still holds | **NOT-CHECKED** — see §7 |
| Network transport / real remote registry | **OUT OF SCOPE BY DESIGN** — see §7 |
| Benchmark evidence end-to-end | MEASURED: `hello-skill` ships a real document; MKT-L13 validates it and fires when a control is falsified |

## 1. Baseline

The pinned brief says the platform suite baseline is 2,767. **That number is stale** — three
defect-fix siblings (D1, D2, D5) landed tests since it was written. Re-captured immediately before
any edit of mine:

```
$ python -m pytest platform -q
3071 passed, 14 skipped in 169.50s (0:02:49)
```

Two sibling units independently reported the same staleness (D1 measured 2812, D3 corroborated it),
so I am using my own measurement rather than the pinned figure and saying so.

Nothing outside `platform/marketplace/` was modified by this unit. `command-center/`,
`platform/lib/`, `platform/schema/`, `platform/council/` and `platform/workflows/` are untouched.

## 2. The tournament minority report — what I adopted, and what I declined

`architecture/TOURNAMENT-VERDICT.md` §4 **M1** says marketplace-first "held the better answer" on
the entire Phase 4-6 surface and that the winning spine is "unlawful to publish without it".
`architecture/marketplace-first.md` §7.2 then **refutes its own deployment half**. Both were read
before designing. Adoption, item by item:

### ADOPTED

| finding | how it is enforced here |
|---|---|
| **M1 / Stage 0 — licence basis is a blocking precondition.** No root `LICENSE`/`COPYING`/`NOTICE` exists in this repo while 31 Apache-2.0 payload entries sit under a declared MIT. | `license-basis-present` in `governance-policy.json`; `mkt publish` refuses with **`MKT-P05`** when no basis file is supplied. Both-states control: `test_publish_refuses_without_a_licence_basis`. |
| **M1 / §4.2 — the aggregate-licence misstatement is invisible to a LICENSE-*file* scanner** (a CC BY-SA 4.0 entry read as clean). | Per-component SPDX is **mandatory** in `sbom.schema.json` (`licenses` minItems 1) and `sbom.build` REFUSES to emit a component with no licence. Publish refuses with **`MKT-P08`**, install with **`MKT-I11`**, lint flags **MKT-L03/L04**. The `apache-mixer` fixture package is that exact shape. |
| **FM-1 — the index is a single point of TOTAL failure**, and the advocate's own path scanner produced a false "346 missing" from an `lstrip("./")` normalisation bug. | `registry.load_index` is all-or-nothing (schema-validated before any entry is readable). MKT-L02 checks payload existence **with no path normalisation at all** — the schema's positive char class already forbids the shapes that would need it. `lint.self_test` proves the rule fires on a known-BROKEN package and is silent on the known-GOOD one. |
| **FM-2 — 233 generated shims with no drift detector.** | `lockfile.schema.json` pins `manifest_digest` + `payload_digest` per package; `--frozen` turns drift into a hard failure (**`MKT-I09`** / **`MKT-I13`**), proven by `test_frozen_install_refuses_a_digest_drift`. |
| **FM-4 — payload bloat and local-topology leakage** (a real `C:/Users/...` path already committed in a registry row). | Payload is an **explicit allowlist**, checked in both directions: a declared-but-absent file refuses (**`MKT-P02`**) and a present-but-undeclared file refuses (**`MKT-P03`**). A deny-by-default scanner (SEC-1..SEC-7) refuses on private keys, absolute user paths, credential-shaped assignments, bearer headers, provider prefixes, UNC paths and high-entropy tokens (**`MKT-P06`**). This build record's own proof output is path-redacted by the same principle. |
| **FM-5 — "untyped silence": 118 units whose declared contract silently WIDENED to a permissive default.** | Adopted as a **principle across the whole surface**, not one gate: every absence is typed (`on_missing.*` defaults to `refuse`), `channel` is a filter and never a fallback, an unrecognised severity ranks as the WORST, an unparseable revocation range REVOKES, and `trust-policy.schema.json` makes `signature: warn` **unrepresentable**. |
| **§4.4 — reuse the path containment at `platform/lib/schema_resolver.py:147`, do not re-derive it.** | `canon.ensure_within` is that idiom, generalised, with the trailing `os.sep` that stops `<root>-evil` passing as `<root>`. Regression: `test_ensure_within_rejects_sibling_prefix`. |
| **§1.5 — exactly three control planes.** | identity/version (`registry-index`), integrity (`lockfile` + `signature` + `sbom`), acceptance (`governance-policy` publish preconditions). The fourth (distribution) is reduced, per §7.3. |
| **M6 / config-first P-1 — one physical definition per constraint.** | `common.schema.json` holds every shared `$def`; there is no second copy of `sha256` or `semver`. One `permissions.subsumes()` is imported by BOTH the linter and the installer, so the ceiling cannot drift between them. |
| **§7.2/§7.3 — the advocate's own refutation of the deployment half.** | Publisher **reputation was dropped outright**: `publisher.schema.json` has no `stars`, `downloads` or `rating`. Moderation, dispute, mirrors, collections and offline bundles are built (the spec requires them) but their scope is stated in GOVERNANCE.md §9: schema-gated and executable, exercised only by the fixture marketplace, with no human moderation body and no network transport. |
| **M2 (ux-product-first) — `render.py` writes by DEFAULT; `--check` is opt-in.** Not my surface, but the hazard class is. | `mkt lint` writes nothing unless `--out` is passed; `mkt keygen` **refuses to overwrite** an existing key file. |

### DECLINED, with the reason

* **FM-6 — the plugin-loader coupling probe.** marketplace-first calls it "a blocking probe, not a
  step" and rates it *roughly even* that Claude Code's loader can host a `hooks/hooks.json`
  battery. It is a Phase-5 plugin question, not a Phase-6 registry question, and it is
  **NOT-CHECKED** here. Settling experiment unchanged: install a scratch plugin carrying
  `hooks/hooks.json` into a throwaway `CLAUDE_CONFIG_DIR` and check whether the handler fires.
* **The literal `mkt-profile` receipt gate.** M1's dissent says adopt it "regardless of the spine".
  The `profile=` widening lives on the **receipt** plane owned by
  `platform/lib/receipt_schema_gate.py` + `completion_predicate.py`. Touching it from this unit
  would put a second control plane on someone else's surface, which contradicts the §1.5
  singularity rule I am otherwise enforcing. The *principle* is adopted (see FM-5 above); the
  receipt-plane gate is left to that plane's owner, and I did not re-measure the 118-unit figure.
* **FM-7 — `command-center/receipts/` absent for 1,021 units.** Informational; untouched.

## 3. Contract surface — 19 schemas

```
$ python -m mkt selfcheck
{ "declared": 19, "checked": 19, "failures": [] }
SUCCESS:mkt-selfcheck
```

`common` · `package-manifest` · `registry-index` · `publisher` · `signature` · `sbom` ·
`trust-policy` · `lockfile` · `revocation` · `advisory` · `install-receipt` · `collection` ·
`mirror` · `moderation-case` · `offline-bundle` · `quality-score` · `benchmark-evidence` ·
`governance-policy` · `lint-report`.

Every spec-required capability maps to a field or a document; the mapping is in `README.md`. Three
schema choices are load-bearing rather than cosmetic:

* **`benchmark-evidence.controls.control_known_broken.fired` is `const: true`** — the schema will
  not let a publisher record a benchmark whose instrument never fired on a known-broken input.
* **`trust-policy.on_missing.signature` is a one-value enum (`refuse`)** — a build in which an
  unsigned package can install is not expressible.
* **`lint-report` requires BOTH `rules_total` and `rules_evaluated`** — an empty `findings` array
  alone is not a pass, so the "0 findings / 0 rules" swallow cannot read as green.

## 4. Tooling

| deliverable | entry point | evidence |
|---|---|---|
| marketplace linter | `mkt.lint` / `python -m mkt lint` | 20 rules MKT-L01..L20; fixture registry verdict **PASS** with **20/20 evaluated**; `lint.self_test` fires on 3 distinct known-broken mutations |
| publisher CLI | `python -m mkt <verb>` | 15 verbs; every verb emits `SUCCESS:`/`FAILED:` and the **exit code agrees** (asserted in `test_cli.py`) |
| package scaffolder | `mkt.scaffold` / `mkt scaffold` | `test_scaffolded_package_publishes_installs_and_lints_clean` — scaffold → publish → lint **PASS** → install SUCCESS |
| local validator | `mkt validate --schema <name>` | validates any of the 19 documents; a missing file is a **failure**, never a pass |
| test fixture marketplace | `mkt.fixture` / `mkt fixture --into` | 4 packages published, **3 refused with the expected code**, 1 private mirror, 1 collection, signed revocation + advisory lists |

```
$ python -m mkt fixture --into <tmp>
published : hello-skill@1.0.0(90) hello-skill@1.1.0(90) dep-consumer@1.0.0(90) vulnerable-lib@1.0.0(90)
refusals  : evil-overreach   expected MKT-P07  actual MKT-P07
            secret-leaker    expected MKT-P06  actual MKT-P06
            apache-mixer     expected MKT-P08  actual MKT-P08
SUCCESS:mkt-fixture
```

The refusals are **returned, not swallowed**, and asserted per-code. A fixture marketplace in
which everything publishes cannot demonstrate that anything is enforced.

## 5. Executable proof

### 5.1 The required sequence

```
$ python platform/marketplace/probe_e2e_marketplace.py   ->  exit 0
SUCCESS:phase6-marketplace-e2e
```

Full output in [`PROOF-e2e.json`](PROOF-e2e.json) (local paths redacted). The load-bearing lines:

| step | result |
|---|---|
| 1 PUBLISH | `hello-skill@1.0.0`, `manifest_signature_verifies: true`, score 90, lint `PASS` |
| 2 INSTALL | `SUCCESS`, `gates_evaluated: 13`, `gates_declared: 13`, `all_gates_accounted: true` |
| 3 VERIFY | signature verifies on the installed manifest; SBOM `3/3 components matched`; **control**: a one-byte tamper makes it `hash_mismatch=1` |
| 4 REVOKE | `install_refused_after_revocation: true`, `refusal_code: MKT-I04`, `nothing_written_to_site: true` |
| 4 rollback | `rollback_to_revoked_version_refused: true`, code `MKT-I04` (after a REAL install→update, so a previous version existed) |
| 4 fail-closed | deleting `revocation.json` → **refused**, `MKT-I04` |
| 4b dispute | appeal upheld → revocation removed → the same install SUCCEEDS again |
| 5 MALICIOUS | `publish_refused: true` (`MKT-P07`) **and**, forced into a properly signed index, `install refused` (`MKT-I05`) — with the control that a benign package from the **same** index still installs |

### 5.2 Revocation actually blocks — five independent angles

The task names this as the failure mode, so it is asserted five ways:

1. **Both-states:** the identical install SUCCEEDS before the revocation and REFUSES after.
2. **No partial write:** `site/packages/hello-skill/` does not exist after the refusal.
3. **Every scope blocks:** `version`, `range`, `package` and `key` scopes each refuse; a key-scoped
   revocation propagates through dependencies (measured — an earlier draft of that test wrongly
   expected the dependant to install).
4. **Fail-closed, four breakages:** deleting, unsigning, rogue-signing or blanking the revocation
   list all refuse. A revocation channel you can delete to re-enable a package is not one.
5. **No escape hatch:** rollback re-runs every gate, so rolling back to a since-revoked version
   refuses too. Offline import carries the revocation list, so an air-gapped import refuses as well.

### 5.3 The gates are LOAD-BEARING, not decorative

A gate that refuses is not yet a gate that matters — the install could be failing for an unrelated
reason. So each guard is REMOVED from `install.py`'s own source, loaded as a separate module, and
the identical scenario re-run. Load-bearing iff **real → REFUSED with the expected code AND
mutant → SUCCESS**.

```
$ python -m mkt mutations
M1-revocation-match          real=REFUSED/MKT-I04  mutant=SUCCESS  load_bearing=True
M2-revocation-fail-closed    real=REFUSED/MKT-I04  mutant=SUCCESS  load_bearing=True
M3-permission-ceiling        real=REFUSED/MKT-I05  mutant=SUCCESS  load_bearing=True
M4-manifest-signature        real=REFUSED/MKT-I03  mutant=SUCCESS  load_bearing=True
M5-payload-digest            real=REFUSED/MKT-I09  mutant=SUCCESS  load_bearing=True
M6-sbom-bijection            real=REFUSED/MKT-I10  mutant=SUCCESS  load_bearing=True
M7-advisory-ceiling          real=REFUSED/MKT-I07  mutant=SUCCESS  load_bearing=True
M8-license-components        real=REFUSED/MKT-I11  mutant=SUCCESS  load_bearing=True
M9-index-maintainer-key      real=REFUSED/MKT-I01  mutant=SUCCESS  load_bearing=True
M10-platform-compatibility   real=REFUSED/MKT-I06  mutant=SUCCESS  load_bearing=True
M11-advisory-maintainer-key  real=REFUSED/MKT-I07  mutant=SUCCESS  load_bearing=True
M12-lockfile-pin             real=REFUSED/MKT-I13  mutant=SUCCESS  load_bearing=True
M13-dependency-resolution    real=REFUSED/MKT-I12  mutant=SUCCESS  load_bearing=True
SUCCESS:mkt-mutation-battery 13/13 load-bearing
```

**13 mutations cover 13 of 13 gates.** M11-M13 were added after the two self-review defects in
§5.6, and M13 exists because `dependencies` was the one gate with no mutation: the fixture's
`dep-consumer` carries an *optional* missing dependency (which must be SKIPPED), so a package with
a genuinely unresolvable *required* dependency had to be synthesised to reach `MKT-I12` at all.
Reaching a gate is part of testing it.

**Two defects in my own instrument, found and fixed rather than reported around:**

* **M5 was initially 9/10 — a SHADOWED gate.** Tampering a payload byte breaks the payload digest
  *and* the SBOM hash, so the mutant refused at the SBOM gate and the run proved nothing about the
  payload-digest gate. Fixed by updating the SBOM to match the tampered bytes, isolating the gate.
  The payload-digest gate is also TWO comparisons (registry copy, then installed copy), so the
  mutation disables both — disabling one left the other refusing, which would have read as
  "load-bearing" while measuring a different check.
* **`ruff format` silently broke every literal needle.** The formatter wrapped four guarded lines
  and all ten `str.count` needles stopped matching. Because `mutate()` raises on a zero-match the
  battery FAILED rather than reporting ten false passes — and
  `test_every_battery_pattern_is_unique_in_the_source` named the cause in one line. Needles are now
  whitespace-flexible at token level (a plain whitespace split was measured to *still* miss, because
  the formatter inserts a newline immediately after an open paren, inside such a token).

### 5.4 Two defects in MY OWN installer, found by self-review, not by a failing test

Both were exploitable-shaped, both are fixed, both now have a test AND a mutation. Recording them
because a build record that only lists what went right is a sales document.

1. **The advisory list was verified against whatever key signed it.** `_gate_revocation` checked
   `rev_key not in maintainers`; `_gate_advisory` did **not**. So an attacker able to write
   `advisories.json` could re-sign a copy with **every advisory removed** and it would verify
   perfectly — the vulnerability gate would see nothing to block. Fixed (`MKT-I07` now requires the
   signing key to be a declared maintainer key), regression
   `test_advisory_list_signed_by_a_non_maintainer_is_refused` — which includes the control that the
   *same emptied list*, signed by the real maintainer key, DOES clear the gate, proving the refusal
   is about the key and not about the emptying — plus mutation **M11**. The asymmetry between two
   sibling gates is exactly what a self-review is for; no test would have found it, because no test
   thought to ask.

2. **A `--frozen` refusal half-installed the package.** The lockfile gate ran *after* the payload
   copy, so a pin-drift refusal left the bytes in the site with no state entry pointing at them.
   Fixed by splitting the gate: `_check_lockfile_pin` refuses **before** any write, `_commit_lockfile`
   writes after the installed digest is re-verified, and the copy block now rolls itself back
   (`shutil.rmtree`) on any exception. Regression
   `test_a_frozen_refusal_leaves_nothing_in_the_site` plus mutation **M12**.

   Writing that test surfaced a third thing worth naming: **gate 13 had never actually been
   reached.** The existing drift test tampered a payload, which trips gate 9 first. Reaching
   `MKT-I13` needs a *legitimate re-publish of the same version* — correctly signed, so gates 3/9/10
   all pass and only the pin disagrees. A gate you cannot reach is a gate you have not tested.

### 5.5 Signatures verified by a second, independent implementation

The Ed25519 here is a pure-Python RFC 8032 construction (no runtime dependency, so an air-gapped
import can still verify). "The signature check works" would otherwise rest on the same code that
produces the signature, so it is cross-checked against `cryptography` (Rust/OpenSSL):

```
$ python platform/marketplace/probe_crypto_crossverify.py
"ours_verified_by_cryptography": true
"cryptography_verified_by_ours": true
"signature_bytes_identical":     true
SUCCESS:crypto-crossverify
```

Byte-identical, both directions. If `cryptography` is absent the test SKIPS and says so; it is
never folded into a pass.

### 5.6 Malicious package: excessive permissions rejected TWICE

`evil-overreach` requests `secrets:read:**`, `net:egress:**`, `exec:process:**`, `fs:write:**` and
`hook:register:PreToolUse`. Every one is individually refused
(`test_the_malicious_manifest_permissions_are_individually_excessive`):

* `secrets:read:**` / `exec:process:**` — **forbidden** outright, and a per-publisher grant cannot
  re-enable a forbidden entry (otherwise the ceiling would be advisory);
* `net:egress:**` / `fs:write:**` — dangerous capability at universal (`**`) width, which requires
  an exact explicit grant, not a wildcard ceiling;
* `hook:register:PreToolUse` — not subsumed by any grant.

Refused at publish (`MKT-P07`) **and** at install (`MKT-I05`) after being forced into a correctly
signed index. The second half is the one that matters: refusing at publish only protects a registry
the attacker does not control.

## 6. Suite, lint, and size

```
$ python -m pytest platform/marketplace -q
162 passed in 12.93s

$ python -m pytest platform -q
3716 passed, 14 skipped in 221.51s (0:03:41)

$ uvx ruff@0.15.17 check platform/marketplace     ->  All checks passed!
$ uvx ruff@0.15.17 format --check platform/marketplace  ->  29 files already formatted
```

ruff is CI's **pinned 0.15.17**, not the ambient version — a local green against a different
version verifies nothing.

**The suite delta is NOT all mine, and I am not claiming it.** 3,085 → 3,730 collected is +645,
while this unit contributes 162. The gap is concurrent sibling work landing in `platform/` during
this run. Attributed by measurement rather than by inference:

```
$ python -m pytest platform --ignore=platform/marketplace -q --collect-only  ->  3568 tests
$ python -m pytest platform/marketplace          -q --collect-only  ->   162 tests
                                                                        -----
                                                                         3730  = 3716 passed + 14 skipped
```

3,568 vs the 3,085 in my baseline = **+483 from other units**; **+162 is this unit**. The two
readings now reconcile exactly, which is the only reason either is quotable — a delta that did not
add up would be a measurement defect, not a result.

| | |
|---|---|
| files (excl. `__pycache__`) | 68 |
| JSON schemas | 19 (1,163 lines) |
| Python | 29 files / 8,961 lines — 23 runtime modules, 4 test modules, 2 probes |
| tests | 162 |
| lint rules | 20, all evaluated on the fixture registry |
| install gates | 13, all accounted for in every receipt |
| mutations | 13, all load-bearing, covering 13/13 gates |

Raw captures: [`SUITE-baseline.txt`](SUITE-baseline.txt) (the §1 baseline) and
[`SUITE-after.txt`](SUITE-after.txt) (the final run). Both live under this unit's own root so the
whole footprint of `build/phase6-marketplace` is one directory.

## 7. Residual, NOT-CHECKED, and honest scope

* **No network transport, by design.** The registry, its mirrors and its bundles are filesystem
  roots. There is no HTTP client anywhere in `mkt`, so "private/federated mirrors" and "offline
  export/import" are proven as *federation and bundle semantics*, not as a remote protocol. A real
  remote registry would add a transport and a TLS/host-trust story that nothing here measures.
  Confidence that the security properties (signature, revocation, permission, SBOM, licence) carry
  over unchanged to a remote transport: **likely (55-80%)** — they are all content-addressed and
  transport-independent — but availability and freshness properties (a mirror withholding a
  revocation update) would need their own design. **NOT-CHECKED.**
* **`marketplace-first` FM-6 (plugin loader can host the hook battery) remains NOT-CHECKED** at
  *roughly even* odds, unchanged from the source document. It is a Phase-5 question.
* **Whether the live 118-unit `profile=` widening still holds is NOT-CHECKED.** I adopted the
  principle, not the receipt-plane gate, and did not re-measure the figure.
* **Moderation, dispute, collections and reputation are honestly scoped, not oversold.** The
  advocate's own §7.2 calls them dead weight for a one-user estate. The state machines, role
  separation and reversal path are executable and tested; there is no human moderation body.
  Reputation was dropped rather than stubbed.
* **Stopping condition 13 ("release/canary succeeds") is unsatisfiable as literally written**
  because release mode is **PR-ONLY and binding**. Read, as instructed, as *"a merged PR plus a
  local rollback rehearsal"* — **and I am saying so explicitly.** The **local rollback rehearsal was
  performed**: install 1.0.0 → update to 1.1.0 → rollback to 1.0.0, with the site state asserted at
  each step, plus the negative rehearsal (rollback to a since-revoked version refuses). **The merged
  PR half is NOT done by this unit** — per the standing constraint, ~20 agents share one git index,
  so this unit ran no `git` command at all. The orchestrator commits between waves.
* **The fixture trust policy is deliberately strict** (`fs:read:packages/**` ceiling,
  `secrets:read` and `exec:process` forbidden, fail-closed on every absence). A laxer real-world
  policy would admit more, which is the operator's decision to make explicitly — the schema makes
  the choice visible instead of implicit.
* **Owner decision still open:** this repository has **no root `LICENSE`/`COPYING`/`NOTICE`**, and
  `fixture/LICENSE` is a fixture basis only, not a declaration for the repo. The
  `license-basis-present` gate now makes that blocking for any publish rather than forgettable, but
  **choosing the licence is an owner action** and is not made here.
* **One sensitive-artifact notice fired repeatedly** during authoring, classified
  `POTENTIAL-CREDENTIAL` on files containing the strings `ed25519:`, `secrets:read` and
  `--key-file`. No credential of this estate was read, written, printed, rotated or revoked by this
  unit; fixture keys are derived from committed public labels and exist only in temp roots.