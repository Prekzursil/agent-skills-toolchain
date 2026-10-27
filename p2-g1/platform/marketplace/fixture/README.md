# The test fixture marketplace

This directory holds the **committed sources**. The live registry is **built**, never committed —
`mkt.fixture.build(work_root)` (or `python -m mkt fixture --into <dir>`) assembles it into a
caller-supplied root. Three measured reasons for that split:

1. **A committed digest would be wrong on one platform.** git stores LF, Windows checks out CRLF,
   so a committed `payload_digest` or `manifest_digest` is correct on exactly one of them. Building
   into a temp root means every digest is computed and compared inside a single run on a single
   filesystem, which is the only comparison that means anything.
2. **A committed signature needs committed key bytes.** Fixture identities are derived from public
   labels — `sha256("mkt-fixture:alpha-tools")` — so this repository contains the label that
   reproduces a key and never the key. These are local test keys, not credentials of this estate.
3. **The adversarial packages must not be committed.** `secret-leaker` exists to prove the payload
   scanner fires; committing a credential-shaped string to satisfy a test would trip this
   repository's own secret gates and teach exactly the wrong lesson. It is synthesised at build
   time in `mkt/fixture.py` from an obviously-fake literal and only ever lives in a temp root.

## What is here

| path | role |
|---|---|
| `trust-policy.json` | the CONSUMER policy: fail-closed on every absence, `fs:read:packages/**` ceiling, `secrets:read` and `exec:process` forbidden outright. Its `registry_maintainer_keys` holds an all-zero PLACEHOLDER so the committed file is schema-valid; `mkt.fixture.trust_policy()` substitutes the derived key. |
| `LICENSE` | the licence BASIS the `license-basis-present` publish precondition points at. Removing it makes `mkt publish` refuse with `MKT-P05`, which is the both-states control for that gate. |
| `packages/hello-skill-1.0.0/` | the control package: stable, MIT, one narrow permission. Published, installed, verified, revoked. |
| `packages/hello-skill-1.1.0/` | same package on `beta`. Proves channel filtering is a filter, not a fallback, and is the update/rollback target. |
| `packages/dep-consumer-1.0.0/` | depends on `hello-skill ^1.0.0` plus one OPTIONAL dependency published nowhere. Proves transitive install, optional-vs-required, and remove-with-dependants refusal. |
| `packages/vulnerable-lib-1.0.0/` | structurally perfect, blocked by a signed advisory. Proves vulnerability status is derived at install time, not stored on the package. |

## Synthesised at build time (`mkt/fixture.py`)

| package | must be refused with |
|---|---|
| `evil-overreach` | `MKT-P07` at publish, `MKT-I05` at install even from a signed index |
| `secret-leaker` | `MKT-P06` — payload carries a fake credential and an absolute owner path |
| `apache-mixer` | `MKT-P08` — Apache-2.0 component under a declared MIT aggregate (the TOURNAMENT-VERDICT M1 shape) |

`fixture.build()` RETURNS those refusals rather than swallowing them, and
`test_fixture_refuses_every_adversarial_package_with_the_expected_code` asserts each one arrived
with the expected code. **A fixture marketplace in which everything publishes cannot demonstrate
that anything is enforced** — the negative cases are as much of the fixture as the positive ones.

## Also built

One private mirror (`mirrors/private-a`) in `verify-and-require-primary-index` mode, one curated
collection (`col:starter`), an empty-but-SIGNED revocation list — present-and-empty is a different
fact from absent, and the fail-closed installer treats them differently on purpose — and a signed
advisory list carrying `adv:2026-0001` against `vulnerable-lib`.
