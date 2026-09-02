"""Normative plugin-manifest clauses for ARC-0078.

The contract JSON Schema embeds these strings so probes can prove the
artifact is not a vacuous $schema wrapper.
"""

from __future__ import annotations

UNIT_ID = "ARC-0078"
SENTINEL = "SUCCESS:ARC-0078"
CONTRACT_REL = "command-center/phase4/contracts/ARC-0078.json"
SCHEMA_URI = (
    "https://ast-integrate.local/command-center/phase4/contracts/ARC-0078.json"
)
SCHEMA_VERSION = "arc-0078.plugin-manifest.v1"
CONTRACT_ID = "ARC-0078"

REQUIRED_FIELDS_RULE = (
    "Required plugin.json fields are name, version, description, and engines. "
    "Optional fields are author, license, keywords, homepage, repository, "
    "commands, skills, and hooks."
)
UNKNOWN_FIELD_POLICY = (
    "Unknown-field policy is strict for unprefixed keys and tolerant only for "
    "the reserved x- extension prefix: a bare unknown top-level key, including "
    "the recorded $schema key, is rejected; a key matching ^x-[a-z0-9-]+$ is "
    "accepted. Codex HooksFile serde(deny_unknown_fields) is the measured "
    "client: an extra key does not warn, it unloads every hook."
)
INTERPRETER_RULE = (
    "Every script entry (commands[] and hooks[].hooks[]) MUST declare an "
    "explicit interpreter from {python3, bash, pwsh, node} and a script path. "
    "A shebang is not a declaration. A bare .sh invocation on Windows is "
    "forbidden: cmd.exe PATHEXT does not include .sh and does not read #!."
)
COMPAT_RULE = (
    "engines.host.min and optional engines.host.max declare the compatibility "
    "range against host client versions; engines.host.clients names the host "
    "products (claude-code, codex, cursor) the range applies to."
)
ZERO_HOOKS_RULE = (
    "The validator MUST reject the exact recorded zero-hooks shape: a hooks "
    "file that carries a $schema (or any other unprefixed unknown) key. That "
    "shape made Codex report the plugin as installed while loading ZERO hooks. "
    "An empty hooks array is the same failure class and is also rejected."
)
NO_ADV_RULE = (
    "Upstream architecture ratification (ARC-0077) is not on disk in this "
    "worktree; the plugin-manifest contract is substrate-agnostic and does "
    "not wait on an ADV rebuild of the architecture packet."
)

CLAUSE_STRINGS = (
    REQUIRED_FIELDS_RULE,
    UNKNOWN_FIELD_POLICY,
    INTERPRETER_RULE,
    COMPAT_RULE,
    ZERO_HOOKS_RULE,
    NO_ADV_RULE,
    SENTINEL,
)
