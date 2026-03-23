# Local Consultation Lane

Use this reference when the design includes PromptBridge, local Codex app automations, or a local-only scheduler and sidecar flow.

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

## PromptBridge rules to preserve

- `.codex-vscode` is the canonical managed Codex profile.
- `.codex` is a compatibility mirror only.
- CLI proof must work from canonical and mirror profiles.
- VS Code support is not "done" until a fresh chat can surface the sidecar tool.
- If the sidecar is unavailable, the design should explicitly fall back to the primary non-sidecar lane.

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
- Keep local automation and PromptBridge as consultation or backlog-maintenance lanes.
- State the uptime and state-drift tradeoff clearly when recommending a local-first design.
