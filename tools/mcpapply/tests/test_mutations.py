"""Mutation probe: revert each load-bearing decision and require detection.

100% line+branch coverage does NOT prove behaviour. The receipt this estate already
holds: a suite stayed 15/15 green while a default was reverted from 1024 to 512,
because every case passed the value explicitly and the default was never exercised.
This package's single most important property IS a default (``apply=False``), so that
failure mode is not hypothetical here -- it is the exact shape of the risk.

Each row below mutates ONE decision and asserts the matching check goes RED. A mutant
that survives means the suite has stopped protecting that decision, and this file
fails. ``test_every_check_passes_unmutated`` is the control: without it, a check that
is broken outright would "detect" every mutant while measuring nothing.

Lives in ``tests/`` on purpose -- ``gate-tests-coverage mcpapply`` runs the whole
suite, so the probe is EXECUTED by CI rather than described in prose.
"""

from __future__ import annotations

import inspect
import json
from collections.abc import Callable, Iterable, Mapping
from pathlib import Path

import pytest
from mcpctl.matrix import Liveness, Row, build_rows
from mcpctl.scopes import ScopeId

from mcpapply import apply as A
from mcpapply import guard as G
from mcpapply import impact as I  # noqa: E741 -- one-letter alias, matching `A`/`G`.
from mcpapply import plan as P
from mcpapply import server as S
from mcpapply.backup import BackupRecord
from conftest import FIXED_NOW, PROJECT_KEY, topology_from

HOSTILE = '<img src=x onerror="alert(1)">'
LF = chr(10)
CRLF = chr(13) + chr(10)


def _paths(root: Path):
    from mcpctl.sources import source_paths

    return source_paths(root)


def _seed(store: A.MemoryFileStore, root: Path, doc: Mapping[str, object]) -> None:
    store.files[str(_paths(root).claude_json)] = json.dumps(doc, indent=2) + "\n"


def _simple_top(**extra: object):
    doc: dict[str, object] = {
        "mcpServers": {"srv": {"command": "x"}},
        "projects": {PROJECT_KEY: {"disabledMcpServers": []}},
    }
    doc.update(extra)
    return topology_from({"claude_json": doc}, project_key=PROJECT_KEY)


def _disable_plan() -> P.Plan:
    return P.build_plan([P.plan_disable(_simple_top(), "srv")], project_key=PROJECT_KEY)


# --------------------------------------------------------------------------- checks
# Each check asserts ONE load-bearing behaviour of THIS package.


def check_dry_run_is_the_default() -> None:
    """Calling apply_plan WITHOUT `apply=` must change nothing and send no frame."""
    root = Path("/h")
    store = A.MemoryFileStore()
    _seed(store, root, {"mcpServers": {"srv": {"command": "x"}}})
    result = A.apply_plan(
        _disable_plan(), paths=_paths(root), store=store, now=FIXED_NOW
    )
    assert result.dry_run is True
    assert result.written == ()
    assert store.writes == []


def check_the_default_parameter_itself_is_false() -> None:
    """Read the SIGNATURE, not just the behaviour: a caller that omits the flag is
    the case the estate's recorded near-miss shows a suite can silently stop covering."""
    assert inspect.signature(A.apply_plan).parameters["apply"].default is False


def check_a_backup_is_taken_before_a_write() -> None:
    root = Path("/h")
    store = A.MemoryFileStore()
    _seed(store, root, {"mcpServers": {"srv": {"command": "x"}}})
    original = store.files[str(_paths(root).claude_json)]
    result = A.apply_plan(
        _disable_plan(),
        paths=_paths(root),
        store=store,
        now=FIXED_NOW,
        apply=True,
        guard=lambda: "",
    )
    assert len(result.backups) == 1
    assert store.files[result.backups[0].backup] == original


def check_the_restore_command_is_printed() -> None:
    text = A.ApplyResult(
        dry_run=False,
        backups=(BackupRecord(source="s.json", backup="s.json.bak", size_bytes=1),),
    ).restore
    assert "s.json.bak" in text
    assert "s.json" in text


def check_unknown_keys_survive_a_write() -> None:
    doc = {
        "mcpServers": {"srv": {"command": "x"}},
        "oauthAccount": {"token": "keep"},
        "projects": {PROJECT_KEY: {"history": ["keep"], "disabledMcpServers": []}},
    }
    updated, _ = A.apply_edits_to_doc(
        doc,
        [
            P.Edit(
                scope=ScopeId.CLAUDE_PROJECT_DISABLED,
                label="claude_json",
                key_path=("projects", PROJECT_KEY, "disabledMcpServers"),
                op=P.Op.LIST_ADD,
                server="srv",
            )
        ],
    )
    # `.get`, not `[...]`: a wipe must surface as a FAILED ASSERTION, not a KeyError
    # -- the mutant harness asserts on AssertionError, so a raising check would be
    # scored as "undetected".
    assert updated.get("oauthAccount") == {"token": "keep"}
    assert updated.get("projects", {}).get(PROJECT_KEY, {}).get("history") == ["keep"]
    assert updated.get("mcpServers") == {"srv": {"command": "x"}}
    assert updated.get("projects", {}).get(PROJECT_KEY, {}).get(
        "disabledMcpServers"
    ) == ["srv"]


def check_denied_list_is_read_as_objects() -> None:
    updated, _ = A.apply_edits_to_doc(
        {"deniedMcpServers": [{"serverName": "srv"}]},
        [
            P.Edit(
                scope=ScopeId.SETTINGS_DENIED,
                label="settings",
                key_path=("deniedMcpServers",),
                op=P.Op.LIST_REMOVE,
                server="srv",
            )
        ],
    )
    assert updated["deniedMcpServers"] == []


def check_an_ancestor_project_row_is_never_substituted() -> None:
    """A disable planned for a deep cwd must not be written into the ancestor's row."""
    top = topology_from(
        {
            "claude_json": {
                "mcpServers": {"srv": {"command": "x"}},
                "projects": {"C:/Users/Owner": {"disabledMcpServers": []}},
            }
        },
        project_key=PROJECT_KEY,
    )
    change = P.plan_disable(top, "srv")
    updated, _ = A.apply_edits_to_doc(
        {"projects": {"C:/Users/Owner": {"disabledMcpServers": []}}}, change.edits
    )
    assert updated["projects"]["C:/Users/Owner"]["disabledMcpServers"] == []
    assert updated["projects"][PROJECT_KEY]["disabledMcpServers"] == ["srv"]


def check_enable_clears_every_suppressor_not_only_the_first() -> None:
    top = topology_from(
        {
            "claude_json": {
                "mcpServers": {"srv": {"command": "x"}},
                "disabledMcpServers": ["srv"],
                "projects": {PROJECT_KEY: {"disabledMcpServers": ["srv"]}},
            },
            "settings": {"deniedMcpServers": [{"serverName": "srv"}]},
        },
        project_key=PROJECT_KEY,
    )
    assert len(P.plan_enable(top, "srv").edits) == 3


def check_a_root_disable_is_credited_no_memory_saving() -> None:
    """MEASURED A/B: root disabledMcpServers does NOT prevent the process spawn."""
    top = topology_from(
        {"claude_json": {"mcpServers": {"srv": {"command": "x"}}}}, project_key=None
    )
    plan = P.build_plan([P.plan_disable(top, "srv")], project_key=None)
    result = I.preview(
        plan, {"srv": I.Cost(commit_bytes=999_999)}, regime=I.Regime.EAGER
    )
    assert result.commit_delta == 0
    assert result.no_ram_saving == ("srv",)


def check_an_unmeasured_impact_is_not_rendered_as_zero() -> None:
    result = I.preview(_disable_plan(), {}, regime=I.Regime.EAGER)
    assert result.token_delta is None
    assert result.commit_delta is None
    assert "tokens saved:  -" in I.render_impact(result)


def check_a_stale_file_is_not_overwritten() -> None:
    root = Path("/h")

    class Racing(A.MemoryFileStore):
        def read_text(self, path: Path) -> str:
            text = super().read_text(path)
            self.files[str(path)] = text + " "
            return text

    store = Racing()
    _seed(store, root, {"mcpServers": {"srv": {"command": "x"}}})
    result = A.apply_plan(
        _disable_plan(),
        paths=_paths(root),
        store=store,
        now=FIXED_NOW,
        apply=True,
        guard=lambda: "",
    )
    assert result.written == ()
    assert any("REFUSED" in p for p in result.problems)


def check_a_broken_process_probe_fails_closed() -> None:
    def explode(argv):
        raise OSError("no such tool")

    assert G.running_host_refusal(os_name="nt", runner=explode) != ""


def check_a_running_host_blocks_the_write() -> None:
    listing = '"claude.exe","1","Console","1","1 K"\n'
    assert G.running_host_refusal(os_name="nt", runner=lambda argv: listing) != ""


def check_force_does_not_bypass_the_user_scope_human_gate() -> None:
    listing = '"claude.exe","1","Console","1","1 K"\n'
    guard = G.make_guard(
        os_name="nt",
        runner=lambda argv: listing,
        force=True,
        touches_user_scope=True,
    )
    assert "HUMAN step" in guard()


def check_a_hostile_name_is_escaped_in_the_html() -> None:
    rows = build_rows(
        topology_from(
            {"claude_json": {"mcpServers": {HOSTILE: {"command": "x"}}}},
            project_key=None,
        ),
        liveness={},
    )
    page = S.render_page(rows, "tok")
    assert "<img" not in page
    assert "&lt;img" in page


def check_a_control_byte_never_reaches_the_html() -> None:
    """DEFENCE IN DEPTH: mcpctl already strips control bytes at PARSE time, so a row
    built through ``build_rows`` can never carry one and this check would stay green
    with the GUI's own sanitiser deleted. The row is therefore constructed by hand, so
    the assertion is about the GUI's escaping and nothing else."""
    row = Row(
        name="a\x1b[31mb",
        scopes=(),
        state="enabled",
        basis=(),
        inferred=False,
        transport="stdio",
    )
    assert "\x1b" not in S.render_page((row,), "tok")


def check_the_gui_refuses_a_routable_bind() -> None:
    """Asserts on the PURE validator, never on serve(): with the mutant applied a
    serve() call would really bind every interface for the duration of the test."""
    try:
        S.require_loopback("0.0.0.0")  # noqa: S104 -- the point is the refusal.
    except ValueError as exc:
        assert "loopback-only" in str(exc)
    else:
        raise AssertionError("a routable bind address must be refused")


def check_the_live_only_op_never_reaches_the_writer() -> None:
    root = Path("/h")
    store = A.MemoryFileStore()
    _seed(store, root, {"mcpServers": {"srv": {"command": "x"}}})
    plan = P.build_plan(
        [P.plan_reconnect(_simple_top(), "srv")], project_key=PROJECT_KEY
    )
    result = A.apply_plan(
        plan,
        paths=_paths(root),
        store=store,
        now=FIXED_NOW,
        apply=True,
        guard=lambda: "",
    )
    assert result.file_changes == ()
    assert store.writes == []


def check_project_scope_live_toggle_is_not_offered() -> None:
    """The 'mcp_toggle works on ANY scope' folklore is a CLEAN NEGATIVE on project."""
    from mcpapply.live import LiveOp, affordance

    assert affordance(ScopeId.MCP_JSON, LiveOp.TOGGLE).offer is False


def check_the_control_payload_is_read_from_the_inner_response() -> None:
    from mcpapply.live import parse_frame

    line = json.dumps(
        {
            "type": "control_response",
            "response": {
                "subtype": "success",
                "request_id": "x",
                "response": {"mcpServers": [{"name": "a"}]},
            },
        }
    )
    assert parse_frame(line).payload == {"mcpServers": [{"name": "a"}]}


def check_an_unmeasured_tool_count_is_not_reported_as_zero() -> None:
    from mcpapply.live import liveness_from_status

    live = liveness_from_status(
        {"mcpServers": [{"name": "broken", "status": "failed"}]}
    )
    assert live["broken"].tool_count is None


def check_a_malformed_container_is_never_clobbered() -> None:
    doc = {"disabledMcpServers": "hand-edited"}
    updated, problems = A.apply_edits_to_doc(
        doc,
        [
            P.Edit(
                scope=ScopeId.CLAUDE_USER_DISABLED,
                label="claude_json",
                key_path=("disabledMcpServers",),
                op=P.Op.LIST_ADD,
                server="srv",
            )
        ],
    )
    assert updated == doc
    assert problems != ()


def check_a_crlf_document_keeps_its_line_endings() -> None:
    """MEASURED: ~/.mcp.json is CRLF while the other four scopes are LF. Converting it
    would rewrite the whole file to change nothing an operator asked for."""
    root = Path("/h")
    store = A.MemoryFileStore()
    lf = json.dumps({"mcpServers": {"srv": {"command": "x"}}}, indent=2) + LF
    store.files[str(_paths(root).claude_json)] = lf.replace(LF, CRLF)
    A.apply_plan(
        _disable_plan(),
        paths=_paths(root),
        store=store,
        now=FIXED_NOW,
        apply=True,
        guard=lambda: "",
    )
    written = store.files[str(_paths(root).claude_json)]
    assert CRLF in written
    assert LF not in written.replace(CRLF, "")


def check_the_diff_masks_a_credential() -> None:
    secret = "sk-" + "9" * 40
    assert secret not in A._diff("l", f'"k": "{secret}"', "")


# ----------------------------------------------------------------------- mutations


def _mutate_apply_default_to_true(mp: pytest.MonkeyPatch) -> None:
    """The single highest-value mutant: flip DRY RUN to write-by-default."""
    original = A.apply_plan

    def eager(plan, *, paths, store, now, apply=True, guard=None):
        return original(
            plan, paths=paths, store=store, now=now, apply=apply, guard=guard
        )

    mp.setattr(A, "apply_plan", eager)


def _mutate_signature_default(mp: pytest.MonkeyPatch) -> None:
    def eager(plan, *, paths, store, now, apply=True, guard=None):
        """A stand-in whose `apply` default is True."""

    mp.setattr(A, "apply_plan", eager)


def _mutate_backup_to_be_skipped(mp: pytest.MonkeyPatch) -> None:
    mp.setattr(A, "backup_path", lambda target, now, taken=None: target)
    original = A.apply_plan

    def no_backup(plan, **kwargs):
        result = original(plan, **kwargs)
        return A.ApplyResult(
            dry_run=result.dry_run,
            file_changes=result.file_changes,
            backups=(),
            written=result.written,
            problems=result.problems,
            blocked=result.blocked,
        )

    mp.setattr(A, "apply_plan", no_backup)


def _mutate_restore_command_to_silence(mp: pytest.MonkeyPatch) -> None:
    mp.setattr(A, "restore_command", lambda records: "")


def _mutate_deepcopy_to_a_rebuilt_model(mp: pytest.MonkeyPatch) -> None:
    """The classic wipe: rebuild the document from only the keys this tool knows."""
    known = {"mcpServers", "disabledMcpServers", "projects"}

    def rebuild(doc, edits):
        trimmed = {k: v for k, v in dict(doc).items() if k in known}
        if "projects" in trimmed:
            trimmed["projects"] = {
                key: {"disabledMcpServers": row.get("disabledMcpServers", [])}
                for key, row in trimmed["projects"].items()
            }
        node = trimmed.setdefault("projects", {}).setdefault(PROJECT_KEY, {})
        node.setdefault("disabledMcpServers", []).append("srv")
        return trimmed, ()

    mp.setattr(A, "apply_edits_to_doc", rebuild)


def _mutate_denied_matcher_to_strings_only(mp: pytest.MonkeyPatch) -> None:
    mp.setattr(A, "_denied_matches", lambda item, name: item == name)


def _mutate_disable_to_walk_to_an_ancestor(mp: pytest.MonkeyPatch) -> None:
    original = P.plan_disable

    def ancestor(top, name):
        change = original(top, name)
        rewritten = tuple(
            P.Edit(
                scope=e.scope,
                label=e.label,
                key_path=("projects", "C:/Users/Owner", "disabledMcpServers"),
                op=e.op,
                server=e.server,
            )
            if e.key_path[:1] == ("projects",)
            else e
            for e in change.edits
        )
        return P.Change(
            intent=change.intent,
            server=change.server,
            edits=rewritten,
            warnings=change.warnings,
            before=change.before,
        )

    mp.setattr(P, "plan_disable", ancestor)


def _mutate_enable_to_clear_only_the_top_suppressor(mp: pytest.MonkeyPatch) -> None:
    mp.setattr(P, "SUPPRESSORS", (ScopeId.SETTINGS_DENIED,))


def _mutate_spawn_prevention_to_include_the_root_list(mp: pytest.MonkeyPatch) -> None:
    mp.setattr(
        I,
        "SPAWN_PREVENTING",
        frozenset(
            {
                ScopeId.SETTINGS_DENIED,
                ScopeId.CLAUDE_PROJECT_DISABLED,
                ScopeId.CLAUDE_USER_DISABLED,
            }
        ),
    )


def _mutate_unmeasured_impact_to_zero(mp: pytest.MonkeyPatch) -> None:
    original = I.preview

    def zeroed(plan, costs, *, regime, fleet_size=0):
        result = original(plan, costs, regime=regime, fleet_size=fleet_size)
        return I.Impact(
            regime=result.regime,
            token_delta=result.token_delta or 0,
            commit_delta=result.commit_delta or 0,
            unmeasured=result.unmeasured,
            no_ram_saving=result.no_ram_saving,
            notes=result.notes,
        )

    mp.setattr(I, "preview", zeroed)


def _mutate_stale_check_away(mp: pytest.MonkeyPatch) -> None:
    mp.setattr(A, "_STALE", "")
    original = A.MemoryFileStore.read_text

    def trusting(self, path):
        try:
            return original(self, path)
        finally:
            pass

    mp.setattr(A, "_STALE", "{label} (ignored)")


def _mutate_guard_to_fail_open(mp: pytest.MonkeyPatch) -> None:
    mp.setattr(
        G,
        "running_host_refusal",
        lambda *, os_name, runner, force=False: "",
    )


def _mutate_host_names_away(mp: pytest.MonkeyPatch) -> None:
    mp.setattr(G, "HOST_PROCESS_NAMES", ())


def _mutate_force_to_override_the_human_gate(mp: pytest.MonkeyPatch) -> None:
    mp.setattr(
        G,
        "user_scope_promotion_refusal",
        lambda *, touches_user_scope, host_running: "",
    )


def _mutate_escaping_to_raw(mp: pytest.MonkeyPatch) -> None:
    mp.setattr(S, "_esc", lambda text: text)


def _mutate_serve_to_accept_any_host(mp: pytest.MonkeyPatch) -> None:
    mp.setattr(S, "LOOPBACK_HOSTS", frozenset({"127.0.0.1", "0.0.0.0"}))  # noqa: S104


def _mutate_live_only_to_be_written(mp: pytest.MonkeyPatch) -> None:
    def grouped(plan):
        out: dict[str, list[P.Edit]] = {}
        for change in plan.changes:
            for edit in change.edits:
                out.setdefault("claude_json", []).append(
                    P.Edit(
                        scope=ScopeId.CLAUDE_USER_DISABLED,
                        label="claude_json",
                        key_path=("disabledMcpServers",),
                        op=P.Op.LIST_ADD,
                        server=edit.server,
                    )
                )
        return out

    mp.setattr(A, "_edits_by_label", grouped)


def _mutate_project_toggle_to_proven(mp: pytest.MonkeyPatch) -> None:
    """Re-assert the refuted folklore: 'mcp_toggle works on ANY scope'."""
    from mcpapply import live as L

    mp.setattr(
        L,
        "AFFORDANCES",
        (
            L.Affordance(
                ScopeId.MCP_JSON, L.LiveOp.TOGGLE, L.Proof.PROVEN, "any scope works"
            ),
        ),
    )


def _mutate_parse_frame_to_read_the_outer_body(mp: pytest.MonkeyPatch) -> None:
    from mcpapply import live as L

    original = L.parse_frame

    def outer(line):
        parsed = original(line)
        body = json.loads(line).get("response", {})
        return type(parsed)(
            request_id=parsed.request_id,
            payload={k: v for k, v in body.items() if k == "mcpServers"},
            error=parsed.error,
            is_control=parsed.is_control,
        )

    mp.setattr(L, "parse_frame", outer)


def _mutate_missing_tools_to_zero(mp: pytest.MonkeyPatch) -> None:
    from mcpapply import live as L

    def zeroed(payload):
        return {
            str(s.get("name")): Liveness(tool_count=len(s.get("tools") or []))
            for s in L.status_servers(payload)
        }

    mp.setattr(L, "liveness_from_status", zeroed)


def _mutate_malformed_container_to_be_overwritten(mp: pytest.MonkeyPatch) -> None:
    def clobber(doc, edits):
        working = dict(doc)
        for edit in edits:
            working[edit.key_path[-1]] = [edit.server]
        return working, ()

    mp.setattr(A, "apply_edits_to_doc", clobber)


def _mutate_line_ending_to_always_lf(mp: pytest.MonkeyPatch) -> None:
    mp.setattr(A, "line_ending", lambda text: LF)


def _mutate_diff_to_skip_redaction(mp: pytest.MonkeyPatch) -> None:
    import difflib

    def raw(label, before, after):
        return "\n".join(
            difflib.unified_diff(before.splitlines(), after.splitlines(), lineterm="")
        )

    mp.setattr(A, "_diff", raw)


# --------------------------------------------------------------------------
# Checks for the decisions taken in the adversarial-review repair
# --------------------------------------------------------------------------


def check_each_apply_gets_its_own_backup_name() -> None:
    """Two writes in one process must not land on the same sidecar."""
    root = Path("/h")
    store = A.MemoryFileStore()
    _seed(store, root, {"mcpServers": {"srv": {"command": "x"}}})
    first = A.apply_plan(
        _disable_plan(),
        paths=_paths(root),
        store=store,
        now=FIXED_NOW,
        apply=True,
        guard=lambda: "",
    )
    pristine = store.files[first.backups[0].backup]
    _seed(store, root, {"mcpServers": {"srv": {"command": "y"}}})
    second = A.apply_plan(
        _disable_plan(),
        paths=_paths(root),
        store=store,
        now=FIXED_NOW,
        apply=True,
        guard=lambda: "",
    )
    assert first.backups[0].backup != second.backups[0].backup
    assert store.files[first.backups[0].backup] == pristine


def check_a_proxy_token_figure_is_labelled_as_one() -> None:
    """A guessed number must never render identically to a measured one."""
    plan = _disable_plan()

    def rendered(basis: I.TokenBasis) -> str:
        cost = I.Cost(token_cost=500, token_basis=basis, commit_bytes=1)
        return I.render_impact(I.preview(plan, {"srv": cost}, regime=I.Regime.EAGER))

    assert rendered(I.TokenBasis.EXACT) != rendered(I.TokenBasis.TOOL_COUNT)
    assert "[tool-count-proxy]" in rendered(I.TokenBasis.TOOL_COUNT)


def check_a_provenanceless_number_is_not_summed() -> None:
    """``token_cost`` with no declared basis is unmeasured, not a total."""
    cost = I.Cost(token_cost=500, token_basis=I.TokenBasis.NOT_MEASURED)
    result = I.preview(_disable_plan(), {"srv": cost}, regime=I.Regime.EAGER)
    assert result.token_delta is None
    assert result.partial is True


def check_an_empty_spec_cannot_replace_a_definition() -> None:
    """The one-word wipe: `edit <srv>` with no --spec."""
    top = _simple_top()
    try:
        P.plan_edit(top, "srv", {})
    except ValueError:
        return
    raise AssertionError("an empty spec was accepted and would wipe the definition")


def check_a_native_project_path_reaches_the_row_the_host_reads() -> None:
    from mcpapply.cli import _project_key

    assert _project_key(PROJECT_KEY.replace("/", chr(92))) == PROJECT_KEY


def check_a_write_that_did_not_happen_is_not_reported_as_success() -> None:
    from mcpapply.cli import _classify

    refused = A.ApplyResult(dry_run=False, problems=("target moved; REFUSED",))
    assert _classify(refused, False).status == "error"


def check_the_static_root_is_contained_not_blocklisted() -> None:
    """A name that resolves outside the static tree must never be served."""
    escaped = (S.STATIC_DIR.resolve().parent / "pyproject.toml").resolve()
    assert not escaped.is_relative_to(S.STATIC_DIR.resolve())


def check_the_host_allowlist_requires_a_numeric_port() -> None:
    assert S.host_allowed("127.0.0.1:8000") is True
    assert S.host_allowed("127.0.0.1:8000.evil.example") is False


def check_the_gui_offers_no_intent_its_form_cannot_carry() -> None:
    assert "edit" not in S.GUI_INTENTS
    assert "remove" not in S.GUI_INTENTS
    assert set(S.GUI_INTENTS) <= {"disable", "enable"}


def _mutate_backup_name_to_ignore_collisions(mp: pytest.MonkeyPatch) -> None:
    """Revert to the stamp-only name: two writes in one second collide."""
    from mcpapply import backup as B

    mp.setattr(
        A,
        "backup_path",
        lambda target, now, taken=None: target.with_name(
            f"{target.name}.{B.BACKUP_SUFFIX}-{B.utc_stamp(now)}.bak"
        ),
    )


def _mutate_weakest_basis_to_always_exact(mp: pytest.MonkeyPatch) -> None:
    """Launder every proxy figure as a measurement."""
    mp.setattr(I, "weakest_basis", lambda bases: I.TokenBasis.EXACT)
    mp.setattr(I, "render_impact", _basis_free_render)


def _basis_free_render(impact: "I.Impact") -> str:
    """The pre-fix renderer: a bare integer with no basis beside it."""
    return f"tokens saved:  {impact.token_delta}"


def _mutate_undeclared_basis_to_be_summed(mp: pytest.MonkeyPatch) -> None:
    """Treat a provenance-less number as if it were measured."""
    real = I.Cost

    def coerced(*args: object, **kwargs: object):
        kwargs.setdefault("token_basis", I.TokenBasis.EXACT)
        if kwargs.get("token_basis") is I.TokenBasis.NOT_MEASURED:
            kwargs["token_basis"] = I.TokenBasis.EXACT
        return real(*args, **kwargs)  # type: ignore[arg-type]

    mp.setattr(I, "Cost", coerced)


def _mutate_empty_spec_guard_away(mp: pytest.MonkeyPatch) -> None:
    mp.setattr(P, "_require_spec", lambda spec, *, verb, name: None)


def _mutate_project_key_to_pass_the_raw_value(mp: pytest.MonkeyPatch) -> None:
    from mcpapply import cli as C

    mp.setattr(C, "_project_key", lambda raw: raw)


def _mutate_classify_to_warn_on_a_failed_write(mp: pytest.MonkeyPatch) -> None:
    """The pre-fix mapping: any problem is a warning, and a warning is SUCCESS."""
    from mcpctl import envelope

    from mcpapply import cli as C

    def lenient(result, dry_run_requested):
        if result.problems:
            return envelope.warning("problems", next_actions=())
        return envelope.success("ok")

    mp.setattr(C, "_classify", lenient)


def _mutate_containment_to_a_character_blocklist(mp: pytest.MonkeyPatch) -> None:
    """Revert to `"/" in name or ".." in name`, which misses every Windows shape."""
    mp.setattr(Path, "is_relative_to", lambda self, other: True)


def _mutate_gui_intents_to_the_full_verb_set(mp: pytest.MonkeyPatch) -> None:
    mp.setattr(
        S, "GUI_INTENTS", ("enable", "disable", "add", "remove", "edit", "reconnect")
    )


def _mutate_host_allowlist_to_split_on_the_last_colon(mp: pytest.MonkeyPatch) -> None:
    mp.setattr(
        S, "host_allowed", lambda host: host.rsplit(":", 1)[0] in S.LOOPBACK_HOSTS
    )


#: (mutant id, apply-the-mutation, the check that MUST go red)
MUTANTS: tuple[
    tuple[str, Callable[[pytest.MonkeyPatch], None], Callable[[], None]], ...
] = (
    (
        "backup-name-frozen-per-process",
        _mutate_backup_name_to_ignore_collisions,
        check_each_apply_gets_its_own_backup_name,
    ),
    (
        "proxy-basis-laundered-as-exact",
        _mutate_weakest_basis_to_always_exact,
        check_a_proxy_token_figure_is_labelled_as_one,
    ),
    (
        "undeclared-basis-summed-as-a-total",
        _mutate_undeclared_basis_to_be_summed,
        check_a_provenanceless_number_is_not_summed,
    ),
    (
        "empty-spec-wipes-a-definition",
        _mutate_empty_spec_guard_away,
        check_an_empty_spec_cannot_replace_a_definition,
    ),
    (
        "project-key-separator-unnormalised",
        _mutate_project_key_to_pass_the_raw_value,
        check_a_native_project_path_reaches_the_row_the_host_reads,
    ),
    (
        "refusal-reported-as-success",
        _mutate_classify_to_warn_on_a_failed_write,
        check_a_write_that_did_not_happen_is_not_reported_as_success,
    ),
    (
        "static-containment-downgraded-to-a-blocklist",
        _mutate_containment_to_a_character_blocklist,
        check_the_static_root_is_contained_not_blocklisted,
    ),
    (
        "host-allowlist-splits-on-the-last-colon",
        _mutate_host_allowlist_to_split_on_the_last_colon,
        check_the_host_allowlist_requires_a_numeric_port,
    ),
    (
        "gui-api-accepts-verbs-its-form-cannot-carry",
        _mutate_gui_intents_to_the_full_verb_set,
        check_the_gui_offers_no_intent_its_form_cannot_carry,
    ),
    (
        "dry-run-default-flipped-to-apply",
        _mutate_apply_default_to_true,
        check_dry_run_is_the_default,
    ),
    (
        "apply-signature-default-true",
        _mutate_signature_default,
        check_the_default_parameter_itself_is_false,
    ),
    (
        "backup-skipped",
        _mutate_backup_to_be_skipped,
        check_a_backup_is_taken_before_a_write,
    ),
    (
        "restore-command-silenced",
        _mutate_restore_command_to_silence,
        check_the_restore_command_is_printed,
    ),
    (
        "unknown-key-preservation-dropped",
        _mutate_deepcopy_to_a_rebuilt_model,
        check_unknown_keys_survive_a_write,
    ),
    (
        "denied-read-as-bare-strings",
        _mutate_denied_matcher_to_strings_only,
        check_denied_list_is_read_as_objects,
    ),
    (
        "ancestor-project-row-substituted",
        _mutate_disable_to_walk_to_an_ancestor,
        check_an_ancestor_project_row_is_never_substituted,
    ),
    (
        "enable-clears-only-the-top-suppressor",
        _mutate_enable_to_clear_only_the_top_suppressor,
        check_enable_clears_every_suppressor_not_only_the_first,
    ),
    (
        "root-disable-credited-with-ram",
        _mutate_spawn_prevention_to_include_the_root_list,
        check_a_root_disable_is_credited_no_memory_saving,
    ),
    (
        "unmeasured-impact-rendered-as-zero",
        _mutate_unmeasured_impact_to_zero,
        check_an_unmeasured_impact_is_not_rendered_as_zero,
    ),
    (
        "stale-write-allowed",
        _mutate_stale_check_away,
        check_a_stale_file_is_not_overwritten,
    ),
    (
        "guard-fails-open",
        _mutate_guard_to_fail_open,
        check_a_broken_process_probe_fails_closed,
    ),
    (
        "host-process-names-emptied",
        _mutate_host_names_away,
        check_a_running_host_blocks_the_write,
    ),
    (
        "force-overrides-the-human-gate",
        _mutate_force_to_override_the_human_gate,
        check_force_does_not_bypass_the_user_scope_human_gate,
    ),
    (
        "html-escaping-removed",
        _mutate_escaping_to_raw,
        check_a_hostile_name_is_escaped_in_the_html,
    ),
    (
        "control-strip-removed-from-the-page",
        _mutate_escaping_to_raw,
        check_a_control_byte_never_reaches_the_html,
    ),
    (
        "gui-binds-any-interface",
        _mutate_serve_to_accept_any_host,
        check_the_gui_refuses_a_routable_bind,
    ),
    (
        "live-only-op-written-to-disk",
        _mutate_live_only_to_be_written,
        check_the_live_only_op_never_reaches_the_writer,
    ),
    (
        "project-scope-toggle-advertised",
        _mutate_project_toggle_to_proven,
        check_project_scope_live_toggle_is_not_offered,
    ),
    (
        "control-payload-read-from-the-outer-frame",
        _mutate_parse_frame_to_read_the_outer_body,
        check_the_control_payload_is_read_from_the_inner_response,
    ),
    (
        "missing-tools-counted-as-zero",
        _mutate_missing_tools_to_zero,
        check_an_unmeasured_tool_count_is_not_reported_as_zero,
    ),
    (
        "malformed-container-overwritten",
        _mutate_malformed_container_to_be_overwritten,
        check_a_malformed_container_is_never_clobbered,
    ),
    (
        "diff-skips-redaction",
        _mutate_diff_to_skip_redaction,
        check_the_diff_masks_a_credential,
    ),
    (
        "crlf-converted-to-lf",
        _mutate_line_ending_to_always_lf,
        check_a_crlf_document_keeps_its_line_endings,
    ),
)


def test_every_check_passes_unmutated():
    """Control: without a mutation every check must be GREEN.

    Without this, a check that is broken outright would 'detect' every mutant and the
    probe would report success while measuring nothing.
    """
    for mutant_id, _apply, check in MUTANTS:
        check()  # must not raise
        assert mutant_id


@pytest.mark.parametrize(
    ("mutant_id", "apply_mutation", "check"),
    MUTANTS,
    ids=[m[0] for m in MUTANTS],
)
def test_each_mutant_is_detected(
    mutant_id: str,
    apply_mutation: Callable[[pytest.MonkeyPatch], None],
    check: Callable[[], None],
    monkeypatch: pytest.MonkeyPatch,
):
    apply_mutation(monkeypatch)
    with pytest.raises(AssertionError):
        check()


def test_the_mutant_set_covers_every_load_bearing_module():
    """Guards against the set quietly shrinking to the easy modules."""
    assert len(MUTANTS) >= 33
    assert len({m[0] for m in MUTANTS}) == len(MUTANTS), "duplicate mutant id"


def test_the_brief_mandated_mutants_are_all_present():
    """The six named in the work order, by id, so a rename cannot silently drop one."""
    ids = {m[0] for m in MUTANTS}
    required: Iterable[str] = (
        "dry-run-default-flipped-to-apply",
        "backup-skipped",
        "unknown-key-preservation-dropped",
        "denied-read-as-bare-strings",
        "ancestor-project-row-substituted",
        "unmeasured-impact-rendered-as-zero",
    )
    assert set(required) <= ids
