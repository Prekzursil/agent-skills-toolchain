"""SEM-008..SEM-011 - the work-unit authorization plane (defect D2).

Before this plane existed, ``check_work_units`` implemented SEM-001..007 and NOT ONE of them
was about authorization, while ``check_workflow`` carried DSL-SEM-001..014 including a
deny-by-default tool policy. A unit could hold ``Task`` (spawn subagents), reach an MCP
server, or wildcard a whole server family, and nothing objected. Measured on the real
catalog at that moment: 144 units declared ``owner_approval_required: true``, 25 held
``Task`` with 23 of those unapproved, 261 held an ``mcp__`` token, and 120 held a token
containing ``*``.

Every test below is a both-states control: the rule must FIRE on a seeded violation and be
SILENT on the good state. A rule that is silent in both measures nothing
(``rules/common/single-signal-verification.md`` 3b), and a green suite over a rule that
cannot go red is indistinguishable from a no-op (``rules/common/ci-hygiene.md`` section 1).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from wfdsl import authz_census, schemas, semantics, validate

CATALOG = schemas.REPO_ROOT / "command-center" / "WORK-UNIT-CATALOG.json"

AUTHZ_RULES = ("SEM-008", "SEM-009", "SEM-010", "SEM-011")

#: a policy narrow enough that the seeds below are unambiguous
POLICY: dict = {
    "default": "deny",
    "allow": ["Read", "Grep", "Write", "Bash", "Task", "mcp__github__search_code"],
    "deny": ["mcp__github__merge_pull_request"],
    "require_owner_approval": ["Task"],
}


def unit(**over) -> dict:
    base = {
        "id": "AUZ-0001",
        "execution_substrate": "local-serialized",
        "owner_approval_required": False,
        "tool_permissions": ["Read", "Grep"],
    }
    base.update(over)
    return base


def fired(units, policy=POLICY) -> dict[str, int]:
    return {
        r.rule: len(r.violations)
        for r in semantics.check_work_unit_authorization(units, policy)
    }


# ------------------------------------------------------------------- the token parser


@pytest.mark.parametrize(
    ("raw", "identity", "scope", "base", "server", "method"),
    [
        ("Read", "Read", "", "Read", "", ""),
        ("Bash:python", "Bash:python", "", "Bash", "", ""),
        ("Bash(pytest)", "Bash", "pytest", "Bash", "", ""),
        (
            "Write(command-center/research/**)",
            "Write",
            "command-center/research/**",
            "Write",
            "",
            "",
        ),
        (
            "PowerShell(read-only: Get-ChildItem/Get-Content)",
            "PowerShell",
            "read-only: Get-ChildItem/Get-Content",
            "PowerShell",
            "",
            "",
        ),
        (
            "mcp__github__search_code",
            "mcp__github__search_code",
            "",
            "mcp__github__search_code",
            "github",
            "search_code",
        ),
        (
            "mcp__search-hub__* (read-only retrieval)",
            "mcp__search-hub__*",
            "read-only retrieval",
            "mcp__search-hub__*",
            "search-hub",
            "*",
        ),
        (
            "mcp__codex__codex-reply",
            "mcp__codex__codex-reply",
            "",
            "mcp__codex__codex-reply",
            "codex",
            "codex-reply",
        ),
    ],
)
def test_parse_tool_token_splits_every_surface_form(
    raw: str, identity: str, scope: str, base: str, server: str, method: str
) -> None:
    t = semantics.parse_tool_token(raw)
    assert (t.identity, t.scope, t.base, t.server, t.method) == (
        identity,
        scope,
        base,
        server,
        method,
    )


def test_a_scope_glob_is_a_narrowing_not_a_wildcard() -> None:
    """The distinction the corpus census turns on: 111 of the 120 '*' units are narrowings.

    ``Write(command-center/research/**)`` grants LESS than the bare ``Write`` that 1,549
    units hold. Treating it as a broadening would gate least privilege behind an approval
    and reward the unscoped grant.
    """
    narrow = semantics.parse_tool_token("Write(command-center/research/**)")
    broad = semantics.parse_tool_token("mcp__search-hub__*")
    assert narrow.scope_wildcard and not narrow.identity_wildcard
    assert broad.identity_wildcard and not broad.scope_wildcard
    assert (
        fired([unit(tool_permissions=["Write(command-center/research/**)"])])["SEM-009"]
        == 0
    )
    assert fired([unit(tool_permissions=["mcp__search-hub__*"])])["SEM-009"] == 1


@pytest.mark.parametrize(
    ("entry", "token", "permits"),
    [
        ("Read", "Read", True),
        ("Bash", "Bash:python", True),  # sub-shell form is less than the base grant
        ("Bash", "Bash(pytest)", True),  # path/arg scope is less than the base grant
        ("Bash:python", "Bash", False),  # the reverse must NOT hold
        ("Write", "Write(command-center/research/**)", True),
        ("mcp__github__*", "mcp__github__search_code", True),
        (
            "mcp__github__search_code",
            "mcp__github__*",
            False,
        ),  # specific never covers *
        ("mcp__github__search_code", "mcp__github__list_commits", False),
        ("mcp__github__*", "mcp__deepwiki__ask_question", False),
        ("Read", "mcp__github__search_code", False),
        ("mcp__github__*", "Read", False),
        # A scoped POLICY entry matches only by exact string. If it fell back to base-family
        # matching, an allowlist of `Write(reports/**)` would silently permit a bare `Write`
        # and the author would believe writes were restricted.
        ("Write(reports/**)", "Write", False),
        ("Write(reports/**)", "Write(other/**)", False),
        ("Write(reports/**)", "Write(reports/**)", True),
    ],
)
def test_policy_entry_family_semantics(entry: str, token: str, permits: bool) -> None:
    assert (
        semantics.policy_entry_permits(entry, semantics.parse_tool_token(token))
        is permits
    )


# --------------------------------------------------------- SEM-008 deny by default


def test_sem008_allows_a_listed_tool_and_rejects_an_unlisted_one() -> None:
    assert fired([unit(tool_permissions=["Read", "Grep"])])["SEM-008"] == 0
    assert (
        fired([unit(tool_permissions=["Read", "mcp__deepwiki__ask_question"])])[
            "SEM-008"
        ]
        == 1
    )


def test_sem008_deny_beats_allow() -> None:
    policy = {**POLICY, "allow": [*POLICY["allow"], "mcp__github__merge_pull_request"]}
    assert (
        fired([unit(tool_permissions=["mcp__github__merge_pull_request"])], policy)[
            "SEM-008"
        ]
        == 1
    )


def test_sem008_fails_closed_when_no_policy_is_declared() -> None:
    """'No policy found' must never read as 'nothing to check'."""
    assert fired([unit()], None)["SEM-008"] == 1
    assert fired([unit()], {})["SEM-008"] == 1
    assert fired([unit()], POLICY)["SEM-008"] == 0


def test_sem008_honours_an_explicit_default_allow_but_still_enforces_deny() -> None:
    policy = {"default": "allow", "deny": ["mcp__github__merge_pull_request"]}
    assert (
        fired([unit(tool_permissions=["mcp__deepwiki__ask_question"])], policy)[
            "SEM-008"
        ]
        == 0
    )
    assert (
        fired([unit(tool_permissions=["mcp__github__merge_pull_request"])], policy)[
            "SEM-008"
        ]
        == 1
    )


def test_sem008_does_not_charge_a_unit_that_requests_no_tool() -> None:
    res = semantics.check_work_unit_authorization([unit(tool_permissions=[])], None)
    sem008 = next(r for r in res if r.rule == "SEM-008")
    assert sem008.checked == 0
    assert not sem008.violations


# ------------------------------------------------------------ SEM-009 approval coherence


def test_sem009_gates_task_and_is_satisfied_by_a_recorded_approval() -> None:
    bad = unit(tool_permissions=["Read", "Task"], owner_approval_required=False)
    good = unit(tool_permissions=["Read", "Task"], owner_approval_required=True)
    assert fired([bad])["SEM-009"] == 1
    assert fired([good])["SEM-009"] == 0


def test_sem009_gates_an_identity_wildcard_grant() -> None:
    bad = unit(tool_permissions=["Read", "mcp__paper-search__*"])
    assert fired([bad])["SEM-009"] == 1
    assert fired([{**bad, "owner_approval_required": True}])["SEM-009"] == 0


def test_sem009_floor_survives_a_loosened_policy() -> None:
    """A policy edit cannot un-gate ``Task``: the floor is code, not data.

    G4 of the tournament verdict requires exactly this - "a test must fail if the policy is
    ever loosened past a hardcoded floor".
    """
    loose = {"default": "allow", "allow": ["Task"], "require_owner_approval": []}
    assert fired([unit(tool_permissions=["Read", "Task"])], loose)["SEM-009"] == 1
    assert semantics.APPROVAL_FLOOR_TOOLS == frozenset({"Task"})


def test_sem009_gates_a_policy_listed_tool_beyond_the_floor() -> None:
    policy = {**POLICY, "require_owner_approval": ["Task", "mcp__github__search_code"]}
    assert (
        fired([unit(tool_permissions=["mcp__github__search_code"])], policy)["SEM-009"]
        == 1
    )
    assert (
        fired([unit(tool_permissions=["mcp__github__search_code"])], POLICY)["SEM-009"]
        == 0
    )


def test_sem009_treats_a_non_true_flag_as_unapproved() -> None:
    for value in (False, None, "true", 1, "yes"):
        assert (
            fired([unit(tool_permissions=["Task"], owner_approval_required=value)])[
                "SEM-009"
            ]
            == 1
        ), value


# ----------------------------------------------------------- SEM-010 substrate coherence


@pytest.mark.parametrize("substrate", sorted(semantics.REMOTE_SUBSTRATES))
@pytest.mark.parametrize("tool", sorted(semantics.SESSION_LOCAL_TOOLS))
def test_sem010_rejects_a_session_local_tool_on_every_remote_substrate(
    substrate: str, tool: str
) -> None:
    bad = unit(
        execution_substrate=substrate,
        tool_permissions=["Read", tool],
        owner_approval_required=True,
    )
    assert fired([bad])["SEM-010"] == 1


@pytest.mark.parametrize(
    "substrate", ["local-parallel", "local-serialized", "worktree-isolated"]
)
def test_sem010_permits_the_same_tool_on_a_local_substrate(substrate: str) -> None:
    ok = unit(
        execution_substrate=substrate,
        tool_permissions=["Read", "Task"],
        owner_approval_required=True,
    )
    assert fired([ok])["SEM-010"] == 0


def test_sem010_is_not_cured_by_an_approval() -> None:
    """Approval is a permission fact; substrate coherence is a capability fact.

    Both TST-0293 and TST-0294 declared ``owner_approval_required: true`` AND
    ``cloud-batch`` AND ``Task``. The approval was real; the substrate still could not
    honour the tool.
    """
    bad = unit(
        execution_substrate="cloud-batch",
        tool_permissions=["Read", "Task"],
        owner_approval_required=True,
    )
    assert fired([bad])["SEM-010"] == 1


def test_sem010_does_not_charge_a_local_unit() -> None:
    res = semantics.check_work_unit_authorization([unit()], POLICY)
    sem010 = next(r for r in res if r.rule == "SEM-010")
    assert sem010.checked == 0


# ---------------------------------------------------------- SEM-011 mcp specificity


@pytest.mark.parametrize(
    "token",
    [
        "mcp__search-hub__*",
        "mcp__search-hub__* (read-only retrieval)",
        "mcp__paper-search__*",
        "mcp__github__search_*",
    ],
)
def test_sem011_rejects_a_wildcarded_mcp_token(token: str) -> None:
    bad = unit(tool_permissions=[token], owner_approval_required=True)
    assert fired([bad])["SEM-011"] == 1


@pytest.mark.parametrize(
    "token",
    [
        "mcp__github__search_code",
        "mcp__codex__codex-reply",
        "mcp__search-hub__web_search_exa",
    ],
)
def test_sem011_accepts_a_fully_named_mcp_token(token: str) -> None:
    assert (
        fired([unit(tool_permissions=[token], owner_approval_required=True)])["SEM-011"]
        == 0
    )


def test_sem011_rejects_a_token_that_is_not_a_parseable_mcp_id() -> None:
    assert fired([unit(tool_permissions=["mcp__NotAServer__x"])])["SEM-011"] == 1
    assert fired([unit(tool_permissions=["mcp__github__"])])["SEM-011"] == 1


def test_sem011_ignores_native_tokens_entirely() -> None:
    res = semantics.check_work_unit_authorization(
        [unit(tool_permissions=["Read", "Bash:python", "Write(a/**)"])], POLICY
    )
    sem011 = next(r for r in res if r.rule == "SEM-011")
    assert sem011.checked == 0
    assert not sem011.violations


# ------------------------------------------------------------------ wiring + the corpus


def test_check_work_units_returns_the_authorization_plane() -> None:
    rules = [r.rule for r in semantics.check_work_units([unit()], POLICY)]
    assert rules[:7] == [f"SEM-00{i}" for i in range(1, 8)]
    assert rules[7:] == list(AUTHZ_RULES)


def test_every_authorization_rule_is_a_violation_not_an_advisory() -> None:
    """Landed at `violation`, not `advisory`: the corpus is clean, so an advisory here
    would be a gate that cannot go red - see the module docstring."""
    for r in semantics.check_work_unit_authorization([unit()], POLICY):
        assert r.severity == "violation", r.rule


@pytest.fixture(scope="module")
def catalog() -> dict:
    if not CATALOG.is_file():  # pragma: no cover - environment guard
        pytest.skip(f"catalog not present at {CATALOG}")
    return json.loads(Path(CATALOG).read_text(encoding="utf-8"))


def test_the_real_catalog_declares_a_deny_by_default_tool_policy(catalog: dict) -> None:
    policy = catalog.get("tool_policy")
    assert policy, "the catalog must declare tool_policy or SEM-008 denies every tool"
    assert policy.get("default") == "deny"
    assert "Task" in policy.get("require_owner_approval", [])
    assert policy.get("allow"), (
        "an empty allowlist under default=deny denies everything"
    )


def test_the_real_catalog_has_zero_authorization_violations(catalog: dict) -> None:
    by_rule = {
        r.rule: r
        for r in semantics.check_work_unit_authorization(
            catalog["work_units"], catalog.get("tool_policy")
        )
    }
    for rule in AUTHZ_RULES:
        assert by_rule[rule].violations == [], (rule, by_rule[rule].violations[:5])
    # and the rules actually looked at something - a checked=0 pass is a no-op pass
    assert by_rule["SEM-008"].checked == len(catalog["work_units"])
    assert by_rule["SEM-009"].checked > 0
    assert by_rule["SEM-010"].checked > 0
    assert by_rule["SEM-011"].checked > 0


def test_validate_catalog_surfaces_the_authorization_plane() -> None:
    report = validate.validate_catalog(CATALOG, profiles=("structural",))
    assert report["tool_policy_declared"] is True
    by_rule = {r["rule"]: r["violations"] for r in report["semantic_rules"]}
    for rule in AUTHZ_RULES:
        assert by_rule[rule] == 0, rule


def test_the_census_gate_is_green_and_its_controls_discriminate() -> None:
    report = authz_census.build_report(CATALOG)
    assert report["ok"], report["failures"]
    assert report["controls_discriminating"]
    for key, row in report["both_states"].items():
        assert row["fires_on_bad"], key
        assert row["silent_on_good"], key


@pytest.mark.parametrize(
    ("mutation", "expected_red"),
    [
        ("drop_tool_policy", "the catalog declares a deny-by-default tool_policy"),
        ("flip_default_to_allow", "the catalog declares a deny-by-default tool_policy"),
        (
            "seed_unapproved_task",
            "every work-unit authorization rule is clean on the real catalog",
        ),
    ],
)
def test_run_all_gate_goes_red_on_a_seeded_authorization_defect(
    tmp_path: Path, catalog: dict, mutation: str, expected_red: str
) -> None:
    """Both-states control on the two gating assertions added to ``run_all``.

    They already read PASS on the clean tree (asserted by
    ``test_validate_catalog_surfaces_the_authorization_plane`` and the census gate). A
    green that cannot turn red proves nothing, so each mutation is applied to a catalog
    built from REAL units plus the REAL policy, and the named assertion must flip to False.

    The slice is 3 units rather than all 2,007 only for wall time: ``run_all`` validates
    every unit against three profiles, and the corpus-wide cleanliness of these rules is
    asserted against the full catalog in
    ``test_the_real_catalog_has_zero_authorization_violations``.
    """
    mutated = json.loads(json.dumps(catalog))
    # The slice is chosen so all FOUR rules have a subject: TST-0257 holds Task (SEM-009),
    # TST-0198 declares a remote substrate (SEM-010), WFA-0021 holds mcp tokens (SEM-011).
    # A slice with no subject would make the gate pass on checked=0 - which the assertion
    # itself forbids, and which is how this control found its own first draft to be wrong.
    keep = {"TST-0257", "TST-0198", "WFA-0021"}
    mutated["work_units"] = [u for u in mutated["work_units"] if u["id"] in keep]
    assert len(mutated["work_units"]) == 3
    # the control direction: this slice must be GREEN before the mutation is applied
    clean = tmp_path / "clean.json"
    clean.write_text(json.dumps(mutated), encoding="utf-8")
    baseline = validate.run_all(clean)
    assert baseline["ok"], baseline["assertions_failed"]

    if mutation == "drop_tool_policy":
        mutated.pop("tool_policy")
    elif mutation == "flip_default_to_allow":
        mutated["tool_policy"]["default"] = "allow"
    else:
        for u in mutated["work_units"]:
            if u["id"] == "TST-0257":
                u["owner_approval_required"] = False
    path = tmp_path / "WORK-UNIT-CATALOG.json"
    path.write_text(json.dumps(mutated), encoding="utf-8")

    report = validate.run_all(path)
    assert expected_red in report["assertions_failed"], report["assertions_failed"]
    assert report["ok"] is False


def test_the_census_gate_fails_closed_on_an_empty_catalog(tmp_path: Path) -> None:
    empty = tmp_path / "empty.json"
    empty.write_text(
        json.dumps({"schema_version": 1, "work_units": []}), encoding="utf-8"
    )
    with pytest.raises(authz_census.AuthzCensusError):
        authz_census.build_report(empty)
    missing = tmp_path / "nope.json"
    with pytest.raises(authz_census.AuthzCensusError):
        authz_census.build_report(missing)


def test_the_before_state_is_re_derivable_from_the_pinned_commit() -> None:
    """The BEFORE half of the census must survive the commit.

    `*.log` is gitignored, so a console log is evidence that disappears. The baseline is
    therefore recomputed from ``git cat-file -p <pinned rev>:<catalog>``. If the object is
    unreachable (shallow checkout) the helper records NOT-CHECKED rather than inventing a
    number, and this test skips rather than passing vacuously.
    """
    base = authz_census.baseline_census()
    if not base["available"]:
        pytest.skip(base.get("reason", "baseline object unreachable"))
    c, r = base["census"], base["rules"]
    assert c["owner_approval_required_true"] == 144
    assert c["hold_Task"] == 25
    assert c["hold_Task_unapproved"] == 23
    assert c["hold_mcp_token"] == 261
    assert c["wildcard_token_any_position"] == 120
    assert c["wildcard_in_token_identity"] == 9
    assert c["wildcard_in_scope_only"] == 111
    assert c["remote_substrate_holding_session_local_tool"] == 2
    assert c["tool_policy_declared"] is False
    # and every rule was RED there - the gate can go red, it is not a no-op
    assert r["SEM-008"]["violations"] == 2007
    assert r["SEM-009"]["violations"] == 30
    assert r["SEM-010"]["violations"] == 2
    assert r["SEM-011"]["violations"] == 10


def test_census_counts_match_the_after_state_on_disk(catalog: dict) -> None:
    """The numbers the D2 report cites, re-derived here so the report cannot drift."""
    c = authz_census.census(catalog)
    assert c["work_units"] == 2007
    assert c["hold_Task"] == 25
    assert c["hold_Task_unapproved"] == 0
    assert c["hold_mcp_token"] == 261
    assert c["wildcard_in_token_identity"] == 0
    assert c["wildcard_in_scope_only"] == 111
    assert c["remote_substrate_holding_session_local_tool"] == 0
    assert c["owner_approval_required_true"] == 167
