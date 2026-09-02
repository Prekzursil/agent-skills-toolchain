"""Named health probes and fixture trees for IMP-0043.

Seven registered probes -- hooks loaded, skills registered, MCP reachable, router
responding, ledger writable, cache valid, deploy in sync -- each carrying an
IMP-0044 both-states control: a planter for the known-good tree, a planter for the
known-broken tree, and the terminal state expected on each.  Every probe observes
``HealthContext.root`` only; nothing reads the operator's live machine implicitly
(IMP-0038/IMP-0039 live surfaces are NOT claimed here).

Observation-root layout (what a caller supplies, and what the planters produce):

    hooks.json          {"loaded": bool, "hooks": [..]}
    skills.json         {"registered": bool, "ids": [..]}
    mcp.json            {"reachable": bool, "servers": [..]}
    router.json         {"responding": bool, "pid": int}
    ledger/             a DIRECTORY that accepts write-read-unlink
    cache.json          {"valid": bool, ...}
    live_manifest.json  {"files": [..], "sha256": hex}   must equal
    repo_manifest.json  {"files": [..], "sha256": hex}
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Callable

from health_check import BothStatesControl, HealthContext, ProbeResult

BOTH_STATES_UNIT = "IMP-0044"

REQUIRED_PROBE_IDS = (
    "hooks_loaded",
    "skills_registered",
    "mcp_reachable",
    "router_responding",
    "ledger_writable",
    "cache_valid",
    "deploy_in_sync",
)

HEALTHY_DOCUMENTS: dict[str, dict[str, Any]] = {
    "hooks.json": {"loaded": True, "hooks": ["PreToolUse", "PostToolUse"], "count": 2},
    "skills.json": {"registered": True, "ids": ["skill.council", "skill.health"]},
    "mcp.json": {"reachable": True, "servers": ["filesystem", "memory"]},
    "router.json": {"responding": True, "pid": 4242},
    "cache.json": {"valid": True, "entries": 3, "bytes": 128},
}
MANIFEST_FILES = ["plugin.json", "hooks.json"]


def manifest_document(files: list[str]) -> dict[str, Any]:
    """A deploy manifest: the file list plus the sha256 of its canonical JSON."""
    canonical = json.dumps(sorted(files), separators=(",", ":")).encode("utf-8")
    return {"files": list(files), "sha256": hashlib.sha256(canonical).hexdigest()}


def _write_json(path: Path, document: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _read_json(path: Path) -> tuple[dict[str, Any] | None, str]:
    if not path.is_file():
        return None, "missing"
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return None, f"unreadable:{type(exc).__name__}"
    if not isinstance(document, dict):
        return None, "not-an-object"
    return document, "ok"


def _non_empty_list(value: Any) -> bool:
    return isinstance(value, list) and len(value) > 0


class JsonCriterionProbe:
    """SUCCESS iff ``<root>/<rel>`` parses to an object satisfying ``criterion``."""

    def __init__(
        self,
        probe_id: str,
        rel: str,
        criterion: Callable[[dict[str, Any]], bool],
        *,
        known_good: str,
        known_broken: str,
    ) -> None:
        self.probe_id = probe_id
        self.rel = rel
        self.criterion = criterion
        self.both_states = BothStatesControl(
            unit_id=BOTH_STATES_UNIT,
            known_good=known_good,
            known_broken=known_broken,
            expected_good="SUCCESS",
            expected_broken="FAILED",
            plant_good=plant_healthy_tree,
            plant_broken=lambda root, _pid=probe_id: plant_broken_tree(root, only=_pid),
        )

    def run(self, ctx: HealthContext) -> ProbeResult:
        path = Path(ctx.root) / self.rel
        document, status = _read_json(path)
        if document is None:
            return ProbeResult(
                self.probe_id,
                "FAILED",
                reason=f"{self.rel} {status}",
                evidence={"path": str(path), "exists": path.exists(), "reason": status},
            )
        met = bool(self.criterion(document))
        return ProbeResult(
            self.probe_id,
            "SUCCESS" if met else "FAILED",
            reason="criterion-met" if met else f"{self.rel} criterion not met",
            evidence={
                "path": str(path),
                "exists": True,
                "document": document,
                "reason": "criterion-met" if met else "criterion-not-met",
            },
        )


class LedgerWritableProbe:
    """SUCCESS iff ``<root>/ledger`` is a directory that accepts write, read-back and unlink."""

    probe_id = "ledger_writable"
    rel = "ledger"

    def __init__(self) -> None:
        self.both_states = BothStatesControl(
            unit_id=BOTH_STATES_UNIT,
            known_good="ledger directory accepts write-read-unlink",
            known_broken="ledger path is a file, not a directory",
            expected_good="SUCCESS",
            expected_broken="FAILED",
            plant_good=plant_healthy_tree,
            plant_broken=lambda root: plant_broken_tree(root, only="ledger_writable"),
        )

    def run(self, ctx: HealthContext) -> ProbeResult:
        path = Path(ctx.root) / self.rel
        evidence: dict[str, Any] = {"path": str(path), "exists": path.exists()}
        if not path.is_dir():
            evidence["reason"] = "not-a-directory" if path.exists() else "missing"
            return ProbeResult(self.probe_id, "FAILED", reason=f"ledger {evidence['reason']}", evidence=evidence)
        probe_file = path / f".health-probe-{os.getpid()}.tmp"
        payload = b"health-check\n"
        try:
            probe_file.write_bytes(payload)
            read_back = probe_file.read_bytes()
            probe_file.unlink()
        except OSError as exc:
            evidence["reason"] = f"io-error:{type(exc).__name__}"
            return ProbeResult(self.probe_id, "FAILED", reason=f"ledger {evidence['reason']}", evidence=evidence)
        if read_back != payload:
            evidence["reason"] = "read-back-mismatch"
            return ProbeResult(self.probe_id, "FAILED", reason="ledger read-back mismatch", evidence=evidence)
        evidence["reason"] = "write-read-unlink-ok"
        return ProbeResult(self.probe_id, "SUCCESS", reason="write-read-unlink-ok", evidence=evidence)


class DeployInSyncProbe:
    """SUCCESS iff the live deploy manifest equals the repo manifest (files AND sha256)."""

    probe_id = "deploy_in_sync"
    live_rel = "live_manifest.json"
    repo_rel = "repo_manifest.json"

    def __init__(self) -> None:
        self.both_states = BothStatesControl(
            unit_id=BOTH_STATES_UNIT,
            known_good="live_manifest.json equals repo_manifest.json",
            known_broken="live_manifest.json sha256 differs from repo",
            expected_good="SUCCESS",
            expected_broken="FAILED",
            plant_good=plant_healthy_tree,
            plant_broken=lambda root: plant_broken_tree(root, only="deploy_in_sync"),
        )

    def run(self, ctx: HealthContext) -> ProbeResult:
        live_path = Path(ctx.root) / self.live_rel
        repo_path = Path(ctx.root) / self.repo_rel
        live, live_status = _read_json(live_path)
        repo, repo_status = _read_json(repo_path)
        evidence: dict[str, Any] = {
            "live_path": str(live_path),
            "live_exists": live_path.is_file(),
            "repo_path": str(repo_path),
            "repo_exists": repo_path.is_file(),
        }
        if live is None or repo is None:
            evidence["reason"] = f"live:{live_status} repo:{repo_status}"
            return ProbeResult(self.probe_id, "FAILED", reason=evidence["reason"], evidence=evidence)
        evidence["live"] = live
        evidence["repo"] = repo
        same_sha = live.get("sha256") == repo.get("sha256")
        same_files = sorted(map(str, live.get("files") or [])) == sorted(map(str, repo.get("files") or []))
        if same_sha and same_files and live.get("sha256"):
            evidence["reason"] = "manifests-equal"
            return ProbeResult(self.probe_id, "SUCCESS", reason="manifests-equal", evidence=evidence)
        evidence["reason"] = "sha256-differs" if not same_sha else ("files-differ" if not same_files else "empty-sha256")
        return ProbeResult(self.probe_id, "FAILED", reason=f"manifests differ: {evidence['reason']}", evidence=evidence)


def default_probes() -> list[Any]:
    return [
        JsonCriterionProbe(
            "hooks_loaded",
            "hooks.json",
            lambda d: d.get("loaded") is True and _non_empty_list(d.get("hooks")),
            known_good="hooks.json loaded=true with a non-empty hooks list",
            known_broken="hooks.json loaded=false",
        ),
        JsonCriterionProbe(
            "skills_registered",
            "skills.json",
            lambda d: d.get("registered") is True and _non_empty_list(d.get("ids")),
            known_good="skills.json registered=true with a non-empty ids list",
            known_broken="skills.json registered=false",
        ),
        JsonCriterionProbe(
            "mcp_reachable",
            "mcp.json",
            lambda d: d.get("reachable") is True and _non_empty_list(d.get("servers")),
            known_good="mcp.json reachable=true with a non-empty servers list",
            known_broken="mcp.json reachable=false",
        ),
        JsonCriterionProbe(
            "router_responding",
            "router.json",
            lambda d: d.get("responding") is True,
            known_good="router.json responding=true",
            known_broken="router.json responding=false",
        ),
        LedgerWritableProbe(),
        JsonCriterionProbe(
            "cache_valid",
            "cache.json",
            lambda d: d.get("valid") is True,
            known_good="cache.json valid=true",
            known_broken="cache.json valid=false",
        ),
        DeployInSyncProbe(),
    ]


def plant_healthy_tree(root: Path) -> None:
    """The known-good observation root: every probe's criterion is met."""
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    for name, document in HEALTHY_DOCUMENTS.items():
        _write_json(root / name, document)
    ledger = root / "ledger"
    if ledger.is_file():
        ledger.unlink()
    ledger.mkdir(exist_ok=True)
    manifest = manifest_document(MANIFEST_FILES)
    _write_json(root / "live_manifest.json", manifest)
    _write_json(root / "repo_manifest.json", manifest)


def plant_broken_tree(root: Path, *, only: str | None = None) -> None:
    """The known-broken root: each probe's criterion fails the way its control names.

    With ``only`` set, the healthy tree is planted and just that one probe's input is
    broken, so a both-states control isolates its own probe.
    """
    root = Path(root)
    plant_healthy_tree(root)
    breakers: dict[str, Callable[[], None]] = {
        "hooks_loaded": lambda: _write_json(root / "hooks.json", {"loaded": False, "hooks": []}),
        "skills_registered": lambda: _write_json(root / "skills.json", {"registered": False, "ids": []}),
        "mcp_reachable": lambda: _write_json(root / "mcp.json", {"reachable": False, "servers": []}),
        "router_responding": lambda: _write_json(root / "router.json", {"responding": False, "pid": None}),
        "ledger_writable": lambda: _make_ledger_a_file(root / "ledger"),
        "cache_valid": lambda: _write_json(root / "cache.json", {"valid": False, "entries": 0, "bytes": 0}),
        "deploy_in_sync": lambda: _write_json(
            root / "live_manifest.json",
            {"files": MANIFEST_FILES, "sha256": hashlib.sha256(b"drifted").hexdigest()},
        ),
    }
    if only is not None:
        if only not in breakers:
            raise KeyError(f"no known-broken planter for probe {only!r}")
        breakers[only]()
        return
    for breaker in breakers.values():
        breaker()


def _make_ledger_a_file(path: Path) -> None:
    if path.is_dir():
        for child in path.iterdir():
            child.unlink()
        path.rmdir()
    path.write_text("not a directory\n", encoding="utf-8")
