# Stop rules — the hard bans and the execution-plane boundary

These are not guidelines; they are gates. If any is unmet, stop and report rather than proceed.

## H1 — never a third-party target

Emulation runs **only** on:

- an owner-owned / owner-operated **lab range** (isolated VMs, a detonation network), or
- **owner cloud** (an account/subscription/project the owner controls), or
- a target with **explicit written authorization** naming it in scope.

Vague scope ("test this site", an IP you cannot attribute to the owner, a shared/production
tenant without authorization) means **stop**. Discovered assets do not auto-enter scope. A
banner or a reachable port is not authorization.

## H2 — never author offensive capability

This skill validates detections against **published** technique catalogs. It will not:

- write or generate C2 servers, beacons, implants, or stagers;
- write stealers, ransomware, wipers, or other malware;
- write or adapt exploit PoCs or attack procedures;
- reproduce atomic *commands* into this repository (reference them by ATT&CK id / Atomic GUID).

If a request needs any of the above, refuse that sub-part and deliver the maximum
detection-validation subset that does not.

## HexStrike is the execution plane

Authorized **active** testing of an in-scope target rides the existing
`hexstrike-ai-authorized-engagement` skill, which already enforces scope-first and reports
tool availability from the local `/health`. This skill does **not** re-implement an active
scanner or attack runner; it wraps the **detection assertion and coverage ledger** around that
execution plane. Route active checks there; keep the blue half here.

## No always-on daemon

CALDERA, Stratus, and any range service are **on-demand for an exercise**, started and stopped
by the operator. None is registered as an MCP in `.agents/agents.json`; none runs as a
persistent daemon in the agent runtime. (0-new-daemon doctrine.)

## Degrade honestly

- If a detection's firing cannot be confirmed by an **independent** instrument (a SIEM/EDR
  query separate from the runner), the verdict is `MISSED` or `UNVERIFIED` — never an assumed
  `DETECTED` (`claim-verify-gate`).
- If a log source is down or the emulation window is wrong, a silence measures nothing —
  verify the detector against a known-present event first.
- Report what was actually emulated and asserted; do not paint the ATT&CK matrix green beyond
  the techniques the manifest covers.

## If a platform safeguard blocks a sub-part

State it plainly in the receipt and ship the maximum defensive / detection-validation subset
that remains in policy. The defensive half of purple teaming — the assertion, the ledger, the
coverage map — is the point of this skill and is fully in policy.
