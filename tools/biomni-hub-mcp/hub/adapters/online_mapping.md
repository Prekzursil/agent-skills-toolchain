# Online backend adapter — canonical tool → phylo v2 mapping (dry-run)

`hub/adapters/online.py` (`OnlineBiomniAdapter`) routes the hub's 10 canonical
tools to the hosted **Biomni Lab** (`api.phylo.bio/v2`). It is a faithful
in-process port of cloud-hub's `bm_*` REST client
(`agent-skills-toolchain/tools/mcp/cloud-hub/biomni-mcp/server.py`) — the
**reference contract**. Envelope on every call: `{ok, status, data}` (success)
or `{ok:false, error, backend:"online", status?, response?}` (failure). Auth =
Bearer/broker, identical to the reference. `base_url` configurable via
`BIOMNI_API_BASE` env or the `api_base` ctor arg.

## The 10 canonical tools

| # | Canonical tool | Adapter method | Reference `bm_*` | phylo v2 endpoint | Lifecycle fields preserved |
|---|----------------|----------------|------------------|-------------------|-----------------------------|
| 1 | create_project | `create_project(name, description="")` | `bm_create_project` | `POST /v2/projects` | `project_id` (id/proj_id) |
| 2 | list_projects | `list_projects()` | `bm_list_projects` | `GET /v2/projects` | `projects[]` |
| 3 | list_workspaces | `list_workspaces()` | *(none — derived)* | `GET /v2/workspaces` (provisional) → fallback `GET /v2/auth/me` | `workspaces[]{id,name,current}` |
| 4 | switch_workspace | `switch_workspace(workspace_id)` | *(none — stateful)* | `POST /v2/workspaces/{id}/activate` (best-effort) + local bind | `workspace_id`, `current` |
| 5 | upload_file | `upload_file(local_path, dest_name=None, project_id=None)` | *(none)* | `POST /v2/files/upload` (provisional) | `name`, `size` |
| 6 | start_new_task | `start_new_task(prompt, project_id=None, model_profile="standard", attached_skills=None, resources=None)` | `bm_create_session` (+`bm_send_message`+`bm_start_processing` when attaching) | `POST /v2/agent/sessions/create` (compose: `+ POST /v2/agent/{sid}/user_message` `+ POST /v2/agent/{sid}/start_processing?message_id=`) | **`task_id`**(=session_id), `project_id`, `message_id`, `status`, `biomni_url`, `display_instruction`, `model_profile` |
| 7 | send_message | `send_message(task_id, message, attached_skills=None, is_clarification_response=False)` | `bm_send_message` + `bm_start_processing` | `POST /v2/agent/{sid}/user_message` → `POST /v2/agent/{sid}/start_processing?message_id=` | `task_id`, `message_id`, `status`, `biomni_url` |
| 8 | wait_for_next_update | `wait_for_next_update(task_id, since=None, timeout_s=120, poll_interval=3)` | `bm_get_messages` (+`bm_get_session`; `bm_get_streaming` best-effort) | poll `GET /v2/agent/{sid}/messages` + `GET /v2/agent/{sid}` (status) | `task_id`, `status`, `cursor`, `done`, `new_messages[]`, `new_log[]`, `result_files[]`(on done), `biomni_url`, `display_instruction` |
| 9 | list_tasks | `list_tasks(project_id=None)` | `bm_list_sessions` | `GET /v2/agent/projects/{pid}/sessions` (aggregates all projects when `pid` omitted) | `tasks[]` |
| 10 | list_result_files | `list_result_files(task_id=None)` | `bm_list_results` | `GET /v2/files/results` (client-side filter by `task_id`) | `result_files[]{name,size,path,session_id}` |

## Beyond the 10 (parity with `databricks.py`)

| Method | phylo v2 | Notes |
|--------|----------|-------|
| `name` (property) | — | returns `"online"` |
| `status()` | `GET /v2/auth/me` | `biomni_backends` catalog entry: `available`, `identity`, `auth_mode`, `execution_model`, `cost_hint`. Never raises (fail-closed). |
| `fetch_artifact(task_id, name)` | `GET /v2/files/results/{task_id}/{name}` (provisional) | Online sandbox paths are **not** API-fetchable → returns a web-download hint, not bytes (Databricks backend returns real bytes). |
| `build_adapter(**overrides)` | — | factory the selector calls |

## Task-lifecycle mapping (the async protocol the hub relies on)

```
start_new_task(prompt)
    └─ POST /v2/agent/sessions/create {project_id, content, model_profile,
                                       submit_initial_message: true}
           → data.session_id  ==>  task_id            (biomni_url = web/session/{sid})
           (submit_initial_message already RUNS the first turn)

    when attached_skills/resources present (app-required compose path):
       POST .../sessions/create {submit_initial_message: false}
       POST /v2/agent/{sid}/user_message {content:"@res ...", attached_skills}
                                                          → message_id
       POST /v2/agent/{sid}/start_processing?message_id={message_id}

send_message(task_id, msg)
       POST /v2/agent/{task_id}/user_message   → message_id
       POST /v2/agent/{task_id}/start_processing?message_id={message_id}

wait_for_next_update(task_id, since=cursor)
       loop: GET /v2/agent/{task_id}/messages         (reliable trace)
             GET /v2/agent/{task_id}                  (status → done?)
       → new_messages = messages[cursor:] ; cursor = len(messages)
       → done when status ∈ {completed, failed, cancelled, ...}
       → on done: result_files = list_result_files(task_id)

list_result_files(task_id)
       GET /v2/files/results  → [{name, size, path, session_id}]
       (filter rows to task_id when they carry a session ref)
```

## Auth resolution (ported from the reference client)

`_resolve_token()` priority: **broker** (`BIOMNI_BROKER=1` or loopback
`BIOMNI_API_BASE` → `Bearer broker` sentinel; a local proxy injects the real
cookie/Bearer) → **explicit** ctor `token` → **`BIOMNI_TOKEN`** (static session
Bearer) → **`BIOMNI_REFRESH_TOKEN`** (minted to short-lived access tokens via
the WorkOS refresh grant, cached in-process). No credential is ever logged.

## Provisional routes — verify when the reference MCP is connected

`mcp__claude_ai_Biomni_Lab__*` was NOT live during authoring, and cloud-hub's
`bm_*` does not cover *workspaces* or *file upload*. `list_workspaces`,
`switch_workspace`, `upload_file`, and `fetch_artifact` use the most-likely
`/v2` routes, try them first, and **degrade gracefully** (never hard-fail):
identity-derived workspace, local workspace bind, web-upload/web-download hints.
Swap for verified routes once the official connector's traffic is observed.
