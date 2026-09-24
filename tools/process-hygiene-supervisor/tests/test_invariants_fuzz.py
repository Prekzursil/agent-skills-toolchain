"""Seeded property fuzz: random process tables against the safety invariants.

The unit tests prove each rule on a hand-built table; this file proves the
INVARIANTS hold on tables nobody hand-built - protected daemons under random
wrappers, dangling parents, runtimes nested three deep, duplicate MCP members with
and without a port owner, browsers, vmmem, retired components, random pressure,
random idleness, random ESTABLISHED sockets - across several observation rounds.

Invariants (every one is a safety property a mutation could silently break):
  I1  a protected process is never a stop-tree member (by exe pattern, name or token)
  I2  the supervisor's own pids are never a stop-tree member
  I3  every stop tree is ordered children-first (child index < parent index)
  I4  no pid is claimed by two stop decisions in one plan
  I5  every stop-tree member is the root or a descendant of the root
  I6  idle-gated rules (orphan, session-age, rss-*) only stop whole-tree-idle trees
  I7  a runtime with a live protected IDE ancestor is never stopped except as retired
  I8  parentless cursor-agent trees are never stopped when the reaper is available
  I9  raw tier is monotonic in pressure (less available RAM never lowers it)
  I10 the plan round-trips through JSON; dry-run never actuates; ledger rows keep schema
  I11 two fresh engines fed the same snapshot sequence produce identical plans
  I12 a network-vetoed tree increments its deferral counter at most once per run
  I13 an unprotected parentless port owner is reported as a daemon, never stopped
  I14 memory-priority demotions (opt-in rule) obey the stop guards: never protected,
      never the supervisor, never a pid also being stopped, always confirmed idle

It is seeded and bounded (CASES x ROUNDS evaluations, ~seconds), so it is a CI
gate, not a soak. Raise CASES locally to hunt.
"""

from __future__ import annotations

import json
import random

import pytest

import hygiene
from test_hygiene import (
    CURSOR_AGENT_EXE,
    CURSOR_IDE_EXE,
    GIB,
    MIB,
    NOW,
    STEP,
    WT_EXE,
    FakeActuator,
    engine,
    ledger_rows,
    policy,
    registry,
)

CASES = 120
ROUNDS = 5

NODE = "C:\\Program Files\\nodejs\\node.exe"
PY = "C:\\Python314\\python.exe"
PWSH = "C:\\Program Files\\PowerShell\\7\\pwsh.exe"
CMD = "C:\\Windows\\System32\\cmd.exe"


class Table:
    """Random process-table builder with the ground truth the invariants need."""

    def __init__(self, rng: random.Random):
        self.rng = rng
        self.rows: list[dict] = []
        self.protected: set[int] = set()
        self.ide_owned_runtimes: set[int] = set()
        self.delegated_cursor: set[int] = set()
        self.next_pid = 100
        self.connections: list[tuple[int, str]] = []
        self.listeners: list[tuple[int, int]] = []
        self.port_owners: set[int] = set()

    def pid(self) -> int:
        self.next_pid += self.rng.randint(1, 7)
        return self.next_pid

    def add(
        self,
        ppid,
        name,
        exe,
        cmd,
        *,
        age,
        private=100 * MIB,
        idle=None,
        protected=False,
    ):
        pid = self.pid()
        idle = self.rng.random() < 0.6 if idle is None else idle
        # Physical consistency: a child cannot predate its parent. The engine
        # reads "child older than parent" as PID reuse (the real parent died and
        # this ppid now names a newer process) and treats the child as parentless
        # - correctly. An extended fuzz run produced exactly that impossible
        # table and flagged the engine; the generator was wrong, not the engine.
        parent = next((r for r in self.rows if r["pid"] == ppid), None)
        if parent is not None:
            age = min(age, (NOW - parent["created_unix"]) - 1)
        self.rows.append(
            {
                "pid": pid,
                "ppid": ppid,
                "name": name,
                "executable": exe,
                "command_line": cmd,
                "created_unix": NOW - age,
                # idle rows keep cpu/io flat across rounds; active rows drift
                "cpu_seconds": 1.0,
                "io_bytes": 10,
                "working_set_bytes": private,
                "private_bytes": private,
                "_idle": idle,
            }
        )
        if protected:
            self.protected.add(pid)
        return pid

    # -- actors ---------------------------------------------------------

    def explorer(self):
        return self.add(
            1,
            "explorer.exe",
            "C:\\Windows\\explorer.exe",
            "explorer",
            age=400_000,
            protected=True,
        )

    def terminal(self, ppid):
        return self.add(
            ppid, "WindowsTerminal.exe", WT_EXE, "wt", age=300_000, protected=True
        )

    def ide(self, ppid):
        return self.add(
            ppid,
            "Cursor.exe",
            CURSOR_IDE_EXE,
            "Cursor",
            age=200_000,
            private=900 * MIB,
            protected=True,
        )

    def shell(self, ppid, age=None):
        return self.add(
            ppid,
            "pwsh.exe",
            PWSH,
            "pwsh",
            age=age or self.rng.choice([600, 7200, 40_000]),
        )

    def runtime(
        self,
        ppid,
        kind,
        *,
        age=None,
        private=None,
        under_ide=False,
        parentless=False,
        reaper=True,
    ):
        exe, cmd, name = {
            "cursor-agent": (CURSOR_AGENT_EXE, "node cursor-agent", "node.exe"),
            "claude": ("C:\\Users\\x\\.local\\bin\\claude.exe", "claude", "claude.exe"),
            "codex": ("C:\\Users\\x\\.local\\bin\\codex.exe", "codex", "codex.exe"),
            "grok": ("C:\\Users\\x\\.local\\bin\\grok.exe", "grok", "grok.exe"),
        }[kind]
        age = (
            age
            if age is not None
            else self.rng.choice([1200, 7200, 30 * 3600, 3 * 86_400])
        )
        private = (
            private
            if private is not None
            else self.rng.choice([200 * MIB, 1800 * MIB, 3 * GIB, 5 * GIB])
        )
        pid = self.add(ppid, name, exe, cmd, age=age, private=private)
        if under_ide:
            self.ide_owned_runtimes.add(pid)
        if parentless and kind == "cursor-agent" and reaper:
            self.delegated_cursor.add(pid)
        # a runtime usually hosts an MCP child or two
        for _ in range(self.rng.randint(0, 2)):
            child = self.mcp_child(pid, age=age - 10)
            if under_ide:
                self.ide_owned_runtimes.add(child)
            if parentless and kind == "cursor-agent" and reaper:
                self.delegated_cursor.add(child)
        return pid

    def mcp_child(self, ppid, *, age):
        if self.rng.random() < 0.4:
            wrapper = self.add(ppid, "cmd.exe", CMD, "cmd /c npx -y @x/server", age=age)
            return self.add(
                wrapper,
                "node.exe",
                NODE,
                "node C:\\x\\_npx\\a\\node_modules\\x\\dist\\index.js",
                age=age - 1,
            )
        return self.add(ppid, "node.exe", NODE, "node C:\\x\\mcp\\index.js", age=age)

    def orphan(self, dangling):
        kind = self.rng.choice(["node", "python", "pwsh", "cmd"])
        name, exe, cmd = {
            "node": ("node.exe", NODE, "node C:\\x\\left\\behind.js"),
            "python": ("python.exe", PY, "python -m some.server"),
            "pwsh": ("pwsh.exe", PWSH, "pwsh -File C:\\x\\loop.ps1"),
            "cmd": ("cmd.exe", CMD, "cmd /c npx -y @x/stale"),
        }[kind]
        age = self.rng.choice([600, 3600, 10 * 3600, 40 * 3600])
        pid = self.add(dangling, name, exe, cmd, age=age)
        if kind == "cmd" and self.rng.random() < 0.7:
            self.add(pid, "node.exe", NODE, "node C:\\x\\stale\\index.js", age=age - 1)
        return pid

    def protected_daemon(self, dangling):
        which = self.rng.choice(["auth2api", "bm", "watchdog", "reaper", "host"])
        cmd = {
            "auth2api": "node C:\\Users\\x\\Cowork\\tools\\auth2api\\dist\\index.js",
            "bm": "python -m basic_memory mcp --transport streamable-http --port 8765",
            "watchdog": "pwsh -File C:\\x\\bm-watchdog.ps1",
            "reaper": "pwsh -File C:\\x\\cursor-orphan-reaper.ps1",
            "host": "python C:\\x\\mcp_http_host.py --port 9000",
        }[which]
        name = (
            "python.exe"
            if cmd.startswith("python")
            else "pwsh.exe"
            if cmd.startswith("pwsh")
            else "node.exe"
        )
        exe = PY if name == "python.exe" else PWSH if name == "pwsh.exe" else NODE
        # Ground truth, stated precisely (the fuzzer's first run taught this):
        # auth2api / the watchdog / the reaper / the MCP host are protected by
        # ALLOWLIST token. The Basic Memory daemon is protected by being the
        # singleton PORT OWNER - a second copy that does not own :8765 is a
        # duplicate singleton and is a legitimate stop once past grace.
        first_bm = which == "bm" and not any(
            "basic_memory" in r["command_line"] for r in self.rows
        )
        pid = self.add(
            dangling,
            name,
            exe,
            cmd,
            age=self.rng.choice([3600, 200_000]),
            protected=(which != "bm") or first_bm,
        )
        # protected daemons sometimes have children that inherit nothing but are
        # still under a protected root
        if self.rng.random() < 0.3:
            self.add(
                pid,
                "node.exe",
                NODE,
                "node C:\\x\\helper.js",
                age=3000,
                protected=False,
            )
        return pid

    def retired(self, ppid):
        return self.add(
            ppid,
            "node.exe",
            NODE,
            "node C:\\x\\@raysonmeng\\agentbridge\\dist\\bridge-server.js",
            age=self.rng.choice([100, 3000, 20_000]),
            private=150 * MIB,
        )

    def browser(self, ppid):
        name = self.rng.choice(["chrome.exe", "msedge.exe"])
        for _ in range(self.rng.randint(1, 6)):
            self.add(
                ppid,
                name,
                f"C:\\Program Files\\{name}",
                f"{name} --type=renderer",
                age=30_000,
                private=self.rng.choice([60, 300, 900]) * MIB,
                protected=True,
            )

    def vmmem(self):
        return self.add(
            4,
            "vmmemWSL",
            "",
            "",
            age=50 * 3600,
            private=self.rng.choice([400, 1100, 3000]) * MIB,
            protected=True,
        )

    def windows_binary(self, ppid):
        return self.add(
            ppid,
            "svchost.exe",
            "C:\\Windows\\System32\\svchost.exe",
            "svchost -k x",
            age=400_000,
            protected=True,
        )

    def listener_daemon(self, dangling):
        """An UNPROTECTED parentless process that owns a listening port: the
        `daemon` carve-out must report it and never stop it (nobody double-starts
        a listener by accident; a parentless port owner is an intentional service)."""
        pid = self.add(
            dangling,
            "node.exe",
            NODE,
            "node C:\\x\\api\\server.js",
            age=self.rng.choice([3600, 90_000]),
        )
        self.listeners.append((3000 + len(self.listeners), pid))
        self.port_owners.add(pid)
        return pid

    def socket(self, pid, remote):
        self.connections.append((pid, remote))


def build(seed: int) -> tuple[Table, bool]:
    rng = random.Random(seed)
    t = Table(rng)
    reaper = rng.random() < 0.7
    ex = t.explorer()
    t.windows_binary(ex)
    term = t.terminal(ex)
    ide = t.ide(ex) if rng.random() < 0.8 else None
    dangling = 60_000 + rng.randint(0, 99)  # a ppid that does not exist

    for _ in range(rng.randint(0, 3)):
        host = rng.choice([term, ide or term, t.shell(term)])
        t.runtime(
            host,
            rng.choice(["cursor-agent", "claude", "codex", "grok"]),
            under_ide=(host == ide),
        )
    for _ in range(rng.randint(0, 2)):
        t.runtime(dangling, "cursor-agent", parentless=True, reaper=reaper)
    for _ in range(rng.randint(0, 2)):
        t.runtime(
            dangling,
            rng.choice(["claude", "codex", "grok"]),
            parentless=True,
            reaper=reaper,
        )
    for _ in range(rng.randint(0, 4)):
        t.orphan(dangling)
    for _ in range(rng.randint(0, 3)):
        t.protected_daemon(dangling)
    for _ in range(rng.randint(0, 2)):
        t.listener_daemon(dangling)
    for _ in range(rng.randint(0, 2)):
        t.retired(
            rng.choice([term, dangling])
            if rng.random() < 0.5
            else t.runtime(term, "grok")
        )
    if rng.random() < 0.7:
        t.browser(ex)
    if rng.random() < 0.6:
        t.vmmem()
    pids = [r["pid"] for r in t.rows]
    for _ in range(rng.randint(0, 4)):
        t.socket(
            rng.choice(pids),
            rng.choice(
                ["52.1.2.3:443", "127.0.0.1:8765", "[::1]:8812", "10.0.0.7:11434"]
            ),
        )
    return t, reaper


def snapshot_for(
    t: Table, taken: int, round_index: int, host: dict
) -> hygiene.Snapshot:
    rows = []
    for r in t.rows:
        row = {k: v for k, v in r.items() if not k.startswith("_")}
        if not r["_idle"]:
            row["cpu_seconds"] = 1.0 + round_index * 2.0
            row["io_bytes"] = 10 + round_index * 4096
        rows.append(row)
    return hygiene.parse_snapshot(
        {
            "schema": hygiene.SCHEMA_SNAPSHOT,
            "taken_unix": taken,
            "host": host,
            "wsl": {
                "available": True,
                "running_distros": ["Ubuntu"]
                if any(r["name"] == "vmmemWSL" for r in t.rows)
                else [],
            },
            "listeners": [
                {"port": 8765, "pid": p["pid"]}
                for p in t.rows
                if "basic_memory" in p["command_line"]
            ][:1]
            + [
                {"port": 8317, "pid": p["pid"]}
                for p in t.rows
                if "auth2api" in p["command_line"]
            ][:1]
            + [{"port": port, "pid": pid} for port, pid in t.listeners],
            "connections": [
                {"pid": pid, "remote": remote} for pid, remote in t.connections
            ],
            "supervisor_pids": [1],
            "processes": rows,
        }
    )


def random_host(rng: random.Random) -> dict:
    return {
        "physical_bytes": 32 * GIB,
        "free_bytes": rng.choice([1 * GIB, 3 * GIB, 8 * GIB, 16 * GIB]),
        "commit_total_bytes": rng.choice([20 * GIB, 50 * GIB, 66 * GIB]),
        "commit_limit_bytes": rng.choice([0, 64 * GIB, 100 * GIB]),
    }


def descendants(snapshot: hygiene.Snapshot, root: int) -> set[int]:
    out, stack = set(), [root]
    while stack:
        pid = stack.pop()
        for child in snapshot.children.get(pid, []):
            if child not in out:
                out.add(child)
                stack.append(child)
    return out


IDLE_GATED = {"orphan", "session-age", "rss-soft", "rss-hard"}


def check_plan(
    plan: hygiene.Plan,
    snapshot: hygiene.Snapshot,
    t: Table,
    reaper: bool,
    eng: hygiene.Engine,
    seed: int,
):
    ctx = f"seed={seed} ts={plan.taken_unix}"
    stops = [d for d in plan.decisions if d.action == "stop"]
    claimed: dict[int, str] = {}
    observations = eng.policy["idle"]["observations"]
    for d in stops:
        members = [m.pid for m in d.tree]
        assert members, f"{ctx}: empty stop tree for {d.rule}"
        assert d.root.pid in members, f"{ctx}: root not in its own tree ({d.rule})"
        desc = descendants(snapshot, d.root.pid) | {d.root.pid}
        for m in d.tree:
            assert m.pid not in t.protected, (
                f"{ctx}: I1 protected pid {m.pid} in {d.rule} tree"
            )
            assert m.pid not in snapshot.supervisor_pids, (
                f"{ctx}: I2 supervisor pid in tree"
            )
            assert m.pid in desc, (
                f"{ctx}: I5 {m.pid} is not under root {d.root.pid} ({d.rule})"
            )
            assert m.pid not in claimed, (
                f"{ctx}: I4 {m.pid} claimed by {claimed.get(m.pid)} and {d.rule}"
            )
            claimed[m.pid] = d.rule
        index = {pid: i for i, pid in enumerate(members)}
        for m in d.tree:
            for child in snapshot.children.get(m.pid, []):
                if child in index:
                    assert index[child] < index[m.pid], (
                        f"{ctx}: I3 child {child} after parent {m.pid} ({d.rule})"
                    )
        if (
            d.rule in IDLE_GATED
            and not eng.policy["escalation"]["stopActiveAtCritical"]
        ):
            for m in d.tree:
                streak = eng.state["observations"][hygiene._key(m)]["idle_streak"]
                assert streak >= observations, (
                    f"{ctx}: I6 {d.rule} stopped non-idle pid {m.pid} (streak {streak})"
                )
        if d.rule != "retired":
            for m in d.tree:
                assert m.pid not in t.ide_owned_runtimes, (
                    f"{ctx}: I7 IDE-owned {m.pid} stopped by {d.rule}"
                )
        if reaper:
            for m in d.tree:
                assert m.pid not in t.delegated_cursor, (
                    f"{ctx}: I8 delegated cursor pid {m.pid} stopped by {d.rule}"
                )
        if d.rule != "retired":
            assert d.root.pid not in t.port_owners, (
                f"{ctx}: I13 parentless port owner {d.root.pid} stopped by {d.rule}"
            )
    # I14 memory-priority demotions obey the same guards as stops: never a
    # protected or supervisor pid, never a pid claimed for a stop, always idle
    stopped = {m.pid for d in stops for m in d.tree}
    for d in plan.decisions:
        if d.action != "demote":
            continue
        pid = d.root.pid
        assert pid not in t.protected, f"{ctx}: I14 protected pid {pid} demoted"
        assert pid not in snapshot.supervisor_pids, f"{ctx}: I14 supervisor pid demoted"
        assert pid not in stopped, f"{ctx}: I14 pid {pid} both stopped and demoted"
        streak = eng.state["observations"][hygiene._key(d.root)]["idle_streak"]
        assert streak >= observations, (
            f"{ctx}: I14 non-idle pid {pid} demoted (streak {streak})"
        )
    # I10
    encoded = json.dumps(plan.to_dict())
    assert json.loads(encoded)["tier"] == plan.tier


@pytest.mark.parametrize("seed", range(CASES))
def test_invariants_hold_on_random_tables(seed, tmp_path):
    t, reaper = build(seed)
    rng = random.Random(seed + 1_000_000)
    host = random_host(rng)
    # every other seed runs with the opt-in memory-priority rule ON, so its
    # demote/restore decisions are held to the same invariants as stops
    pol = policy(**{"memoryPriority.enabled": True}) if seed % 2 else policy()
    eng = engine(pol)
    twin = engine(pol)
    plans = []
    deferrals_before: dict[str, int] = {}
    for r in range(ROUNDS):
        snapshot = snapshot_for(t, NOW + r * STEP, r, host)
        plan = eng.evaluate(snapshot, reaper_available=reaper)
        check_plan(plan, snapshot, t, reaper, eng, seed)
        # I11 determinism
        twin_plan = twin.evaluate(
            snapshot_for(t, NOW + r * STEP, r, host), reaper_available=reaper
        )
        assert twin_plan.to_dict() == plan.to_dict(), (
            f"seed={seed}: I11 non-deterministic plan"
        )
        # I12 the deferral counter of EVERY tree advances by at most one per run
        # (a looser bound let a real double-charge slip through - see
        # test_network_veto_is_decided_once_per_tree_per_run_across_rules)
        current = {
            key: entry["network_deferrals"]
            for key, entry in eng.state["observations"].items()
        }
        for key, value in current.items():
            assert value - deferrals_before.get(key, 0) <= 1, (
                f"seed={seed}: I12 deferrals for {key} advanced by more than one in one run"
            )
        deferrals_before = current
        plans.append(plan)
    # I10 dry-run never actuates and rows keep the schema
    actuator = FakeActuator()
    ledger = hygiene.Ledger(tmp_path / "l.jsonl")
    hygiene.apply_plan(plans[-1], actuator, ledger, apply=False, run_id="fuzz")
    assert actuator.stopped == [] and actuator.wsl_calls == 0
    for row in ledger_rows(tmp_path / "l.jsonl"):
        assert row["schema"] == hygiene.SCHEMA_LEDGER


@pytest.mark.parametrize("seed", range(0, CASES, 6))
def test_raw_tier_is_monotonic_in_available_ram(seed):
    t, reaper = build(seed)
    tiers = []
    for free in (16 * GIB, 8 * GIB, 3 * GIB, 1 * GIB):
        host = {
            "physical_bytes": 32 * GIB,
            "free_bytes": free,
            "commit_total_bytes": 30 * GIB,
            "commit_limit_bytes": 64 * GIB,
        }
        plan = engine().evaluate(snapshot_for(t, NOW, 0, host), reaper_available=reaper)
        tiers.append(hygiene.TIER_ORDER[plan.raw_tier])
    assert tiers == sorted(tiers), (
        f"seed={seed}: I9 tier fell as RAM got scarcer: {tiers}"
    )


def test_fuzzer_exercises_every_actor_at_least_once():
    """Guards the fuzzer itself: a generator that never produces an actor proves nothing."""
    seen_rules: set[str] = set()
    seen_protected = seen_delegated = seen_ide = False
    for seed in range(CASES):
        t, reaper = build(seed)
        seen_protected |= bool(t.protected)
        seen_delegated |= bool(t.delegated_cursor) and reaper
        seen_ide |= bool(t.ide_owned_runtimes)
        eng = engine()
        for r in range(ROUNDS):
            plan = eng.evaluate(
                snapshot_for(t, NOW + r * STEP, r, random_host(random.Random(seed))),
                reaper_available=reaper,
            )
            seen_rules |= {d.rule for d in plan.decisions}
    assert seen_protected and seen_delegated and seen_ide
    expected = {
        "retired",
        "orphan",
        "daemon",
        "session-age",
        "rss-hard",
        "wrapper-chain",
        "browser",
        "cursor-orphan-reaper",
    }
    missing = expected - seen_rules
    assert not missing, f"fuzzer never produced rules {missing}; widen the generator"


def test_helper_imports_are_the_real_ones():
    # keep the shared-helper dependency explicit so a rename there fails here loudly
    assert callable(policy) and callable(registry)
