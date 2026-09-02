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


def test_node_preflight_probe_mirrors_the_node_command():
    """The probe is only meaningful if it runs the SAME command the node runs per unit:
    perms come from the `--dangerously-bypass-approvals-and-sandbox` FLAG and the owner's
    fast/effort settings from `-c`, because `--ignore-user-config` drops ~/.codex/config.toml.
    Asserted here because a probe that silently drops those flags measures a different codex."""
    p = preflight_units.node_preflight_unit().prompt
    assert "--dangerously-bypass-approvals-and-sandbox" in p
    assert "-c service_tier=priority" in p
    assert "--skip-git-repo-check" in p and "--ignore-user-config" in p


def test_runnability_unit_shape():
    u = preflight_units.runnability_unit(
        "env-inspector", "https://github.com/Prekzursil/env-inspector"
    )
    assert u.id == "runnability-env-inspector" and u.lane == "runnability"
    p = u.prompt
    assert "clone" in p.lower() and "pytest" in p.lower() and "uncovered_files:" in p
    assert "agent/E-env-inspector-preflight" in p  # the throwaway local-commit probe
    assert "UNIT-COMPLETE: runnability-env-inspector" in p


def test_runnability_unit_probes_a_local_commit_and_never_pushes():
    """R1: the node has no write token, and the push half was deliberately DELETED so that
    running this preflight cannot re-require the fleet-wide credential it retires. Both
    states are asserted — the local-commit field must be present AND the push wording gone —
    because asserting only the new field would stay green if the push step crept back."""
    p = preflight_units.runnability_unit("env-inspector", "https://x/y").prompt
    assert "commit_probe: <ok|failed>" in p
    assert "Do NOT push" in p
    assert "push_probe" not in p
    assert "GITHUB_TOKEN" not in p


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


def test_parse_gaps_drops_non_source_files():
    """Observed on a real Whisper_GUI run: 11 of 39 gaps were junk — site-packages, a /tmp
    file, and test files. Fanning out on those spends Codex units covering third-party code
    or a temp path that no longer exists, so they must never reach coverage_units()."""
    text = (
        "uncovered_files:\n"
        "- backend/main.py: 10, 11\n"
        "- ../../../../usr/lib/python3/dist-packages/six.py: 49, 50\n"
        "- ../../../../tmp/tmp4bcbb9fz/_remote_module_non_scriptable.py: 15\n"
        "- tests/test_translation.py: 42, 44\n"
        "- modules/whisper/data_classes.py: 7\n"
    )
    gaps = preflight_units.parse_gaps(text)
    assert [g["file"] for g in gaps] == [
        "backend/main.py",
        "modules/whisper/data_classes.py",
    ]


def test_parse_gaps_keeps_source_named_like_a_test():
    """Guard against over-filtering: only a tests/ dir or a test_*.py basename is excluded,
    not any path that merely contains the substring 'test'."""
    text = "uncovered_files:\n- backend/latest_run.py: 3\n- src/contest/scoring.py: 9\n"
    assert [g["file"] for g in preflight_units.parse_gaps(text)] == [
        "backend/latest_run.py",
        "src/contest/scoring.py",
    ]


def test_is_fanout_target_rejection_reasons():
    """Direct cover for the branches the parse_gaps cases reach only partly: the artifact
    fixtures above exercise dist-packages and a tests/ DIRECTORY, so `site-packages` and the
    `<name>_test.py` SUFFIX would otherwise be unexercised (a tests/ segment short-circuits
    first). Backslash paths are normalised, so a Windows-style gap line filters identically."""
    assert preflight_units.is_fanout_target("backend/main.py") is True
    assert preflight_units.is_fanout_target("../up/out.py") is False
    assert preflight_units.is_fanout_target("venv/lib/site-packages/six.py") is False
    assert preflight_units.is_fanout_target("pkg/scoring_test.py") is False
    assert preflight_units.is_fanout_target("pkg/test_scoring.py") is False
    assert preflight_units.is_fanout_target("src\\test\\helper.py") is False
    # An empty path yields no segments; documented here to pin the `parts[-1] if parts`
    # fallback. parse_gaps cannot produce it (its regex requires a non-space char).
    assert preflight_units.is_fanout_target("") is True
