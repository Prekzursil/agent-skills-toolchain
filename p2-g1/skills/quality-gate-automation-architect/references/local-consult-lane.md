# Local Consultation Lane

Use this reference when the design includes a local agent sidecar, local Codex app automations, or a local-only scheduler flow.

## When the local lane is useful

- blocked-case diagnosis
- sidecar or IDE consultation
- rich local context not available in CI
- human-in-the-loop design and escalation
- small recurring maintenance jobs that can tolerate machine uptime requirements

## Why it should usually stay secondary

- Local automations depend on the machine, the app, the repo checkout, and any sidecar services staying healthy.
- State drift is more likely across Windows, WSL, VS Code, and mirrored Codex homes than in a hosted CI path.
- A local lane is strong at analysis and iteration, but weaker as the primary unattended executor for PR rescue.

## Sidecar rules to preserve

These were written for the PromptBridge sidecar, which was deleted from this repo on
2026-08-09. Two of the original five were specific to that lane's profile layout and are
dropped as obsolete: they claimed `.codex-vscode` was the canonical managed Codex profile
and `.codex` only a mirror. That is no longer true here — `tools/mcp/workstation-codex-bundle`
records `C:\Users\Prekzursil\.codex` as canonical and `.codex-vscode` as migration input
only. The transferable rules:

- Name ONE canonical agent-home profile and treat every other as read-only migration input;
  say which is which in the design.
- Proof must be reproducible from the canonical profile, not only from a developer's box.
- IDE support is not "done" until a fresh chat in that IDE can actually surface the sidecar
  tool — a registered server is not a mounted tool.
- If the sidecar is unavailable, the design must explicitly fall back to the primary
  non-sidecar lane, and the fallback must be observable rather than silent.

## Good uses for the local lane

- classify whether a failing PR should go to PR repair, coverage ratchet, or debt burn-down
- generate a human-readable remediation memo for blocked runs
- test prompts and workflows before promoting them into CI or app automations
- run small nightly backlog jobs on a trusted machine when the team accepts that dependency

## Bad uses for the local lane

- sole backbone for "while I am away" repo repair
- zero-touch merge authority
- workflows that cannot tolerate VS Code sidecar, auth, or path drift

## Design default

- Keep GitHub or another remote control plane primary for unattended repair.
- Keep local automation and any local sidecar as consultation or backlog-maintenance lanes.
- State the uptime and state-drift tradeoff clearly when recommending a local-first design.
