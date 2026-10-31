---
name: drive-biomni-lab
description: 'Use when the user wants to run a biomedical/clinical-genomics analysis
  on the hosted Biomni Lab (biomni.phylo.bio, Phylo Inc.) from Claude Code - starting
  or continuing a Biomni agent task, controlling effort/model, attaching skills or
  @-resources, polling a run, switching/rotating accounts, or checking usage/billing.
  Triggers: "run this on Biomni", "rotate Biomni accounts", or the bm_* tools.'
permalink: dqverify-repo-20261013/skills/drive-biomni-lab/skill
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
     (`"max"` is accepted as an alias for premium). Use `premium` for hard/multimodal
     work, `fast` for cheap iteration.
   - `submit_initial_message=True` (default) starts the run immediately.
   - To attach **skills** or **@-resources**, instead create with
     `submit_initial_message=False`, then `bm_send_message(session_id, content, …)` +
     `bm_start_processing`.
4. **Attach skills / resources** (via `bm_send_message`):
   - **Skills** → `attached_skills_json` = a JSON array of skills from `bm_list_skills`
     (`{id,name,category,intent:"use"}`); only *active* skills apply
     (`bm_set_skill_status`).
   - **Resources** (tools/databases/packages) → `@name` mentions **inside** `content`
     (e.g. `"@Addgene @airr analyse …"`). There is no separate field.
5. **Watch it** — poll `bm_get_messages` (reliable) for the reasoning/tool trace;
   `bm_session_runtime(session_id, kind=…)` for live compute (`background-processes` |
   `gpu-sandboxes` | `hpc-jobs` | `hpc-pipelines` | `machines`);
   `bm_get_streaming` for a best-effort live peek. Biomni tasks take 30 s–10 min —
   poll a few times, don't spin. `bm_cancel` stops a run.
6. **Results** — `bm_list_results` lists output file names/sizes; the files are
   downloaded from the Biomni web app (not directly). Point the user to the run link.

## Cautions

- **$$$ / billable:** `bm_create_session(submit_initial_message=True)` and
  `bm_start_processing` consume the account's usage (real HPC/GPU). Confirm intent for
  large or repeated runs; rotate accounts with `bm_billing_balance` before one runs dry.
- **`bm_api_raw`** can reach mutating/`DELETE` routes on the user's own account —
  confirm before calling those.
- **Trust but verify Biomni output.** Biomni is an autonomous agent and has produced
  confident-but-wrong numbers/citations before; treat its results as
  hypothesis-generation and have it (or a second pass) self-audit before you rely on them.

## Escape hatch

`bm_api_raw(method, path, body_json, query_json)` calls ANY `api.phylo.bio` endpoint
(e.g. `/v2/users/me/memory`, `/v2/mcp/servers`) — use it for anything the 25 typed
tools don't cover.