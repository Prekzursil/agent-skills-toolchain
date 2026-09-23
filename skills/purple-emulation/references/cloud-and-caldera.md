# Stratus Red Team (owner cloud) and CALDERA (range REST)

Two range-scale emulation planes beyond single-host atomics. Both are **owner-owned only** and
neither is a payload builder or an always-on service.

## Stratus Red Team — owner cloud only

Stratus Red Team (DataDog, Apache-2.0) is "Atomic Red Team for the cloud": a catalog of cloud
attack techniques (AWS / Azure / GCP / Kubernetes) each mapped to MITRE ATT&CK, with a built-in
`detonate` → `revert` lifecycle. It exists to validate **cloud detections** (GuardDuty, CloudTrail
rules, Azure/GCP alerts) against real technique execution.

- **Owner cloud only.** Point it at a cloud account/subscription/project the owner controls,
  via the owner's own credentials (env NAME only, e.g. `${AWS_PROFILE}` — never a shared or
  production tenant, never a third-party account). This is the H1 gate in cloud form.
- Enumerate before running: `stratus list`, `stratus show <technique-id>`.
- Lifecycle: `stratus detonate <id>` then **always** `stratus revert <id>` / `stratus cleanup <id>`.
  Each technique documents the ATT&CK id it emulates and the detection it is meant to trip.
- Feed the technique id + expected cloud detection into the same expected-hit manifest; the
  coverage checker treats cloud atomics identically to host atomics.

Reference, do not vendor: <https://github.com/DataDog/stratus-red-team>. Stratus writes its own
warm-up/cleanup; this skill adds the detection assertion around it, no cloud attack code here.

## CALDERA — a range REST endpoint, NOT a fleet MCP

MITRE CALDERA (Apache-2.0) runs multi-step adversary-emulation operations across a range using
agents and an ability library. In this estate it is used as a **range REST endpoint you start
for an exercise and stop after** — explicitly:

- **NOT a fleet MCP.** CALDERA is *not* registered in `.agents/agents.json` and *not* wired onto
  the MCP bus. It is not an always-on daemon in the agent runtime (0-new-daemon doctrine).
- **NOT third-party.** Its agents run only on **range hosts you own**. Operations are launched
  against the owner range, never external infrastructure.
- **REST, on demand.** Drive it through its documented REST API (`/api/v2/...`, `KEY` header from
  `${CALDERA_API_KEY}`) *while an exercise is running on the range*, then shut the server down.
  Read operation results (which abilities ran, which ATT&CK techniques) and fold the technique
  ids into the expected-hit manifest for the same coverage assertion.

CALDERA is the multi-step range plane; Invoke-Atomic is the single-technique plane; Stratus is
the cloud plane. All three produce the same thing this skill cares about: a list of ATT&CK
techniques that were exercised, to assert detections against.

Reference: <https://github.com/mitre/caldera>. Do not build abilities that are C2/payload/
exploit code (H2); use the published ability library on the owner range.

## What none of these do here

- No payload generation, no stager/implant building, no exploit development.
- No pointing any of the three at a target the owner does not own or is not authorized to test.
- No standing service: start for the exercise, stop after, keep results in the manifest/ledger.
