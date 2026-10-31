"""Strict manifest parsing, unknown-field policy, case-collision guard, client negotiation.

The shipped manifest is ``.claude-plugin/plugin.json`` inside the package. It is a **superset**
of the repo-root `.claude-plugin/plugin.json` that Claude Code already reads: every field the
client understands keeps its meaning, and everything this package adds lives under
``compatibility``/``interpreters``/``entrypoints`` plus the reserved ``x-`` namespace.

"Strict" means three separate things, all enforced here:

* required fields are present and typed (``E_MANIFEST``);
* an unknown top-level or nested key is **rejected**, not ignored, unless it is in the reserved
  ``x-`` extension namespace — a parser that silently drops a key it does not know is how a
  typo becomes a security hole;
* two keys that differ only by case are a hard error, because JSON permits them and
  ``dict``/case-insensitive filesystems do not.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .errors import PluginError

MANIFEST_RELPATH = ".claude-plugin/plugin.json"
EXTENSION_PREFIX = "x-"

SEMVER_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)(?:[-+].*)?$")

#: Every key this parser understands, per object. Anything else is an error.
ALLOWED: dict[str, frozenset[str]] = {
    "": frozenset(
        {
            "name",
            "version",
            "description",
            "author",
            "license",
            "keywords",
            "homepage",
            "compatibility",
            "interpreters",
            "entrypoints",
            "payload",
            "deploy",
        }
    ),
    "author": frozenset({"name", "email", "url"}),
    "compatibility": frozenset(
        {"min_client", "max_client", "platforms", "shells", "schema_version"}
    ),
    "interpreters": frozenset({"id", "floor", "required"}),
    "entrypoints": frozenset(
        {"id", "kind", "path", "interpreter", "args", "description"}
    ),
    "payload": frozenset({"max_bytes", "max_files", "include", "exclude"}),
    "deploy": frozenset({"targets"}),
    "deploy.targets": frozenset({"source", "target", "mode"}),
}

REQUIRED_TOP = ("name", "version", "description", "author", "license", "compatibility")
ENTRYPOINT_KINDS = frozenset({"command", "hook", "script", "skill"})
DEPLOY_MODES = frozenset({"copy", "merge", "link"})


def parse_semver(text: object, *, where: str) -> tuple[int, int, int]:
    if not isinstance(text, str) or not SEMVER_RE.match(text):
        raise PluginError(
            "E_MANIFEST", f"{where} must be semver MAJOR.MINOR.PATCH, got {text!r}"
        )
    m = SEMVER_RE.match(text)
    assert m is not None
    return (int(m.group(1)), int(m.group(2)), int(m.group(3)))


def _case_guard(raw: str) -> None:
    """Reject JSON that declares two keys differing only by case, at any depth (IMP-0009).

    ``json.loads`` keeps only the last of two case-distinct duplicates, so this must run on the
    raw text with an ``object_pairs_hook`` — a post-parse dict cannot see the collision.
    """

    def hook(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        seen: dict[str, str] = {}
        for key, _ in pairs:
            low = key.lower()
            if low in seen:
                raise PluginError(
                    "E_MANIFEST",
                    f"case-distinct duplicate keys {seen[low]!r} and {key!r} in the same object",
                )
            seen[low] = key
        return dict(pairs)

    # This runs BEFORE the main json.loads, so a syntax error surfaces here first. It must be
    # classified as E_MANIFEST, not escape as a raw JSONDecodeError — an unclassified crash has no
    # exit code, no cause, and no next command.
    try:
        json.loads(raw, object_pairs_hook=hook)
    except json.JSONDecodeError as exc:
        raise PluginError("E_MANIFEST", f"manifest is not valid JSON: {exc}") from exc


def _reject_unknown(obj: dict[str, Any], scope: str) -> None:
    allowed = ALLOWED.get(scope)
    if allowed is None:
        return
    for key in obj:
        if key.startswith(EXTENSION_PREFIX):
            continue
        if key not in allowed:
            raise PluginError(
                "E_MANIFEST",
                f"unknown field {key!r} in {scope or '<root>'!r}; "
                f"use the reserved {EXTENSION_PREFIX!r} namespace for extensions",
                context={"allowed": ", ".join(sorted(allowed))},
            )


@dataclass(frozen=True)
class Entrypoint:
    ident: str
    kind: str
    path: str
    interpreter: str | None
    args: tuple[str, ...] = ()
    description: str = ""

    def as_dict(self) -> dict[str, object]:
        d: dict[str, object] = {"id": self.ident, "kind": self.kind, "path": self.path}
        if self.interpreter:
            d["interpreter"] = self.interpreter
        if self.args:
            d["args"] = list(self.args)
        if self.description:
            d["description"] = self.description
        return d


@dataclass(frozen=True)
class DeployTarget:
    """One live-deployment route: a payload subtree projected onto a live-config path."""

    source: str
    target: str
    mode: str

    def as_dict(self) -> dict[str, object]:
        return {"source": self.source, "target": self.target, "mode": self.mode}


@dataclass
class Manifest:
    name: str
    version: str
    description: str
    author: dict[str, str]
    license: str
    min_client: str
    max_client: str | None
    platforms: tuple[str, ...]
    shells: tuple[str, ...]
    schema_version: int
    keywords: tuple[str, ...] = ()
    homepage: str | None = None
    interpreters: tuple[dict[str, Any], ...] = ()
    entrypoints: tuple[Entrypoint, ...] = ()
    deploy_targets: tuple[DeployTarget, ...] = ()
    payload_max_bytes: int = 0
    payload_max_files: int = 0
    extensions: dict[str, Any] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def semver(self) -> tuple[int, int, int]:
        return parse_semver(self.version, where="version")

    def as_dict(self) -> dict[str, Any]:
        """Round-trippable form: what ``build`` writes into the package."""
        doc: dict[str, Any] = {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "author": dict(self.author),
            "license": self.license,
        }
        if self.keywords:
            doc["keywords"] = list(self.keywords)
        if self.homepage:
            doc["homepage"] = self.homepage
        compat: dict[str, Any] = {
            "min_client": self.min_client,
            "platforms": list(self.platforms),
            "shells": list(self.shells),
            "schema_version": self.schema_version,
        }
        if self.max_client:
            compat["max_client"] = self.max_client
        doc["compatibility"] = compat
        if self.interpreters:
            doc["interpreters"] = [dict(i) for i in self.interpreters]
        if self.entrypoints:
            doc["entrypoints"] = [e.as_dict() for e in self.entrypoints]
        if self.payload_max_bytes or self.payload_max_files:
            doc["payload"] = {
                "max_bytes": self.payload_max_bytes,
                "max_files": self.payload_max_files,
            }
        if self.deploy_targets:
            doc["deploy"] = {"targets": [t.as_dict() for t in self.deploy_targets]}
        doc.update(self.extensions)
        return doc

    def negotiate(self, client_version: str) -> tuple[bool, str]:
        """Minimum-client negotiation (IMP-0008). Returns (compatible, human reason)."""
        try:
            cv = parse_semver(client_version, where="client version")
        except PluginError as exc:
            return False, exc.detail
        lo = parse_semver(self.min_client, where="compatibility.min_client")
        if cv < lo:
            return (
                False,
                f"client {client_version} is below min_client {self.min_client}",
            )
        if self.max_client:
            hi = parse_semver(self.max_client, where="compatibility.max_client")
            if cv > hi:
                return (
                    False,
                    f"client {client_version} is above max_client {self.max_client}",
                )
        return (
            True,
            f"client {client_version} is within [{self.min_client}, {self.max_client or '*'}]",
        )


def parse(raw_text: str) -> Manifest:
    """Parse + strictly validate manifest text. Raises ``E_MANIFEST`` with a specific reason."""
    _case_guard(raw_text)
    try:
        doc = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise PluginError("E_MANIFEST", f"manifest is not valid JSON: {exc}") from exc
    if not isinstance(doc, dict):
        raise PluginError("E_MANIFEST", "manifest root must be a JSON object")

    _reject_unknown(doc, "")
    missing = [k for k in REQUIRED_TOP if k not in doc]
    if missing:
        raise PluginError(
            "E_MANIFEST", f"missing required field(s): {', '.join(missing)}"
        )

    if not isinstance(doc["name"], str) or not re.fullmatch(
        r"[a-z0-9][a-z0-9\-]{1,63}", doc["name"]
    ):
        raise PluginError(
            "E_MANIFEST",
            f"name must be lowercase kebab-case, 2-64 chars, got {doc['name']!r}",
        )
    parse_semver(doc["version"], where="version")
    if not isinstance(doc["description"], str) or not doc["description"].strip():
        raise PluginError("E_MANIFEST", "description must be a non-empty string")
    author = doc["author"]
    if not isinstance(author, dict):
        raise PluginError("E_MANIFEST", "author must be an object")
    _reject_unknown(author, "author")
    if not isinstance(author.get("name"), str) or not author["name"].strip():
        raise PluginError("E_MANIFEST", "author.name is required")
    if not isinstance(doc["license"], str) or not doc["license"].strip():
        raise PluginError("E_MANIFEST", "license must be a non-empty SPDX id")

    compat = doc["compatibility"]
    if not isinstance(compat, dict):
        raise PluginError("E_MANIFEST", "compatibility must be an object")
    _reject_unknown(compat, "compatibility")
    if "min_client" not in compat:
        raise PluginError("E_MANIFEST", "compatibility.min_client is required")
    parse_semver(compat["min_client"], where="compatibility.min_client")
    if compat.get("max_client") is not None:
        parse_semver(compat["max_client"], where="compatibility.max_client")
    platforms = tuple(compat.get("platforms") or ("windows", "macos", "linux"))
    bad = [p for p in platforms if p not in {"windows", "macos", "linux"}]
    if bad:
        raise PluginError(
            "E_MANIFEST", f"unsupported platform(s) declared: {', '.join(bad)}"
        )
    shells = tuple(compat.get("shells") or ("pwsh", "bash", "zsh", "cmd"))
    schema_version = compat.get("schema_version", 1)
    if not isinstance(schema_version, int) or schema_version < 1:
        raise PluginError(
            "E_MANIFEST", "compatibility.schema_version must be a positive integer"
        )

    interpreters: list[dict[str, Any]] = []
    for item in doc.get("interpreters") or ():
        if not isinstance(item, dict):
            raise PluginError(
                "E_MANIFEST", "each interpreters[] entry must be an object"
            )
        _reject_unknown(item, "interpreters")
        if not isinstance(item.get("id"), str):
            raise PluginError("E_MANIFEST", "interpreters[].id is required")
        interpreters.append(dict(item))
    declared_ids = {i["id"] for i in interpreters}

    entrypoints: list[Entrypoint] = []
    seen_ep: set[str] = set()
    for item in doc.get("entrypoints") or ():
        if not isinstance(item, dict):
            raise PluginError(
                "E_MANIFEST", "each entrypoints[] entry must be an object"
            )
        _reject_unknown(item, "entrypoints")
        for req in ("id", "kind", "path"):
            if req not in item:
                raise PluginError("E_MANIFEST", f"entrypoints[].{req} is required")
        if item["kind"] not in ENTRYPOINT_KINDS:
            raise PluginError(
                "E_MANIFEST",
                f"entrypoints[{item['id']!r}].kind must be one of {sorted(ENTRYPOINT_KINDS)}",
            )
        if item["id"] in seen_ep:
            raise PluginError("E_MANIFEST", f"duplicate entrypoint id {item['id']!r}")
        seen_ep.add(item["id"])
        interp = item.get("interpreter")
        if item["kind"] in {"script", "hook", "command"} and not interp:
            raise PluginError(
                "E_MANIFEST",
                f"entrypoint {item['id']!r} of kind {item['kind']!r} must declare an interpreter "
                "(inferring one from the shebang is not portable)",
            )
        if interp and interp not in declared_ids:
            raise PluginError(
                "E_MANIFEST",
                f"entrypoint {item['id']!r} names interpreter {interp!r}, "
                "which is not in interpreters[]",
            )
        entrypoints.append(
            Entrypoint(
                ident=item["id"],
                kind=item["kind"],
                path=item["path"],
                interpreter=interp,
                args=tuple(item.get("args") or ()),
                description=item.get("description", ""),
            )
        )

    payload = doc.get("payload") or {}
    if payload:
        _reject_unknown(payload, "payload")
    deploy = doc.get("deploy") or {}
    if deploy:
        _reject_unknown(deploy, "deploy")
    targets: list[DeployTarget] = []
    for item in deploy.get("targets") or ():
        if not isinstance(item, dict):
            raise PluginError(
                "E_MANIFEST", "each deploy.targets[] entry must be an object"
            )
        _reject_unknown(item, "deploy.targets")
        for req in ("source", "target", "mode"):
            if req not in item:
                raise PluginError("E_MANIFEST", f"deploy.targets[].{req} is required")
        if item["mode"] not in DEPLOY_MODES:
            raise PluginError(
                "E_MANIFEST",
                f"deploy.targets[].mode must be one of {sorted(DEPLOY_MODES)}",
            )
        targets.append(DeployTarget(item["source"], item["target"], item["mode"]))

    extensions = {k: v for k, v in doc.items() if k.startswith(EXTENSION_PREFIX)}

    return Manifest(
        name=doc["name"],
        version=doc["version"],
        description=doc["description"],
        author={k: v for k, v in author.items() if isinstance(v, str)},
        license=doc["license"],
        min_client=compat["min_client"],
        max_client=compat.get("max_client"),
        platforms=platforms,
        shells=shells,
        schema_version=schema_version,
        keywords=tuple(doc.get("keywords") or ()),
        homepage=doc.get("homepage"),
        interpreters=tuple(interpreters),
        entrypoints=tuple(entrypoints),
        deploy_targets=tuple(targets),
        payload_max_bytes=int(payload.get("max_bytes") or 0),
        payload_max_files=int(payload.get("max_files") or 0),
        extensions=extensions,
        raw=doc,
    )


def load(path: Path) -> Manifest:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise PluginError("E_MANIFEST", f"cannot read manifest {path}: {exc}") from exc
    return parse(text)


def dumps(manifest: Manifest) -> str:
    """Canonical serialisation: sorted keys, LF, trailing newline — byte-stable across platforms."""
    return (
        json.dumps(manifest.as_dict(), indent=2, sort_keys=True, ensure_ascii=False)
        + "\n"
    )
