"""Executable MCP adapter contract: one negative case per rule, both-states."""
from __future__ import annotations

from typing import Any, Callable

from adapter import (
    ANY_SCOPE_DISABLE,
    BARE_NAMES,
    CONFORMING,
    DESTROY_ENABLE,
    EMPTY_SUCCESS,
    LEAK_REAP,
    NO_CAP,
    NO_DECLARATION,
    NO_TRANSPORT,
    SCHEMA_DRIFT,
    STDIO_CAP,
    Adapter,
    Policy,
    bind,
)
from protocol import namespaced
from servers import MALFORMED_INJECTIONS, MockServer, alpha_stdio, beta_http, fixture_pair


def _fresh(policy: Policy) -> Adapter:
    return bind(policy, fixture_pair())


def _stdio_server(n: int) -> MockServer:
    return MockServer(
        f"stdio{n}",
        transport="stdio",
        tools=[
            {
                "name": "echo",
                "description": f"stdio{n} echo",
                "inputSchema": {"type": "object"},
            }
        ],
    )


def rule_schema_fidelity() -> dict:
    good = _fresh(CONFORMING)
    ok, why = good.schema_fidelity_ok()
    mutant = _fresh(SCHEMA_DRIFT)
    mok, mwhy = mutant.schema_fidelity_ok()
    return {
        "id": "schema-fidelity",
        "title": "Adapter surfaces advertised tool schemas faithfully",
        "positive": {"pass": ok, "detail": why, "adapter": CONFORMING.name},
        "negative": {
            "pass": (not mok),
            "detail": mwhy,
            "adapter": SCHEMA_DRIFT.name,
            "fired_on_bad": (not mok),
        },
    }


def rule_namespacing() -> dict:
    good = _fresh(CONFORMING)
    names = [t["name"] for t in good.list_tools()]
    expect = {
        namespaced("alpha", "echo"),
        namespaced("beta", "echo"),
        namespaced("beta", "inspect"),
    }
    pos = set(names) == expect
    collision = False
    try:
        _fresh(BARE_NAMES).list_tools()
    except ValueError as exc:
        collision = "collision" in str(exc)
    return {
        "id": "namespacing",
        "title": "Tool names are namespaced per server so echo does not collide",
        "positive": {
            "pass": pos,
            "detail": sorted(names),
            "adapter": CONFORMING.name,
        },
        "negative": {
            "pass": collision,
            "detail": "bare-name echo collides across alpha/beta",
            "adapter": BARE_NAMES.name,
            "fired_on_bad": collision,
        },
    }


def _inject_all(adapter: Adapter) -> list[dict]:
    rows: list[dict] = []
    server = adapter.servers["alpha"]
    tool = namespaced("alpha", "echo") if adapter.policy.namespace else "echo"
    for code, payload in MALFORMED_INJECTIONS:
        server.inject = (code, payload)
        graded = adapter.classify_call(tool, {"text": "probe"})
        graded["injection"] = code
        graded["adapter"] = adapter.policy.name
        rows.append(graded)
        server.inject = None
    return rows


def rule_malformed_loud_degrade() -> dict:
    good_rows = _inject_all(_fresh(CONFORMING))
    bad_rows = _inject_all(_fresh(EMPTY_SUCCESS))
    good_ok = all(
        r["classification"]["class"] == "SCHEMA_INVALID"
        and r["terminal"]["status"] == "FAILED"
        and not r["classification"]["empty_success"]
        for r in good_rows
    )
    bad_is_empty = all(
        r["classification"]["class"] == "EMPTY_SUCCESS"
        and r["classification"]["severity"] == "P1"
        for r in bad_rows
    )
    return {
        "id": "malformed-loud-degrade",
        "title": "Malformed CallToolResult degrades loudly; empty SUCCESS is P1",
        "positive": {
            "pass": good_ok,
            "detail": {
                "n": len(good_rows),
                "classes": sorted({r["classification"]["class"] for r in good_rows}),
            },
            "adapter": CONFORMING.name,
        },
        "negative": {
            "pass": bad_is_empty,
            "detail": {
                "n": len(bad_rows),
                "classes": sorted({r["classification"]["class"] for r in bad_rows}),
            },
            "adapter": EMPTY_SUCCESS.name,
            "fired_on_bad": bad_is_empty,
        },
        "injections": {
            "conforming": [
                {
                    "injection": r["injection"],
                    "class": r["classification"]["class"],
                    "status": r["terminal"]["status"],
                    "failure_class": r["terminal"].get("failure_class"),
                    "reason": r["terminal"].get("reason"),
                    "empty_success": r["classification"]["empty_success"],
                    "severity": r["classification"].get("severity"),
                }
                for r in good_rows
            ],
            "empty_success_mutant": [
                {
                    "injection": r["injection"],
                    "class": r["classification"]["class"],
                    "status": r["terminal"]["status"],
                    "empty_success": r["classification"]["empty_success"],
                    "severity": r["classification"].get("severity"),
                }
                for r in bad_rows
            ],
        },
    }


def rule_wellformed_success() -> dict:
    good = _fresh(CONFORMING)
    terminal = good.call(namespaced("alpha", "echo"), {"text": "ping"})
    ok = (
        terminal["status"] == "SUCCESS"
        and terminal["id"]
        and terminal["content"] == [{"type": "text", "text": "ping"}]
    )
    mutant = _fresh(EMPTY_SUCCESS)
    mutant.servers["alpha"].inject = ("null-result", None)
    mt = mutant.call(namespaced("alpha", "echo"), {"text": "ping"})
    fired = mt.get("status") == "SUCCESS" and not mt.get("id")
    return {
        "id": "wellformed-success",
        "title": "A well-formed result is SUCCESS with id; the mutant still fails malformed",
        "positive": {"pass": ok, "detail": terminal, "adapter": CONFORMING.name},
        "negative": {
            "pass": fired,
            "detail": mt,
            "adapter": EMPTY_SUCCESS.name,
            "fired_on_bad": fired,
        },
    }


def rule_server_declaration() -> dict:
    good = Adapter(policy=CONFORMING)
    mounted = good.mount(alpha_stdio(), declaration={"command": ["mock"]})
    mutant = Adapter(policy=NO_DECLARATION)
    accepted = mutant.mount(alpha_stdio(), declaration={})
    rejected = False
    try:
        Adapter(policy=CONFORMING).mount(alpha_stdio(), declaration={})
    except ValueError:
        rejected = True
    return {
        "id": "server-declaration",
        "title": "Mount requires a command or url declaration",
        "positive": {
            "pass": bool(mounted.get("mounted")) and rejected,
            "detail": mounted,
            "adapter": CONFORMING.name,
        },
        "negative": {
            "pass": bool(accepted.get("mounted")),
            "detail": accepted,
            "adapter": NO_DECLARATION.name,
            "fired_on_bad": bool(accepted.get("mounted")),
        },
    }


def rule_transport_recorded() -> dict:
    good = _fresh(CONFORMING)
    transports = sorted(
        {s.transport for s in good.servers.values() if s.spawned}
    )
    pos = transports == ["http", "stdio"]
    mutant = Adapter(policy=NO_TRANSPORT)
    result = mutant.mount(
        alpha_stdio(), declaration={"command": ["mock"]}
    )
    missing = result.get("transport") in (None, "")
    return {
        "id": "transport-recorded",
        "title": "Each mount records stdio vs http",
        "positive": {
            "pass": pos,
            "detail": transports,
            "adapter": CONFORMING.name,
        },
        "negative": {
            "pass": missing,
            "detail": result,
            "adapter": NO_TRANSPORT.name,
            "fired_on_bad": missing,
        },
    }


def rule_stdio_cap() -> dict:
    good = Adapter(policy=CONFORMING)
    ok = True
    detail: dict[str, Any] = {"cap": STDIO_CAP, "mounted": 0}
    try:
        for i in range(STDIO_CAP):
            good.mount(_stdio_server(i), declaration={"command": ["mock"]})
            detail["mounted"] = i + 1
        refused = False
        try:
            good.mount(_stdio_server(STDIO_CAP), declaration={"command": ["mock"]})
        except ValueError:
            refused = True
        ok = refused
        detail["refused_over_cap"] = refused
    except ValueError as exc:
        ok = False
        detail["error"] = str(exc)
    mutant = Adapter(policy=NO_CAP)
    for i in range(STDIO_CAP + 2):
        mutant.mount(_stdio_server(i), declaration={"command": ["mock"]})
    over = sum(1 for s in mutant.servers.values() if s.transport == "stdio")
    return {
        "id": "stdio-process-cap",
        "title": "Hard per-session stdio process cap is enforced",
        "positive": {"pass": ok, "detail": detail, "adapter": CONFORMING.name},
        "negative": {
            "pass": over > STDIO_CAP,
            "detail": {"mounted_stdio": over, "cap": STDIO_CAP},
            "adapter": NO_CAP.name,
            "fired_on_bad": over > STDIO_CAP,
        },
    }


def rule_disable_scope() -> dict:
    good = Adapter(policy=CONFORMING)
    good.set_enabled("alpha", True, scope="project")
    good.set_enabled("alpha", False, scope="user")
    wrong = good.mount(alpha_stdio(), declaration={"command": ["mock"]})
    good.unmount("alpha")
    good.set_enabled("alpha", False, scope="project")
    right = good.mount(alpha_stdio(), declaration={"command": ["mock"]})
    pos = bool(wrong.get("mounted")) and not bool(right.get("mounted"))

    mutant = Adapter(policy=ANY_SCOPE_DISABLE)
    mutant.set_enabled("alpha", True, scope="project")
    mutant.set_enabled("alpha", False, scope="user")
    inert_treated_as_real = mutant.mount(
        alpha_stdio(), declaration={"command": ["mock"]}
    )
    fired = not bool(inert_treated_as_real.get("mounted"))
    return {
        "id": "disable-scope",
        "title": "Disable at the wrong scope is inert; effective-scope disable holds",
        "positive": {
            "pass": pos,
            "detail": {"wrong_scope_still_mounted": wrong, "right_scope": right},
            "adapter": CONFORMING.name,
        },
        "negative": {
            "pass": fired,
            "detail": inert_treated_as_real,
            "adapter": ANY_SCOPE_DISABLE.name,
            "fired_on_bad": fired,
        },
    }


def rule_enable_preserved() -> dict:
    good = Adapter(policy=CONFORMING)
    good.set_enabled("alpha", False, scope="project")
    snap = good.snapshot_enable()
    good.set_enabled("alpha", True, scope="local")
    good.migrate(snap)
    pos = good.enable == snap and good.enable["project"].get("alpha") is False

    mutant = Adapter(policy=DESTROY_ENABLE)
    mutant.set_enabled("alpha", False, scope="project")
    msnap = mutant.snapshot_enable()
    mutant.migrate(msnap)
    destroyed = mutant.enable != msnap
    return {
        "id": "curated-enable-preserved",
        "title": "Migration restores the curated enable map byte-identically",
        "positive": {"pass": pos, "detail": snap, "adapter": CONFORMING.name},
        "negative": {
            "pass": destroyed,
            "detail": mutant.enable,
            "adapter": DESTROY_ENABLE.name,
            "fired_on_bad": destroyed,
        },
    }


def rule_lifecycle_reap() -> dict:
    good = Adapter(policy=CONFORMING)
    s = alpha_stdio()
    good.mount(s, declaration={"command": ["mock"]})
    good.unmount("alpha")
    pos = s.spawned is False
    mutant = Adapter(policy=LEAK_REAP)
    leaked = alpha_stdio()
    mutant.mount(leaked, declaration={"command": ["mock"]})
    mutant.unmount("alpha")
    fired = leaked.spawned is True
    return {
        "id": "lifecycle-reap",
        "title": "Adapter owns start/reap; unmount reaps the stdio child",
        "positive": {"pass": pos, "detail": {"spawned_after_unmount": s.spawned}, "adapter": CONFORMING.name},
        "negative": {
            "pass": fired,
            "detail": {"spawned_after_unmount": leaked.spawned},
            "adapter": LEAK_REAP.name,
            "fired_on_bad": fired,
        },
    }


RULES: list[tuple[str, Callable[[], dict]]] = [
    ("schema-fidelity", rule_schema_fidelity),
    ("namespacing", rule_namespacing),
    ("malformed-loud-degrade", rule_malformed_loud_degrade),
    ("wellformed-success", rule_wellformed_success),
    ("server-declaration", rule_server_declaration),
    ("transport-recorded", rule_transport_recorded),
    ("stdio-process-cap", rule_stdio_cap),
    ("disable-scope", rule_disable_scope),
    ("curated-enable-preserved", rule_enable_preserved),
    ("lifecycle-reap", rule_lifecycle_reap),
]


def run_suite() -> dict:
    results = []
    for rid, fn in RULES:
        row = fn()
        if row.get("id") != rid:
            raise RuntimeError(f"rule id mismatch {rid} vs {row.get('id')}")
        pos = bool(row["positive"]["pass"])
        neg = bool(row["negative"]["pass"])
        row["both_states"] = pos and neg
        row["verdict"] = "PASS" if row["both_states"] else "FAIL"
        results.append(row)
    passed = [r["id"] for r in results if r["verdict"] == "PASS"]
    failed = [r["id"] for r in results if r["verdict"] == "FAIL"]
    return {
        "n_rules": len(results),
        "n_pass": len(passed),
        "n_fail": len(failed),
        "passed": passed,
        "failed": failed,
        "all_pass": not failed,
        "results": results,
    }


def malformed_matrix() -> dict:
    """Evidence: malformed-result injection per adapter with classification."""
    adapters = [
        _fresh(CONFORMING),
        _fresh(EMPTY_SUCCESS),
        _fresh(SCHEMA_DRIFT),
    ]
    matrix = []
    p1_empty = []
    for adapter in adapters:
        rows = _inject_all(adapter)
        entry = {
            "adapter": adapter.policy.name,
            "n": len(rows),
            "classifications": [
                {
                    "injection": r["injection"],
                    "class": r["classification"]["class"],
                    "severity": r["classification"].get("severity"),
                    "empty_success": r["classification"]["empty_success"],
                    "status": r["terminal"]["status"],
                    "reason": r["terminal"].get("reason"),
                }
                for r in rows
            ],
        }
        matrix.append(entry)
        if adapter.policy.name == EMPTY_SUCCESS.name:
            p1_empty = [
                c["injection"]
                for c in entry["classifications"]
                if c["class"] == "EMPTY_SUCCESS"
            ]
    return {
        "per_adapter": matrix,
        "empty_success_is_p1": True,
        "empty_success_injections_on_mutant": p1_empty,
        "mutant_all_empty_success": len(p1_empty) == len(MALFORMED_INJECTIONS),
        "conforming_has_empty_success": any(
            c["class"] == "EMPTY_SUCCESS"
            for e in matrix
            if e["adapter"] == CONFORMING.name
            for c in e["classifications"]
        ),
    }
