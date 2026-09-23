---
name: "security-threat-model"
description: Repository-grounded threat modeling that enumerates trust boundaries, assets, attacker capabilities, abuse paths, and mitigations, and writes a concise Markdown threat model. Trigger only when the user explicitly asks to threat model a codebase or path, enumerate threats/abuse paths, or perform AppSec threat modeling. Not for general architecture summaries or code review.
---

# Threat Model Source Code Repo

Deliver an actionable AppSec-grade threat model that is specific to the repository or a project path, not a generic checklist. Anchor every architectural claim to evidence in the repo and keep assumptions explicit. Prioritizing realistic attacker goals and concrete impacts over generic checklists.

## Quick start

1) Collect (or infer) inputs:
- Repo root path and any in-scope paths.
- Intended usage, deployment model, internet exposure, and auth expectations (if known).
- Any existing repository summary or architecture spec.
- Use prompts in `references/prompt-template.md` to generate a repository summary.
- Follow the required output contract in `references/prompt-template.md`. Use it verbatim when possible.

## Workflow

### 1) Scope and extract the system model
- Identify primary components, data stores, and external integrations from the repo summary.
- Identify how the system runs (server, CLI, library, worker) and its entrypoints.
- Separate runtime behavior from CI/build/dev tooling and from tests/examples.
- Map the in-scope locations to those components and exclude out-of-scope items explicitly.
- Do not claim components, flows, or controls without evidence.

### 2) Derive boundaries, assets, and entry points
- Enumerate trust boundaries as concrete edges between components, noting protocol, auth, encryption, validation, and rate limiting.
- List assets that drive risk (data, credentials, models, config, compute resources, audit logs).
- Identify entry points (endpoints, upload surfaces, parsers/decoders, job triggers, admin tooling, logging/error sinks).

### 3) Calibrate assets and attacker capabilities
- List the assets that drive risk (credentials, PII, integrity-critical state, availability-critical components, build artifacts).
- Describe realistic attacker capabilities based on exposure and intended usage.
- Explicitly note non-capabilities to avoid inflated severity.


### 4) Enumerate threats as abuse paths
- Prefer attacker goals that map to assets and boundaries (exfiltration, privilege escalation, integrity compromise, denial of service).
- Classify each threat and tie it to impacted assets.
- Keep the number of threats small but high quality.

### 5) Prioritize with explicit likelihood and impact reasoning
- Use qualitative likelihood and impact (low/medium/high) with short justifications.
- Set overall priority (critical/high/medium/low) using likelihood x impact, adjusted for existing controls.
- State which assumptions most influence the ranking.

### 6) Validate service context and assumptions with the user
- Summarize key assumptions that materially affect threat ranking or scope, then ask the user to confirm or correct them.
- Ask 1–3 targeted questions to resolve missing context (service owner and environment, scale/users, deployment model, authn/authz, internet exposure, data sensitivity, multi-tenancy).
- Pause and wait for user feedback before producing the final report.
- If the user declines or can’t answer, state which assumptions remain and how they influence priority.

### 7) Recommend mitigations and focus paths
- Distinguish existing mitigations (with evidence) from recommended mitigations.
- Tie mitigations to concrete locations (component, boundary, or entry point) and control types (authZ checks, input validation, schema enforcement, sandboxing, rate limits, secrets isolation, audit logging).
- Prefer specific implementation hints over generic advice (e.g., "enforce schema at gateway for upload payloads" vs "validate inputs").
- Base recommendations on validated user context; if assumptions remain unresolved, mark recommendations as conditional.

### 8) Run a quality check before finalizing
- Confirm all discovered entrypoints are covered.
- Confirm each trust boundary is represented in threats.
- Confirm runtime vs CI/dev separation.
- Confirm user clarifications (or explicit non-responses) are reflected.
- Confirm assumptions and open questions are explicit.
- Confirm that the format of the report matches closely the required output format defined in prompt template: `references/prompt-template.md`
- Write the final Markdown to a file named `<repo-or-dir-name>-threat-model.md` (use the basename of the repo root, or the in-scope directory if you were asked to model a subpath).


## Risk prioritization guidance (illustrative, not exhaustive)
- High: pre-auth RCE, auth bypass, cross-tenant access, sensitive data exfiltration, key or token theft, model or config integrity compromise, sandbox escape.
- Medium: targeted DoS of critical components, partial data exposure, rate-limit bypass with measurable impact, log/metrics poisoning that affects detection.
- Low: low-sensitivity info leaks, noisy DoS with easy mitigation, issues requiring unlikely preconditions.

## Defending-Code Review Flow (`/threat-model` → `/vuln-scan` → `/triage` → `/patch`)

> **Attribution:** This flow adapts **Anthropic's defending-code reference
> harness** (the Claude Code security-review reference:
> <https://github.com/anthropics/claude-code-security-review>). The stages below
> are an original summary that **points at this estate's existing skills** — it
> adds **no new daemon, MCP server, or slash-command runtime**. The `/name`
> labels are stage names, not installed commands; each stage is "invoke skill X".

Use this when a threat model should drive an end-to-end find-and-fix pass, not
just a document. Each stage consumes the previous stage's output, and the whole
loop rides the skill bus:

### `/threat-model` → this skill

Run the workflow above to produce the repo-grounded threat model: trust
boundaries, assets, attacker capabilities, ranked abuse paths. **Output that
scopes everything downstream:** the prioritized list of high-risk boundaries and
entry points. Do not scan blind — let the model aim the scanners.

### `/vuln-scan` → `$semgrep` + `$code-security` + `$security-review`

Enumerate candidate vulnerabilities across the paths the threat model marked
high-priority. This is the *static* first pass (Stage 1 of the `$security-review`
scanner-driven loop). Treat findings as leads, ordered by reachability from the
abuse paths above — not as verdicts.

### `/triage` → `$security-review` loop + `$claim-verify-gate`

Confirm true positives and discard scanner noise. Apply the `$security-review`
differential + variant stages, and gate each finding through `$claim-verify-gate`
("is this reachable and real?") before it counts. Rank surviving findings by the
threat model's impact rating, not the scanner's default severity.

### `/patch` → minimal fix + re-scan + variant rule

For each confirmed finding, propose the smallest fix tied to the concrete
location (component / boundary / entry point) named in the threat model. Then:
re-run `/vuln-scan` to prove the finding is closed, and commit a `$security-review`
Stage-3 variant rule so the pattern cannot silently return.

**Loop:** `/threat-model` scopes → `/vuln-scan` finds → `/triage` confirms →
`/patch` fixes → re-scan. Defensive, authorized/own-repo only; no exploit code is
produced at any stage — a confirmed finding yields a *fix and a detection*, not a
PoC.

## References

- Output contract and full prompt template: `references/prompt-template.md`
- Optional controls/asset list: `references/security-controls-and-assets.md`
- Anthropic Claude Code security review (reference harness this flow adapts): <https://github.com/anthropics/claude-code-security-review>

Only load the reference files you need. Keep the final result concise, grounded, and reviewable.
