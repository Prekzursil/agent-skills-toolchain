---
name: drive-biomni-lab
description: Use when the user wants to run a biomedical/clinical-genomics analysis on the hosted Biomni Lab (biomni.phylo.bio, Phylo Inc.) from Claude Code — starting or continuing a Biomni agent task, controlling effort/model, attaching skills or @-resources, polling a running run, switching/rotating Biomni accounts, or checking Biomni usage/billing. Triggers include "run this on Biomni", "ask Biomni to…", "start a Biomni task", "rotate Biomni accounts", "which Biomni account", or mentions of the bm_* tools. Applies to the cloud-hub `biomni` backend driven through the local cookie-broker.
---

# Drive Biomni Lab (hosted) via the cookie-broker connector

The cloud-hub **`biomni`** backend exposes 25 `bm_*` tools that drive the hosted
Biomni Lab far beyond its official 10-tool claude.ai connector — **effort control,
skills, @-resources, live HPC/GPU introspection, usage-aware account rotation** —
while **never handling the credential** (a local broker injects the `session_id`
cookie; you only ever see masked previews). Setup + architecture:
`tools/mcp/cloud-hub/biomni-mcp/README.md`.

## Preconditions (fail fast, don't improvise auth)

- The `bm_*` tools are live (hub restarted after the backend was registered).
- For each account, its **daemons are running** — debug Chrome (signed in) + broker +
  refresher (see the biomni-mcp README / `autostart.py`).
- If a call returns **401 / no-auth**, the account's cookie is stale → tell the user to
  ensure that account's debug Chrome is signed in and its refresher is running. **Do
  NOT** try to obtain or paste a token yourself — auth is the broker's job.

## The task loop

1. **Pick the account** — `bm_account_list` / `bm_account_current`; switch with
   `bm_account_switch` or rotate with `bm_account_cycle`. Before a heavy run, check
   `bm_billing_balance` and rotate to an account with headroom (runs consume usage).
2. **Pick a project** — `bm_list_projects` (or `bm_create_project`).
3. **Start a task** — `bm_create_session(project_id, content, model_profile=…)`:
   - `model_profile` is the EFFORT tier: `standard` (default) | `fast` | `premium`

### Cautions
### Escape hatch
