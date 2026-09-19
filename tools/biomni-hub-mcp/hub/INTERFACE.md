# biomni-hub adapter interface (A1 → A2 + B1 contract)

Component **A1** (`hub/`) defines the canonical tool surface, the backend
selector, and the interface below. Components **A2** (online) and **B1**
(databricks) implement this interface — they do **not** redeclare tool names,
parameters, or result shapes; they import them from `schema.py`.

Coordinate any change to this file across A1/A2/B1.

## What each adapter module must expose

Each adapter is a module importable by name (they must be on `sys.path` next to
`backends.py`):

| Backend      | Module                  | Factory                       |
|--------------|-------------------------|-------------------------------|
| `online`     | `online_adapter.py`     | `get_backend() -> BiomniBackend` |
| `databricks` | `databricks_adapter.py` | `get_backend() -> BiomniBackend` |

`get_backend()` is a zero-arg factory returning an instance of
`backends.BiomniBackend`. It should be cheap and side-effect-light (construction,
not network I/O) — `backends.load_backend` caches the result per process and sets
`.name`. Config comes from env / the existing `bm_*` / `dbx_*` credential stores;
do not require constructor args.

If construction genuinely cannot proceed (missing package, unconfigured creds),
`get_backend()` may raise — `load_backend` wraps it in `AdapterUnavailable`, and
the `biomni_backends` catalog reports the backend as `available: false` with the
reason. Prefer, however, to construct successfully and report degraded state via
`describe()` (so per-tool errors are specific).

## The `BiomniBackend` interface

Subclass `backends.BiomniBackend` and implement every method. All ten tool
methods are **synchronous** and return a `schema.ToolEnvelope`. The async *task*
model is expressed through `start_new_task` + `wait_for_next_update`, not Python
async.

```python
from backends import BiomniBackend
from schema import Backend, BackendDescriptor, ResultFile, ToolEnvelope


class OnlineBackend(BiomniBackend):
    name = Backend.ONLINE.value

    def describe(self) -> BackendDescriptor: ...

    def create_project(self, name: str, description: str = "") -> ToolEnvelope: ...
    def list_projects(self) -> ToolEnvelope: ...
    def list_workspaces(self) -> ToolEnvelope: ...
    def switch_workspace(self, workspace_id: str) -> ToolEnvelope: ...
    def upload_file(self, local_path: str, project_id: str = "", destination: str = "") -> ToolEnvelope: ...
    def start_new_task(self, project_id: str, prompt: str, model_profile: str = "standard") -> ToolEnvelope: ...
    def send_message(self, task_id: str, content: str) -> ToolEnvelope: ...
    def wait_for_next_update(self, task_id: str, timeout_seconds: float = 60.0) -> ToolEnvelope: ...
    def list_tasks(self, project_id: str = "") -> ToolEnvelope: ...
    def list_result_files(self, task_id: str = "") -> ToolEnvelope: ...


def get_backend() -> BiomniBackend:
    return OnlineBackend()
```

### Method-by-method contract

| Tool method            | Params (types in `schema.py`)                          | `data` payload on success                         |
|------------------------|--------------------------------------------------------|---------------------------------------------------|
| `create_project`       | `name: str, description=""`                             | the created project object (with its id)          |
| `list_projects`        | —                                                      | list of project objects                           |
| `list_workspaces`      | —                                                      | list of workspace objects                         |
| `switch_workspace`     | `workspace_id: str`                                    | the now-active workspace object                   |
| `upload_file`          | `local_path: str, project_id="", destination=""`       | uploaded-file reference (name, size, id/path)     |
| `start_new_task`       | `project_id: str, prompt: str, model_profile="standard"` | `{"task_id": ..., "status": ...}` (returns fast) |
| `send_message`         | `task_id: str, content: str`                           | message ack (message id, status)                  |
| `wait_for_next_update` | `task_id: str, timeout_seconds=60.0`                   | newest update (status + new messages/events)      |
| `list_tasks`           | `project_id=""`                                        | list of task objects                              |
| `list_result_files`    | `task_id=""`                                           | list of `ResultFile` (name + size)                |

### Return-envelope rules

- Build results with `ToolEnvelope.success(backend=self.name, tool="<name>", data=..., display_instruction=..., biomni_url=...)`.
- For **handled** errors (bad id, auth expired, empty result, not-yet-supported
  on this backend), return `ToolEnvelope.failure(self.name, "<name>", "<msg>")` —
  do **not** raise. Unhandled/programmer errors may raise; the server wraps them
  into an error envelope, so the client always gets terminal-state JSON.
- Set `display_instruction` (short "how to present this" string) and `biomni_url`
  (deep link into the web app / a job-run URL / a Volume path hint) whenever the
  backend has them; leave them `None` otherwise.
- `list_result_files` items must be `ResultFile` (or dicts with at least `name`
  and integer `size`).

### `describe()` for the catalog

Return a `BackendDescriptor`:

```python
BackendDescriptor(
    name=self.name,
    available=True,                 # False if selectable but not ready
    is_default=False,               # the server overwrites this flag
    status="ready",                 # "ready" | "unconfigured" | "auth-expired" | ...
    cost="hosted usage credits",    # short cost-model summary
    detail="account foo@bar; broker :18787",
)
```

`is_default` is set by the server (it knows the fail-closed target), so the value
you pass is ignored — set it to `False`.

## Selector behavior A2/B1 can rely on

- The server passes the per-call `backend` string straight to
  `select_backend_name`, which fail-closes to `online`. Adapters never see an
  invalid backend name.
- `backends.register_backend(name, instance)` lets tests/embedders inject a
  backend without the module import (used by A1's tests; A2/B1 can use it too).
