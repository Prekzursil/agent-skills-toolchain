# Detection assertion — the "did the detection fire?" loop

Running an atomic proves nothing on its own. The purple loop only pays off when you **assert**
that a detection fired, and you assert it the way `claim-verify-gate` demands: with an
instrument **mechanically different** from the one that produced the action.

## Why claim-verify-gate applies here

`rules/common/single-signal-verification.md`: two signals must be mechanically independent —
"a different shell, a different data field, a different measurement ... not the same query
re-run." Map that onto purple teaming:

- **source probe** = the emulation. The atomic ran under `Invoke-Atomic` on the range VM.
- **verify probe** = the detection. A **SIEM/EDR query** (a different tool, a different field —
  the alert record, not the runner's exit code) reports whether a rule fired.

If the only evidence that "the detection works" is that the atomic "ran successfully", that is
the same tool confirming itself — zero signals. The firing must come from the blue side.

- **Verify the detector before trusting a silence.** A `MISSED` can mean the rule is broken,
  the log source is down, or the emulation window/timezone is wrong. Confirm the pipeline can
  see a *known-present* event first (both-states discipline), else a silence measures nothing.

## The expected-hit manifest (schema)

A JSON object the checker reads. One row per atomic. This is the "documented expected-hit
manifest" the wave contract accepts as the pairing artifact.

```jsonc
{
  "engagement": "owner-lab-2026-09-02",
  "scope": "range VM lab.local 10.10.0.0/24 — owner-owned, isolated",
  "atomics": [
    {
      "id": "T1059.001-1",                 // required, unique
      "technique": "T1059.001",            // required, ATT&CK ID
      "tactic": "execution",               // optional, Navigator grouping
      "name": "PowerShell download cradle", // optional, human label
      "atomic_guid": "3ff36bb1-...",       // reference into ART catalog, NOT the command
      "data_sources": ["PowerShell/4104"], // optional, expected telemetry
      "expected_detections": [             // required to assert; empty = UNVERIFIED
        "sigma_ps_downloadstring",
        {"id": "edr_rule_1234", "evidence": "detections/edr/1234.yml:1"}
      ]
    }
  ]
}
```

- `expected_detections` entries are either a bare id string or an object
  `{"id": "...", "evidence": "<file:line or URL>"}`. The evidence anchor is what lets the
  emitted `claim-verify-gate` ledger pass `claim_gate.py`'s `no-evidence-anchor` rule. If you
  omit it, the checker anchors to the results file path so the ledger still passes; replace it
  with the real rule file or SIEM permalink.
- An atomic with an empty `expected_detections` cannot be asserted — it becomes `UNVERIFIED`
  with a settling experiment ("author an expected detection and re-run"), never a pass.

## The results file

What your lab tooling reports as fired during the emulation window — a file **you export**, so
the checker stays offline. Any of:

```jsonc
["sigma_ps_downloadstring", "edr_rule_1234"]      // a JSON array of fired detection ids
{"fired": ["sigma_ps_downloadstring"]}             // or an object with a "fired" list
```

or a newline-delimited text file of ids. The checker normalises all three.

## Verdicts

| verdict | meaning |
|---|---|
| `DETECTED` | every expected detection for the atomic fired |
| `PARTIAL` | some, but not all, expected detections fired |
| `MISSED` | no expected detection fired — a visibility/detection gap |
| `UNVERIFIED` | the atomic declared no expected detection — cannot assert |

`MISSED` and `PARTIAL` are the backlog. Route them to `detection-as-code` to author/fix the
rule, then re-run the loop to confirm the gap closed.
