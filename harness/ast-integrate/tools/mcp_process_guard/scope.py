"""Effective vs inert disable scopes for Claude MCP config (IMP-0472)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

SCOPE_CLAUDE_ROOT = "claude-root"
SCOPE_CLAUDE_PROJECT = "claude-project"


@dataclass
class ScopeRecord:
    name: str
    scope: str
    declared_disabled: bool
    effective_disabled: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "scope": self.scope,
            "declared_disabled": self.declared_disabled,
            "effective_disabled": self.effective_disabled,
        }


def fixture_inert_root_disable(servers: Iterable[str]) -> dict[str, Any]:
    servers = tuple(servers)
    return {
        "scope": SCOPE_CLAUDE_ROOT,
        "mcpServers": {s: {"disabled": True, "command": s} for s in servers},
        "project": None,
    }


def fixture_effective_project_disable(
    servers: Iterable[str], disabled: Iterable[str]
) -> dict[str, Any]:
    servers = tuple(servers)
    disabled = tuple(disabled)
    return {
        "scope": SCOPE_CLAUDE_PROJECT,
        "mcpServers": {s: {"disabled": s in disabled, "command": s} for s in servers},
        "project": "ast-integrate",
    }


def resolve(cfg: dict[str, Any]) -> dict[str, ScopeRecord]:
    scope = cfg.get("scope") or SCOPE_CLAUDE_ROOT
    out = {}
    for name, rec in (cfg.get("mcpServers") or {}).items():
        declared = bool(rec.get("disabled"))
        effective = declared and scope == SCOPE_CLAUDE_PROJECT
        out[name] = ScopeRecord(name, scope, declared, effective)
    return out


def would_spawn_names(cfg: dict[str, Any]) -> tuple[str, ...]:
    recs = resolve(cfg)
    return tuple(n for n, r in recs.items() if not r.effective_disabled)


def inert_root_disables(cfg: dict[str, Any]) -> tuple[str, ...]:
    recs = resolve(cfg)
    return tuple(
        n
        for n, r in recs.items()
        if r.declared_disabled and r.scope == SCOPE_CLAUDE_ROOT and not r.effective_disabled
    )


def naive_trust_root_disable(cfg: dict[str, Any]) -> frozenset[str]:
    """Negative control: trusts root-level disabled flags."""
    names = []
    for name, rec in (cfg.get("mcpServers") or {}).items():
        if rec.get("disabled"):
            names.append(name)
    return frozenset(names)
