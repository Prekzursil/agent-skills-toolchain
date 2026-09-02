# Atomic Red Team / Invoke-Atomic on a range VM (owner lab only)

Atomic Red Team (Red Canary, MIT) is a library of small, portable tests ("atomics") each
keyed to a MITRE ATT&CK technique. It is a **detection-validation** catalog: you run one
atomic on a machine **you own**, then check whether your detections saw it. This reference
covers running it safely on a range VM. It deliberately does **not** reproduce atomic
commands — reference them by technique ID and Atomic GUID and let the runner fetch them.

## The runner

`Invoke-AtomicRedTeam` is the PowerShell execution framework (cross-platform via PowerShell 7).
The operator installs it and the atomics on the **range VM**, not on this repo host.

- Enumerate what an atomic will do *before* running it: `Invoke-AtomicTest <Txxxx> -ShowDetails`
  (or `-ShowDetailsBrief`). Read the prerequisites and the cleanup command first.
- Run a specific atomic by number: `Invoke-AtomicTest <Txxxx> -TestNumbers <n>`.
- Always run cleanup after asserting: `Invoke-AtomicTest <Txxxx> -TestNumbers <n> -Cleanup`.
- Prefer `-GetPrereqs` over hand-fetching payloads; never paste an atomic's command into this
  repository (that is an attack procedure — H2).

Reference the catalog, do not vendor it: <https://github.com/redcanaryco/atomic-red-team>
(`atomics/<Txxxx>/<Txxxx>.yaml` and `.md`). The Atomic GUID in each YAML is the stable handle
to record in your manifest.

## Range hygiene (reversible, isolated, cleaned up)

1. **Snapshot** the range VM before the run so the whole thing is revertible.
2. **Isolate** the range network (host-only / detonation VLAN). No route to third-party or
   production systems — that is the H1 gate in `stop-rules.md`.
3. **One technique at a time**, so a firing (or a silence) maps to exactly one atomic.
4. **Cleanup** every atomic, then **revert to snapshot** for a clean baseline before the next.
5. **Record the emulation window** (start/stop timestamps) — the SIEM/EDR export in the
   assertion step is scoped to that window.

## What to record per atomic (feeds the expected-hit manifest)

| field | example | why |
|---|---|---|
| `technique` | `T1059.001` | ATT&CK ID — the coverage-ledger key |
| `atomic_guid` | `3ff36bb1-...` | stable handle into the ART catalog (NOT the command) |
| `tactic` | `execution` | Navigator/DeTT&CT grouping |
| `data_sources` | `["PowerShell/4104"]` | which telemetry SHOULD have seen it |
| `expected_detections` | `["sigma_ps_downloadstring"]` | the rules you assert must fire |

The command itself lives only on the range, fetched by the runner. This repo stores the
*catalog reference and the assertion*, never the payload.

## Not here

- No payload generation, obfuscation, or weaponization.
- No C2 beaconing setup (CALDERA's range agent is covered separately as a REST operation, not
  a payload builder).
- No running atomics against anything you do not own or are not authorized to test.
