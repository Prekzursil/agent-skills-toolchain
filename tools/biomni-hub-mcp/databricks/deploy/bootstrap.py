"""biomni-hub :: Databricks driver-side bootstrap (source of truth).

This is the persistent-REPL program the adapter sends into the warm execution
context on the owned all-purpose cluster. It is embedded verbatim as the
``BOOTSTRAP`` string in ``hub/adapters/databricks.py`` so the adapter is
self-contained; keep the two in sync (this file is the canonical copy and the
one to edit + test in a Databricks notebook cell).

CONTRACT
--------
Sent AFTER the libraries are installed and the kernel restarted:

    %pip install --quiet biomni langchain_openai langchain_anthropic
    dbutils.library.restartPython()
    <this file's body>                     # defines the hub_* helpers
    hub_setup("dbfs:/biomni-hub", "claude-sonnet-4-20250514")

Then per canonical tool the adapter calls one helper:

    hub_start_task(prompt, "biomni-hub", "anthropic_api_key")
    hub_wait_update(task_id, since=None)
    hub_send_message(task_id, message)
    hub_list_tasks()

Every helper prints exactly one line ``@@BIOMNI_HUB@@{json}@@END@@`` that the
adapter parses out of the command stdout. Task state (A1 objects, log buffers)
lives in the module global ``_BIOMNI_HUB`` and survives across commands because
the execution context is a single long-lived Python process.

WHY %pip + restart (not subprocess pip): Databricks Runtime 15.4 ships a
compiled pydantic v1 under /databricks/python/lib that shadows a subprocess-pip
-installed pydantic v2, breaking ``import langchain_core`` with
``ImportError: cannot import name 'PydanticDeprecationWarning'``. Notebook
-scoped %pip installs into a path-prioritised env and the restart makes it win.
Verified on cluster 0708-143705-igywn40c (r5.2xlarge, DBR 15.4 LTS, Py 3.11).
"""

import os
import json
import time
import threading
import traceback

_BIOMNI_HUB = globals().setdefault("_BIOMNI_HUB", {
    "tasks": {},          # task_id -> {status, log[], result_dir, cursor, agent}
    "ready": False,
    "biomni_version": None,
    "data_root": None,
    "llm_model": None,
})


def _hub_emit(obj):
    print("@@BIOMNI_HUB@@" + json.dumps(obj) + "@@END@@")


def hub_setup(data_root, llm_model):
    H = _BIOMNI_HUB
    H["data_root"] = data_root
    H["llm_model"] = llm_model
    local_root = data_root.replace("dbfs:/", "/dbfs/")
    os.makedirs(local_root, exist_ok=True)
    os.makedirs(os.path.join(local_root, "tasks"), exist_ok=True)
    import biomni  # must already be importable post-%pip
    from biomni.agent import A1  # noqa: F401  fail loud if a dep is missing
    H["biomni_version"] = getattr(biomni, "__version__", "unknown")
    H["ready"] = True
    _hub_emit({"op": "setup", "ready": True,
               "biomni_version": H["biomni_version"]})


def _run_agent(task_id, prompt, llm_secret_scope, llm_secret_key):
    H = _BIOMNI_HUB
    rec = H["tasks"][task_id]
    try:
        key = dbutils.secrets.get(llm_secret_scope, llm_secret_key)  # noqa
        os.environ["ANTHROPIC_API_KEY"] = key
        from biomni.agent import A1
        local_root = H["data_root"].replace("dbfs:/", "/dbfs/")
        agent = A1(path=os.path.join(local_root, "tasks", task_id),
                   llm=H["llm_model"], api_key=key)
        rec["agent"] = agent
        rec["status"] = "running"
        gen = agent.go_stream(prompt) if hasattr(agent, "go_stream") \
            else iter([agent.go(prompt)])
        for step in gen:
            rec["log"].append(str(step)[:4000])
        rec["status"] = "completed"
    except Exception as e:
        rec["status"] = "failed"
        rec["log"].append("ERROR: " + repr(e))
        rec["log"].append(traceback.format_exc()[-2000:])


def hub_start_task(prompt, llm_secret_scope, llm_secret_key):
    H = _BIOMNI_HUB
    task_id = "t_" + os.urandom(4).hex()
    local_root = H["data_root"].replace("dbfs:/", "/dbfs/")
    result_dir = os.path.join(local_root, "tasks", task_id)
    os.makedirs(result_dir, exist_ok=True)
    H["tasks"][task_id] = {"status": "queued", "log": [],
                           "result_dir": result_dir, "cursor": 0,
                           "agent": None}
    threading.Thread(target=_run_agent, daemon=True,
                     args=(task_id, prompt, llm_secret_scope,
                           llm_secret_key)).start()
    _hub_emit({"op": "start_task", "task_id": task_id, "status": "queued"})


def hub_wait_update(task_id, since=None):
    rec = _BIOMNI_HUB["tasks"].get(task_id)
    if rec is None:
        _hub_emit({"op": "wait", "error": "unknown task_id"})
        return
    cur = rec["cursor"] if since is None else int(since)
    new = rec["log"][cur:]
    rec["cursor"] = len(rec["log"])
    _hub_emit({"op": "wait", "task_id": task_id, "status": rec["status"],
               "cursor": rec["cursor"], "new_log": new})


def hub_send_message(task_id, message):
    rec = _BIOMNI_HUB["tasks"].get(task_id)
    if rec is None or rec.get("agent") is None:
        _hub_emit({"op": "send", "error": "no live agent for task"})
        return
    try:
        ag = rec["agent"]
        fn = getattr(ag, "add_message", None) or getattr(ag, "go", None)
        rec["log"].append("USER: " + message)
        if fn:
            rec["log"].append(str(fn(message))[:4000])
        _hub_emit({"op": "send", "task_id": task_id, "status": "ok"})
    except Exception as e:
        _hub_emit({"op": "send", "error": repr(e)})


def hub_list_tasks():
    _hub_emit({"op": "list_tasks", "tasks": {
        k: {"status": v["status"], "log_len": len(v["log"]),
            "result_dir": v["result_dir"]}
        for k, v in _BIOMNI_HUB["tasks"].items()}})
