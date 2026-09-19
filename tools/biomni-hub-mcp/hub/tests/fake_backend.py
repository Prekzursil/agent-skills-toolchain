"""A minimal in-memory BiomniBackend for wiring tests (NOT a real adapter)."""

from __future__ import annotations

from backends import BiomniBackend
from schema import BackendDescriptor, ResultFile, ToolEnvelope


class FakeBackend(BiomniBackend):
    """Records calls and returns canned success envelopes."""

    def __init__(self, name: str = "online", available: bool = True) -> None:
        self.name = name
        self._available = available
        self.calls: list[tuple[str, tuple, dict]] = []

    def _rec(self, tool: str, *args, **kwargs) -> ToolEnvelope:
        self.calls.append((tool, args, kwargs))
        return ToolEnvelope.success(self.name, tool, data={"args": list(args)})

    def describe(self) -> BackendDescriptor:
        return BackendDescriptor(
            name=self.name,
            available=self._available,
            is_default=False,
            status="ready" if self._available else "unconfigured",
            cost="test",
            detail="fake backend",
        )

    def create_project(self, name: str, description: str = "") -> ToolEnvelope:
        return self._rec("create_project", name, description)

    def list_projects(self) -> ToolEnvelope:
        return self._rec("list_projects")

    def list_workspaces(self) -> ToolEnvelope:
        return self._rec("list_workspaces")

    def switch_workspace(self, workspace_id: str) -> ToolEnvelope:
        return self._rec("switch_workspace", workspace_id)

    def upload_file(
        self, local_path: str, project_id: str = "", destination: str = ""
    ) -> ToolEnvelope:
        return self._rec("upload_file", local_path, project_id, destination)

    def start_new_task(
        self, project_id: str, prompt: str, model_profile: str = "standard"
    ) -> ToolEnvelope:
        self.calls.append(("start_new_task", (project_id, prompt, model_profile), {}))
        return ToolEnvelope.success(
            self.name,
            "start_new_task",
            data={"task_id": "task_1", "status": "queued"},
            display_instruction="Poll wait_for_next_update for progress.",
            biomni_url="https://biomni.example/task/task_1",
        )

    def send_message(self, task_id: str, content: str) -> ToolEnvelope:
        return self._rec("send_message", task_id, content)

    def wait_for_next_update(
        self, task_id: str, timeout_seconds: float = 60.0, *, since: int | None = None
    ) -> ToolEnvelope:
        return self._rec("wait_for_next_update", task_id, timeout_seconds, since=since)

    def list_tasks(self, project_id: str = "") -> ToolEnvelope:
        return self._rec("list_tasks", project_id)

    def list_result_files(self, task_id: str = "") -> ToolEnvelope:
        self.calls.append(("list_result_files", (task_id,), {}))
        return ToolEnvelope.success(
            self.name,
            "list_result_files",
            data=[ResultFile(name="out.csv", size=42, task_id=task_id).model_dump()],
        )


class ExplodingBackend(BiomniBackend):
    """Every tool raises — exercises the server's error-wrapping path."""

    name = "online"

    def describe(self) -> BackendDescriptor:  # pragma: no cover - trivial
        return BackendDescriptor(
            name=self.name,
            available=True,
            is_default=False,
            status="ready",
            cost="test",
        )

    def _boom(self, *_a, **_k):
        raise RuntimeError("kaboom")

    create_project = _boom
    list_projects = _boom
    list_workspaces = _boom
    switch_workspace = _boom
    upload_file = _boom
    start_new_task = _boom
    send_message = _boom
    wait_for_next_update = _boom
    list_tasks = _boom
    list_result_files = _boom
