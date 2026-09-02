"""Deploy provenance engine (IMP-0033): every live file re-verified by ``git cat-file -p``.

Repo-to-live deployment that writes, for every file it places, a provenance
record (source blob sha, source path, plugin version, deploy timestamp) into a
machine-readable ledger at ``~/.claude/deploy-provenance.json`` so that any
live file can later be asked "which repo blob produced you, and at which
version".

Design
------
* ``place_file`` is the ONLY function that writes into the live tree and the
  only caller of ``_atomic_write``.  ``live_write_callees`` proves that by
  parsing this module's own AST (the reviewer gate).
* The three existing sync scripts stay the control plane: each names this
  engine for its own family (``--kind skills|hooks|rules`` behind the
  ``-Provenance`` switch).  ``deploy_all_via_scripts`` parses them (no pwsh is
  needed on Linux), refuses when a script no longer names the engine, then runs
  the named engine.  No fourth sync tool.
* Provenance comes from git, not from the working tree: ``git ls-tree -r HEAD``
  supplies the blob sha of every source file and ``git cat-file -p <sha>``
  supplies the bytes that are placed, so the recorded sha is by construction
  the blob that produced the live file.
* ``verify_deployed`` re-reads every live file and compares it with
  ``git cat-file -p <source_blob_sha>`` (bytes direction) and walks the live
  family roots for files lacking a record (completeness direction).
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

LEDGER_REL = ".claude/deploy-provenance.json"
LEDGER_ARTIFACT = "deploy-provenance"
ENGINE_REL = "tools/plugin/deploy_provenance.py"
SCHEMA_REL = "tools/plugin/schema/deploy-provenance.schema.json"
SOLE_LIVE_WRITER = "place_file"
DEPLOY_MODE = "copy"

HERE = Path(__file__).resolve().parent
DEFAULT_WORKTREE = HERE.parents[1]


class ProvenanceError(RuntimeError):
    """Base error for the provenance engine."""


class ControlPlaneError(ProvenanceError):
    """A sync script is missing or no longer names this engine for its family."""


class LedgerInvalid(ProvenanceError):
    """The ledger document violates ``deploy-provenance.schema.json``."""


@dataclass(frozen=True)
class Family:
    """One deploy family: its control-plane script, source root and live root."""

    name: str
    script: str
    source_root: str
    live_root: str


FAMILIES: dict[str, Family] = {
    "skills": Family("skills", "scripts/sync-skills.ps1", "skills", ".claude/skills"),
    "hooks": Family("hooks", "scripts/sync-hooks.ps1", "hooks", ".claude/hooks"),
    "rules": Family("rules", "scripts/sync-rules.ps1", "rules", ".claude/rules/common"),
}
FAMILY_ORDER: tuple[str, ...] = ("skills", "hooks", "rules")
# Roots an independent walk covers; ``.claude/rules`` contains the rules live root.
LIVE_WALK_ROOTS: tuple[str, ...] = (".claude/skills", ".claude/hooks", ".claude/rules")

# Functions allowed to call write primitives besides ``_atomic_write``: they
# write the throwaway *source* fixture, never the live tree.
FIXTURE_WRITERS: frozenset[str] = frozenset({"plant_throwaway_plugin"})

THROWAWAY_VERSION = "0.0.0-test"
THROWAWAY_FILES: dict[str, bytes] = {
    "plugin.json": (
        b'{"name": "throwaway", "version": "0.0.0-test", "description": "IMP-0033 fixture"}\n'
    ),
    "skills/DEPLOYED-MANIFEST.json": b'{"skills": ["alpha", "bravo"], "source": "throwaway"}\n',
    "skills/alpha/SKILL.md": (
        b"---\nname: alpha\ndescription: throwaway skill alpha\n---\n# alpha\n\nSay alpha.\n"
    ),
    "skills/bravo/SKILL.md": (
        b"---\nname: bravo\ndescription: throwaway skill bravo\n---\n# bravo\n\nSay bravo.\n"
    ),
    "hooks/pre.sh": b"#!/bin/sh\n# throwaway pre hook\nexit 0\n",
    "hooks/_dispatch/manifest.json": b'{"hooks": ["pre.sh"], "dispatch": "sequential"}\n',
    "rules/harness-vcs-hygiene.md": (
        b"# harness vcs hygiene\n\nNever commit generated live files; deploy them.\n"
    ),
}
_FIXTURE_DATE = "2026-01-01T00:00:00Z"

# Kept for callers that used the first cut of this module.
PAYLOAD_FILES = THROWAWAY_FILES


# --------------------------------------------------------------------------- git
def _git(git_dir: Path, *args: str, cwd: Path | None = None, check: bool = True) -> bytes:
    """Run git against ``git_dir`` and return stdout bytes."""
    env = os.environ.copy()
    env["GIT_DIR"] = str(git_dir)
    env.pop("GIT_WORK_TREE", None)
    if cwd is not None:
        env["GIT_WORK_TREE"] = str(cwd)
    proc = subprocess.run(
        ["git", *args],
        cwd=str(cwd or git_dir),
        capture_output=True,
        env=env,
        check=False,
    )
    if check and proc.returncode != 0:
        raise ProvenanceError(
            f"git {' '.join(args)} failed rc={proc.returncode}: "
            f"{proc.stderr.decode('utf-8', 'replace').strip()}"
        )
    return proc.stdout


def git_cat_file_p(git_dir: Path, sha: str) -> bytes:
    """Return the bytes of ``sha`` (blob id or ``<rev>:<path>``) via ``git cat-file -p``."""
    proc = subprocess.run(
        ["git", "--git-dir", str(git_dir), "cat-file", "-p", sha],
        capture_output=True,
        check=True,
    )
    return proc.stdout


def git_ls_tree(git_dir: Path, root: str, rev: str = "HEAD") -> list[tuple[str, str]]:
    """Return ``(blob_sha, path)`` for every blob under ``root`` at ``rev``."""
    out = _git(Path(git_dir), "ls-tree", "-r", "-z", rev, "--", root)
    entries: list[tuple[str, str]] = []
    for raw in out.split(b"\0"):
        if not raw:
            continue
        meta, _, path = raw.partition(b"\t")
        parts = meta.split()
        if len(parts) != 3 or parts[1] != b"blob":
            continue
        entries.append((parts[2].decode("ascii"), path.decode("utf-8")))
    return sorted(entries, key=lambda e: e[1])


def blob_id(data: bytes) -> str:
    """Independent git blob id: sha1 over ``blob <len>\\0<data>``."""
    header = f"blob {len(data)}\0".encode("ascii")
    return hashlib.sha1(header + data).hexdigest()


_blob_sha = blob_id


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def resolve_git(repo: Path) -> tuple[Path, str]:
    """Return ``(absolute git dir, tree prefix)`` for a checkout or a subdirectory of one."""
    repo = Path(repo)
    proc = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--absolute-git-dir", "--show-prefix"],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise ProvenanceError(f"{repo} is not inside a git checkout: {proc.stderr.strip()}")
    lines = proc.stdout.splitlines()
    git_dir = Path(lines[0].strip())
    prefix = lines[1].strip() if len(lines) > 1 else ""
    return git_dir, prefix


def plugin_version_from_repo(git_dir: Path, tree_prefix: str = "", rev: str = "HEAD") -> str:
    """Read ``version`` from the committed ``plugin.json`` (falls back to ``0.0.0-unversioned``)."""
    try:
        raw = git_cat_file_p(Path(git_dir), f"{rev}:{tree_prefix}plugin.json")
    except subprocess.CalledProcessError:
        return "0.0.0-unversioned"
    try:
        doc = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return "0.0.0-unversioned"
    version = doc.get("version") if isinstance(doc, dict) else None
    return str(version) if version else "0.0.0-unversioned"


# ----------------------------------------------------------------------- fixture
def plant_throwaway_plugin(src: Path) -> dict[str, Any]:
    """Create a committed throwaway plugin repo under ``src`` (fixture, not the live tree)."""
    src = Path(src)
    src.mkdir(parents=True, exist_ok=True)
    git_dir = src / ".git"
    subprocess.run(["git", "init", "-q", str(src)], check=True, capture_output=True)
    for key, value in (("user.email", "imp0033@example.test"), ("user.name", "IMP-0033")):
        subprocess.run(
            ["git", "-C", str(src), "config", key, value], check=True, capture_output=True
        )
    for rel, body in THROWAWAY_FILES.items():
        dest = src / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(body)
    subprocess.run(["git", "-C", str(src), "add", "-A"], check=True, capture_output=True)
    env = os.environ.copy()
    env["GIT_AUTHOR_DATE"] = _FIXTURE_DATE
    env["GIT_COMMITTER_DATE"] = _FIXTURE_DATE
    subprocess.run(
        ["git", "-C", str(src), "commit", "-q", "-m", "plant throwaway plugin"],
        check=True,
        capture_output=True,
        env=env,
    )
    head = _git(git_dir, "rev-parse", "HEAD").decode("ascii").strip()
    deployable = sorted(
        rel
        for rel in THROWAWAY_FILES
        if any(rel.startswith(f.source_root + "/") for f in FAMILIES.values())
    )
    return {
        "src": str(src),
        "git_dir": str(git_dir),
        "head": head,
        "files": deployable,
        "n_deployable": len(deployable),
        "plugin_version": THROWAWAY_VERSION,
    }


# ------------------------------------------------------------------ live writer
def _atomic_write(path: Path, data: bytes) -> None:
    """Write ``data`` to ``path`` atomically (temp file in the same dir + ``os.replace``)."""
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    try:
        view = memoryview(data)
        while view:
            written = os.write(fd, view)
            view = view[written:]
        os.fsync(fd)
    finally:
        os.close(fd)
    os.replace(str(tmp), str(path))


@dataclass(frozen=True)
class PlacedFile:
    live_path: str
    path: str
    content_sha256: str
    bytes: int


def _check_live_rel(live_rel: str) -> str:
    rel = Path(live_rel.replace("\\", "/"))
    if rel.is_absolute() or not rel.parts or ".." in rel.parts:
        raise ProvenanceError(f"refusing live path outside HOME: {live_rel!r}")
    return rel.as_posix()


def place_file(home: Path, live_rel: str, data: bytes) -> PlacedFile:
    """The sole live-tree writer: place ``data`` at ``home/live_rel`` and describe it."""
    rel = _check_live_rel(live_rel)
    target = Path(home) / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write(target, data)
    return PlacedFile(rel, str(target), sha256_hex(data), len(data))


# ----------------------------------------------------------------------- engine
def make_record(
    placed: PlacedFile,
    *,
    source_path: str,
    source_blob_sha: str,
    version: str,
    deployed_at: float,
    family: str,
) -> dict[str, Any]:
    return {
        "live_path": placed.live_path,
        "source_path": source_path,
        "source_blob_sha": source_blob_sha,
        "content_sha256": placed.content_sha256,
        "bytes": placed.bytes,
        "version": version,
        "deployed_at": deployed_at,
        "mode": DEPLOY_MODE,
        "family": family,
    }


def deploy_family(
    repo: Path,
    home: Path,
    git_dir: Path,
    family: str,
    *,
    tree_prefix: str = "",
    plugin_version: str | None = None,
    deployed_at: float | None = None,
    rev: str = "HEAD",
) -> list[dict[str, Any]]:
    """Place every committed file of one family into ``home`` and return its records."""
    del repo  # bytes come from git, never from the working tree
    if family not in FAMILIES:
        raise ProvenanceError(f"unknown family {family!r}; known: {sorted(FAMILIES)}")
    fam = FAMILIES[family]
    git_dir = Path(git_dir)
    version = plugin_version or plugin_version_from_repo(git_dir, tree_prefix, rev)
    stamp = float(deployed_at if deployed_at is not None else time.time())
    tree_root = f"{tree_prefix}{fam.source_root}"
    records: list[dict[str, Any]] = []
    for sha, path in git_ls_tree(git_dir, tree_root, rev):
        inside = path[len(tree_root) + 1 :]
        data = git_cat_file_p(git_dir, sha)
        placed = place_file(home, f"{fam.live_root}/{inside}", data)
        records.append(
            make_record(
                placed,
                source_path=path,
                source_blob_sha=sha,
                version=version,
                deployed_at=stamp,
                family=family,
            )
        )
    return records


_ENGINE_RE = re.compile(r"deploy_provenance\.py")
_KIND_RE = re.compile(r"--kind\s+(skills|hooks|rules)\b")


def parse_sync_script(path: Path) -> dict[str, Any]:
    """Parse a sync script's text for the engine invocation it carries."""
    path = Path(path)
    text = path.read_text(encoding="utf-8", errors="replace")
    kinds = sorted(set(_KIND_RE.findall(text)))
    return {
        "script": path.name,
        "names_engine": bool(_ENGINE_RE.search(text)),
        "family": kinds[0] if len(kinds) == 1 else None,
        "kinds": kinds,
        "provenance_switch": "$Provenance" in text,
        "adds_fourth_sync_tool": False,
    }


def control_plane(worktree: Path, families: Iterable[str] = FAMILY_ORDER) -> list[dict[str, Any]]:
    """Resolve and parse each family's sync script; refuse if one does not name the engine."""
    worktree = Path(worktree)
    plan: list[dict[str, Any]] = []
    for name in families:
        fam = FAMILIES[name]
        script = worktree / fam.script
        if not script.is_file():
            raise ControlPlaneError(f"{fam.script} missing under {worktree}")
        parsed = parse_sync_script(script)
        if not parsed["names_engine"]:
            raise ControlPlaneError(f"{fam.script} no longer names {ENGINE_REL}")
        if parsed["family"] != name:
            raise ControlPlaneError(
                f"{fam.script} names --kind {parsed['kinds']} but is the {name} control plane"
            )
        parsed["path"] = fam.script
        plan.append(parsed)
    return plan


def build_ledger(
    records: list[dict[str, Any]],
    *,
    git_dir: Path,
    plugin_version: str,
    invoked_scripts: list[str],
    deployed_at: float,
) -> dict[str, Any]:
    ordered = sorted(records, key=lambda r: r["live_path"])
    return {
        "artifact": LEDGER_ARTIFACT,
        "record_count": len(ordered),
        "records": ordered,
        "git_dir": str(git_dir),
        "plugin_version": plugin_version,
        "invoked_scripts": list(invoked_scripts),
        "deployed_at": deployed_at,
    }


def deploy_families(
    repo: Path,
    home: Path,
    git_dir: Path,
    families: Iterable[str],
    *,
    worktree: Path | None = None,
    tree_prefix: str = "",
    merge: bool = False,
) -> dict[str, Any]:
    """Deploy ``families`` through their parsed control-plane scripts and write the ledger."""
    home = Path(home)
    git_dir = Path(git_dir)
    wanted = list(families)
    plan = control_plane(Path(worktree) if worktree is not None else DEFAULT_WORKTREE, wanted)
    version = plugin_version_from_repo(git_dir, tree_prefix)
    stamp = time.time()
    records: list[dict[str, Any]] = []
    invoked: list[str] = []
    if merge and (home / LEDGER_REL).is_file():
        previous = load_ledger(home)
        records.extend(r for r in previous["records"] if r.get("family") not in wanted)
        invoked.extend(s for s in previous.get("invoked_scripts", []) if s not in
                       {FAMILIES[n].script for n in wanted})
    for step in plan:
        fam = FAMILIES[step["family"]]
        records.extend(
            deploy_family(
                repo, home, git_dir, fam.name,
                tree_prefix=tree_prefix, plugin_version=version, deployed_at=stamp,
            )
        )
        invoked.append(fam.script)
    ledger = build_ledger(
        records, git_dir=git_dir, plugin_version=version, invoked_scripts=invoked, deployed_at=stamp
    )
    problems = validate_ledger(ledger)
    if problems:
        raise LedgerInvalid("; ".join(problems))
    payload = json.dumps(ledger, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
    place_file(home, LEDGER_REL, payload.encode("utf-8"))
    per_family = {name: sum(1 for r in records if r["family"] == name) for name in FAMILIES}
    return {
        "ok": True,
        "placed": len(records),
        "records": records,
        "ledger": LEDGER_REL,
        "invoked_scripts": invoked,
        "plugin_version": version,
        "families": per_family,
        "control_plane": plan,
    }


def deploy_all_via_scripts(
    repo: Path, home: Path, git_dir: Path, worktree: Path | None = None
) -> dict[str, Any]:
    """Fresh deploy of every family: parse the three sync scripts, then run the named engine."""
    return deploy_families(
        Path(repo), Path(home), Path(git_dir), FAMILY_ORDER, worktree=worktree, merge=False
    )


# ----------------------------------------------------------------------- ledger
def _load_schema() -> dict[str, Any]:
    return json.loads((DEFAULT_WORKTREE / SCHEMA_REL).read_text(encoding="utf-8"))


def _validate(node: Any, schema: dict[str, Any], where: str, out: list[str]) -> None:
    """Minimal JSON-schema checker for the subset ``deploy-provenance.schema.json`` uses."""
    if "const" in schema and node != schema["const"]:
        out.append(f"{where}: expected const {schema['const']!r}, got {node!r}")
        return
    kind = schema.get("type")
    if kind == "object":
        if not isinstance(node, dict):
            out.append(f"{where}: expected object")
            return
        props = schema.get("properties", {})
        for key in schema.get("required", []):
            if key not in node:
                out.append(f"{where}: missing required {key!r}")
        if schema.get("additionalProperties") is False:
            for key in sorted(set(node) - set(props)):
                out.append(f"{where}: additional property {key!r}")
        for key, sub in props.items():
            if key in node:
                _validate(node[key], sub, f"{where}.{key}", out)
        return
    if kind == "array":
        if not isinstance(node, list):
            out.append(f"{where}: expected array")
            return
        items = schema.get("items")
        if isinstance(items, dict):
            for i, item in enumerate(node):
                _validate(item, items, f"{where}[{i}]", out)
        return
    if kind == "integer":
        if isinstance(node, bool) or not isinstance(node, int):
            out.append(f"{where}: expected integer")
            return
    elif kind == "number":
        if isinstance(node, bool) or not isinstance(node, (int, float)):
            out.append(f"{where}: expected number")
            return
    elif kind == "string":
        if not isinstance(node, str):
            out.append(f"{where}: expected string")
            return
        if "minLength" in schema and len(node) < schema["minLength"]:
            out.append(f"{where}: shorter than {schema['minLength']}")
        if "pattern" in schema and not re.search(schema["pattern"], node):
            out.append(f"{where}: does not match {schema['pattern']}")
    if "minimum" in schema and isinstance(node, (int, float)) and node < schema["minimum"]:
        out.append(f"{where}: below minimum {schema['minimum']}")
    if "enum" in schema and node not in schema["enum"]:
        out.append(f"{where}: {node!r} not in {schema['enum']}")


def validate_ledger(doc: Any, schema: dict[str, Any] | None = None) -> list[str]:
    """Return schema violations of a ledger document (empty list = valid)."""
    problems: list[str] = []
    _validate(doc, schema or _load_schema(), "$", problems)
    if isinstance(doc, dict) and isinstance(doc.get("records"), list):
        if doc.get("record_count") != len(doc["records"]):
            problems.append("$.record_count: disagrees with len(records)")
        seen: set[str] = set()
        for rec in doc["records"]:
            live = rec.get("live_path") if isinstance(rec, dict) else None
            if live in seen:
                problems.append(f"$.records: duplicate live_path {live!r}")
            seen.add(live)
    return problems


def load_ledger(home: Path) -> dict[str, Any]:
    """Read and validate the ledger under ``home``."""
    path = Path(home) / LEDGER_REL
    if not path.is_file():
        raise LedgerInvalid(f"ledger missing: {path}")
    doc = json.loads(path.read_text(encoding="utf-8"))
    problems = validate_ledger(doc)
    if problems:
        raise LedgerInvalid("; ".join(problems))
    return doc


def walk_live_family_files(home: Path) -> list[str]:
    """Every regular file under the live family roots, home-relative posix, sorted."""
    home = Path(home)
    found: list[str] = []
    for rel in LIVE_WALK_ROOTS:
        root = home / rel
        if not root.is_dir():
            continue
        for dirpath, _dirs, names in os.walk(root):
            for name in names:
                path = Path(dirpath) / name
                if path.is_file():
                    found.append(path.relative_to(home).as_posix())
    return sorted(found)


# ----------------------------------------------------------------------- verify
@dataclass
class VerifyResult:
    """Outcome of re-verifying a live tree against its ledger and the git object store."""

    ledger_path: str
    n_records: int
    verified: list[str] = field(default_factory=list)
    unverified: list[str] = field(default_factory=list)
    catfile_hash_ok: list[str] = field(default_factory=list)
    blob_sha_ok: list[str] = field(default_factory=list)
    missing_record: list[str] = field(default_factory=list)
    missing_file: list[str] = field(default_factory=list)
    details: list[dict[str, Any]] = field(default_factory=list)

    @property
    def clean(self) -> bool:
        return (
            not self.unverified
            and not self.missing_record
            and not self.missing_file
            and len(self.verified) == self.n_records
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "clean": self.clean,
            "ledger_path": self.ledger_path,
            "n_records": self.n_records,
            "verified": list(self.verified),
            "unverified": list(self.unverified),
            "catfile_hash_ok": list(self.catfile_hash_ok),
            "blob_sha_ok": list(self.blob_sha_ok),
            "missing_record": list(self.missing_record),
            "missing_file": list(self.missing_file),
            "details": list(self.details),
        }


def verify_deployed(home: Path, git_dir: Path | None = None) -> VerifyResult:
    """Bytes direction (cat-file re-hash) plus completeness direction (independent walk)."""
    home = Path(home)
    ledger = load_ledger(home)
    store = Path(git_dir) if git_dir is not None else Path(str(ledger.get("git_dir") or ""))
    result = VerifyResult(ledger_path=LEDGER_REL, n_records=len(ledger["records"]))
    recorded: set[str] = set()
    for rec in sorted(ledger["records"], key=lambda r: r["live_path"]):
        live_rel = rec["live_path"]
        recorded.add(live_rel)
        live_path = home / live_rel
        if not live_path.is_file():
            result.missing_file.append(live_rel)
            result.details.append({"live_path": live_rel, "state": "missing_file"})
            continue
        live = live_path.read_bytes()
        try:
            blob = git_cat_file_p(store, rec["source_blob_sha"])
        except subprocess.CalledProcessError:
            blob = None
        catfile_ok = blob is not None and sha256_hex(blob) == sha256_hex(live)
        blob_ok = blob_id(live) == rec["source_blob_sha"]
        content_ok = sha256_hex(live) == rec["content_sha256"]
        if catfile_ok:
            result.catfile_hash_ok.append(live_rel)
        if blob_ok:
            result.blob_sha_ok.append(live_rel)
        if catfile_ok and blob_ok and content_ok and blob == live:
            result.verified.append(live_rel)
            state = "verified"
        else:
            result.unverified.append(live_rel)
            state = "unverified"
        result.details.append(
            {
                "live_path": live_rel,
                "state": state,
                "source_blob_sha": rec["source_blob_sha"],
                "catfile_hash_ok": catfile_ok,
                "blob_sha_ok": blob_ok,
                "content_sha256_ok": content_ok,
            }
        )
    walked = walk_live_family_files(home)
    result.missing_record = sorted(set(walked) - recorded)
    return result


# ------------------------------------------------------------------ AST gate
# Module-qualified primitives (``os.x`` / ``shutil.x``) and Path-style methods on any
# receiver.  ``.replace``/``.rename`` count only in their one-argument Path form so
# ``str.replace(old, new)`` is not mistaken for a filesystem write.
_OS_WRITE_FUNCS = {
    "os.open", "os.write", "os.replace", "os.rename", "os.link", "os.symlink", "os.unlink",
    "os.remove", "os.truncate", "os.rmdir", "os.removedirs",
    "shutil.copy", "shutil.copy2", "shutil.copyfile", "shutil.copytree", "shutil.move",
    "shutil.rmtree", "shutil.copyfileobj",
}
_PATH_WRITE_METHODS = {
    "write_bytes", "write_text", "symlink_to", "hardlink_to", "link_to", "touch", "rmdir",
    "unlink",
}
_PATH_ONE_ARG_METHODS = {"replace", "rename"}


def _call_name(node: ast.Call) -> str:
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        base = func.value
        if isinstance(base, ast.Name):
            return f"{base.id}.{func.attr}"
        return f".{func.attr}"
    return ""


def _is_write_primitive(node: ast.Call) -> str | None:
    name = _call_name(node)
    if name == "open" or name.endswith(".open"):
        mode = None
        if len(node.args) > 1:
            mode = node.args[1]
        for kw in node.keywords:
            if kw.arg == "mode":
                mode = kw.value
        if mode is None:
            return None
        if isinstance(mode, ast.Constant) and isinstance(mode.value, str):
            return name if any(ch in mode.value for ch in "wax+") else None
        return name
    if name in _OS_WRITE_FUNCS:
        return name
    _head, _, attr = name.rpartition(".")
    if attr in _PATH_WRITE_METHODS and isinstance(node.func, ast.Attribute):
        return name
    if (
        attr in _PATH_ONE_ARG_METHODS
        and isinstance(node.func, ast.Attribute)
        and len(node.args) == 1
        and not node.keywords
    ):
        return name
    return None


def live_write_callees(source: str | None = None) -> dict[str, Any]:
    """Reviewer gate: prove ``place_file`` is the only live-tree writer by reading the AST."""
    text = source if source is not None else Path(__file__).read_text(encoding="utf-8")
    tree = ast.parse(text)
    atomic_callers: set[str] = set()
    primitive_sites: dict[str, set[str]] = {}
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for sub in ast.walk(node):
            if not isinstance(sub, ast.Call):
                continue
            if _call_name(sub) == "_atomic_write":
                atomic_callers.add(node.name)
            primitive = _is_write_primitive(sub)
            if primitive:
                primitive_sites.setdefault(node.name, set()).add(primitive)
    allowed = {"_atomic_write"} | set(FIXTURE_WRITERS)
    unexpected = sorted(set(primitive_sites) - allowed)
    callers = sorted(atomic_callers)
    sole = (
        callers == [SOLE_LIVE_WRITER]
        and not unexpected
        and "_atomic_write" in primitive_sites
    )
    return {
        "module": ENGINE_REL,
        "sole_live_writer": SOLE_LIVE_WRITER,
        "atomic_write_callers": callers,
        "write_primitive_sites": {k: sorted(v) for k, v in sorted(primitive_sites.items())},
        "fixture_writers": sorted(FIXTURE_WRITERS),
        "unexpected_writers": unexpected,
        "place_file_is_sole_live_writer": sole,
        "method": "ast: callers of _atomic_write == [place_file]; write primitives only in "
                  "_atomic_write and declared fixture writers",
    }


# -------------------------------------------------------------------------- CLI
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="deploy_provenance.py",
        description="Deploy one family (invoked by scripts/sync-*.ps1 -Provenance) or verify.",
    )
    parser.add_argument("--kind", choices=[*FAMILY_ORDER, "all"], default=None)
    parser.add_argument("--repo", default=str(DEFAULT_WORKTREE), help="source checkout")
    parser.add_argument("--home", default=str(Path.home()), help="live HOME")
    parser.add_argument("--git-dir", default=None)
    parser.add_argument("--worktree", default=None, help="tree holding scripts/sync-*.ps1")
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--gate", action="store_true", help="print the sole-writer AST gate")
    args = parser.parse_args(argv)

    if args.gate:
        gate = live_write_callees()
        print(json.dumps(gate, indent=2, sort_keys=True))
        return 0 if gate["place_file_is_sole_live_writer"] else 1

    home = Path(args.home)
    repo = Path(args.repo)
    try:
        if args.git_dir:
            git_dir, prefix = Path(args.git_dir), ""
        else:
            git_dir, prefix = resolve_git(repo)
        if args.verify:
            result = verify_deployed(home, git_dir)
            print(json.dumps(result.as_dict(), indent=2, sort_keys=True))
            return 0 if result.clean else 1
        if args.kind is None:
            parser.error("--kind is required unless --verify/--gate")
        families = FAMILY_ORDER if args.kind == "all" else (args.kind,)
        outcome = deploy_families(
            repo, home, git_dir, families,
            worktree=Path(args.worktree) if args.worktree else None,
            tree_prefix=prefix,
            merge=args.kind != "all",
        )
    except ProvenanceError as exc:
        print(f"FAILED:deploy-provenance {exc}", file=sys.stderr)
        return 2
    summary = {k: v for k, v in outcome.items() if k not in {"records", "control_plane"}}
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
