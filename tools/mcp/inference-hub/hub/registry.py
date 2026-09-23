"""Registry access for inference-hub: snapshots, resolution, deny lists, halt.

The SSOT is ``.agents/models.json`` (BUILD-CONTRACT section 1). Its path comes
from the constructor, else ``INFERENCE_HUB_REGISTRY``, else
``<repo>/.agents/models.json`` where the repo root is found by walking up from
this file (:func:`find_repo_root`).

Validation is delegated to ``.agents/scripts/models_control_plane.py`` when that
module exists: it is imported lazily by path (:func:`load_validator`) so the hub
does not depend on the scripts directory being a package, and so a missing or
broken validator degrades to a structural check with ``validated: False`` in
the snapshot rather than taking the hub down.

Snapshots reload when the file's mtime (or size) changes. Effective
capabilities apply the endpoint lattice with the model's DOWNWARD overrides,
using the same rank table as the contract, implemented locally.
"""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import os
import re
import sys
import threading
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType
from typing import Any

from hub.errors import (
    CALLER_DENIED,
    ENDPOINT_DISABLED,
    INVALID_ARGUMENT,
    MODEL_DISABLED,
    REGISTRY_UNAVAILABLE,
    UNKNOWN_MODEL,
    HubError,
)

__all__ = [
    "DEFAULT_HALT_ENV",
    "DEFAULT_HALT_FILE",
    "LATTICE_RANK",
    "LATTICE_STATES",
    "REGISTRY_ENV",
    "Registry",
    "RegistrySnapshot",
    "ResolvedModel",
    "caller_family",
    "effective_capabilities",
    "find_repo_root",
    "lattice_rank",
    "lattice_state",
    "load_validator",
    "registry_hash",
]

REGISTRY_ENV = "INFERENCE_HUB_REGISTRY"
DEFAULT_HALT_ENV = "INFERENCE_HALT"
DEFAULT_HALT_FILE = ".agents/INFERENCE-HALT"
LATTICE_STATES: tuple[str, ...] = ("native", "probed", "declared", "emulated", "absent")
LATTICE_RANK: dict[str, int] = {
    "native": 4,
    "probed": 3,
    "declared": 2,
    "emulated": 1,
    "absent": 0,
}
_CAPABILITY_GROUPS = ("wire", "features")
_FALSE_WORDS = frozenset({"", "0", "false", "no", "off"})
_VALIDATOR_MODULE_NAME = "_inference_hub_models_control_plane"
_VALIDATOR_RELATIVE = Path(".agents") / "scripts" / "models_control_plane.py"
_VALIDATOR_CACHE: dict[str, ModuleType | None] = {}
_FAMILY_SPLIT_RE = re.compile(r"[-_/\s]")


# -- lattice ---------------------------------------------------------------------
def lattice_state(value: Any) -> str:
    """The state name of a lattice value (``absent`` for anything unrecognised)."""
    if isinstance(value, str):
        return value if value in LATTICE_RANK else "absent"
    if isinstance(value, dict):
        state = value.get("state")
        if isinstance(state, str) and state in LATTICE_RANK:
            return state
    return "absent"


def lattice_rank(value: Any) -> int:
    return LATTICE_RANK[lattice_state(value)]


def effective_capabilities(config: Mapping[str, Any], model_id: str) -> dict[str, Any]:
    """Endpoint lattice with the model's downward overrides (upward ones ignored)."""
    model = config["models"][model_id]
    endpoint = config["endpoints"][model["endpoint"]]
    result: dict[str, Any] = {}
    for group in _CAPABILITY_GROUPS:
        base = dict(endpoint.get(group) or {})
        overrides = model.get(group) or {}
        for key, value in overrides.items():
            if lattice_rank(value) <= lattice_rank(base.get(key)):
                base[key] = value
        result[group] = base
    return result


def registry_hash(config: Mapping[str, Any]) -> str:
    """sha256 of the canonical JSON, first 16 hex - the managed-by marker."""
    canonical = json.dumps(
        config, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


# -- repo root / validator -----------------------------------------------------
def find_repo_root(start: Path | None = None) -> Path | None:
    """The nearest ancestor of ``start`` (default: this file) holding ``.agents/models.json``."""
    origin = Path(__file__).resolve() if start is None else Path(start)
    for candidate in (origin, *origin.parents):
        if (candidate / ".agents" / "models.json").is_file():
            return candidate
    return None


def _import_by_path(module_path: Path) -> ModuleType:
    scripts_dir = str(module_path.parent)
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    spec = importlib.util.spec_from_file_location(_VALIDATOR_MODULE_NAME, module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"no import spec for {module_path.name}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[_VALIDATOR_MODULE_NAME] = module
    spec.loader.exec_module(module)
    return module


def load_validator(repo_root: Path) -> ModuleType | None:
    """``models_control_plane`` loaded by path, or None when absent or broken."""
    module_path = repo_root / _VALIDATOR_RELATIVE
    key = str(module_path)
    if key in _VALIDATOR_CACHE:
        return _VALIDATOR_CACHE[key]
    module: ModuleType | None = None
    if module_path.is_file():
        try:
            module = _import_by_path(module_path)
        except Exception:
            module = None
    _VALIDATOR_CACHE[key] = module
    return module


def caller_family(name: Any) -> str:
    """The caller's family: ``claude-code``, ``claude``, ``Claude-Code/2.1.x`` -> ``claude``."""
    if not isinstance(name, str):
        return ""
    return _FAMILY_SPLIT_RE.split(name.strip().lower(), maxsplit=1)[0]


def _structural_check(config: Any) -> dict[str, Any]:
    """Minimal shape check used when the validator module is unavailable."""
    if not isinstance(config, dict):
        raise HubError(REGISTRY_UNAVAILABLE, "registry root must be a JSON mapping")
    if config.get("schemaVersion") != 1:
        raise HubError(REGISTRY_UNAVAILABLE, "registry schemaVersion must be 1")
    for key in ("policy", "endpoints", "models"):
        if not isinstance(config.get(key), dict):
            raise HubError(REGISTRY_UNAVAILABLE, f"registry {key} must be a mapping")
    aliases = config.get("aliases", {})
    if not isinstance(aliases, dict):
        raise HubError(REGISTRY_UNAVAILABLE, "registry aliases must be a mapping")
    endpoints = config["endpoints"]
    for endpoint_id, endpoint in endpoints.items():
        if not isinstance(endpoint, dict):
            raise HubError(
                REGISTRY_UNAVAILABLE, f"endpoint {endpoint_id} must be a mapping"
            )
    for model_id, model in config["models"].items():
        if not isinstance(model, dict):
            raise HubError(REGISTRY_UNAVAILABLE, f"model {model_id} must be a mapping")
        if model.get("endpoint") not in endpoints:
            raise HubError(
                REGISTRY_UNAVAILABLE,
                f"model {model_id} names unknown endpoint {model.get('endpoint')!r}",
            )
    for alias, target in aliases.items():
        if target not in config["models"]:
            raise HubError(
                REGISTRY_UNAVAILABLE, f"alias {alias} names unknown model {target!r}"
            )
    return config


# -- data ----------------------------------------------------------------------------
@dataclass(frozen=True)
class RegistrySnapshot:
    """One loaded registry file."""

    config: dict[str, Any]
    path: Path
    mtime: int
    hash: str
    validated: bool
    warnings: list[str] = field(default_factory=list)
    size: int = 0


@dataclass(frozen=True)
class ResolvedModel:
    """A model reference resolved to its rows and effective capabilities."""

    model_id: str
    model: dict[str, Any]
    endpoint_id: str
    endpoint: dict[str, Any]
    remote_id: str
    capabilities: dict[str, Any]


# -- registry ------------------------------------------------------------------------
class Registry:
    """Thread-safe reader of ``.agents/models.json`` with mtime-based reload."""

    path: Path
    repo_root: Path

    def __init__(
        self,
        path: Path | str | None = None,
        environ: Mapping[str, str] | None = None,
        *,
        repo_root: Path | None = None,
    ) -> None:
        env: Mapping[str, str] = os.environ if environ is None else environ
        self._environ = env
        explicit = path if path is not None else (env.get(REGISTRY_ENV) or None)
        if explicit is not None:
            self.path = Path(explicit)
            root = repo_root or find_repo_root(self.path) or find_repo_root()
            self.repo_root = root if root is not None else self.path.parent
        else:
            root = repo_root or find_repo_root()
            if root is None:
                raise HubError(
                    REGISTRY_UNAVAILABLE,
                    "no registry path given and no .agents/models.json found upward",
                )
            self.repo_root = root
            self.path = root / ".agents" / "models.json"
        self._lock = threading.Lock()
        self._snapshot: RegistrySnapshot | None = None

    # -- loading ----------------------------------------------------------------------
    def snapshot(self) -> RegistrySnapshot:
        """The current registry, reloaded when the file changed on disk."""
        try:
            stat = self.path.stat()
        except OSError as exc:
            raise HubError(
                REGISTRY_UNAVAILABLE,
                f"registry not readable: {self.path.name}: {type(exc).__name__}",
            ) from exc
        with self._lock:
            current = self._snapshot
            if (
                current is not None
                and current.mtime == stat.st_mtime_ns
                and current.size == stat.st_size
            ):
                return current
            loaded = self._load(stat.st_mtime_ns, stat.st_size)
            self._snapshot = loaded
            return loaded

    def _load(self, mtime: int, size: int) -> RegistrySnapshot:
        try:
            config = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise HubError(
                REGISTRY_UNAVAILABLE,
                f"registry unparseable: {self.path.name}: {type(exc).__name__}",
            ) from exc
        config = _structural_check(config)
        validator = load_validator(self.repo_root)
        if validator is None:
            return RegistrySnapshot(
                config, self.path, mtime, registry_hash(config), False, [], size
            )
        try:
            warnings = [str(item) for item in validator.validate_registry(config)]
            digest = str(validator.registry_hash(config))
        except Exception as exc:
            raise HubError(REGISTRY_UNAVAILABLE, f"registry invalid: {exc}") from exc
        return RegistrySnapshot(config, self.path, mtime, digest, True, warnings, size)

    def hash(self) -> str:
        return self.snapshot().hash

    def policy(self) -> dict[str, Any]:
        return copy.deepcopy(self.snapshot().config.get("policy") or {})

    def endpoint(self, endpoint_id: str) -> dict[str, Any]:
        endpoints = self.snapshot().config["endpoints"]
        if endpoint_id not in endpoints:
            raise HubError(INVALID_ARGUMENT, f"unknown endpoint {endpoint_id!r}")
        return endpoints[endpoint_id]

    def concurrency_limit(self, endpoint_id: str) -> int:
        concurrency = self.endpoint(endpoint_id).get("concurrency") or {}
        return int(concurrency.get("maxInFlight") or 1)

    def credential_names(self) -> list[str]:
        """Union of ``auth.env`` + ``altEnv`` over ENABLED endpoints, sorted."""
        names: set[str] = set()
        for endpoint in self.snapshot().config["endpoints"].values():
            if not endpoint.get("enabled"):
                continue
            auth = endpoint.get("auth") or {}
            env_name = auth.get("env")
            if isinstance(env_name, str):
                names.add(env_name)
            names.update(
                alt for alt in auth.get("altEnv") or [] if isinstance(alt, str)
            )
        return sorted(names)

    # -- resolution ---------------------------------------------------------------------
    @staticmethod
    def _denied(caller: str | None, *rows: Mapping[str, Any]) -> bool:
        if caller is None:
            return False
        family = caller_family(caller)
        for row in rows:
            if any(
                caller_family(entry) == family for entry in row.get("denyCallers") or []
            ):
                return True
        return False

    def resolve(self, ref: Any, caller: str | None = None) -> ResolvedModel:
        """``<id>``, ``<id>@<endpoint>`` or an alias -> :class:`ResolvedModel`."""
        if not isinstance(ref, str) or not ref.strip():
            raise HubError(
                INVALID_ARGUMENT, "model reference must be a non-empty string"
            )
        config = self.snapshot().config
        name, separator, endpoint_hint = ref.strip().partition("@")
        model_id = config.get("aliases", {}).get(name, name)
        model = config["models"].get(model_id)
        if model is None:
            raise HubError(UNKNOWN_MODEL, f"unknown model {ref.strip()!r}", model=name)
        endpoint_id = str(model["endpoint"])
        if separator and endpoint_hint != endpoint_id:
            raise HubError(
                UNKNOWN_MODEL,
                f"model {model_id!r} is served by {endpoint_id!r}, not {endpoint_hint!r}",
                model=model_id,
            )
        endpoint = config["endpoints"][endpoint_id]
        if not model.get("enabled"):
            raise HubError(
                MODEL_DISABLED,
                f"model {model_id!r} is disabled",
                endpoint=endpoint_id,
                model=model_id,
            )
        if not endpoint.get("enabled"):
            raise HubError(
                ENDPOINT_DISABLED,
                f"endpoint {endpoint_id!r} is disabled",
                endpoint=endpoint_id,
                model=model_id,
            )
        if self._denied(caller, endpoint, model):
            raise HubError(
                CALLER_DENIED,
                f"caller family {caller_family(caller)!r} is denied for "
                f"{model_id}@{endpoint_id}",
                endpoint=endpoint_id,
                model=model_id,
            )
        return ResolvedModel(
            model_id=model_id,
            model=model,
            endpoint_id=endpoint_id,
            endpoint=endpoint,
            remote_id=str(model.get("remoteId") or model_id),
            capabilities=effective_capabilities(config, model_id),
        )

    def models_list(
        self, filter: str | None = None, caller: str | None = None
    ) -> list[dict[str, Any]]:
        """Every model row; denied or disabled rows stay listed with ``callable: False``."""
        config = self.snapshot().config
        needle = (filter or "").strip().lower()
        rows: list[dict[str, Any]] = []
        for model_id, model in config["models"].items():
            endpoint_id = str(model["endpoint"])
            endpoint = config["endpoints"][endpoint_id]
            label = str(model.get("label") or "")
            haystack = " ".join((model_id, label, endpoint_id)).lower()
            if needle and needle not in haystack:
                continue
            deny = set(endpoint.get("denyCallers") or []) | set(
                model.get("denyCallers") or []
            )
            callable_now = (
                bool(model.get("enabled"))
                and bool(endpoint.get("enabled"))
                and not self._denied(caller, endpoint, model)
            )
            rows.append(
                {
                    "id": model_id,
                    "endpoint": endpoint_id,
                    "remote_id": str(model.get("remoteId") or model_id),
                    "enabled": bool(model.get("enabled")),
                    "status": model.get("status"),
                    "tier": model.get("tier"),
                    "label": label,
                    "capabilities": effective_capabilities(config, model_id),
                    "cost": copy.deepcopy(model.get("cost")),
                    "deny_callers": sorted(str(entry) for entry in deny),
                    "callable": callable_now,
                }
            )
        return rows

    # -- halt -------------------------------------------------------------------------------
    def halted(self, environ: Mapping[str, str] | None = None) -> bool:
        """``policy.hub.haltEnv`` set truthy, or ``policy.hub.haltFile`` present."""
        env = self._environ if environ is None else environ
        try:
            hub_policy = self.policy().get("hub") or {}
        except HubError:
            hub_policy = {}
        halt_env = str(hub_policy.get("haltEnv") or DEFAULT_HALT_ENV)
        halt_file = str(hub_policy.get("haltFile") or DEFAULT_HALT_FILE)
        if env.get(halt_env, "").strip().lower() not in _FALSE_WORDS:
            return True
        return (self.repo_root / halt_file).exists()
