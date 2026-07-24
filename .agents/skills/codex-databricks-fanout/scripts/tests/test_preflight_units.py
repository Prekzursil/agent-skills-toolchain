from harness.lanes import preflight_units
from harness.contract import floor_for


def test_node_preflight_unit_shape():
    u = preflight_units.node_preflight_unit()
    assert u.id == "node-preflight" and u.lane == "preflight"
    assert floor_for(u.lane) >= 1024  # unknown lane -> default 1024 floor
    p = u.prompt
    assert "codex --version" in p and 'model_reasoning_effort="ultra"' in p
    assert "codex_version:" in p and "ultra_rc:" in p and "bogus_rc:" in p
    assert (
        "UNIT-COMPLETE: node-preflight" in p and "1200" in p
    )  # padded past the node 1024 gate


def test_runnability_unit_shape():
    u = preflight_units.runnability_unit(
        "env-inspector", "https://github.com/Prekzursil/env-inspector"
    )
    assert u.id == "runnability-env-inspector" and u.lane == "runnability"
    p = u.prompt
    assert "clone" in p.lower() and "pytest" in p.lower() and "uncovered_files:" in p
    assert "agent/E-env-inspector-preflight" in p  # the throwaway push probe
    assert "UNIT-COMPLETE: runnability-env-inspector" in p


def test_parse_gaps_extracts_file_and_lines():
    text = (
        "suite_status: green\nbaseline_coverage: 87.3\nuncovered_files:\n"
        "- src/a.py: 10, 11, 45\n- src/b.py: 3\n"
        + "x" * 1100
        + "\nUNIT-COMPLETE: runnability-env-inspector\n"
    )
    gaps = preflight_units.parse_gaps(text)
    assert gaps == [
        {"file": "src/a.py", "uncovered": [10, 11, 45]},
        {"file": "src/b.py", "uncovered": [3]},
    ]


def test_parse_gaps_empty_when_no_block():
    assert preflight_units.parse_gaps("suite_status: green\nno gaps here\n") == []
