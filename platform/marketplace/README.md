---
title: README
type: note
permalink: dqverify-repo-20261013/platform/marketplace/readme
---

# `platform/marketplace/` — the Phase 6 marketplace

Spec: `_USER-PROMPTS.md:10844-10871`. Governance: [`GOVERNANCE.md`](GOVERNANCE.md) +
[`governance-policy.json`](governance-policy.json). Build record and evidence:
[`MARKETPLACE-BUILD.md`](MARKETPLACE-BUILD.md).

## Layout

```
schema/                19 contracts. common.schema.json holds every shared $def, so there is
                       ONE physical definition per constraint and no second copy of `sha256`.
mkt/                   the executable half (import mkt; python -m mkt <verb>)
  canon.py             canonical bytes, digests, atomic writes, path containment
  crypto.py            pure-Python Ed25519 (no runtime dep) + domain-separated signatures
  versions.py          semver + a deliberately small range grammar
  permissions.py       ONE subsumption function, shared by the linter and the installer
  schemas.py           offline schema registry, deny-by-default retrieval
  registry.py          canonical index: load, verify, search, resolve, federate
  sbom.py              SBOM build + BIDIRECTIONAL verification against real bytes
  publish.py           publish pipeline + blocking preconditions + secret scan
  install.py           install/update/remove/rollback + the 13 enforcement gates + lockfile
  bundle.py            offline export / import
  moderation.py        cases, disputes, the revocations they authorise, advisories
  lint.py              the marketplace linter (MKT-L01..MKT-L20)
  scaffold.py          package scaffolder
  cli.py               publisher CLI
  fixture.py           the test fixture marketplace (deterministic builder)
  mutations.py         both-states mutation battery over the install gates
  test_*.py            154 tests
fixture/               committed fixture package SOURCES + the consumer trust policy
probe_e2e_marketplace.py     the end-to-end proof script; output in PROOF-e2e.json
probe_crypto_crossverify.py  cross-verifies the Ed25519 against `cryptography`
```

## Quick start

```bash
cd platform/marketplace

python -m mkt selfcheck                                     # 19/19 schemas compile
python -m mkt fixture --into /tmp/mkt                       # build the fixture marketplace
python -m mkt search --registry /tmp/mkt/registry --tag fixture
python -m mkt install hello-skill --registry /tmp/mkt/registry --site /tmp/site \
        --range '=1.0.0' --channel stable --fixture-policy
python -m mkt lint /tmp/mkt/registry --fixture-policy        # 20/20 rules, verdict PASS
python -m mkt mutations                                      # 10/10 gates load-bearing

python probe_e2e_marketplace.py     # publish -> install -> verify -> revoke -> refuse
python probe_crypto_crossverify.py  # our Ed25519 == cryptography's, byte-for-byte
```

## The three planes (and the fourth, deliberately reduced)

`architecture/marketplace-first.md` §1.5 names three control planes; this build keeps exactly
those three and reduces the fourth.

| plane | owner | answers |
|---|---|---|
| identity / version | `registry-index.schema.json` | what exists, at what version, from whom, under what licence |
| integrity | `lockfile.schema.json` + `signature.schema.json` + `sbom.schema.json` | are these the bytes that were certified |
| acceptance | `governance-policy.json` publish preconditions | may this version be published at all |
| ~~distribution~~ | reduced | no network transport; mirrors and bundles are filesystem roots |

## Where the enforcement actually is

Thirteen install gates, in order, each recorded in the install receipt with a machine code:

| # | gate | code | refuses when |
|---|---|---|---|
| 1 | `index-signature` | `MKT-I01` | the index is not signed by a declared maintainer key |
| 2 | `publisher-known` | `MKT-I02` | the publisher/key is untrusted or not `active` |
| 3 | `manifest-signature` | `MKT-I03` | the signature fails, or the index row disagrees with the signed manifest |
| 4 | `revocation` | `MKT-I04` | any revocation matches — or the list is missing/unsigned (**fail-closed**) |
| 5 | `permissions` | `MKT-I05` | a permission is forbidden, universal-dangerous, or unsubsumed |
| 6 | `compatibility` | `MKT-I06` | platform or client version is out of range |
| 7 | `advisory` | `MKT-I07` | an open advisory exceeds the policy severity ceiling |
| 8 | `conformance-score` | `MKT-I08` | the score is below the policy floor |
| 9 | `payload-digest` | `MKT-I09` | the payload on disk (or as installed) does not match the signed digest |
| 10 | `sbom` | `MKT-I10` | the SBOM is not a bijection with the payload |
| 11 | `license` | `MKT-I11` | the aggregate or any component licence is not admissible |
| 12 | `dependencies` | `MKT-I12` | a required dependency is unresolvable, or a cycle exists |
| 13 | `lockfile` | `MKT-I13` | `--frozen` and the resolution drifts from the pin |

An install reports SUCCESS only when **all thirteen** have an outcome
(`Attempt.assert_complete`). "Nothing blocking" is not a pass here: a gate that did not run has
told you nothing.

Publish-side refusals are `MKT-P01..MKT-P12`; lint rules are `MKT-L01..MKT-L20`. See
`GOVERNANCE.md` §2 for the publish preconditions and their codes.

## Design rules worth not re-litigating

* **Floats are forbidden in canonical form.** Scores are integers; benchmark values are
  `value_milli`. A float has no portable JSON spelling and would break its own signature.
* **No committed digest, ever.** git stores LF and Windows checks out CRLF, so a committed
  `payload_digest` is right on one platform and wrong on the other. The fixture registry is
  generated into a temp root and every digest is produced and compared inside one run.
* **No committed key material.** Fixture keys are derived from public labels
  (`sha256("mkt-fixture:publisher-alpha")`). The repo holds the label, never the bytes.
* **Absence is never "empty".** `load_revocation` returns `None` for a missing list and the
  trust policy decides what that means; the default is `refuse`.
* **`fs:read:a/**` does NOT cover bare `a`.** `**` means one or more trailing segments. The
  narrower reading is the documented grammar and the safe direction.
* **Deprecation warns, yank hides, revocation blocks.** Three strengths, no overlap.