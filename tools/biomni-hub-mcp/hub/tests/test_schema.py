"""Canonical schema tests: the 10-tool registry + envelope + result models."""

from __future__ import annotations

import schema
from schema import CANONICAL_TOOL_NAMES, CANONICAL_TOOLS, ResultFile, ToolEnvelope

EXPECTED = {
    "create_project",
    "list_projects",
    "list_workspaces",
    "switch_workspace",
    "upload_file",
    "start_new_task",
    "send_message",
    "wait_for_next_update",
    "list_tasks",
    "list_result_files",
}


def test_exactly_ten_canonical_tools():
    assert len(CANONICAL_TOOLS) == 10
    assert set(CANONICAL_TOOL_NAMES) == EXPECTED


def test_tool_specs_have_param_models():
    for spec in CANONICAL_TOOLS:
        assert issubclass(spec.params_model, schema.BaseModel)
        assert spec.summary


def test_tool_spec_lookup():
    assert schema.tool_spec("start_new_task").name == "start_new_task"
    import pytest

    with pytest.raises(KeyError):
        schema.tool_spec("does_not_exist")


def test_envelope_success_and_failure():
    ok = ToolEnvelope.success("online", "list_projects", data=[1, 2])
    assert ok.ok and ok.backend == "online" and ok.data == [1, 2]
    bad = ToolEnvelope.failure("databricks", "upload_file", "boom")
    assert not bad.ok and bad.error == "boom" and bad.data is None


def test_envelope_display_protocol_fields():
    env = ToolEnvelope.success(
        "online",
        "start_new_task",
        data={"task_id": "t1"},
        display_instruction="Open the notebook.",
        biomni_url="https://biomni.example/t1",
    )
    assert env.display_instruction == "Open the notebook."
    assert env.biomni_url == "https://biomni.example/t1"


def test_result_file_requires_name_and_nonneg_size():
    rf = ResultFile(name="a.csv", size=10)
    assert rf.name == "a.csv" and rf.size == 10
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        ResultFile(name="a", size=-1)


def test_param_model_validation():
    from schema import StartNewTaskParams, WaitForNextUpdateParams

    p = StartNewTaskParams(project_id="p1", prompt="hi")
    assert p.model_profile == "standard"
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        WaitForNextUpdateParams(task_id="t", timeout_seconds=0)  # gt=0
    with pytest.raises(ValidationError):
        WaitForNextUpdateParams(task_id="t", timeout_seconds=9999)  # le=600
