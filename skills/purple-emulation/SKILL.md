---
name: purple-emulation
description: "Use when validating that detections fire against known adversary techniques on an owner-owned lab range or owner cloud — Atomic Red Team / Invoke-Atomic emulation paired with a detection assertion, an ATT&CK Navigator / DeTT&CT coverage ledger, and Stratus Red Team for owner cloud. Emulation catalog + detection validation only; not for third-party targets and not for authoring offensive capability."
license: "References Atomic Red Team (MIT, Red Canary), Stratus Red Team (Apache-2.0, DataDog), MITRE CALDERA (Apache-2.0), ATT&CK Navigator + DeTT&CT (Apache-2.0 / GPL-3.0, MITRE Engenuity / rabobank-cdc). No tool code is vendored; this skill ships only a stdlib coverage checker."
---

# purple-emulation — adversary emulation for detection validation (lab / owned only)

Purple teaming is one loop, not two teams: a **red action** you already understand,
immediately followed by a **blue assertion** — *did the detection fire?* This skill owns
that loop for an **owner-owned lab range** (or **owner cloud**). It is a detection-validation
harness, not an attack toolkit. The artifact is an **emulation catalog** (techniques to
exercise, keyed to MITRE ATT&CK) plus the mechanical **did-it-fire?** check and a coverage
ledger — never payload generators, C2, or exploit code.

The offensive half is deliberately thin and outsourced: this skill **references** published,
open-source atomics by ATT&CK technique ID and Atomic GUID rather than reproducing attack
commands, and points at the existing execution planes (Invoke-Atomic on the range;
`hexstrike-ai-authorized-engagement` for any authorized active check). Everything this skill
*adds* is blue: the assertion, the ledger, the coverage map, the gap backlog.

## Scope first — the non-negotiable gate

Mirror `hexstrike-ai-authorized-engagement`: **ownership and boundary before any atomic.**
No technique is executed until the target is confirmed to be one of:

- an **owner-owned / owner-operated lab range** (isolated VMs, a detonation network you own), or
- **owner cloud** — a cloud account/subscription/project the owner controls (Stratus Red Team), or
- a target with **explicit written authorization** naming it in scope.

If scope is vague ("test this box", a hostname you do not own, a shared/prod tenant without
authorization), **stop** and ask. Discovered assets do NOT auto-enter scope. This gate is the
first thing to satisfy and the last thing to relax.

## When to use

- The owner wants to know whether their SIEM/EDR/Sigma rules actually catch a given technique.
- Building or refreshing an ATT&CK coverage map (Navigator / DeTT&CT) from real emulation.
- Validating cloud detections against Stratus Red Team on an owner cloud account.
- Standing up a range emulation exercise (CALDERA operation over its REST API on the range).

## When NOT to use

- Any third-party or non-authorized target (see `references/stop-rules.md`, hard ban H1).
- Authoring C2, stealers, ransomware, malware, or exploit PoCs (hard ban H2). This skill will
  not do it; it validates detections against *published* technique catalogs only.
- Live authorized *active testing* of an in-scope target — that rides
  `hexstrike-ai-authorized-engagement`, which stays the execution plane. This skill is the
  detection-assertion loop wrapped around it.
- Installing an always-on BAS daemon or a CALDERA fleet MCP — out of doctrine (0 new daemon).

## Reference map

- `references/atomic-red-team.md` — Invoke-Atomic / Atomic Red Team on a range VM: scope,
  isolation, cleanup, and reference-by-technique (no reproduced payloads).
- `references/detection-assertion.md` — the `claim-verify-gate` "did the detection fire?" loop
  and the **expected-hit manifest** schema.
- `references/coverage-ledger.md` — the ATT&CK Navigator layer + DeTT&CT coverage ledger the
  checker emits, and how to read the gap backlog.
- `references/cloud-and-caldera.md` — Stratus Red Team for **owner cloud**, and CALDERA framed
  as a **range REST** endpoint (explicitly NOT a fleet MCP / always-on daemon).
- `references/stop-rules.md` — H1/H2 hard bans, the HexStrike execution-plane boundary, and the
  degrade-honestly rule.

## The loop

1. **SELECT** — pick a technique to validate (ATT&CK ID, e.g. `T1059.001`). Record the atomic
   you will use by Atomic GUID; do not paste the attack command into this repo.
2. **SCOPE** — confirm range VM / owner cloud / written authorization (gate above). Snapshot
   the range VM so the run is reversible.
3. **EMULATE** — run the atomic on the range via Invoke-Atomic (or Stratus for cloud), then run
   its cleanup. The execution plane is the range; for any authorized *active* check use
   `hexstrike-ai-authorized-engagement`, not new tooling here.
4. **ASSERT** — the blue half. Export which detections fired from *your own* SIEM/EDR for the
   emulation window, and treat "the detection fired" as a **claim to verify with a
   mechanically different instrument** than the one that ran the atomic (`claim-verify-gate`):
   the atomic ran under Invoke-Atomic; the *firing* is confirmed by a SIEM/EDR query. Same tool
   confirming itself is not a signal.
5. **LEDGER** — record each atomic → expected-detection outcome in an expected-hit manifest and
   compute coverage. `DETECTED` / `PARTIAL` / `MISSED` per technique; MISSED is a visibility gap.
6. **CLOSE** — the gap list is the detection-engineering backlog. Route new/edited rules to
   `detection-as-code`; re-run this loop to confirm the gap closed.

## The mechanical half — `scripts/detection_coverage.py`

The judgement (which technique, which instrument is "different") stays with the operator; the
part a model must not be trusted to fudge — *tallying whether expected detections fired* — is
code. Deterministic, stdlib-only, no network, no model call.

```
# score an emulation run against an expected-hit manifest
python3 .agents/skills/purple-emulation/scripts/detection_coverage.py \
    --manifest manifest.json --results fired.json

# also emit an ATT&CK Navigator layer and a claim-verify-gate ledger
python3 .agents/skills/purple-emulation/scripts/detection_coverage.py \
    --manifest manifest.json --results fired.json \
    --navigator layer.json --ledger ledger.json --format json

# prove the checker distinguishes a firing detection from a silent one (both-states)
python3 .agents/skills/purple-emulation/scripts/detection_coverage.py --self-test
```

- `--manifest` is the expected-hit manifest (schema in `references/detection-assertion.md`).
- `--results` is the list of detection IDs your lab tooling reports as fired (a file you
  export; the checker never touches the network).
- `--navigator` writes an ATT&CK Navigator v4.5 layer coloured by coverage.
- `--ledger` writes a `claim-verify-gate` ledger so each "detection fired" claim can be run
  through `claim_gate.py` — the two skills chain.
- Exit `0` full coverage · `1` a gap (MISSED/PARTIAL) exists · `2` unusable input.

Chaining into the verify gate (the emitted ledger is built to pass it):

```
python3 .agents/skills/claim-verify-gate/scripts/claim_gate.py --claims ledger.json
```

## Stop rules

- **H1 — never a third-party target.** Range VM / owner cloud / explicitly authorized only.
- **H2 — never author offensive capability.** No C2, stealers, ransomware, malware, exploit
  PoCs, or attack procedures. Reference published atomics by ID; do not reproduce payloads.
- **HexStrike stays the execution plane** for authorized active checks; this skill adds the
  detection assertion and coverage ledger around it, it does not replace it.
- **No always-on daemon.** CALDERA is a range REST endpoint you start for an exercise and stop
  after; it is not a fleet MCP and not registered in `.agents/agents.json`.
- **Degrade honestly.** If a detection cannot be confirmed by an independent instrument, the
  verdict is `MISSED`/`UNVERIFIED`, never an assumed `DETECTED`.

## Composes with

- `claim-verify-gate` — the did-it-fire assertion; the emitted ledger feeds `claim_gate.py`.
- `detection-as-code` — where MISSED gaps become new/edited Sigma rules (the close step).
- `hexstrike-ai-authorized-engagement` — the authorized active-testing execution plane.
- `dfir-triage` — the log/artifact sources the detections read from.

## Sources

- Red Canary, *Atomic Red Team* (MIT) — atomics keyed to MITRE ATT&CK; Invoke-AtomicRedTeam runner.
- DataDog, *Stratus Red Team* (Apache-2.0) — cloud-native attack emulation for owner cloud.
- MITRE, *CALDERA* (Apache-2.0) — adversary emulation platform with a REST API for range operations.
- MITRE Engenuity, *ATT&CK Navigator* — coverage layer format; rabobank-cdc *DeTT&CT* — detection coverage scoring.
