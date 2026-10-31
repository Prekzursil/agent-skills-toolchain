---
title: WAVE4-MARKETPLACE-LIFECYCLE
type: note
permalink: dqverify-repo-20261013/command-center/wave4-marketplace-lifecycle
---

# Wave 4 — INDEPENDENT verification: Phase 6 marketplace lifecycle

**Unit:** `verify/marketplace-lifecycle` · **Target:** `platform/marketplace/` (Phase 6) ·
**Probe:** [`wave4_marketplace_lifecycle_verify.py`](wave4_marketplace_lifecycle_verify.py) ·
**Machine output:** [`WAVE4-MARKETPLACE-LIFECYCLE.json`](WAVE4-MARKETPLACE-LIFECYCLE.json) ·
**Recorded:** 2026-08-10

**Headline:** all six required checks **PASS**, each with a both-states control — and the
revocation channel, the load-bearing one, blocks on every path I could reach **except two**:
`mkt import` of a stale offline bundle **silently deletes the destination's revocation list**,
and a `verify-always` mirror serves a revoked version from its build-time snapshot. Both are
CONFIRMED by execution with the good/bad states shown side by side.

## COVERAGE — what is measured here and what is not

| section | state |
|---|---|
| checks 1-6 (the assigned list), each with a both-states control | **MEASURED**, CLI-driven, exit codes quoted |
| revocation bypass hunt: update · rollback · dependency · offline bundle · stale mirror · deleted/blanked/rogue-signed list | **MEASURED**, 8 paths |
| the briefed "Wave 3 never reached the marketplace checks" | **MEASURED → REFUTED** (mechanically different probe) |
| `platform/marketplace` suite re-run | **MEASURED**: 162 passed in 38.18 s |
| whole-`platform` suite / the 3,026 baseline | **NOT-CHECKED** — this unit changed nothing under `platform/`, and ~20 agents are writing that tree, so a count taken now is a snapshot, not an invariant |
| network transport / a real remote registry | **OUT OF SCOPE** — `mkt` has no HTTP client; every root here is a filesystem root |
| Phase 5 plugin lifecycle | **NOT MINE** — a sibling unit owns it (`WAVE4-PLUGIN-LIFECYCLE-VERIFY.*`) |

## Independence of this probe

| axis | build lane's `probe_e2e_marketplace.py` | this unit |
|---|---|---|
| transport | in-process Python API | `subprocess` → `python -m mkt <verb>` |
| entry point | `install.Installer(...).install(...)` | the shipped CLI, cwd `platform/marketplace` |
| pass signal | its own JSON assertions | process **exit code** + the terminal `SUCCESS:`/`FAILED:` marker |
| verified against | itself | 16 CLI invocations recorded verbatim in the JSON |

There is **no `mkt verify` verb** (measured, see §Findings F3), so the two cryptographic
primitives — Ed25519 `verify_document` and the CycloneDX component-hash recomputation — are the
only places this probe calls the library, and each is paired with a falsification control.

## The six required checks

### 1. PUBLISH a fixture package to the local registry — **PASS**

```
$ python -m mkt fixture --into <TMP>/base
SUCCESS:mkt-fixture            exit 0   (registry lands at <TMP>/base/registry, NOT <TMP>/base)

$ python -m mkt scaffold --name verify-probe --into <TMP>/src --version 1.0.0 --channel stable
SUCCESS:mkt-scaffold           exit 0

$ python -m mkt publish <TMP>/src/verify-probe --registry <TMP>/base/registry \
    --publisher pub:alpha-tools --fixture-key pub:alpha-tools --fixture-policy
FAILED:mkt-publish MKT-P05     exit 1   <- BAD STATE: no licence basis

$ python -m mkt publish <TMP>/src/verify-probe --registry <TMP>/base/registry \
    --publisher pub:alpha-tools --fixture-key pub:alpha-tools --fixture-policy \
    --license-basis platform/marketplace/fixture/LICENSE
SUCCESS:mkt-publish            exit 0   <- GOOD STATE: verify-probe@1.0.0, score 90, 3 payload files
```

The fixture's own negative half reproduced exactly: `evil-overreach → MKT-P07`,
`secret-leaker → MKT-P06`, `apache-mixer → MKT-P08`, each **expected == actual**.

### 2. INSTALL it from the registry into a temp prefix — **PASS**

```
$ python -m mkt install verify-probe --registry <TMP>/base/registry --site <TMP>/site \
    --range =1.0.0 --fixture-policy
SUCCESS:mkt-install            exit 0
```

3 payload files landed under `<TMP>/site/packages/verify-probe/1.0.0`, `state/installed.json`
written, `mkt-lock.json` written, **13 gates recorded in the receipt** (`gates_evaluated: 13`).
`hello-skill@1.0.0` installs into the same prefix the same way.

### 3. VERIFY signature + SBOM, then CORRUPT and show the refusal — **PASS**

| probe | good state | bad state |
|---|---|---|
| Ed25519 manifest signature, key pinned to the index row | `verified: true` | one hex char flipped → `false` (`signature mismatch`) |
| CycloneDX 1.5 SBOM vs the **installed** copy | `3/3 components matched`, `hash_mismatch=0` | 1 byte appended to an installed file → `ok=false`, `hash_mismatch=1` |
| `mkt install` with the registry manifest signature corrupted **on disk** | clean registry → **exit 0**, files land | corrupted → **exit 1 `MKT-I03`**, nothing lands |
| `mkt install` with the SBOM component hash zeroed | (same clean control) | **exit 1 `MKT-I10`**, nothing lands |

### 4. REVOKE, and show the install path refuses — **PASS** (see §Findings for two escapes)

```
$ python -m mkt install hello-skill --range =1.0.0 --site <TMP>/site-rev-before   -> exit 0, 3 files
$ python -m mkt revoke --registry <TMP>/reg-revoke --scope version --name hello-skill \
    --version 1.0.0 --reason "wave4 independent verification" --severity critical \
    --authority pub:registry-root --fixture-key pub:registry-root
SUCCESS:mkt-revoke             exit 0   rev:32f6ebf744de
$ python -m mkt install hello-skill --range =1.0.0 --site <TMP>/site-rev-after    -> exit 1 MKT-I04
```

**0 files in the site after the refusal** — the refusal does not half-install.

| angle | result |
|---|---|
| scoped, not a kill switch | `=1.1.0` still installs, **exit 0** |
| revocation list **deleted** | **exit 1 `MKT-I04`** — fail-closed |
| list emptied and re-signed by a **rogue publisher key** | **exit 1 `MKT-I04`** |
| the SAME emptied list re-signed by the **maintainer** key | **exit 0** — so the refusal above is about the KEY, not the emptiness |
| `update` to a revoked newer version | **exit 1 `MKT-I04`**; the site still holds 1.0.0 |
| `rollback` to a version revoked after the update | **exit 1 `MKT-I04`** |
| a revoked package pulled in as a **dependency** | dependant installed cleanly before; **exit 1 `MKT-I04`** after, and **neither** dependant nor dependency left in the site |

### 5. Malicious package (excessive permissions) rejected — **PASS**

`evil-overreach` requests `exec:process:**`, `fs:write:**`, `hook:register:PreToolUse`,
`net:egress:**`, `secrets:read:**`.

| state | result |
|---|---|
| publish under the strict fixture policy | **exit 1 `MKT-P07`** |
| publish under a **lax registry policy** I wrote (all `**` granted, nothing forbidden) | exit 0 — it is now a properly signed row in a properly signed index |
| install that row with the **strict consumer** policy | **exit 1 `MKT-I05`**, nothing lands |
| control: benign `hello-skill` from that **same** index, same strict policy | **exit 0** |

The second half is the load-bearing one: refusing only at publish protects only a registry the
attacker does not control. This is the strongest form of the test — a real lax registry, not a
hand-edited index.

### 6. Lockfile determinism — **PASS**

Seed a lockfile pinning `hello-skill@1.0.0`, copy it into two fresh prefixes, `install --frozen`
in each:

| site | exit | resolved | payload digest |
|---|---|---|---|
| site-lock-a | 0 | **1.0.0** | `sha256:8c8d5998…4b6d385b` |
| site-lock-b | 0 | **1.0.0** | `sha256:8c8d5998…4b6d385b` |

Identical version **and** identical payload digest, and the lockfile is byte-equal after both runs.
Two controls make that non-vacuous: the **unfrozen** install of the same `*` range resolves
**1.1.0** (so the lockfile is what pinned it, not the resolver's only option), and a lockfile whose
`payload_digest` I drifted refuses with **`MKT-I13`**, nothing landing.

## FINDINGS

### F1 — `mkt import` of a stale offline bundle DELETES the destination's revocation list · **P1 · CONFIRMED**

`mkt/bundle.py:238-242` copies the bundle's `revocation.json` **over** the destination's and
re-signs the index. There is no union, no `updated_at` comparison, and no freshness check in
`verify_bundle` — it only asserts the bundle *has* a list, never that it is not older.

```
export bundle of hello-skill@1.0.0        exit 0     (bundle carries the then-empty list)
revoke hello-skill@1.0.0 in that registry exit 0
install hello-skill =1.0.0                exit 1 MKT-I04     <- GOOD STATE
import the stale bundle into it           exit 0
install hello-skill =1.0.0                exit 0, 3 files land   <- BYPASS
revocations left in destination list:     0   (revocation_ids_still_present: [])
```

Two independent signals: the install **exit code flips 1 → 0**, and the destination
`revocation.json` read straight off disk now holds **zero** revocations.

**Scope, stated precisely.** The actor must hold the registry-maintainer key, because the import
re-signs the destination index — so this is **not** an unprivileged bypass. It is an operation
whose stated purpose is "merge packages" silently performing a **revocation-clearing** write, in
the ordinary air-gap direction (export a mirror set, revoke later, re-import). The existing test
`test_offline_import_carries_the_revocation_so_a_revoked_package_still_refuses`
(`mkt/test_marketplace.py:913`) revokes **before** exporting and imports into an **empty**
destination, so it measures the one ordering that cannot fail. `MARKETPLACE-BUILD.md` §5.2 item 5
("Offline import carries the revocation list, so an air-gapped import refuses as well") is
therefore **an overclaim, not a false gate** — correctly scoped it reads *"a bundle exported after
a revocation carries it"*.

**Fix:** union revocations by `revocation_id`, keep the newer `updated_at`, and refuse an import
whose bundle list is older than the destination's. Settling experiment: re-run this probe's
`stale_offline_bundle_import` case; the post-import install must stay `MKT-I04`.

### F2 — a `verify-always` mirror serves a revoked version from its build-time snapshot · **P2 · CONFIRMED**

`install.py:542` evaluates revocation against **the resolving root's own** list
(`reg.load_revocation(source.root, source.index)`). A mirror's `revocation.json` is a copy made at
mirror-build time (`fixture.py:530-533`), so a revocation added to the primary afterwards is
invisible to a mirror-sourced install. Measured with the discriminator, not assumed:

| mirror `trust_mode` | install of the revoked `=1.0.0` | receipt's source |
|---|---|---|
| `verify-always` | **exit 0**, 3 files land | `reg:fixture-mirror-a` |
| `verify-and-require-primary-index` (the fixture default) | **exit 1 `MKT-I12`** | — |

Reachability needs both the primary row withdrawn *and* a `verify-always` mirror; the fixture's
require-primary-index mode is what closes it today, and that mode is declared **by the registry
index**, not by the consumer's trust policy — so the consumer cannot insist on it. The build record
discloses mirror-withheld revocation as a *remote-transport* residual
(`MARKETPLACE-BUILD.md` §7); measured here it is reachable **locally**, which is a wider scope
than the disclosure states. `mirror` appears in the Wave 3 audit artifact only inside a registry
file census — no stale-mirror probe existed.

**Fix:** evaluate revocation against the consumer-anchored primary list, or union primary+mirror,
never mirror-only; and let the trust policy require a minimum mirror trust mode.

### F3 — there is no standalone `mkt verify` verb · **P3 · CONFIRMED**

`python -m mkt verify` → argparse *invalid choice*, exit 2; the control `python -m mkt install`
(a real verb, missing args) exits 2 **without** *invalid choice*. Signature and SBOM verification
exist only *inside* the install path, so an operator cannot re-verify an already-installed package,
which is exactly what an incident response needs. **Detector note:** my first detector searched
`--help` for the substring `verify` and reported the opposite — the word occurs in the `import`
help text. A substring search over help output is not a verb detector.

### F4 — `mkt revoke` never checks the SIGNING key, only the authority ROLE · **P3 · CONFIRMED (Wave 3's finding, still open)**

`--authority pub:alpha-tools` (a publisher) is correctly refused, **exit 1** — so Wave 3's
phrasing "a non-maintainer can publish a revocation" is too broad. The reachable shape is a
maintainer **authority string** signed with a publisher **key**: that exits **0** with
`SUCCESS:mkt-revoke`, and every later install from that registry refuses `MKT-I04` — including
versions that were never revoked. Impact is therefore **denial of service plus a misleading exit
code**, not a revocation bypass, and the marginal privilege is small (an actor who can write
`revocation.json` could already delete it). Fix: validate the signing key against
`registry_maintainer_keys` at revoke time so the failure surfaces where it is caused.

## Briefed-fact re-probe

| briefed fact | verdict |
|---|---|
| "PLUGIN + MARKETPLACE UNVERIFIED. The Wave 3 audit never reached those checks. Nobody has … exercised publish → install → verify signature+SBOM → REVOKE → refuse." | **REFUTED** |

Mechanically different probe — the audit's **machine artifact**, not its prose:
`command-center/WAVE3-FLOOR-AUDIT.json` has top-level keys `check2_phase5_plugin`
(`VERDICT: PASS`, 13,071 chars, including a real `plugin.cli build` at exit 0 with a reproducible
`sha256`) and `check3_phase6_marketplace` (`VERDICT: PASS`, 24,844 chars, with sub-keys
`publish` · `install` · `install_after_revoke` · `install_other_version_after_revoke` ·
`signature_verification` · `signature_forgery_control` · `sbom_verification` · `tamper_control`).
`WAVE3-AUDIT-CORRECTION.md` says the same thing in prose and names commit `4444005d`/`200942b9`
as having mis-described the audit as partial.

**The residual the brief was pointing at is real, though, and this is the honest version:** Wave 3
reached the chain but not these, all of which this unit measured for the first time —
`MKT-I03` **via the install path**, `MKT-I10` at all, `MKT-I05` (the malicious-package
**install-side** half), `MKT-I13` and lockfile determinism, offline `export`/`import` (**0**
occurrences of `bundle` or `import` in that artifact), `update`/`rollback` to a revoked version,
and a revoked **dependency**.

## Side observation — a build-record claim that does hold

`python -m mkt mutations` → **exit 0**, `SUCCESS:mkt-mutation-battery 13/13 load-bearing`,
`all_load_bearing: true`, empty stderr. Wave 3 reported it "exits 1 with a traceback"; at this HEAD,
run from `platform/marketplace`, it does not. Two signals: exit code and terminal marker.

## Residual / NOT-CHECKED

* **Whole-`platform` suite: NOT-CHECKED.** This unit wrote nothing under `platform/`; `git status
  -uall -- platform` shows only other lanes' files (e.g. a modified
  `platform/lib/_mutation_selfcheck.py` I never touched).
* **Network transport: OUT OF SCOPE.** No HTTP client exists in `mkt`. Whether F1/F2 get worse over
  a real transport is **NOT-CHECKED**; both are content/state defects rather than transport ones, so
  they almost certainly carry over unchanged (**almost certain, 90-99%**, from reading
  `bundle.py:238` and `install.py:542`), while a mirror actively *withholding* a fresh revocation
  adds a freshness problem nothing here measures.
* **Stopping condition 13 ("release/canary succeeds") is unsatisfiable as written** because release
  mode is PR-ONLY and binding. Read as *"a merged PR plus a local rollback rehearsal"*: the
  **rollback rehearsal is done** (install 1.0.0 → update 1.1.0 → rollback, plus the negative
  rehearsal where rollback to a since-revoked version refuses `MKT-I04`). The **merged-PR half is
  not this unit's** — it ran no `git` command that writes; the orchestrator commits between waves.
* **F1 and F2 are unfixed.** This is a verification unit; it changed no product file. Both fixes
  land in `platform/marketplace/mkt/bundle.py` and `install.py`, which are the build lane's files.
* Local paths in the JSON are redacted (`<REPO>`, `<TMP>`, `<HOME>`) by the same deny-by-default
  principle the target applies to its own proof output.