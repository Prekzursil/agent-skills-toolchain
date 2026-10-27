"""Offline CI config-lint for the versioned Codex profiles (spec §4).

Anti-rot gate for ``tools/codex/profiles``. Every check here is OFFLINE (parse +
schema + cross-reference against the versioned manifests) — the authoritative LIVE
probes (allowlist ⊆ live base, model slug resolves, MCP-def harvest, and the
exec-runtime scope proof) belong to ``codex-doctor`` and run behind a ``--live``
marker per codex release, NOT here (spec §2d/§4).

Checks implemented (spec §4 CI config-lint, a-e):
  a. ``<name>.config.toml`` parses (tomllib) AND contains only known codex keys.
  b. ``<name>.scope.json`` validates against the scope schema, incl. ``mode ∈
     {M0,M1,M2}`` and the fail-closed rule ``seal && allowlist != [] ⇒
     captured_mcp_defs present``.
  c. Every ``mcp_allowlist`` name is a subset of the canonical MCP manifest.
  d. The pinned model slug is in the allowed set OR the profile has fallbacks
     (and every fallback slug is itself allowed).
  e. The Windows ``-c`` nested-TOML / env-table / ``${VAR}`` round-trip cases of
     spec §3e (2)-(4) round-trip through tomllib byte-for-byte in structure.

Plus grounded anti-rot assertions: profile pairing, the exact set of expected
profiles, the M0 static-disable block == ``base − mcp_allowlist``, secrets
discipline (``${VAR}`` only, no inline creds), and the fanout ``--output-schema``
reference resolving on disk.
"""

from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path

import pytest

# ci/tests/ -> repo root is parents[2]. This file was salvaged from the stale
# ci/harness/tests/ mirror (which quality.yml never executes); ci/tests/ IS run
# wholesale by skill-dual-write.yml, so the gate actually fires here.
REPO_ROOT = Path(__file__).resolve().parents[2]
PROFILES_DIR = REPO_ROOT / "tools" / "codex" / "profiles"

# The 5 canonical profiles (spec §2f). Kept explicit so an accidental add/remove
# in the versioned tree fails loudly rather than silently changing the fleet.
EXPECTED_PROFILES = frozenset(
    {
        "audit-readonly-max",
        "build-sandboxed",
        "exec-fast",
        "fanout-json",
        "consult-review",
    }
)

# Real, --strict-config-clean codex keys the profiles are allowed to carry
# (spec §2a / G6). tomllib flattens `[shell_environment_policy]` into this top-level
# table name. `mcp_servers` is deliberately EXCLUDED: a standalone config file whose
# `mcp_servers.<x>` entry carries no transport is a HARD codex load error ("invalid
# transport") — such a file cannot load and codex-doctor rejects it. M0 disables live
# in scope.static_disable and are applied by codex-invoke as `-c mcp_servers.<x>.
# enabled=false` OVERRIDES (which ride the transport-carrying base server), never as
# inline config.toml tables. See test_config_toml_has_no_inline_mcp_servers.
ALLOWED_TOML_KEYS = frozenset(
    {
        "model",
        "model_reasoning_effort",
        "approval_policy",
        "sandbox_mode",
        "web_search",
        "service_tier",
        "shell_environment_policy",
    }
)

# Stable codex enums — value typos are a common rot vector, so pin the ones that
# are stable in codex-cli. `model_reasoning_effort` is intentionally NOT pinned to
# an enum (codex accepts medium/high/max/xhigh/ultra and the set moves per release);
# it is only required to be a non-empty string.
SANDBOX_MODES = frozenset({"read-only", "workspace-write", "danger-full-access"})
APPROVAL_POLICIES = frozenset({"never", "on-request", "on-failure", "untrusted"})
WEB_SEARCH_VALUES = frozenset({"live", "disabled"})

VALID_MODES = frozenset({"M0", "M1", "M2"})

# ${VAR} placeholder form — the ONLY permitted shape for an MCP credential value.
VAR_PLACEHOLDER = re.compile(r"^\$\{[A-Za-z_][A-Za-z0-9_]*\}$")


# --------------------------------------------------------------------------- #
# fixtures / loaders
# --------------------------------------------------------------------------- #


def _load_manifest(name: str) -> dict:
    return json.loads((PROFILES_DIR / name).read_text(encoding="utf-8"))


MCP_MANIFEST = _load_manifest("mcp-manifest.json")
MODELS_MANIFEST = _load_manifest("models-manifest.json")
CANONICAL_MCPS = frozenset(MCP_MANIFEST["servers"])
ALLOWED_MODELS = frozenset(MODELS_MANIFEST["allowed"])


def _profile_names() -> list[str]:
    # Path.stem on "x.config.toml" yields "x.config" (strips only ".toml"); drop the
    # trailing ".config" so the profile name is just "x".
    return sorted(p.name[: -len(".config.toml")] for p in PROFILES_DIR.glob("*.config.toml"))


def _load_toml(name: str) -> dict:
    return tomllib.loads((PROFILES_DIR / f"{name}.config.toml").read_text(encoding="utf-8"))


def _load_scope(name: str) -> dict:
    return json.loads((PROFILES_DIR / f"{name}.scope.json").read_text(encoding="utf-8"))


PROFILE_NAMES = _profile_names()


# --------------------------------------------------------------------------- #
# structure / pairing
# --------------------------------------------------------------------------- #


def test_profiles_dir_exists():
    assert PROFILES_DIR.is_dir(), f"missing profiles dir: {PROFILES_DIR}"


def test_expected_profile_set_present():
    assert set(PROFILE_NAMES) == EXPECTED_PROFILES


def test_every_config_has_a_scope_sidecar():
    for name in PROFILE_NAMES:
        assert (PROFILES_DIR / f"{name}.scope.json").is_file(), f"{name}: missing .scope.json"


def test_no_orphan_scope_files():
    for scope in PROFILES_DIR.glob("*.scope.json"):
        base = scope.name[: -len(".scope.json")]
        assert (PROFILES_DIR / f"{base}.config.toml").is_file(), (
            f"orphan scope file with no .config.toml: {scope.name}"
        )


# --------------------------------------------------------------------------- #
# (a) config.toml parses + only-known-key allowset
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("name", PROFILE_NAMES)
def test_config_toml_parses_and_only_known_keys(name):
    doc = _load_toml(name)  # raises tomllib.TOMLDecodeError on malformed config
    unknown = set(doc) - ALLOWED_TOML_KEYS
    assert not unknown, f"{name}: unknown top-level codex keys (not --strict-config-clean): {unknown}"

    assert doc.get("model"), f"{name}: missing `model`"
    effort = doc.get("model_reasoning_effort")
    assert isinstance(effort, str) and effort, f"{name}: bad model_reasoning_effort"

    if "sandbox_mode" in doc:
        assert doc["sandbox_mode"] in SANDBOX_MODES, f"{name}: bad sandbox_mode {doc['sandbox_mode']!r}"
    if "approval_policy" in doc:
        assert doc["approval_policy"] in APPROVAL_POLICIES, f"{name}: bad approval_policy"
    if "web_search" in doc:
        assert doc["web_search"] in WEB_SEARCH_VALUES, f"{name}: bad web_search {doc['web_search']!r}"


@pytest.mark.parametrize("name", PROFILE_NAMES)
def test_config_toml_has_no_inline_mcp_servers(name):
    """No profile config.toml may declare an inline `mcp_servers` table. A
    transport-less `mcp_servers.<x>.enabled=false` overlay is a HARD codex load error
    ("invalid transport") — the file cannot load and codex-doctor rejects it. M0
    disables belong in scope.static_disable, applied by codex-invoke as `-c
    mcp_servers.<x>.enabled=false` overrides (which ride the transport-carrying base
    server and disable it — valid where a standalone file is not)."""
    doc = _load_toml(name)
    assert "mcp_servers" not in doc, (
        f"{name}: config.toml declares an inline mcp_servers table (un-loadable "
        f"transport-less overlay); move the disables to scope.static_disable"
    )


# --------------------------------------------------------------------------- #
# (b) scope.json schema + fail-closed rule
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("name", PROFILE_NAMES)
def test_scope_json_schema(name):
    scope = _load_scope(name)

    assert scope["mode"] in VALID_MODES, f"{name}: mode {scope['mode']!r} not in {VALID_MODES}"
    assert isinstance(scope["seal"], bool), f"{name}: `seal` must be bool"

    for list_field in ("mcp_allowlist", "skills_allowlist", "model_fallbacks"):
        val = scope.get(list_field)
        assert isinstance(val, list) and all(isinstance(x, str) for x in val), (
            f"{name}: `{list_field}` must be a list[str]"
        )

    # `static_disable` is the M0 offline disable set (optional; only M0 profiles carry
    # it). When present it must be a list[str].
    if "static_disable" in scope:
        sd = scope["static_disable"]
        assert isinstance(sd, list) and all(isinstance(x, str) for x in sd), (
            f"{name}: `static_disable` must be a list[str]"
        )

    assert isinstance(scope.get("tools", {}), dict), f"{name}: `tools` must be a table"
    assert isinstance(scope.get("captured_mcp_defs", {}), dict), f"{name}: `captured_mcp_defs` must be a table"
    assert isinstance(scope.get("notes", ""), str), f"{name}: `notes` must be a string"


@pytest.mark.parametrize("name", PROFILE_NAMES)
def test_scope_fail_closed_seal_requires_captured_defs(name):
    """spec §4(b): a sealed profile with a NON-empty allowlist (M2b) must ship
    captured_mcp_defs — otherwise there is nothing to re-materialize the servers
    from and it would be `seal-uncaptured` fail-closed at launch."""
    scope = _load_scope(name)
    if scope["seal"] and scope["mcp_allowlist"]:
        captured = scope.get("captured_mcp_defs") or {}
        assert captured, f"{name}: sealed + non-empty allowlist but no captured_mcp_defs (seal-uncaptured)"
        for srv in scope["mcp_allowlist"]:
            assert srv in captured, f"{name}: allowlisted {srv!r} missing from captured_mcp_defs"


@pytest.mark.parametrize("name", PROFILE_NAMES)
def test_m2a_full_seal_has_empty_allowlist(name):
    """A sealed profile with an EMPTY allowlist is M2a (zero-MCP); a sealed profile
    is EITHER M2a (empty) or M2b (non-empty + captured). `seal` implies mode M2."""
    scope = _load_scope(name)
    if scope["seal"]:
        assert scope["mode"] == "M2", f"{name}: seal=true requires mode M2"


# --------------------------------------------------------------------------- #
# (c) mcp_allowlist ⊆ canonical manifest
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("name", PROFILE_NAMES)
def test_mcp_allowlist_subset_of_canonical_manifest(name):
    scope = _load_scope(name)
    unknown = set(scope["mcp_allowlist"]) - CANONICAL_MCPS
    assert not unknown, f"{name}: mcp_allowlist references non-canonical MCP(s): {unknown}"


def test_manifest_server_names_are_unique_and_nonempty():
    servers = MCP_MANIFEST["servers"]
    assert servers, "empty MCP manifest"
    assert len(servers) == len(set(servers)), "duplicate names in MCP manifest"


# --------------------------------------------------------------------------- #
# (d) model slug in allowed set OR has fallbacks
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("name", PROFILE_NAMES)
def test_model_slug_allowed_or_has_fallbacks(name):
    doc = _load_toml(name)
    scope = _load_scope(name)
    model = doc["model"]
    fallbacks = scope.get("model_fallbacks", [])
    assert model in ALLOWED_MODELS or fallbacks, (
        f"{name}: pinned model {model!r} not in allowed set and no model_fallbacks"
    )
    # Any declared fallback must itself be an allowed slug (keeps the chain honest).
    unknown_fallbacks = set(fallbacks) - ALLOWED_MODELS
    assert not unknown_fallbacks, f"{name}: model_fallbacks not in allowed set: {unknown_fallbacks}"


def test_primary_model_is_allowed():
    assert MODELS_MANIFEST["primary"] in ALLOWED_MODELS


# --------------------------------------------------------------------------- #
# (e) Windows -c nested-TOML / env-table / ${VAR} round-trip (spec §3e 2-4)
# --------------------------------------------------------------------------- #
# Offline proxy for the acceptance gate: the TOML fragments the M1/M2b/skills
# materializer emits through the PowerShell `& codex @args` boundary must survive
# as structure. The byte-exact live `& codex @args` comparison is the doctor's
# --live lane; here we prove the TOML shape itself round-trips via tomllib.


def _roundtrip(toml_text: str) -> dict:
    return tomllib.loads(toml_text)


def test_roundtrip_multi_element_array_with_spaces():
    # spec §3e(1)-(2): -c 'mcp_servers.x.args=["a b","c d"]'
    parsed = _roundtrip('[mcp_servers.x]\nargs = ["a b", "c d"]\n')
    assert parsed["mcp_servers"]["x"]["args"] == ["a b", "c d"]


def test_roundtrip_env_subtable_with_spaces_and_placeholder():
    # spec §3e(2): -c 'mcp_servers.x.env={API_KEY="${API_KEY}",REGION="eu west"}'
    parsed = _roundtrip(
        '[mcp_servers.x.env]\nAPI_KEY = "${API_KEY}"\nREGION = "eu west"\n'
    )
    env = parsed["mcp_servers"]["x"]["env"]
    assert env == {"API_KEY": "${API_KEY}", "REGION": "eu west"}


def test_roundtrip_var_placeholder_survives_unexpanded():
    # spec §3e(3): ${VAR} must survive un-expanded as a literal string.
    parsed = _roundtrip('[mcp_servers.x.env]\nTOKEN = "${TOKEN}"\n')
    assert parsed["mcp_servers"]["x"]["env"]["TOKEN"] == "${TOKEN}"


def test_roundtrip_values_with_dollar_brackets_spaces_quotes():
    # spec §3e(4): $ / [ / ] / spaces / quotes in combination.
    literal = '${TOKEN}[0] a "b" c'
    # TOML basic string: escape the embedded double-quotes.
    escaped = literal.replace('"', '\\"')
    parsed = _roundtrip(f'[mcp_servers.x]\nval = "{escaped}"\n')
    assert parsed["mcp_servers"]["x"]["val"] == literal


def test_roundtrip_inline_table_form_matches_multiline_form():
    # The materializer may emit either an inline table or a [sub.table]; both must
    # parse to the same structure (the two shapes -c can produce).
    inline = _roundtrip('[mcp_servers.x]\nenv = { TOKEN = "${TOKEN}", REGION = "eu west" }\n')
    multiline = _roundtrip('[mcp_servers.x.env]\nTOKEN = "${TOKEN}"\nREGION = "eu west"\n')
    assert inline == multiline


# --------------------------------------------------------------------------- #
# grounded anti-rot: M0 static-disable block, secrets discipline, output-schema
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("name", PROFILE_NAMES)
def test_m0_static_disable_matches_base_minus_allowlist(name):
    """For an M0 profile, scope.static_disable must be EXACTLY (canonical base −
    mcp_allowlist) — so the OFFLINE scoping (applied by codex-invoke as
    `-c mcp_servers.<x>.enabled=false` overrides) cannot rot out of sync with the
    manifest. The disable set lives in scope.json, NOT as transport-less mcp_servers
    lines in the config.toml (which codex rejects as un-loadable). An M0 profile with
    an empty disable set would run UNSCOPED (the invoker fails CLOSED on that), so an
    M0 profile is required to enumerate a non-empty disable set here (spec §2b M0)."""
    scope = _load_scope(name)
    if scope["mode"] != "M0":
        return
    static_disable = set(scope.get("static_disable", []))
    expected = CANONICAL_MCPS - set(scope["mcp_allowlist"])
    assert static_disable == expected, (
        f"{name}: M0 static_disable drifted from base − allowlist.\n"
        f"  missing (should be disabled): {expected - static_disable}\n"
        f"  extra (not in base/allowlist): {static_disable - expected}"
    )
    assert static_disable, (
        f"{name}: M0 profile has an empty static_disable — it would load the FULL "
        f"base UNSCOPED (codex-invoke fails closed on this). Enumerate base − allowlist."
    )


@pytest.mark.parametrize("name", PROFILE_NAMES)
def test_no_inline_secret_values_anywhere(name):
    """Secrets discipline (spec §2f): no config.toml or scope.json may carry an
    inline credential. Any env value in captured_mcp_defs must be a ${VAR}
    placeholder, never a literal secret."""
    scope = _load_scope(name)
    for srv, sdef in (scope.get("captured_mcp_defs") or {}).items():
        for var_name, var_val in (sdef.get("env") or {}).items():
            assert isinstance(var_val, str) and VAR_PLACEHOLDER.match(var_val), (
                f"{name}: captured_mcp_defs.{srv}.env.{var_name} is not a ${{VAR}} placeholder"
            )
    # Belt-and-suspenders: scan the raw scope.json for obvious secret-looking assignments.
    raw = (PROFILES_DIR / f"{name}.scope.json").read_text(encoding="utf-8")
    assert not re.search(r'"(sk-|ghp_|xox[baprs]-)', raw), f"{name}: scope.json looks like it contains a real token"


def test_fanout_output_schema_reference_resolves():
    scope = _load_scope("fanout-json")
    so = scope.get("structured_output")
    assert so and so.get("flag") == "--output-schema", "fanout-json must declare --output-schema"
    ref = PROFILES_DIR / so["schema_ref"]
    assert ref.is_file(), f"fanout-json structured_output.schema_ref missing on disk: {ref}"
    schema = json.loads(ref.read_text(encoding="utf-8"))
    assert schema.get("type") == "object", "fanout schema must be a JSON-Schema object"


def test_readonly_profiles_have_no_write_sandbox():
    """audit / consult / fanout are advisory read-only passes — assert the sandbox
    actually matches that intent (a read-only profile that drifted to workspace-write
    would silently gain write capability)."""
    for name in ("audit-readonly-max", "fanout-json", "consult-review"):
        doc = _load_toml(name)
        assert doc.get("sandbox_mode") == "read-only", f"{name}: expected read-only sandbox"
        assert doc.get("approval_policy") == "never", f"{name}: read-only pass expects approval never"
