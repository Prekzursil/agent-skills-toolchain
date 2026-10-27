"""Load the live marketplace manifest with canonical round-trip (TST-0034)."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

RULE_ROUND_TRIP = "round-trip-byte-identity"
RULE_SOURCE_RESOLVABLE = "source-path-resolvable"


@dataclass
class Finding:
    rule: str
    message: str


@dataclass
class Manifest:
    data: dict[str, Any]
    path: Path
    raw: bytes = b""


@dataclass
class ManifestEntry:
    name: str
    source: str
    resolved: str | None
    exists: bool
    plugin_json_exists: bool


@dataclass
class ManifestReport:
    ok: bool
    findings: list[Finding] = field(default_factory=list)
    round_trip: bool = True
    entries: list[ManifestEntry] = field(default_factory=list)
    listed: int = 0
    resolved: int = 0
    unresolved: int = 0


def live_path(repo: Path) -> Path:
    return Path(repo) / ".claude-plugin" / "marketplace.json"


def dump_bytes(data: dict[str, Any]) -> bytes:
    return (json.dumps(data, indent=2, sort_keys=True, ensure_ascii=True) + "\n").encode("utf-8")


def load_manifest(path: Path) -> Manifest:
    raw = Path(path).read_bytes()
    text = raw.decode("utf-8")
    data = json.loads(text)
    if not isinstance(data, dict):
        data = {}
    return Manifest(data=data, path=Path(path), raw=raw.replace(b"\r\n", b"\n"))


def canonical_plugin_document() -> dict[str, Any]:
    return {
        "name": "agent-skills-toolchain",
        "version": "0.3.0",
    }


def canonical_live_document() -> dict[str, Any]:
    return {
        "name": "ast-integrate-marketplace",
        "plugins": [{"name": "agent-skills-toolchain", "source": "."}],
        "schema_version": 1,
    }


def ensure_live_subject(repo: Path) -> Path:
    path = live_path(repo)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.is_file():
        path.write_bytes(dump_bytes(canonical_live_document()))
    else:
        loaded = load_manifest(path)
        if dump_bytes(loaded.data) != loaded.raw:
            path.write_bytes(dump_bytes(loaded.data))
    return path


def check_manifest(path: Path, repo: Path | None = None) -> ManifestReport:
    loaded = load_manifest(path)
    dumped = dump_bytes(loaded.data)
    rt = dumped == loaded.raw
    findings: list[Finding] = []
    if not rt:
        findings.append(Finding(RULE_ROUND_TRIP, "dump(load) is not byte-identical"))
    entries: list[ManifestEntry] = []
    plugins = loaded.data.get("plugins") or []
    root = Path(path).resolve().parent
    for item in plugins:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "")
        source = str(item.get("source") or "")
        cand = (root / source).resolve() if source else None
        exists = bool(cand and cand.exists())
        plugin_json = bool(cand and (cand / "plugin.json").is_file()) if exists else False
        if not exists:
            findings.append(
                Finding(RULE_SOURCE_RESOLVABLE, f"unresolved source {source!r} for {name}")
            )
        entries.append(
            ManifestEntry(
                name=name,
                source=source,
                resolved=str(cand) if cand else None,
                exists=exists,
                plugin_json_exists=plugin_json,
            )
        )
    listed = len(entries)
    resolved_n = sum(1 for e in entries if e.exists)
    unresolved = listed - resolved_n
    ok = not findings
    return ManifestReport(
        ok=ok,
        findings=findings,
        round_trip=rt,
        entries=entries,
        listed=listed,
        resolved=resolved_n,
        unresolved=unresolved,
    )
