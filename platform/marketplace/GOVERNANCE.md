---
title: GOVERNANCE
type: note
permalink: dqverify-repo-20261013/platform/marketplace/governance
---

# Marketplace governance model

The machine-readable half of this document is `governance-policy.json`. `mkt lint` rule
**MKT-L17** fails when a publish precondition or role named there is absent from the prose here,
so the two halves cannot drift apart. A governance value the prose does not state is a value
nobody agreed to; a governance promise no gate enforces is a memo.

## 1. Roles and what each may do

| role | may |
|---|---|
| `publisher` | publish a package, yank one of its own versions, install, file an appeal |
| `registry-maintainer` | sign the index, revoke, yank, operate a mirror, install |
| `moderator` | open and close a moderation case, revoke as the outcome of a case |
| `security-response` | publish a security advisory, revoke, open a case |
| `consumer` | install, open a moderation case |

Separation is **enforced, not documented**. `mkt.moderation.revoke` refuses an authority whose
publisher record does not carry `registry-maintainer`, `moderator` or `security-response`, and
`mkt.moderation.publish_advisory` refuses anyone but `security-response` / `registry-maintainer`.
A publisher therefore cannot revoke a rival, and — the case that matters — cannot un-revoke itself.

Only `registry-maintainer` keys listed in the consumer's `trust-policy.json`
(`registry_maintainer_keys`) may sign the canonical index, the revocation list, the advisory list
or an offline bundle. One key that can do everything is one key whose loss ends the marketplace.

## 2. Publish preconditions (blocking)

`mkt publish` refuses unless all of these hold. Each maps to a machine code so a refusal is
branchable rather than prose:

| precondition | code | what it means |
|---|---|---|
| `license-basis-present` | `MKT-P05` | a `LICENSE`/`COPYING`/`NOTICE` basis is supplied |
| `payload-allowlist-explicit` | `MKT-P03` | every payload file is enumerated; no glob, and an undeclared file present on disk refuses |
| `no-secret-findings` | `MKT-P06` | the deny-by-default payload scan is clean |
| `permissions-within-ceiling` | `MKT-P07` | every declared permission is subsumed by the trust policy |
| `license-aggregate-consistent` | `MKT-P08` | the declared SPDX covers every SBOM component licence |
| `conformance-score-floor` | `MKT-P09` | the recomputed conformance score meets the policy floor |
| `signature-present` | `MKT-P10` | the manifest is signed and the signature verifies against the bytes just written |
| `sbom-complete` | `MKT-L06` | the SBOM is a bijection with the payload, checked in both directions |
| `provenance-complete` | `MKT-L14` | source, revision, builder and build time are recorded |

**`license-basis-present` is the one this build was told not to skip.**
`architecture/TOURNAMENT-VERDICT.md` §4 M1 records that this repository has **no root
`LICENSE`/`COPYING`/`NOTICE`** while aggregating **31 Apache-2.0** payload entries under a declared
**MIT**, plus at least one **CC BY-SA 4.0** share-alike entry that a LICENSE-*file* scanner reports
as clean — and concludes the winning spine is "unlawful to publish without" this lane. Turning that
into a blocking gate, rather than a paragraph, is the adoption.

## 3. Deprecation, yank, revocation — three strengths, no overlap

| verb | where it lives | effect on discovery | effect on install |
|---|---|---|---|
| **deprecation** | signed package manifest | still listed | proceeds; recorded as an override |
| **yank** | index row (`yanked: true`) | hidden from resolution | an exact pin still installs |
| **revocation** | separately signed `revocation.json` | (index should also yank) | **REFUSED** |

Revocation is **fail-closed**. If the revocation list is absent, unparseable, unsigned, or signed
by a key that is not a declared maintainer key, every install **refuses** — the default in
`trust-policy.json` is `on_missing.revocation_list = "refuse"`. A revocation channel that can be
deleted to re-enable a revoked package is not a revocation channel. Rollback re-runs every gate, so
rolling back to a since-revoked version refuses too.

## 4. Moderation and dispute process

A case is an append-only event log with a legal-transition table
(`mkt.moderation.TRANSITIONS`); an illegal transition raises rather than being recorded.

```
open ──▶ under-review ──▶ action-taken ──▶ appealed ──▶ appeal-upheld
  │            │                                    └─▶ appeal-rejected
  └──▶ dismissed ◀────────┘
```

* **Opening.** Any role, including `consumer`, may open a case with a reason category
  (`malware`, `excessive-permissions`, `license-violation`, `impersonation`, `spam`, `privacy`,
  `other`), a note, and evidence anchors.
* **Triage SLA.** 14 days (`slas.moderation_triage_days`).
* **Action.** `action-taken` is the only state that authorises a revocation entry, and the
  revocation records the `case_id` that produced it.
* **Appeal.** The publisher may appeal within 30 days (`slas.appeal_window_days`).
* **Reversal is mandatory.** `uphold_appeal` removes the revocation the case created and re-signs
  the list; if the revocation is not there to remove it **raises** rather than reporting a reversal
  that did not happen. A moderation system with no reversal is a deletion system with a form
  attached.

## 5. Security advisory flow

`reported → triaged → confirmed → fixed | disputed | withdrawn`, in a separately signed
`advisories.json` that only `security-response` may write.

* Vulnerability status for a version is **derived** from open advisories at install time, never
  stored on the package — a stored status goes stale the moment a new advisory lands, and staleness
  in that field is indistinguishable from safety.
* `fixed`, `withdrawn` and `disputed` stop gating. `disputed` is deliberately non-gating **and**
  deliberately visible: the dispute process exists so a contested claim stops blocking installs
  while the moderation case record holds the contest.
* Advisory triage SLA is 7 days (`slas.advisory_triage_days`).
* An advisory above the consumer's `max_advisory_severity` refuses the install. The
  `--allow-vulnerable` override exists only if the trust policy sets
  `allow_vulnerable_override: true`, and its use is written into the install receipt: an override
  nobody can audit is not an override, it is a hole.
* Embargo: `coordinated_until` may withhold an advisory from a **public** mirror, never from a
  private one. An embargo that hides an advisory from the operator running the code protects the
  wrong party.

## 6. Mirrors and federation

A mirror is another filesystem registry root, resolved in `priority` order. Federation **cannot
introduce trust**: every mirror entry is still verified against the consumer's own trust policy and
the publisher's own signature. A hostile mirror can therefore withhold a package or serve a stale
one — it cannot substitute a payload. `verify-and-require-primary-index` additionally requires the
primary index to agree on `(name, version, manifest_digest)`, which defeats a mirror serving a
package the primary never published.

## 7. Offline export and import

A bundle is a signed slice of a registry that **carries the revocation and advisory lists**. An
import refuses a bundle that omits a list the consumer's policy is fail-closed on: an air-gapped
import that shipped packages without their revocations would install exactly the versions the
online path refuses.

## 8. Amendment

An amendment changes this document and `governance-policy.json` in the same pull request; quorum 1
(single-owner estate). Release mode is **PR-ONLY**, so every amendment is reviewed before it takes
effect.

## 9. Scope honesty

`architecture/marketplace-first.md` §7.2 — written by this lane's own advocate — **refutes** the
deployment half of a marketplace for a one-user estate: moderation, dispute process, federated
mirrors, publisher reputation, collections and a public channel are called "dead weight" there.
This build adopts that finding as a **scope statement**, not as a reason to skip a required
deliverable:

* The **contract, provenance and integrity** half is load-bearing and exercised end-to-end.
* The **distribution** half (moderation state machine, dispute reversal, mirrors, collections,
  offline bundles) is implemented, schema-gated and tested, but is exercised only by the fixture
  marketplace. There is no human moderation body, no publisher reputation, and no network
  transport.
* Publisher **reputation** was dropped outright rather than stubbed: `publisher.schema.json` has no
  `stars`, `downloads` or `rating`. What remains is falsifiable — can this key verify this
  signature, and is this key in the trust policy.