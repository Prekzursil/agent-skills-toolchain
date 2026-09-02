#!/usr/bin/env python3
"""Isolated-HOME canary for REL-0006: fetch gate, behaviour probe, typed inverses.

Does not mutate the owner's live profile. Hook subprocesses receive HOME set to
the isolated prefix; the parent process keeps its original HOME.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
FIX = HERE / "fixtures"
INVERSES_PATH = FIX / "inverses.json"
RUNBOOK_PATH = FIX / "RUNBOOK-FRAGMENT.md"

N1_VERSION = "1.0.0-n-1"
N_VERSION = "2.0.0-n"
N1_BEHAVIOR = "BEHAVIOR:n-1-accept"
N_BEHAVIOR = "BEHAVIOR:n-candidate"
ZIP_DATE = (2026, 8, 1, 0, 0, 0)

INSTALLER_PATHS = (
    "plugin/VERSION",
    "plugin/plugin.json",
    "plugin/hooks/on_session.py",
    "plugin/payload/behaviour.txt",
)

OWNER_FILES = {
    "plugin/owner-authored/skill.md": (
        "# Owner skill\nDo not delete me during downgrade.\n"
    ),
    "plugin/owner-authored/settings.json": (
        '{"theme":"owner-dark","keys":["custom"]}\n'
    ),
    "plugin/owner-authored/edited-rule.md": (
        "# Edited rule\nowner-hand-edit: keep\n"
    ),
    "plugin/owner-authored/in-flight-ledger.json": (
        '{"entries":[{"id":"e1","status":"open"}]}\n'
    ),
}


class IsolationError(RuntimeError):
    pass


class RetrievabilityBlocked(RuntimeError):
    def __init__(self, fetched: str, expected: str, path: str) -> None:
        super().__init__(
            f"retrievability-blocked fetched={fetched} expected={expected} path={path}"
        )
        self.fetched = fetched
        self.expected = expected
        self.path = path


class InverseContractError(RuntimeError):
    pass


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def owner_home() -> Path:
    return Path(os.environ.get("HOME") or str(Path.home())).resolve()


def assert_isolated(isolated: Path, real_home: Path) -> None:
    iso = isolated.resolve()
    real = real_home.resolve()
    if iso == real:
        raise IsolationError(f"isolated HOME resolved to owner profile: {iso}")
    try:
        iso.relative_to(real)
        raise IsolationError(f"isolated HOME is inside owner profile: {iso} under {real}")
    except ValueError:
        pass
    marker = iso / ".rel0006-canary-marker"
    if not marker.is_file():
        raise IsolationError("isolation marker missing")


def make_isolated(real_home: Path) -> Path:
    tmp = Path(tempfile.mkdtemp(prefix="rel0006-canary-"))
    (tmp / ".rel0006-canary-marker").write_text("isolated-canary\n", encoding="utf-8")
    (tmp / ".lifecycle").mkdir(parents=True, exist_ok=True)
    assert_isolated(tmp, real_home)
    return tmp


def hook_source(token: str) -> str:
    return (
        "from pathlib import Path\n"
        "p = Path(__file__).resolve().parent.parent / 'side_effects'\n"
        "p.mkdir(parents=True, exist_ok=True)\n"
        f"(p / 'hook-fired.txt').write_text({token!r} + '\\n', encoding='utf-8')\n"
    )


def payload_tree(version: str, behavior: str) -> dict[str, bytes]:
    plugin = {
        "id": "rel0006-canary",
        "version": version,
        "hooks": ["on_session"],
    }
    return {
        "VERSION": (version + "\n").encode("utf-8"),
        "plugin.json": (json.dumps(plugin, indent=2) + "\n").encode("utf-8"),
        "hooks/on_session.py": hook_source(behavior).encode("utf-8"),
        "payload/behaviour.txt": (behavior + "\n").encode("utf-8"),
    }


def pack_zip(files: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_STORED) as zf:
        for name in sorted(files):
            info = zipfile.ZipInfo(name, date_time=ZIP_DATE)
            info.compress_type = zipfile.ZIP_STORED
            zf.writestr(info, files[name])
    return buf.getvalue()


def load_inverses() -> dict[str, Any]:
    doc = json.loads(INVERSES_PATH.read_text(encoding="utf-8"))
    validate_inverses(doc)
    return doc


def validate_inverses(doc: dict[str, Any]) -> None:
    actions = doc.get("actions") or []
    if not isinstance(actions, list) or not actions:
        raise InverseContractError("inverses.actions missing")
    for act in actions:
        if not isinstance(act, dict):
            raise InverseContractError("action is not an object")
        inv = act.get("inverse")
        if not isinstance(inv, dict):
            raise InverseContractError(f"{act.get('id')}: missing inverse")
        created_by = bool(act.get("created_by_installer"))
        if inv.get("type") in {"delete_path", "rm", "unlink"}:
            if not created_by:
                raise InverseContractError(
                    f"{act.get('id')}: inverse deletes a path the installer did not create"
                )
        if (not created_by) and not inv.get("must_not_delete"):
            raise InverseContractError(
                f"{act.get('id')}: owner/preexisting path must declare must_not_delete"
            )
        if inv.get("total") is not True and not inv.get("residue"):
            raise InverseContractError(
                f"{act.get('id')}: partial inverse omitted residue"
            )


def parse_runbook_slo(path: Path = RUNBOOK_PATH) -> float:
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip().strip("`")
        if stripped.startswith("MTTR_SLO_SECONDS="):
            return float(stripped.split("=", 1)[1])
    raise RuntimeError("RUNBOOK fragment missing MTTR_SLO_SECONDS")


def build_release_store(store: Path) -> dict[str, Any]:
    store.mkdir(parents=True, exist_ok=True)
    n1 = pack_zip(payload_tree(N1_VERSION, N1_BEHAVIOR))
    n = pack_zip(payload_tree(N_VERSION, N_BEHAVIOR))
    n1_path = store / "n-1.zip"
    n_path = store / "n.zip"
    n1_path.write_bytes(n1)
    n_path.write_bytes(n)
    n1_sha = sha256_bytes(n1)
    n_sha = sha256_bytes(n)
    manifest = (
        "# ROLLBACK-MANIFEST (REL-0006 rehearsal fixture)\n"
        "# A plan that assumes an artifact nobody can fetch is not a plan.\n\n"
        f"| artifact | version | sha256 | bytes |\n"
        f"| n-1.zip | {N1_VERSION} | {n1_sha} | {len(n1)} |\n"
        f"| n.zip | {N_VERSION} | {n_sha} | {len(n)} |\n"
    )
    man_path = store / "ROLLBACK-MANIFEST.md"
    man_path.write_text(manifest, encoding="utf-8")
    return {
        "store": str(store),
        "n1_path": str(n1_path),
        "n_path": str(n_path),
        "n1_sha256": n1_sha,
        "n_sha256": n_sha,
        "n1_bytes": len(n1),
        "n_bytes": len(n),
        "manifest_path": str(man_path),
        "manifest_sha256": sha256_file(man_path),
        "manifest_text": manifest,
    }


def parse_manifest_n1_sha(manifest_text: str) -> str:
    for line in manifest_text.splitlines():
        if "| n-1.zip |" in line:
            parts = [p.strip() for p in line.strip("|").split("|")]
            if len(parts) >= 3 and len(parts[2]) == 64:
                return parts[2]
    raise RuntimeError("ROLLBACK-MANIFEST has no n-1.zip sha256")


def fetch_n1(store_meta: dict[str, Any]) -> dict[str, Any]:
    path = Path(store_meta["n1_path"])
    raw = path.read_bytes()
    fetched = sha256_bytes(raw)
    expected = parse_manifest_n1_sha(
        Path(store_meta["manifest_path"]).read_text(encoding="utf-8")
    )
    if fetched != expected:
        raise RetrievabilityBlocked(fetched, expected, str(path))
    return {
        "path": str(path),
        "fetched_sha256": fetched,
        "manifest_sha256": expected,
        "match": True,
        "bytes": len(raw),
        "raw": raw,
    }


def corrupt_n1(store_meta: dict[str, Any]) -> None:
    path = Path(store_meta["n1_path"])
    raw = bytearray(path.read_bytes())
    if not raw:
        raise RuntimeError("empty n-1 artifact")
    raw[0] = raw[0] ^ 0xFF
    path.write_bytes(bytes(raw))


def extract_zip(raw: bytes) -> dict[str, bytes]:
    out: dict[str, bytes] = {}
    with zipfile.ZipFile(io.BytesIO(raw), "r") as zf:
        for name in zf.namelist():
            out[name] = zf.read(name)
    return out


def seed_owner_files(home: Path) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for rel, text in OWNER_FILES.items():
        dest = home / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(text, encoding="utf-8")
        hashes[rel] = sha256_file(dest)
    return hashes


def hash_owner_files(home: Path) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for rel in OWNER_FILES:
        dest = home / rel
        if not dest.is_file():
            hashes[rel] = "MISSING"
        else:
            hashes[rel] = sha256_file(dest)
    return hashes


def install_payload(home: Path, raw: bytes) -> None:
    files = extract_zip(raw)
    for name, blob in files.items():
        dest = home / "plugin" / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(blob)
    journal = home / ".lifecycle"
    journal.mkdir(parents=True, exist_ok=True)
    (journal / "last-install.json").write_text(
        json.dumps({"installer_paths": list(INSTALLER_PATHS)}, indent=2) + "\n",
        encoding="utf-8",
    )


def write_journal(home: Path, **fields: Any) -> None:
    journal = home / ".lifecycle"
    journal.mkdir(parents=True, exist_ok=True)
    path = journal / "journal.json"
    doc: dict[str, Any] = {}
    if path.is_file():
        doc = json.loads(path.read_text(encoding="utf-8"))
    doc.update(fields)
    path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")


def read_journal(home: Path) -> dict[str, Any]:
    path = home / ".lifecycle" / "journal.json"
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def read_version(home: Path) -> str:
    path = home / "plugin" / "VERSION"
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8").strip()


def run_n1_acceptance(home: Path, real_home: Path) -> dict[str, Any]:
    assert_isolated(home, real_home)
    hook = home / "plugin" / "hooks" / "on_session.py"
    env = os.environ.copy()
    env["HOME"] = str(home)
    cmd = [sys.executable, "-B", str(hook)]
    proc = subprocess.run(
        cmd,
        cwd=str(home / "plugin"),
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    fired = home / "plugin" / "side_effects" / "hook-fired.txt"
    output = fired.read_text(encoding="utf-8").strip() if fired.is_file() else ""
    passed = proc.returncode == 0 and output == N1_BEHAVIOR
    return {
        "passed": passed,
        "returncode": proc.returncode,
        "output": output,
        "stdout": (proc.stdout or "").strip(),
        "stderr": (proc.stderr or "").strip(),
        "command": " ".join(cmd),
        "hook": str(hook),
        "expected": N1_BEHAVIOR,
        "version_string": read_version(home),
    }


def apply_downgrade(home: Path, n1_raw: bytes, inverses: dict[str, Any]) -> dict[str, Any]:
    """Restore installer-created paths from the fetched N-1 payload only."""
    validate_inverses(inverses)
    files = extract_zip(n1_raw)
    restored: list[str] = []
    skipped_owner: list[str] = []
    for act in inverses["actions"]:
        rel = str(act["target"])
        if not act.get("created_by_installer"):
            skipped_owner.append(rel)
            continue
        inv = act["inverse"]
        if inv.get("type") != "restore_preimage":
            raise InverseContractError(
                f"{act['id']}: unsupported inverse {inv.get('type')}"
            )
        zip_name = rel[len("plugin/") :] if rel.startswith("plugin/") else rel
        if zip_name not in files:
            raise InverseContractError(f"{act['id']}: N-1 payload missing {zip_name}")
        dest = home / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(files[zip_name])
        restored.append(rel)
    write_journal(
        home,
        downgrade_started=True,
        downgrade_completed=True,
        restored=restored,
    )
    return {"restored": restored, "skipped_owner": skipped_owner}


def refuse_owner_delete(inverses: dict[str, Any]) -> dict[str, Any]:
    mutant = json.loads(json.dumps(inverses))
    for act in mutant["actions"]:
        if act.get("id") == "owner-skill":
            act["inverse"] = {"type": "delete_path", "total": True}
            break
    try:
        validate_inverses(mutant)
        return {"refused": False, "error": ""}
    except InverseContractError as exc:
        return {"refused": True, "error": str(exc)}


def snapshot_plugin(home: Path, dest: Path) -> None:
    if dest.exists():
        shutil.rmtree(dest)
    src = home / "plugin"
    dest.parent.mkdir(parents=True, exist_ok=True)
    if src.is_dir():
        shutil.copytree(src, dest)


def restore_snapshot(home: Path, snap: Path) -> None:
    plugin = home / "plugin"
    if plugin.exists():
        shutil.rmtree(plugin)
    shutil.copytree(snap, plugin)


def mttr_within_slo(measured_s: float, slo_s: float) -> bool:
    return measured_s <= slo_s


def compare_mttr_control(measured_s: float, slo_s: float) -> dict[str, Any]:
    """Both-states: real SLO accepts; a tiny SLO must reject the same measurement."""
    real_ok = mttr_within_slo(measured_s, slo_s)
    tiny = 1e-12
    tiny_ok = mttr_within_slo(measured_s, tiny)
    return {
        "measured_s": measured_s,
        "slo_s": slo_s,
        "real_slo_accepts": real_ok,
        "tiny_slo_accepts": tiny_ok,
        "tiny_slo_s": tiny,
        "pass": real_ok and (not tiny_ok),
    }


def isolation_check_fires_on_real_home(real_home: Path) -> dict[str, Any]:
    """Negative control: pointing the isolator at the owner HOME must fail.

    Does not create or delete files under the owner profile.
    """
    try:
        assert_isolated(real_home, real_home)
        fired = False
        error = ""
    except IsolationError as exc:
        fired = True
        error = str(exc)
    return {"fired": fired, "touched_owner_profile": False, "error": error}
