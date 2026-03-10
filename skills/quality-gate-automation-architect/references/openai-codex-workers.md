# OpenAI Codex Workers

Use this reference when Codex is a candidate worker in CI, the Codex app, or local tooling.

## Where Codex fits

- Codex can pair locally in the terminal, IDE, or Codex app.
- Codex can also be delegated in the cloud to run tasks in an isolated sandbox.
- The Codex app includes worktrees, skills, automations, and Git support.

This makes Codex stronger than a pure GitHub-native agent when the user wants one worker model across local, app, and CI surfaces.

## Codex app automations

- Codex app automations run locally in the Codex app.
- The app must be running, and the selected project must be available on disk.
- In Git repositories, each automation run uses a dedicated background worktree.
- Automations use the default sandbox settings, so write or network behavior depends on those settings.
- OpenAI recommends testing the prompt manually first, then reviewing the first few scheduled outputs closely.
- Skills can be invoked explicitly inside automations by using `$skill-name` in the automation prompt.

## Codex GitHub Action

The Codex GitHub Action exists for CI and workflow use:

- `openai/codex-action@v1` runs `codex exec` from GitHub Actions.
- It expects an API key secret such as `OPENAI_API_KEY`.
- It supports `prompt` or `prompt-file`, `codex-args`, `sandbox`, `model`, `effort`, and `output-file`.
- `codex-args` can include flags such as `--full-auto`.
- The action exposes `safety-strategy`, `sandbox`, and trigger allowlists to reduce risk.

Safe defaults from the docs:

- check out the repo before invoking the action
- prefer Linux or macOS runners
- keep `safety-strategy: drop-sudo`
- choose the narrowest workable sandbox
- treat prompt input from PR text or issue bodies as prompt-injection risk

## When Codex should be the primary worker

- The user wants stronger prompt control than GitHub-native agents expose.
- The workflow needs custom stop rules, output schema, or lane-specific prompt templates.
- The same automation logic should work in CI and local or app workflows.

## When Codex should stay secondary

- The user mainly needs GitHub-governed unattended repair and values boring governance over worker customization.
- The organization already standardizes on GitHub's native agent review model.

## Design heuristics

- Keep GitHub as the control plane when true unattended PR rescue matters.
- Use Codex as the repair worker when the prompts and lane separation need to be explicit.
- Use Codex app automations for backlog maintenance, summaries, or local recurring jobs, not as the only unattended backbone.
- Keep prompt files versioned in-repo when the workflow must be auditable.
