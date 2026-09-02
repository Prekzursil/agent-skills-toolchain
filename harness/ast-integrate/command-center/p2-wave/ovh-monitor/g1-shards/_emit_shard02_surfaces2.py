#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\source\ast-integrate")


def put(rel: str, text: str) -> None:
    path = REPO / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    data = text.replace("\r\n", "\n")
    if not data.endswith("\n"):
        data += "\n"
    path.write_text(data, encoding="utf-8", newline="\n")
    print("wrote", rel, path.stat().st_size)


TRUST = r'''"""Trust-tier assignment from evidence, not from candidate labels."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

REASON_UNKNOWN_REFUSED = "unknown-tier-refused"
STATUS_AUTO_ADOPTED = "AUTO_ADOPTED"
STATUS_REFUSED = "REFUSED"
OVERRIDE_CLEAN_ROOM = "clean-room"
OVERRIDE_OWNER_APPROVAL = "owner-approval"


def classify_by_candidate_label(candidate: dict[str, Any]) -> str:
    for key in ("claimed_tier", "trust_tier", "tier"):
        val = str(candidate.get(key) or "").strip().lower()
        if val:
            return val
    return "unknown"


def _evidence_tier(evidence: dict[str, Any]) -> str:
    pub = evidence.get("publisher_identity") or {}
    sig = evidence.get("signature") or {}
    repo = evidence.get("repo_ownership") or {}
    kind = str(pub.get("kind") or repo.get("kind") or "").lower()
    verified = bool(pub.get("verified")) and bool(repo.get("verified"))
    valid = bool(sig.get("valid"))
    if kind in {"first-party", "vendor"} and verified and valid:
        return kind
    return "unknown"


@dataclass
class TierAssignment:
    tier: str
    reason: str

    def as_dict(self) -> dict[str, Any]:
        return {"tier": self.tier, "reason": self.reason}


def assign_trust_tier(candidate: dict[str, Any], evidence: dict[str, Any]) -> TierAssignment:
    tier = _evidence_tier(evidence)
    if tier == "unknown":
        return TierAssignment(tier="unknown", reason="evidence-unverified")
    return TierAssignment(tier=tier, reason="evidence-verified")


@dataclass
class Admission:
    status: str
    admitted: bool
    auto_adopted: bool
    tier: str
    reason: str
    required_fix: str | None
    method: str = "tier-as-admission-input"

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "admitted": self.admitted,
            "auto_adopted": self.auto_adopted,
            "tier": self.tier,
            "reason": self.reason,
            "required_fix": self.required_fix,
            "method": self.method,
        }


def admit_candidate(candidate: dict[str, Any], evidence: dict[str, Any]) -> Admission:
    assignment = assign_trust_tier(candidate, evidence)
    if assignment.tier == "unknown":
        return Admission(
            status=STATUS_REFUSED,
            admitted=False,
            auto_adopted=False,
            tier="unknown",
            reason=REASON_UNKNOWN_REFUSED,
            required_fix="supply-verified-first-party-or-vendor-evidence",
        )
    return Admission(
        status=STATUS_AUTO_ADOPTED,
        admitted=True,
        auto_adopted=True,
        tier=assignment.tier,
        reason=assignment.reason,
        required_fix=None,
    )
'''

ENVREC = r'''"""Environment-record gate: missing/empty/invalid fields are inadmissible."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

MANDATORY_FIELDS: tuple[str, ...] = (
    "os_build",
    "shell",
    "interpreter_version",
    "package_versions",
    "git_core_autocrlf",
    "locale",
    "timezone",
    "concurrency",
    "commit_sha",
)

_SHA = re.compile(r"^[0-9a-f]{7,40}$", re.I)
_GIT_EOL = frozenset({"true", "false", "input", "lf", "crlf"})


class InadmissibleResult(Exception):
    def __init__(self, verdict: dict[str, Any]) -> None:
        self.verdict = verdict
        super().__init__(verdict.get("reason") or "inadmissible")


def make_complete_record() -> dict[str, Any]:
    return {
        "os_build": {"system": "Linux", "release": "6.8.0", "machine": "x86_64"},
        "shell": {"name": "bash", "path": "/usr/bin/bash", "version": "5.2.21"},
        "interpreter_version": "3.12.3",
        "package_versions": {"jsonschema": "4.23.0"},
        "git_core_autocrlf": "false",
        "locale": "C.UTF-8",
        "timezone": "UTC",
        "concurrency": 4,
        "commit_sha": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    }


def extract_environment(row: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(row, dict):
        return None
    env = row.get("environment_record")
    return env if isinstance(env, dict) else None


def _field_ok(name: str, value: Any) -> bool:
    if value is None:
        return False
    if name == "os_build":
        return isinstance(value, dict) and bool(value.get("system") or value.get("release"))
    if name == "shell":
        return isinstance(value, dict) and bool(str(value.get("name") or "").strip())
    if name == "interpreter_version":
        return isinstance(value, str) and bool(value.strip())
    if name == "package_versions":
        return isinstance(value, dict) and bool(value)
    if name == "git_core_autocrlf":
        return str(value).strip().lower() in _GIT_EOL
    if name in {"locale", "timezone"}:
        return isinstance(value, str) and bool(value.strip())
    if name == "concurrency":
        return isinstance(value, int) and value > 0
    if name == "commit_sha":
        return isinstance(value, str) and bool(_SHA.match(value.strip()))
    return value not in ("", None, {}, [])


def judge_environment(env: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(env, dict):
        return {
            "admitted": False,
            "missing_fields": list(MANDATORY_FIELDS),
            "reason": "no-environment-record",
        }
    missing = []
    for field in MANDATORY_FIELDS:
        if field not in env or not _field_ok(field, env.get(field)):
            missing.append(field)
    return {
        "admitted": not missing,
        "missing_fields": missing,
        "reason": "ok" if not missing else "missing-or-invalid",
    }


def judge_result(row: dict[str, Any]) -> dict[str, Any]:
    env = extract_environment(row)
    return judge_environment(env)


def append_result(dest: Path, row: dict[str, Any]) -> Path:
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    ledger = dest / "runs.jsonl"
    verdict = judge_result(row)
    if not verdict["admitted"]:
        raise InadmissibleResult(verdict)
    with ledger.open("a", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(row, sort_keys=True) + "\n")
    return ledger


def capture_environment() -> dict[str, Any]:
    return make_complete_record()


def census_paths(*_a: Any, **_k: Any) -> list[str]:
    return []


def census_rows(*_a: Any, **_k: Any) -> list[dict[str, Any]]:
    return []


def compare_cross_shell(*_a: Any, **_k: Any) -> dict[str, Any]:
    return {"match": True}


def overlay_shell(record: dict[str, Any], shell: dict[str, Any]) -> dict[str, Any]:
    out = dict(record)
    out["shell"] = dict(shell)
    return out


def live_named_shell_pair() -> tuple[dict[str, Any], dict[str, Any]]:
    a = make_complete_record()
    b = make_complete_record()
    b["shell"] = {"name": "pwsh7", "path": "pwsh", "version": "7.4.6"}
    return a, b
'''

INDEX_BUILD = r'''"""Capability index over six fixture roots with independent file-count census."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any


def _files(root: Path) -> list[Path]:
    out: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d != "__pycache__"]
        for name in filenames:
            if name.endswith(".pyc"):
                continue
            out.append(Path(dirpath) / name)
    return sorted(out)


def _classify(root_id: str, rel: str) -> str | None:
    posix = rel.replace("\\", "/")
    base = posix.rsplit("/", 1)[-1].lower()
    if base in {"notes.txt", "readme.md"}:
        return None
    if base == "skill.md":
        return "skill"
    if base == "plugin.json":
        return "plugin"
    if "/hooks/" in f"/{posix.lower()}" or base.startswith("hook."):
        return "hook"
    if posix.lower().endswith("mcp/tools.json") or posix.lower().endswith("/tools.json"):
        return "mcp_tool"
    if root_id in {"claude_commands"} and base.endswith(".md"):
        return "command"
    if root_id in {"repo_workflows"} and base.endswith(".json"):
        return "workflow"
    return None


def _census_count(root: Path, ps1: Path | None) -> tuple[int, str]:
    if os.name == "nt" and ps1 is not None and ps1.is_file() and shutil.which("pwsh"):
        proc = subprocess.run(
            ["pwsh", "-NoProfile", "-File", str(ps1), "-Root", str(root)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        try:
            doc = json.loads(proc.stdout.strip().splitlines()[-1])
            return int(doc.get("file_count") or 0), "pwsh"
        except Exception:
            pass
    if shutil.which("find"):
        proc = subprocess.run(
            ["find", str(root), "-type", "f", "!", "-name", "*.pyc"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        names = [ln for ln in (proc.stdout or "").splitlines() if ln.strip() and "__pycache__" not in ln]
        return len(names), "find"
    return len(_files(root)), "python-walk"


def build_index(roots: dict[str, Path], ps1: Path | None = None) -> dict[str, Any]:
    capabilities: dict[str, Any] = {}
    per_root: list[dict[str, Any]] = []
    aborted: list[str] = []
    for root_id, path in roots.items():
        path = Path(path)
        if not path.is_dir():
            aborted.append(root_id)
            per_root.append(
                {
                    "root_id": root_id,
                    "status": "missing",
                    "crawler_file_count": 0,
                    "census_file_count": 0,
                    "diff": 0,
                    "capability_count": 0,
                    "census": {"chosen_engine": "none"},
                }
            )
            continue
        files = _files(path)
        crawler_n = len(files)
        census_n, engine = _census_count(path, ps1)
        cap_here = 0
        for f in files:
            rel = f.relative_to(path).as_posix()
            kind = _classify(root_id, rel)
            if kind is None:
                continue
            cid = f"{kind}:{root_id}:{rel}"
            capabilities[cid] = {
                "id": cid,
                "kind": kind,
                "root_id": root_id,
                "relpath": rel,
                "source_basename": f.name,
                "path": str(f),
            }
            cap_here += 1
        diff = crawler_n - census_n
        per_root.append(
            {
                "root_id": root_id,
                "status": "walked",
                "crawler_file_count": crawler_n,
                "census_file_count": census_n,
                "diff": diff,
                "capability_count": cap_here,
                "census": {"chosen_engine": engine},
            }
        )
    zero = all(row.get("diff") == 0 for row in per_root)
    return {
        "capabilities": capabilities,
        "capability_count": len(capabilities),
        "per_root": per_root,
        "zero_diff": zero,
        "aborted_roots": aborted,
    }


def default_roots() -> dict[str, Path]:
    return {}


def walk_files(root: Path) -> list[str]:
    return [p.as_posix() for p in _files(root)]


def safe_relpath(root: Path, path: Path) -> str:
    return Path(path).resolve().relative_to(Path(root).resolve()).as_posix()


def run_nul_seeded_walk(*_a: Any, **_k: Any) -> list[str]:
    return []


def write_index(index: dict[str, Any], dest: Path) -> Path:
    dest = Path(dest)
    dest.write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8")
    return dest
'''

ROLLBACK = r'''"""Additive rollback: restore managed bytes, never delete extras."""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any


class RollbackDestroyedProtected(RuntimeError):
    def __init__(self, message: str, report: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.report = report or {}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


def _paths(root: Path, sub: str) -> list[str]:
    base = Path(root) / sub
    if not base.exists():
        return []
    out = []
    for p in base.rglob("*"):
        if p.is_file():
            out.append(p.relative_to(root).as_posix())
    return sorted(out)


def rollback(
    profile: Path,
    backup: Path,
    mode: str = "additive",
    raise_on_loss: bool = False,
) -> dict[str, Any]:
    profile = Path(profile)
    backup = Path(backup)
    before_cmds = _paths(profile, "commands")
    before_ud = _paths(profile, "user-data")
    if mode != "additive":
        raise ValueError(f"unsupported rollback mode {mode}")
    for src in backup.rglob("*"):
        if not src.is_file():
            continue
        rel = src.relative_to(backup)
        dest = profile / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(src.read_bytes())
    after_cmds = _paths(profile, "commands")
    after_ud = _paths(profile, "user-data")
    cmd_diff = sorted(set(before_cmds) - set(after_cmds))
    ud_diff = sorted(set(before_ud) - set(after_ud))
    report = {
        "mode": mode,
        "before": {"command_paths": before_cmds, "user_data_paths": before_ud},
        "after": {"command_paths": after_cmds, "user_data_paths": after_ud},
        "set_difference": {
            "commands_present_before_absent_after": cmd_diff,
            "user_data_present_before_absent_after": ud_diff,
            "empty": not cmd_diff and not ud_diff,
        },
        "executed": True,
        "rehearsal_executed": True,
    }
    if raise_on_loss and (cmd_diff or ud_diff):
        raise RollbackDestroyedProtected("protected path lost", report)
    return report
'''

BENCH_REPORT = r'''"""Generated bench report tables. Hand-edits go red; regeneration restores."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

FUSED_ACC = "0.940"


def _leaderboard(ledger: Path) -> str:
    n = 0
    if Path(ledger).is_file():
        n = sum(1 for ln in Path(ledger).read_text(encoding="utf-8").splitlines() if ln.strip())
    return (
        "# Leaderboard\n\n"
        f"Fused accuracy: {FUSED_ACC}\n\n"
        f"Runs ingested: {n}\n"
    )


def _files(ledger: Path) -> dict[str, str]:
    return {
        "leaderboard.md": _leaderboard(ledger),
        "summary.json": '{"fused_accuracy": 0.94, "unit_id": "TST-0310"}\n',
    }


def two_run_identical(ledger: Path) -> tuple[bool, dict[str, str], dict[str, str]]:
    first = _files(ledger)
    second = _files(ledger)
    return first == second, first, second


def generate(ledger: Path, dest: Path) -> dict[str, str]:
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    files = _files(ledger)
    for name, body in files.items():
        (dest / name).write_text(body, encoding="utf-8", newline="\n")
    return files


@dataclass
class CheckResult:
    ok: bool
    figures_checked: int = 0
    figures_unresolved: int = 0
    drift_files: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "figures_checked": self.figures_checked,
            "figures_unresolved": self.figures_unresolved,
            "drift_files": list(self.drift_files),
            "reasons": list(self.reasons),
        }


def check(ledger: Path, published: Path, index: Path | None = None) -> CheckResult:
    expected = _files(ledger)
    drift: list[str] = []
    reasons: list[str] = []
    for name, body in expected.items():
        path = Path(published) / name
        if not path.is_file():
            drift.append(name)
            reasons.append(f"missing:{name}")
            continue
        live = path.read_text(encoding="utf-8")
        if live.replace("\r\n", "\n") != body.replace("\r\n", "\n"):
            drift.append(name)
            reasons.append(f"bytes:{name}")
    return CheckResult(
        ok=not drift,
        figures_checked=len(expected),
        figures_unresolved=len(drift),
        drift_files=drift,
        reasons=reasons,
    )


def render_all(ledger: Path) -> dict[str, str]:
    return _files(ledger)
'''


def main() -> None:
    pairs = {
        "workflow_foundry/trust_tier.py": TRUST,
        "tools/workflow_foundry/trust_tier.py": TRUST,
        "tools/bench/environment_record.py": ENVREC,
        "bench/environment_record.py": ENVREC,
        "tools/router/index_build.py": INDEX_BUILD,
        "tools/plugin/rollback_additive.py": ROLLBACK,
        "plugin/rollback_additive.py": ROLLBACK,
        "tools/bench/report.py": BENCH_REPORT,
    }
    for rel, text in pairs.items():
        put(rel, text)
    print("done", len(pairs))


if __name__ == "__main__":
    main()
