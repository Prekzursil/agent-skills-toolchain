"""Golden cross-backend contract: online and databricks must be byte-identical
at the canonical surface (base class, method signatures, ToolEnvelope return
type) AND every online-guaranteed lifecycle field must be present in databricks
responses. This is the gate that keeps backend="online" <-> "databricks"
interchangeable.

Part A is pure (no I/O): base class + signature + describe type. Part B uses a
fake transport (no network, no sleeps) to assert envelope-field parity against
the exact gaps §1's field table called out.
"""

from __future__ import annotations

import inspect

import pytest

import backends
from adapters.databricks import build_adapter as build_databricks
from adapters.online import build_adapter as build_online
from backends import BiomniBackend, load_backend, reset_cache
from schema import CANONICAL_TOOL_NAMES, BackendDescriptor, ResultFile, ToolEnvelope

BUILD = {"online": build_online, "databricks": build_databricks}

# ---- THE CONTRACT (single source of truth for this test) -------------------
# Online guarantees these; A3 tools + clients depend on them, so databricks
# MUST surface the same keys (envelope-level OR inside .data).
REQUIRED_TASK_FIELDS = {
    "task_id", "project_id", "message_id", "status",
    "model_profile", "biomni_url", "display_instruction",
}
REQUIRED_UPDATE_FIELDS = {
    "task_id", "status", "cursor", "done", "new_log",
    "new_messages", "biomni_url", "display_instruction",
}
CANONICAL_RESULTFILE = set(ResultFile.model_fields)  # {name, size, task_id, path}


@pytest.fixture(autouse=True)
def _clean_cache():
    backends.reset_cache()
    yield
    backends.reset_cache()


def _flatten(env: ToolEnvelope) -> set[str]:
    data = env.data if isinstance(env.data, dict) else {}
    return set(env.model_dump(exclude_none=True)) | set(data)


def _positional(sig: inspect.Signature) -> list[str]:
    return [
        p.name
        for p in sig.parameters.values()
        if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD) and p.name != "self"
    ]


# ===== Part A — signature + type contract (no I/O) ==========================
@pytest.mark.parametrize("name", list(BUILD))
def test_adapter_is_biomnibackend(name):
    reset_cache()
    adapter = load_backend(name)  # goes through the REAL loader gate
    assert isinstance(adapter, BiomniBackend)  # backends.py isinstance gate
    assert adapter.name == name


@pytest.mark.parametrize("name", list(BUILD))
@pytest.mark.parametrize("tool", CANONICAL_TOOL_NAMES)
def test_signature_matches_abc(name, tool):
    abc = inspect.signature(getattr(BiomniBackend, tool))
    got = inspect.signature(getattr(BUILD[name](), tool))
    assert _positional(got) == _positional(abc), (
        f"{name}.{tool}{got} diverges from BiomniBackend.{tool}{abc} "
        f"(server dispatches POSITIONALLY -> would misroute)"
    )


def test_three_misrouted_tools_now_align_to_abc():
    """The 3 tools A2/B1 misrouted (start_new_task/upload_file/
    wait_for_next_update) now match the ABC positional order on BOTH adapters."""
    expected = {
        "start_new_task": ["project_id", "prompt", "model_profile"],
        "upload_file": ["local_path", "project_id", "destination"],
        "wait_for_next_update": ["task_id", "timeout_seconds"],
    }
    for tool, want in expected.items():
        assert _positional(inspect.signature(getattr(BiomniBackend, tool))) == want
        for name in BUILD:
            got = _positional(inspect.signature(getattr(BUILD[name](), tool)))
            assert got == want, f"{name}.{tool} positional {got} != {want}"


@pytest.mark.parametrize("name", list(BUILD))
def test_describe_returns_descriptor(name, monkeypatch):
    # Keep describe() hermetic (no network): clear ambient online creds.
    for var in ("BIOMNI_BROKER", "BIOMNI_TOKEN", "BIOMNI_REFRESH_TOKEN"):
        monkeypatch.delenv(var, raising=False)
    assert isinstance(BUILD[name]().describe(), BackendDescriptor)


# ===== Part B — envelope-field parity (fake transport) ======================
@pytest.fixture
def online(monkeypatch):
    a = build_online()
    monkeypatch.setattr(a, "_broker_mode", lambda: False)
    monkeypatch.setattr(a, "_resolve_token", lambda: ("tok", ""))
    routes = {
        ("POST", "/v2/agent/sessions/create"): {
            "session_id": "sess_1", "url": "https://biomni/x"
        },
        ("GET", "/v2/agent/sess_1/messages"): {
            "messages": [{"role": "assistant", "text": "hi"}]
        },
        ("GET", "/v2/agent/sess_1"): {"status": "completed"},
        ("GET", "/v2/files/results"): {
            "results": [{"name": "out.csv", "size": 12, "session_id": "sess_1"}]
        },
    }
    monkeypatch.setattr(
        a, "_request",
        lambda m, p, body=None, query=None, token="", timeout=None: (
            200, routes.get((m, p), {})
        ),
    )
    return a


@pytest.fixture
def dbx(monkeypatch):
    a = build_databricks()
    a._booted = True
    monkeypatch.setattr(a, "_ensure_booted", lambda: None)
    monkeypatch.setattr(a, "_run_page_url", lambda: "https://dbx/run")
    emit = {
        "hub_start_task": (
            '@@BIOMNI_HUB@@{"op":"start_task","task_id":"t_1",'
            '"status":"queued"}@@END@@'
        ),
        "hub_wait_update": (
            '@@BIOMNI_HUB@@{"op":"wait","task_id":"t_1","status":"completed",'
            '"cursor":1,"new_log":["done"]}@@END@@'
        ),
    }
    monkeypatch.setattr(
        a, "_exec",
        lambda code: next((v for k, v in emit.items() if code.startswith(k)), ""),
    )

    class _F:  # fake DBFS entry
        def __init__(self, p, sz=12):
            self.path, self.file_size, self.is_dir = p, sz, False

    class _DBFS:
        def list(self, root):
            if root.rstrip("/").endswith("tasks"):
                d = _F("dbfs:/biomni-hub/tasks/t_1")
                d.is_dir = True
                return [d]
            return [_F(root + "/out.csv")]

    monkeypatch.setattr(a, "_client", lambda: type("W", (), {"dbfs": _DBFS()})())
    return a


def test_online_start_task_fields(online):
    env = online.start_new_task("p_1", "do X", "standard")  # ABC order
    assert isinstance(env, ToolEnvelope) and env.ok
    assert REQUIRED_TASK_FIELDS <= _flatten(env)


def test_online_update_fields(online):
    env = online.wait_for_next_update("sess_1", 5.0)  # ABC order
    assert isinstance(env, ToolEnvelope) and env.ok
    assert REQUIRED_UPDATE_FIELDS <= _flatten(env)


def test_databricks_start_task_matches_online_fields(dbx):
    env = dbx.start_new_task("p_1", "do X", "standard")
    assert isinstance(env, ToolEnvelope) and env.ok
    missing = REQUIRED_TASK_FIELDS - _flatten(env)
    assert not missing, f"databricks start_new_task missing: {missing}"


def test_databricks_update_matches_online_fields(dbx):
    env = dbx.wait_for_next_update("t_1", 5.0)
    assert isinstance(env, ToolEnvelope) and env.ok
    missing = REQUIRED_UPDATE_FIELDS - _flatten(env)
    assert not missing, f"databricks wait_for_next_update missing: {missing}"


def test_result_files_are_canonical(online, dbx):
    for adapter, tid in ((online, "sess_1"), (dbx, "t_1")):
        env = adapter.list_result_files(tid)
        assert isinstance(env, ToolEnvelope) and env.ok
        rows = (env.data or {}).get("result_files", [])
        assert rows, f"{adapter.name} returned no result files"
        for row in rows:
            rf = ResultFile(**row)  # validates name:str + size:int>=0
            # owning id must be canonical task_id, not session_id
            assert rf.task_id == tid, (
                f"{adapter.name} result row must carry task_id, got {row}"
            )
            assert CANONICAL_RESULTFILE <= set(rf.model_dump())


def test_both_backends_expose_identical_result_row_keys(online, dbx):
    """The result-file row schema must be byte-identical across backends."""
    keys = []
    for adapter, tid in ((online, "sess_1"), (dbx, "t_1")):
        rows = (adapter.list_result_files(tid).data or {}).get("result_files", [])
        keys.append(set(rows[0]))
    assert keys[0] == keys[1] == CANONICAL_RESULTFILE
