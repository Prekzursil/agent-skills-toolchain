# `ready_units.py --self-test` control fixtures

`IMP-0433-state-SUCCESS-mutant.json` is a byte-copy of `command-center/receipts/IMP-0433.json`
with exactly ONE field changed: `state` `BLOCKED` -> `SUCCESS`.

It is the **known-broken state** for the contract-vacuity guard. Measured 2026-08-12:

| predicate | verdict on this fixture |
|---|---|
| the predicate shipped on 2026-08-12 (declared contract only) | `delivered=True` — FALSE GREEN |
| the same predicate + condition 4b (vacuity guard + fallback)  | `delivered=False (receipt-errors=3)` |

Why it is a false green without the guard: IMP-0433's catalog row declares
`command-center/schema/meta/json-schema-draft.json`, the draft-2020-12 meta-schema, which accepts
any JSON object — so condition 4 cannot fail for it and the whole predicate collapses to the
`state` field, which is one word away from SUCCESS.

Regenerate with `python command-center/p2-wave/_r2_mkfixture.py` if the source receipt changes.
Do not hand-edit: the fixture must differ from the real receipt in exactly one field, or the
control stops isolating the defect it was built to catch.
