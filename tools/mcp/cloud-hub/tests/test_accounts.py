#!/usr/bin/env python3
"""Tests for the reusable multi-account layer (``accounts.py``) and its wiring
into the hub: env-mode add/list/switch/cycle/current, seeding-from-env,
persistence, the CLI-profile path for Azure/gcloud (via a mock runner, no real
CLI state), env injection at spawn, and kill+respawn on switch."""

from __future__ import annotations

import json
import os
import queue
import sys
import time

import pytest

HUB_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HUB_DIR)

import accounts  # noqa: E402
import hub  # noqa: E402
from accounts import AccountPolicy, AccountStore  # noqa: E402
from backends import BackendSpec, default_backends  # noqa: E402
from registry import build_plan  # noqa: E402

PY = sys.executable
FAKE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fake_backend.py")


# --------------------------------------------------------------------------- #
# env-mode account store
# --------------------------------------------------------------------------- #
def _env_store(tmp_path, environ):
    pol = AccountPolicy(platform="rp", mode="env", seed_env=("RP_KEY",), label="RunPod")
    return AccountStore(str(tmp_path / "acc.json"), [pol], environ=environ), pol


def test_seed_from_env_creates_default(tmp_path):
    store, _ = _env_store(tmp_path, {"RP_KEY": "secret123"})
    listing = store.handle("rp", "list", {})
    assert listing["ok"] and listing["accounts"] == ["default"]
    assert listing["active"] == "default"
    # The seeded default resolves the ${RP_KEY} ref back to the real value.
    assert store.active_env("rp") == {"RP_KEY": "secret123"}


def test_no_seed_when_env_absent(tmp_path):
    store, _ = _env_store(tmp_path, {})  # RP_KEY not present
    listing = store.handle("rp", "list", {})
    assert listing["accounts"] == [] and listing["active"] is None
    assert store.active_env("rp") == {}


def test_add_switch_cycle_current_remove(tmp_path):
    store, _ = _env_store(tmp_path, {"RP_KEY": "secret123"})
    add = store.handle("rp", "add", {"name": "alt", "env": {"RP_KEY": "literalABC"}})
    assert add["ok"] and store.handle("rp", "list", {})["accounts"] == [
        "default",
        "alt",
    ]

    sw = store.handle("rp", "switch", {"name": "alt"})
    assert sw["ok"] and sw["respawn"] is True
    assert store.active_env("rp") == {"RP_KEY": "literalABC"}

    cyc = store.handle("rp", "cycle", {})  # alt -> default (round-robin)
    assert cyc["active"] == "default" and cyc["respawn"] is True
    assert store.active_env("rp") == {"RP_KEY": "secret123"}

    cur = store.handle("rp", "current", {})  # keys only, never values
    assert cur["active"] == "default" and cur["env_keys"] == ["RP_KEY"]

    rm = store.handle("rp", "remove", {"name": "alt"})
    assert rm["ok"] and store.handle("rp", "list", {})["accounts"] == ["default"]


def test_env_store_persists_across_reload(tmp_path):
    store, pol = _env_store(tmp_path, {"RP_KEY": "secret123"})
    store.handle("rp", "add", {"name": "alt", "env": {"RP_KEY": "xyz"}})
    store.handle("rp", "switch", {"name": "alt"})
    fresh = AccountStore(str(tmp_path / "acc.json"), [pol], environ={"RP_KEY": "s"})
    assert fresh.handle("rp", "list", {})["active"] == "alt"
    # No literal secret leaked to disk: the seeded default stays a ${REF}.
    on_disk = json.loads((tmp_path / "acc.json").read_text(encoding="utf-8"))
    assert on_disk["rp"]["accounts"][0]["env"]["RP_KEY"] == "${RP_KEY}"


def test_account_label_stored_and_shown(tmp_path):
    """Optional label (e.g. the account email) is stored on add and surfaced by
    list (a name->label map) + current, so accounts are identifiable beyond the
    switch name -- the cswap/Modal-style identity the user asked for."""
    store, _ = _env_store(tmp_path, {"RP_KEY": "s"})
    assert store.handle(
        "rp",
        "add",
        {"name": "work", "env": {"RP_KEY": "k"}, "label": "andrei@work.com"},
    )["ok"]
    lst = store.handle("rp", "list", {})
    assert lst["labels"] == {"work": "andrei@work.com"}
    assert "default" not in lst["labels"]  # unlabeled accounts absent from the map
    store.handle("rp", "switch", {"name": "work"})
    cur = store.handle("rp", "current", {})
    assert cur["active"] == "work" and cur["label"] == "andrei@work.com"


def test_add_duplicate_and_bad_env_rejected(tmp_path):
    store, _ = _env_store(tmp_path, {"RP_KEY": "s"})
    dup = store.handle("rp", "add", {"name": "default", "env": {"RP_KEY": "x"}})
    assert not dup["ok"] and "already exists" in dup["error"]
    bad = store.handle("rp", "add", {"name": "x", "env": "notadict"})
    assert not bad["ok"]


def test_switch_unknown_account_errors(tmp_path):
    store, _ = _env_store(tmp_path, {"RP_KEY": "s"})
    res = store.handle("rp", "switch", {"name": "ghost"})
    assert not res["ok"] and "no such account" in res["error"]


# --------------------------------------------------------------------------- #
# store-load failures: a git-crypt-LOCKED or otherwise undecodable accounts.json
# must fail LOUDLY and name its remedy -- never degrade to an EMPTY store, which
# would silently disable the whole rotation pool.
# --------------------------------------------------------------------------- #
GITCRYPT_MAGIC = b"\x00GITCRYPT\x00"


def test_gitcrypt_locked_store_raises_naming_gitcrypt_and_remedy(tmp_path):
    """A tracked, git-crypt-ENCRYPTED accounts.json (the state of any worktree
    where git-crypt was never unlocked) must raise an error that names git-crypt,
    the offending path, and the unlock remedy -- not a raw UnicodeDecodeError."""
    path = tmp_path / "acc.json"
    # Byte-for-byte the real git-crypt header: 10-byte magic then the nonce, so
    # the first non-UTF-8 byte lands at position 10 exactly as in production.
    path.write_bytes(GITCRYPT_MAGIC + b"\xe95~\xd5=\xc3!q\xb3\xa4\xfegj\x1a")
    pol = AccountPolicy(platform="rp", mode="env", seed_env=("RP_KEY",), label="RunPod")

    with pytest.raises(accounts.AccountStoreLoadError) as exc:
        AccountStore(str(path), [pol], environ={"RP_KEY": "s"})

    msg = str(exc.value)
    assert "git-crypt" in msg  # names the actual cause
    assert str(path) in msg  # names the offending file
    assert "unlock" in msg.lower()  # states the remedy


def test_undecodable_non_gitcrypt_store_raises_without_blaming_gitcrypt(tmp_path):
    """A genuinely corrupt (non-UTF-8) store must ALSO fail loudly and clearly,
    but must NOT misattribute the corruption to git-crypt."""
    path = tmp_path / "acc.json"
    path.write_bytes(b"\x89PNG\r\n\x1a\n\xff\xd8corrupt-not-json")
    pol = AccountPolicy(platform="rp", mode="env", seed_env=("RP_KEY",), label="RunPod")

    with pytest.raises(accounts.AccountStoreLoadError) as exc:
        AccountStore(str(path), [pol], environ={"RP_KEY": "s"})

    msg = str(exc.value)
    assert "git-crypt" not in msg  # correct discrimination, no false blame
    assert str(path) in msg
    assert "utf-8" in msg.lower()


def test_valid_store_loads_unchanged(tmp_path):
    """(c) A valid store keeps loading exactly as before."""
    path = tmp_path / "acc.json"
    path.write_text(
        json.dumps({"rp": {"active": "alt", "accounts": [{"name": "alt"}]}}),
        encoding="utf-8",
    )
    pol = AccountPolicy(platform="rp", mode="env", seed_env=("RP_KEY",), label="RunPod")
    store = AccountStore(str(path), [pol], environ={"RP_KEY": "s"})
    assert store.handle("rp", "list", {})["accounts"] == ["alt"]


def test_missing_store_still_starts_empty(tmp_path):
    """(d) A MISSING store is the normal first-run case and must stay silent --
    only an unreadable/undecodable one is loud."""
    pol = AccountPolicy(platform="rp", mode="env", seed_env=("RP_KEY",), label="RunPod")
    store = AccountStore(str(tmp_path / "nope.json"), [pol], environ={})
    assert store.handle("rp", "list", {})["accounts"] == []


# NOTE (deliberate regression-guard REPLACEMENT, not a deletion): the test that
# used to live here -- ``test_invalid_json_behaviour_unchanged`` -- PINNED the
# opposite behaviour, i.e. that malformed JSON silently degrades to an empty
# store. That pin was correct for the git-crypt lane, which deliberately scoped
# itself to the *decode* path and left this one untouched. It is now INVERTED on
# purpose: the swallow was measured to cause silent credential substitution and
# irreversible loss of the operator's store (see the two tests below, which pin
# both halves). The old expectation is intentionally no longer supported.
def test_malformed_json_store_raises_and_leaves_the_file_intact(tmp_path):
    """A decodable-but-malformed store must fail LOUDLY rather than degrade to an
    empty one, and the failed load must leave the original bytes untouched so the
    operator can still repair them by hand."""
    path = tmp_path / "acc.json"
    # A trailing comma -- the most common hand-edit error. Still holds the
    # operator's real, recoverable account names and secrets.
    original = (
        '{"rp": {"active": "prod", "accounts": ['
        '{"name": "prod", "env": {"RP_KEY": "SECRET-PROD-abc123"}},'
        "]}}"
    )
    path.write_text(original, encoding="utf-8")
    pol = AccountPolicy(platform="rp", mode="env", seed_env=("RP_KEY",), label="RunPod")

    with pytest.raises(accounts.AccountStoreLoadError) as exc:
        AccountStore(str(path), [pol], environ={"RP_KEY": "envfallback"})

    msg = str(exc.value)
    assert str(path) in msg  # names the offending file
    assert "json" in msg.lower()  # names the actual cause
    assert "git-crypt" not in msg  # correct discrimination, no false blame
    # The protective property: nothing was rewritten, so the store is still
    # repairable. Under the old swallow-to-empty behaviour the first mutating op
    # persisted over exactly these bytes and destroyed them.
    assert path.read_text(encoding="utf-8") == original


def test_malformed_json_error_does_not_leak_store_contents(tmp_path):
    """The store legitimately holds literal secrets, so the raised message must
    locate the syntax error WITHOUT echoing any of the file's content."""
    path = tmp_path / "acc.json"
    path.write_text(
        '{"rp": {"accounts": [{"env": {"RP_KEY": "SECRET-DO-NOT-ECHO"}},]}}',
        encoding="utf-8",
    )
    pol = AccountPolicy(platform="rp", mode="env", seed_env=("RP_KEY",), label="RunPod")

    with pytest.raises(accounts.AccountStoreLoadError) as exc:
        AccountStore(str(path), [pol], environ={})

    msg = str(exc.value)
    assert "SECRET-DO-NOT-ECHO" not in msg
    assert "RP_KEY" not in msg


def test_non_object_json_store_raises(tmp_path):
    """Valid JSON that is not an OBJECT (a list/scalar -- e.g. a bad migration)
    is the same silent-empty class and must raise too, not quietly load empty."""
    path = tmp_path / "acc.json"
    path.write_text('[{"name": "prod"}]', encoding="utf-8")
    pol = AccountPolicy(platform="rp", mode="env", seed_env=("RP_KEY",), label="RunPod")

    with pytest.raises(accounts.AccountStoreLoadError) as exc:
        AccountStore(str(path), [pol], environ={"RP_KEY": "envfallback"})

    assert str(path) in str(exc.value)
    assert path.read_text(encoding="utf-8") == '[{"name": "prod"}]'


@pytest.mark.parametrize("body", ["", "   \n\t  "])
def test_empty_store_file_starts_empty_quietly(tmp_path, body):
    """DELIBERATE TOLERANCE, pinned as intentional: an EMPTY or whitespace-only
    store is treated like a missing one (quiet first-run), NOT as corruption.

    It holds no accounts, so neither failure mode that justifies raising applies
    -- there is no configured credential to substitute away and nothing
    recoverable to overwrite. A zero-byte file is also a plausible bootstrap
    artifact (``touch``, an interrupted create, a truncating ``New-Item -Force``),
    so raising on it would be a false alarm with no protective value.
    """
    path = tmp_path / "acc.json"
    path.write_text(body, encoding="utf-8")
    pol = AccountPolicy(platform="rp", mode="env", seed_env=("RP_KEY",), label="RunPod")
    store = AccountStore(str(path), [pol], environ={})
    assert store.handle("rp", "list", {})["accounts"] == []


# --------------------------------------------------------------------------- #
# cli-mode (Azure / gcloud) via a MOCK runner -- no real CLI state touched
# --------------------------------------------------------------------------- #
class _MockCli:
    """A fake az/gcloud runner returning canned profile listings."""

    def __init__(self):
        self.calls: list[tuple[str, ...]] = []

    def __call__(self, argv):
        self.calls.append(tuple(argv))
        a = list(argv)
        if a[:3] == ["gcloud", "config", "configurations"]:
            if any(x in a for x in ("activate", "create", "delete")):
                return 0, "", ""
            if "--filter=is_active:true" in a:
                return 0, "default\n", ""
            return 0, "default\nwork\n", ""
        if a[:2] == ["az", "account"]:
            if a[2] == "set":
                return 0, "", ""
            if a[2] == "show":
                return 0, "Azure subscription 1\n", ""
            if a[2] == "list":
                return 0, "Azure subscription 1\nAzure for Students\n", ""
        return 0, "", ""


def _cli_store(tmp_path, runner):
    specs = {s.id: s for s in default_backends()}
    pols = [specs["azure"].account, specs["gcloud"].account]
    return AccountStore(str(tmp_path / "cli.json"), pols, environ={}, runner=runner)


def test_gcloud_list_current_switch_cycle(tmp_path):
    runner = _MockCli()
    store = _cli_store(tmp_path, runner)
    lst = store.handle("gcloud", "list", {})
    assert lst["accounts"] == ["default", "work"] and lst["active"] == "default"

    sw = store.handle("gcloud", "switch", {"name": "work"})
    assert sw["ok"] and sw["respawn"] is True
    assert ("gcloud", "config", "configurations", "activate", "work") in runner.calls

    cyc = store.handle("gcloud", "cycle", {})  # active default -> work
    assert cyc["ok"] and cyc["active"] == "work" and cyc["respawn"] is True


def test_azure_list_switch_and_add_unsupported(tmp_path):
    runner = _MockCli()
    store = _cli_store(tmp_path, runner)
    lst = store.handle("azure", "list", {})
    assert lst["accounts"] == ["Azure subscription 1", "Azure for Students"]
    assert lst["active"] == "Azure subscription 1"

    sw = store.handle("azure", "switch", {"name": "Azure for Students"})
    assert sw["ok"] and sw["respawn"] is True
    assert (
        "az",
        "account",
        "set",
        "--subscription",
        "Azure for Students",
    ) in runner.calls

    # Azure subscriptions cannot be "added" via the CLI -> clear hint, no crash.
    add = store.handle("azure", "add", {"name": "new"})
    assert not add["ok"] and "az login" in add["error"]


def test_gcloud_add_creates_configuration(tmp_path):
    runner = _MockCli()
    store = _cli_store(tmp_path, runner)
    res = store.handle("gcloud", "add", {"name": "prod"})
    assert res["ok"]
    assert ("gcloud", "config", "configurations", "create", "prod") in runner.calls


def test_cli_active_env_is_empty(tmp_path):
    # cli-mode backends inject no env (the CLI holds the state).
    store = _cli_store(tmp_path, _MockCli())
    assert store.active_env("azure") == {} and store.active_env("gcloud") == {}


def test_account_tool_defs_shape():
    defs = accounts.account_tool_defs("rp", "runpod", "env", "RunPod")
    names = [d["name"] for d in defs]
    assert names == [
        "rp_account_list",
        "rp_account_current",
        "rp_account_add",
        "rp_account_remove",
        "rp_account_switch",
        "rp_account_cycle",
    ]
    add = next(d for d in defs if d["name"] == "rp_account_add")
    assert "env" in add["inputSchema"]["required"]  # env mode requires env
    cli_add = next(
        d
        for d in accounts.account_tool_defs("az", "azure", "cli")
        if d["name"] == "az_account_add"
    )
    assert cli_add["inputSchema"]["required"] == ["name"]  # cli add: name only


def test_databricks_account_env_seed_and_tools(tmp_path):
    """Databricks is an env-mode backend: it exposes the six db_account_* tools
    and seeds a 'default' account from DATABRICKS_HOST + DATABRICKS_TOKEN (the
    OVH/Kaggle env-rotator pattern, per-workspace credentials)."""
    dbx = {s.id: s for s in default_backends()}["databricks"]
    assert dbx.prefix == "db"
    # Hub-native account surface: db_account_list/current/add/remove/switch/cycle.
    defs = accounts.account_tool_defs(
        dbx.prefix, dbx.account.platform, dbx.account.mode, dbx.label
    )
    assert [d["name"] for d in defs] == [
        "db_account_list",
        "db_account_current",
        "db_account_add",
        "db_account_remove",
        "db_account_switch",
        "db_account_cycle",
    ]
    # Seeding: both registration vars present -> in-memory 'default' account.
    env = {
        "DATABRICKS_HOST": "https://dbc-x.cloud.databricks.com",
        "DATABRICKS_TOKEN": "dapiABC",
    }
    store = AccountStore(str(tmp_path / "acc.json"), [dbx.account], environ=env)
    listing = store.handle("databricks", "list", {})
    assert listing["ok"] and listing["accounts"] == ["default"]
    assert store.active_env("databricks") == env


# --------------------------------------------------------------------------- #
# hub wiring: env injection at spawn + kill/respawn on switch
# --------------------------------------------------------------------------- #
def test_runtime_backend_layers_active_account_env():
    spec = BackendSpec(
        id="rp",
        label="RunPod",
        prefix="rp",
        cmd=("noop",),
        cache="rp.json",
        env={"BASE": "1"},
    )
    rb = hub.RuntimeBackend(
        spec, lambda _s: None, account_env=lambda: {"RP_KEY": "xyz", "BASE": "win"}
    )
    env = rb._spawn_env()
    assert env["RP_KEY"] == "xyz"  # account env injected
    assert env["BASE"] == "win"  # account creds win over spec.env


class _Capture:
    def __init__(self):
        self._q: "queue.Queue[dict]" = queue.Queue()

    def __call__(self, line: str) -> None:
        self._q.put(json.loads(line))

    def wait(self, n: int, timeout: float = 30.0) -> list[dict]:
        got: list[dict] = []
        end = time.monotonic() + timeout
        while len(got) < n and (rem := end - time.monotonic()) > 0:
            try:
                got.append(self._q.get(timeout=rem))
            except queue.Empty:
                break
        return got


@pytest.fixture
def account_hub(tmp_path):
    spec = BackendSpec(
        id="alpha",
        label="Alpha",
        prefix="al",
        cmd=(PY, FAKE, "alpha", "alpha_only"),
        cache="alpha.json",
        account=AccountPolicy(platform="alpha", mode="env", seed_env=("ALPHA_KEY",)),
    )
    cache_dir = str(tmp_path)
    old = hub.CACHE_DIR
    hub.CACHE_DIR = cache_dir
    ok, _n, msg = hub.refresh_backend(spec)
    assert ok, msg
    plan = build_plan([spec], cache_dir)
    store = AccountStore(
        str(tmp_path / "acc.json"), [spec.account], environ={"ALPHA_KEY": "k1"}
    )
    cap = _Capture()
    server = hub.HubServer([spec], plan, emit=cap, account_store=store)
    try:
        yield server, store, cap
    finally:
        hub.CACHE_DIR = old
        for backend in server.backends.values():
            backend._terminate()


def test_account_tools_listed_and_served_without_spawn(account_hub):
    server, _store, cap = account_hub
    server.dispatch({"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}})
    tools = {t["name"] for t in cap.wait(1)[0]["result"]["tools"]}
    assert {
        "al_account_list",
        "al_account_switch",
        "al_account_cycle",
        "alpha_only",
    } <= tools
    server.dispatch(
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": "al_account_list", "arguments": {}},
        }
    )
    reply = cap.wait(1)[0]
    payload = json.loads(reply["result"]["content"][0]["text"])
    assert payload["accounts"] == ["default"]
    # Account management never spawns the backend.
    assert server.backends["alpha"].proc is None


def test_switch_kills_and_resets_backend(account_hub):
    server, store, cap = account_hub
    # Start the backend with a real call.
    server.dispatch(
        {
            "jsonrpc": "2.0",
            "id": 10,
            "method": "tools/call",
            "params": {"name": "alpha_only", "arguments": {}},
        }
    )
    assert cap.wait(1)[0]["id"] == 10
    assert server.backends["alpha"].proc is not None

    store.handle("alpha", "add", {"name": "two", "env": {"ALPHA_KEY": "k2"}})
    server.dispatch(
        {
            "jsonrpc": "2.0",
            "id": 11,
            "method": "tools/call",
            "params": {"name": "al_account_switch", "arguments": {"name": "two"}},
        }
    )
    reply = cap.wait(1)[0]
    payload = json.loads(reply["result"]["content"][0]["text"])
    assert payload["ok"] and payload["active"] == "two"
    # The backend was killed + reset; the next call would respawn with new creds.
    assert server.backends["alpha"].proc is None
    assert server.backends["alpha"].started is False
