# biomni-hub :: Databricks backend (Component B1) — deploy + Phase-1 proof

Self-hosts Biomni on the owner-authorized **bolt-datascience** Databricks
workspace behind the hub's canonical 10-tool surface. Owner
(costin.ionescu@bolt.eu) authorized this workspace for personal Biomni hosting.

- Adapter: `hub/adapters/databricks.py` (`DatabricksBiomniAdapter`)
- Driver program: `databricks/deploy/bootstrap.py` (embedded in the adapter)
- Provisioning: `databricks/deploy/provision.py`
- Data-lake layout: `databricks/deploy/volume_layout.md`
- Plumbing-proof runner (Jobs variant): `databricks/deploy/probe_runner.py`

---

## Execution model — WARM COMMAND/CONTEXT API (empirically forced)

The directive offered a choice between **ephemeral Jobs** (`dbx_run_submit`
with `new_cluster`) and the **warm Command/Context API**. Phase-1 probing of
bolt-datascience made the choice for us — ephemeral Jobs are **not available**
to this identity:

| Probe | Result | Consequence |
|---|---|---|
| `dbx_run_submit` w/ `new_cluster` (m5d.large single-node) | `PERMISSION_DENIED: You are not authorized to create clusters` (run 535086532822559) | ❌ ephemeral Jobs with new_cluster are impossible |
| `dbx_cluster_start` on owned cluster `0708-143705-igywn40c` | `ok` → cluster reached **RUNNING** | ✅ can start an owned all-purpose cluster |
| owned cluster `workload_type.clients` | `{jobs:false, notebooks:true}` | ❌ refuses Jobs runs; ✅ accepts Command Execution API |

**Therefore:** start (or reuse) the owner's all-purpose cluster, hold ONE
long-lived Python execution context on its driver, and drive Biomni by sending
commands into that persistent REPL. The REPL keeps a live `biomni.agent.A1`
object and an in-process task registry across calls — which is exactly what
Biomni's async, multi-turn agent model wants. This is also the "persistent A1
object across calls" pattern from the architecture notes. Ephemeral-Jobs
support remains in the adapter as a dormant path that auto-activates if a
future identity gains cluster-create + jobs entitlement.

### The cluster
`0708-143705-igywn40c` — "Costin-Ioan Ionescu's All-purpose cluster policy
Cluster", r5.2xlarge driver + autoscale 2–8 × r5.2xlarge, **DBR 15.4 LTS
(Python 3.11, x86_64)**, `LEGACY_SINGLE_USER_STANDARD`, autotermination 30 min,
instance profile `datascience-instance-profile` (S3 access), created under
cluster policy `0F61EF4EEC0002D5`. There is also an owned **GPU** cluster
`0709-211344-mwv1340c` (g4dn.xlarge, 16.4 GPU-ML) for future GPU biomni tasks.

---

## Canonical tool → Databricks mapping

| Canonical tool | Mechanism |
|---|---|
| create_project / list_projects | JSON control-plane store `hub_meta.json` on DBFS |
| list_workspaces / switch_workspace | one logical workspace == one cluster id |
| upload_file | `w.dbfs.put` → `inputs/` |
| start_new_task | `hub_start_task`: A1(...).go_stream(prompt) on a daemon thread; returns `task_id` |
| send_message | `hub_send_message`: push a follow-up turn into the running task |
| wait_for_next_update | `hub_wait_update`: poll the in-REPL registry; return new log lines + status |
| list_tasks | `hub_list_tasks`: dump the registry |
| list_result_files | `w.dbfs.list(tasks/<id>)` → name + size |
| fetch_artifact | `w.dbfs.read` looped in ≤1 MB base64 chunks → REAL bytes |

Backend selector (out-of-band): env `BIOMNI_BACKEND=online|databricks` +
optional per-call `backend`; `biomni_backends` catalog reads
`DatabricksBiomniAdapter.status()`. **Fail closed to online** — every adapter
method returns a structured `{ok:false,error}` instead of raising.

---

## Phase-1 proof — REAL evidence (cluster 0708-143705-igywn40c)

All run live against bolt-datascience via the Command Execution API.

1. **Workspace reachable** — `dbx_current_user` → Costin-Ioan Ionescu
   (costin.ionescu@bolt.eu), workspace_id 3829506390716583, AWS eu-central-1.
2. **Code executes on their compute** — REPL reported
   `python 3.11.11`, `machine x86_64`,
   exe `/local_disk0/.ephemeral_nfs/envs/pythonEnv-…/bin/python`.
3. **PyPI reachable + biomni resolvable** — `pip index versions biomni` → rc 0,
   `biomni (0.0.8)` (available 0.0.1–0.0.8). pip routes through the internal
   JFrog mirror `pypi.data.internal`.
4. **biomni installs on their compute** — `pip install biomni` → **rc 0 in 56 s**.
5. **biomni imports** — after the required fix (below):
   ```json
   {"biomni_version":"0.0.8","A1_import":"OK","A1_callable":true,
    "A1_init_params":["self","path","llm","source","use_tool_retriever",
      "timeout_seconds","base_url","api_key","commercial_mode",
      "expected_data_lake_files"],
    "A1_public_methods":["add_data","add_mcp","add_software","add_tool",
      "configure","create_mcp_server","go","go_stream","launch_gradio_demo",
      "save_conversation_history", ...]}
   ```
   → confirms the adapter's mapping: `A1(path=…, llm=…, api_key=…)`,
   `go_stream` for streaming, `add_mcp`/`create_mcp_server` for fleet injection.
6. **Secret plumbing proven** — created OWNED scope `biomni-hub`, put
   `anthropic_api_key`, read it back inside the REPL via
   `dbutils.secrets.get("biomni-hub","anthropic_api_key")` → `secret_readback_ok:true`.
7. **Data-lake + control-plane plumbing proven** — created
   `dbfs:/biomni-hub/{tasks,inputs,data_lake}` and round-tripped
   `hub_meta.json` (write 121 B → read identical).

### The two install gotchas (both fixed, both baked into the deploy)
- **pydantic shadow:** subprocess `pip install` leaves DBR 15.4's preinstalled
  pydantic **v1** ahead on `sys.path`, so `import langchain_core` dies with
  `ImportError: cannot import name 'PydanticDeprecationWarning' from 'pydantic'`.
  **Fix:** notebook-scoped `%pip install` + `dbutils.library.restartPython()`
  → pydantic 2.13.4 from the ephemeral env wins.
- **missing LLM providers:** `pip install biomni` does **not** pull
  `langchain_openai` / `langchain_anthropic`, but `biomni.agent.a1` imports
  them. **Fix:** reduced spec = `biomni langchain_openai langchain_anthropic`.

So the verified reduced boot sequence (encoded in `adapter.boot()`):
```python
%pip install --quiet biomni langchain_openai langchain_anthropic
dbutils.library.restartPython()
<bootstrap.py body>
hub_setup("dbfs:/biomni-hub", "claude-sonnet-4-20250514")   # -> ready:true
```

---

## Deploy steps

1. **Select the profile** (already active): `db_account_switch bolt-ds`
   (label `costin.ionescu@bolt.eu (bolt-datascience)`).
2. **Provision** (cheap, no compute):
   ```bash
   export ANTHROPIC_API_KEY=sk-ant-...        # the real Claude key
   python databricks/deploy/provision.py
   ```
   Creates scope `biomni-hub` + key `anthropic_api_key`, the DBFS layout, and
   seeds `hub_meta.json`. (A placeholder key was written in Phase-1 — **the
   owner must overwrite it with the real key** via provision.py or
   `dbx_secret_put`.)
3. **Wire the backend** into the hub and boot on demand:
   ```python
   from hub.adapters.databricks import build_adapter
   dbx = build_adapter()          # defaults: cluster 0708-…, dbfs:/biomni-hub
   dbx.boot()                     # starts cluster, installs, → ready
   t = dbx.start_new_task("Analyze CRISPR screen …")
   dbx.wait_for_next_update(t["task_id"])
   ```
   The hub's backend selector instantiates this only when
   `BIOMNI_BACKEND=databricks` or a call passes `backend="databricks"`.

## Cost / hygiene
- Billing accrues only while `0708-143705-igywn40c` is RUNNING; it
  **autoterminates after 30 min idle**. `boot()` restarts it on demand.
- No Model Serving is used (its 597 s cap is why); no long agent task or 11 GB
  lake download was run in Phase-1 — plumbing only.
- Phase-1 left behind: scope `biomni-hub` (+placeholder key),
  `dbfs:/biomni-hub/*`. The proof cluster was left to autoterminate.

## Next phases (out of B1 scope)
- Full `biomni_e1` image + pre-seed the 11 GB `data_lake/` once.
- Wire `add_mcp()` fleet injection (biomni consumes other hub MCPs).
- GPU tasks on `0709-211344-mwv1340c`.
- Migrate DATA_ROOT to a UC Volume when SQL/UC entitlement is granted.
