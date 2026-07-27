"""Budgeting. The one rule: an unmeasured cost is `-`/null, NEVER 0."""

from __future__ import annotations

from mcpctl.scopes import ScopeId
from mcpctl.topology import Topology

from mcpapply import plan as P
from mcpapply.impact import (
    TOOL_BLOCK_OVERHEAD_TOKENS,
    Cost,
    Impact,
    Regime,
    TokenBasis,
    preview,
    regime_from_env,
    render_impact,
)
from conftest import PROJECT_KEY, topology_from

# Measured on this box, 2026-07-27. Kept as literals so the anti-correlation the
# two-axis design exists for is visible in the test itself.
CLOUD_HUB = Cost(
    tool_count=409,
    token_cost=77_198,
    token_basis=TokenBasis.EXACT,
    commit_bytes=17_400_000,
    proc_count=2,
    measured_at="2026-07-27",
)
CHROME = Cost(
    tool_count=29,
    token_cost=None,
    token_basis=TokenBasis.NOT_MEASURED,
    commit_bytes=331_000_000,
    proc_count=6,
)
REMOTE = Cost(tool_count=23, token_cost=900, token_basis=TokenBasis.EXACT, remote=True)


def _top(project_key: str | None = PROJECT_KEY) -> Topology:
    return topology_from(
        {
            "claude_json": {
                "mcpServers": {
                    "cloud-hub": {"command": "x"},
                    "chrome-devtools": {"command": "y"},
                    "basic-memory": {"type": "http", "url": "http://127.0.0.1/mcp"},
                },
                "projects": {PROJECT_KEY: {"disabledMcpServers": []}},
            }
        },
        project_key=project_key,
    )


def _plan_disable(name: str, project_key: str | None = PROJECT_KEY) -> P.Plan:
    top = _top(project_key)
    return P.build_plan([P.plan_disable(top, name)], project_key=project_key)


def test_the_regime_is_classified_from_the_env_value_never_assumed():
    assert regime_from_env("auto:5") is Regime.DEFERRED
    assert regime_from_env("1") is Regime.DEFERRED
    assert regime_from_env("0") is Regime.EAGER
    assert regime_from_env("false") is Regime.EAGER
    assert regime_from_env(None) is Regime.UNKNOWN
    assert regime_from_env("   ") is Regime.UNKNOWN


def test_a_measured_disable_reports_both_axes_independently():
    impact = preview(
        _plan_disable("cloud-hub"), {"cloud-hub": CLOUD_HUB}, regime=Regime.EAGER
    )
    assert impact.token_delta == 77_198
    assert impact.commit_delta == 17_400_000
    assert impact.partial is False
    assert any("NEXT session start" in n for n in impact.notes)


def test_an_unmeasured_server_is_never_rendered_as_zero():
    """The whole point of the module: 'not measured' != 'costs nothing'."""
    impact = preview(_plan_disable("cloud-hub"), {}, regime=Regime.EAGER)
    assert impact.token_delta is None
    assert impact.commit_delta is None
    assert impact.unmeasured == ("cloud-hub",)
    text = render_impact(impact)
    assert "tokens saved:  -" in text
    assert "commit saved:  -" in text
    assert "0" not in text.split("note:")[0].replace("2026", "")


def test_a_half_measured_server_marks_the_delta_a_lower_bound():
    impact = preview(
        _plan_disable("chrome-devtools"),
        {"chrome-devtools": CHROME},
        regime=Regime.EAGER,
    )
    assert impact.token_delta is None
    assert impact.commit_delta == 331_000_000
    assert impact.partial is True
    assert "LOWER BOUND" in render_impact(impact)


def test_the_two_axes_are_never_fused_into_one_score():
    """cloud-hub: 77k tokens / 17 MB. chrome-devtools: 0 known tokens / 331 MB."""
    tokens = preview(
        _plan_disable("cloud-hub"), {"cloud-hub": CLOUD_HUB}, regime=Regime.EAGER
    )
    memory = preview(
        _plan_disable("chrome-devtools"),
        {"chrome-devtools": CHROME},
        regime=Regime.EAGER,
    )
    assert tokens.token_delta is not None
    assert memory.commit_delta is not None
    assert memory.commit_delta > (tokens.commit_delta or 0)
    assert (tokens.token_delta or 0) > (memory.token_delta or 0)


def test_a_root_scope_disable_is_credited_zero_memory_with_the_reason():
    """MEASURED: root disabledMcpServers does NOT prevent the spawn."""
    impact = preview(
        _plan_disable("cloud-hub", project_key=None),
        {"cloud-hub": CLOUD_HUB},
        regime=Regime.EAGER,
    )
    assert impact.token_delta == 77_198
    assert impact.commit_delta == 0
    assert impact.no_ram_saving == ("cloud-hub",)
    assert any("not to prevent the spawn" in n for n in impact.notes)


def test_a_remote_server_has_no_memory_axis_at_all():
    impact = preview(
        _plan_disable("basic-memory"), {"basic-memory": REMOTE}, regime=Regime.EAGER
    )
    assert impact.token_delta == 900
    assert impact.commit_delta is None
    assert impact.unmeasured == ()


def test_the_one_off_tool_block_is_credited_only_when_the_last_server_goes():
    plan = _plan_disable("cloud-hub")
    costs = {"cloud-hub": CLOUD_HUB}
    partial = preview(plan, costs, regime=Regime.EAGER, fleet_size=10)
    last = preview(plan, costs, regime=Regime.EAGER, fleet_size=1)
    assert partial.token_delta == 77_198
    assert last.token_delta == 77_198 + TOOL_BLOCK_OVERHEAD_TOKENS
    assert any("tool block is reclaimed" in n for n in last.notes)


def test_the_deferred_regime_is_flagged_because_it_changes_the_arithmetic():
    impact = preview(
        _plan_disable("cloud-hub"), {"cloud-hub": CLOUD_HUB}, regime=Regime.DEFERRED
    )
    assert any("DEFERRED" in n for n in impact.notes)


def test_an_unknown_regime_says_so_rather_than_guessing_eager():
    impact = preview(
        _plan_disable("cloud-hub"), {"cloud-hub": CLOUD_HUB}, regime=Regime.UNKNOWN
    )
    assert any("regime is unknown" in n for n in impact.notes)


def test_a_remove_always_counts_as_spawn_preventing():
    top = _top()
    plan = P.build_plan([P.plan_remove(top, "cloud-hub")], project_key=PROJECT_KEY)
    impact = preview(plan, {"cloud-hub": CLOUD_HUB}, regime=Regime.EAGER)
    assert impact.commit_delta == 17_400_000
    assert impact.no_ram_saving == ()


def test_an_enable_or_reconnect_frees_nothing():
    top = _top()
    for change in (P.plan_enable(top, "cloud-hub"), P.plan_reconnect(top, "cloud-hub")):
        plan = P.build_plan([change], project_key=PROJECT_KEY)
        impact = preview(plan, {"cloud-hub": CLOUD_HUB}, regime=Regime.EAGER)
        assert impact.token_delta is None
        assert impact.commit_delta is None


def test_a_no_op_disable_is_not_counted():
    top = topology_from(
        {
            "claude_json": {
                "mcpServers": {"a": {"command": "x"}},
                "disabledMcpServers": ["a"],
            }
        },
        project_key=None,
    )
    plan = P.build_plan([P.plan_disable(top, "a")], project_key=None)
    assert preview(plan, {"a": CLOUD_HUB}, regime=Regime.EAGER).token_delta is None


def test_a_cost_record_with_a_missing_commit_is_unmeasured_not_zero():
    cost = Cost(token_cost=10, token_basis=TokenBasis.EXACT)
    impact = preview(
        _plan_disable("cloud-hub"), {"cloud-hub": cost}, regime=Regime.EAGER
    )
    assert impact.token_delta == 10
    assert impact.commit_delta is None
    assert impact.unmeasured == ("cloud-hub",)


def test_a_server_missing_both_axes_is_listed_once_not_twice():
    cost = Cost()
    impact = preview(
        _plan_disable("cloud-hub"), {"cloud-hub": cost}, regime=Regime.EAGER
    )
    assert impact.unmeasured == ("cloud-hub",)


def test_a_live_only_edit_is_not_counted_as_a_spawn_prevention():
    top = _top()
    change = P.Change(
        intent=P.Intent.DISABLE,
        server="cloud-hub",
        edits=(
            P.Edit(
                scope=ScopeId.CLAUDE_USER,
                label="(live)",
                key_path=(),
                op=P.Op.LIVE_ONLY,
                server="cloud-hub",
            ),
        ),
    )
    assert top.names()
    impact = preview(
        P.build_plan([change], project_key=None),
        {"cloud-hub": CLOUD_HUB},
        regime=Regime.EAGER,
    )
    assert impact.commit_delta == 0
    assert impact.no_ram_saving == ("cloud-hub",)


def test_every_record_serialises_completely():
    assert CLOUD_HUB.to_dict()["token_basis"] == "exact-count-tokens"
    payload = Impact(regime=Regime.EAGER, unmeasured=("x",)).to_dict()
    assert payload["partial"] is True
    assert payload["token_delta"] is None


def test_the_proxies_are_labelled_so_they_cannot_pass_as_measurements():
    """Tokens-per-tool spans 12.5x, so a proxy number must carry its basis."""
    assert TokenBasis.TOOL_COUNT.value.endswith("proxy")
    assert TokenBasis.SCHEMA_BYTES.value.endswith("proxy")
    assert TokenBasis.EXACT.value == "exact-count-tokens"
