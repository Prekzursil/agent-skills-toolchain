"""CNF-0145 clean-room packer and comparators.

Packs plugin members from `git cat-file -p <rev>:<path>` only.
Never uses `git archive` as a payload source (CNF-0019 trap).
"""
from __future__ import annotations

import gzip
import hashlib
import io
import json
import os
import shutil
import stat
import subprocess
import tarfile
import unicodedata
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT = "CNF-0145"
RELEASE_TAG = "v0.0.0-cnf0145"
CONTROL_REL = "control-crlf.txt"
GIT_IDENT = ["-c", "user.name=CNF-0145", "-c", "user.email=cnf-0145@local"]
# Synthetic marker only. Never a live credential. Report path, never body.
SYNTHETIC_CREDENTIAL = "CNF0145_SYNTHETIC_CREDENTIAL_PLACEHOLDER_ONLY"
SENTINEL = "SUCCESS:CNF-0145"
QUESTION = (
    "Question: does the released plugin artifact rebuild from a fresh clone "
    "at the released tag, with no local caches, no worktree state and no "
    "developer environment, into a normalized-identical package? Spec:10655 "
    "demands a clean-room baseline from a fresh clone. Classify every remaining "
    "diff as benign (timestamps, ordering) or material (content), and require "
    "a normalizer for each benign class."
)
ALLOW_EXACT = frozenset(
    {
        "LICENSE",
        "README.md",
        "payload-allowlist.json",
        CONTROL_REL,
    }
)
ALLOW_PREFIX = (".claude-plugin/", "skills/", "hooks/")
# CNF-0145-PACK-USES-CAT-FILE-NOT-ARCHIVE
BYTE_SOURCE = "git cat-file -p <rev>:<path>"
FORBIDDEN_BYTE_SOURCE = "git archive | tar -x"

# CNF-0145-HYGIENE-SCAN-10842
HYGIENE_CLASSES = ("git", "caches", "transcripts", "credentials", "logs")


class HygieneError(RuntimeError):
    def __init__(self, hits: list[dict[str, str]]) -> None:
        self.hits = hits
        super().__init__(f"hygiene:{[h['class'] for h in hits]}")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return sha256_bytes(raw), len(raw)


def lf(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def nfc(path: str) -> str:
    # CNF-0145-NORMALIZER-ORDER
    return unicodedata.normalize("NFC", path.replace("\\", "/"))


def allowed(path: str) -> bool:
    p = nfc(path).lstrip("./")
    if p in ALLOW_EXACT:
        return True
    return any(p.startswith(pref) for pref in ALLOW_PREFIX)


def git(repo: Path, *args: str, env: dict[str, str] | None = None) -> bytes:
    proc = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        env=env,
    )
    if proc.returncode != 0:
        err = (proc.stderr or b"").decode("utf-8", "replace")
        raise RuntimeError(f"git {' '.join(args)} failed: {err[-500:]}")
    return proc.stdout


def isolated_env(home: Path) -> dict[str, str]:
    env = os.environ.copy()
    home.mkdir(parents=True, exist_ok=True)
    env["HOME"] = str(home)
    env["USERPROFILE"] = str(home)
    env["XDG_CACHE_HOME"] = str(home / ".cache")
    env["GIT_CONFIG_GLOBAL"] = os.devnull
    env["GIT_CONFIG_SYSTEM"] = os.devnull
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["SOURCE_DATE_EPOCH"] = "0"
    for key in ("PYTHONPATH", "PYTHONHOME", "NPM_CONFIG_CACHE", "PIP_CACHE_DIR"):
        env.pop(key, None)
    return env


def cat_file(repo: Path, rel: str, rev: str) -> bytes:
    return git(repo, "cat-file", "-p", f"{rev}:{rel}")


def read_archive(repo: Path, rel: str, rev: str) -> bytes:
    """Trap demonstration only. Never a pack source."""
    raw = git(repo, "archive", rev, "--", rel)
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:") as tf:
        member = tf.extractfile(rel)
        if member is None:
            raise RuntimeError(f"archive missing {rel}")
        return member.read()


def ls_tree(repo: Path, rev: str) -> list[str]:
    text = git(repo, "ls-tree", "-r", "--name-only", "-z", rev)
    return [p for p in text.decode("utf-8").split("\0") if p]


def plugin_files() -> dict[str, bytes]:
    plugin = {
        "name": "cnf-0145-fixture-plugin",
        "version": "0.0.0-cnf0145",
        "description": "Disposable plugin used to confirm clean-room rebuild identity.",
    }
    allow = {
        "deny_by_default": True,
        "globs": [
            ".claude-plugin/**",
            "skills/**",
            "hooks/**",
            "LICENSE",
            "README.md",
            "payload-allowlist.json",
            CONTROL_REL,
        ],
    }
    control = "\n".join([f"control-line-{i:03d}" for i in range(40)]) + "\n"
    return {
        ".claude-plugin/plugin.json": (
            json.dumps(plugin, indent=2, sort_keys=True) + "\n"
        ).encode("utf-8"),
        "skills/hello/SKILL.md": (
            "# hello\n\nCNF-0145 fixture skill. Rebuild must keep these bytes.\n"
        ).encode("utf-8"),
        "hooks/hooks.json": b'{"hooks": []}\n',
        "LICENSE": b"MIT License\n\nCopyright (c) CNF-0145 fixture\n",
        "README.md": b"# CNF-0145 fixture plugin\n\nPacked from git blobs only.\n",
        "payload-allowlist.json": (
            json.dumps(allow, indent=2, sort_keys=True) + "\n"
        ).encode("utf-8"),
        CONTROL_REL: control.encode("utf-8"),
    }


def init_release_repo(root: Path) -> None:
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=str(root), check=True)
    (root / ".gitattributes").write_text(
        f"{CONTROL_REL} text eol=crlf\n", encoding="utf-8", newline="\n"
    )
    for rel, data in plugin_files().items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    subprocess.run(
        ["git", *GIT_IDENT, "add", "-A"],
        cwd=str(root),
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", *GIT_IDENT, "commit", "-q", "-m", "CNF-0145 release fixture"],
        cwd=str(root),
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", *GIT_IDENT, "tag", "-a", RELEASE_TAG, "-m", RELEASE_TAG],
        cwd=str(root),
        check=True,
        capture_output=True,
    )


def tar_members(members: list[tuple[str, bytes]], *, mtime: int = 0) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tf:
        for name, data in sorted(members, key=lambda item: nfc(item[0])):
            info = tarfile.TarInfo(name=nfc(name))
            info.size = len(data)
            info.mtime = mtime  # CNF-0145-NORMALIZER-MTIME
            info.uid = 0  # CNF-0145-NORMALIZER-OWNER
            info.gid = 0
            info.uname = ""
            info.gname = ""
            info.mode = 0o644
            tf.addfile(info, io.BytesIO(data))
    return buf.getvalue()


def gzip_bytes(data: bytes, *, mtime: int = 0) -> bytes:
    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode="wb", mtime=mtime, compresslevel=9) as gz:
        gz.write(data)
    return buf.getvalue()


def pack_from_git(repo: Path, rev: str) -> bytes:
    paths = [p for p in ls_tree(repo, rev) if allowed(p)]
    if not paths:
        raise RuntimeError("pack produced zero allowlisted paths")
    members: list[tuple[str, bytes]] = []
    for rel in paths:
        members.append((rel, cat_file(repo, rel, rev)))
    return gzip_bytes(tar_members(members, mtime=0), mtime=0)


def pack_naive_from_worktree(repo: Path, mtime: int) -> bytes:
    """Non-deterministic packer: worktree bytes, live mtime, gzip timestamp."""
    members: list[tuple[str, bytes]] = []
    for rel, data in plugin_files().items():
        path = repo / rel
        if path.is_file():
            members.append((rel, path.read_bytes()))
        else:
            members.append((rel, data))
    # Insertion order, not NFC-sorted, to exercise the ordering normalizer.
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tf:
        for name, data in members:
            info = tarfile.TarInfo(name=name)
            info.size = len(data)
            info.mtime = mtime
            info.uid = os.getuid()
            info.gid = os.getgid()
            info.mode = 0o644
            tf.addfile(info, io.BytesIO(data))
    return gzip_bytes(buf.getvalue(), mtime=mtime)


def extract_tar_gz(blob: bytes) -> dict[str, bytes]:
    with gzip.GzipFile(fileobj=io.BytesIO(blob), mode="rb") as gz:
        raw = gz.read()
    out: dict[str, bytes] = {}
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:") as tf:
        for member in tf.getmembers():
            if not member.isfile():
                continue
            handle = tf.extractfile(member)
            if handle is None:
                continue
            out[nfc(member.name)] = handle.read()
    return out


def member_sha_set(blob: bytes) -> dict[str, str]:
    return {path: sha256_bytes(data) for path, data in extract_tar_gz(blob).items()}


def sha_set(blob: bytes) -> dict[str, Any]:
    return {
        "archive_sha256": sha256_bytes(blob),
        "member_sha256": member_sha_set(blob),
    }


def normalize_archive(blob: bytes) -> bytes:
    members = list(extract_tar_gz(blob).items())
    return gzip_bytes(tar_members(members, mtime=0), mtime=0)


def classify_pair(path: str, a: bytes, b: bytes) -> dict[str, Any]:
    sa, sb = sha256_bytes(a), sha256_bytes(b)
    if a == b:
        klass = "identical"
        normalizer = None
    elif lf(a) == lf(b):
        klass = "benign-line-ending"
        normalizer = "lf"
    else:
        klass = "material-content"
        normalizer = None
    return {
        "path": path,
        "class": klass,
        "normalizer": normalizer,
        "released_sha256": sa,
        "rebuild_sha256": sb,
    }


def compare_packages(released: bytes, rebuild: bytes) -> dict[str, Any]:
    rel_m = extract_tar_gz(released)
    reb_m = extract_tar_gz(rebuild)
    paths = sorted(set(rel_m) | set(reb_m), key=nfc)
    rows: list[dict[str, Any]] = []
    remaining: list[dict[str, Any]] = []
    for path in paths:
        a = rel_m.get(path, b"")
        b = reb_m.get(path, b"")
        row = classify_pair(path, a, b)
        rows.append(row)
        if row["class"] != "identical":
            remaining.append(row)
    raw_identical = released == rebuild
    norm_identical = normalize_archive(released) == normalize_archive(rebuild)
    return {
        "raw_identical": raw_identical,
        "normalized_identical": norm_identical,
        "classified_diff": rows,
        "remaining_diffs": remaining,
        "material_remaining": sum(1 for r in remaining if r["class"] == "material-content"),
        "released": sha_set(released),
        "rebuild": sha_set(rebuild),
    }


def flip_one_byte(data: bytes) -> bytes:
    if not data:
        return b"X"
    return data[:-1] + bytes([data[-1] ^ 0x01])


def mutate_member(blob: bytes, rel: str) -> bytes:
    members = extract_tar_gz(blob)
    if rel not in members:
        raise RuntimeError(f"missing member {rel}")
    members[rel] = flip_one_byte(members[rel])
    return gzip_bytes(tar_members(list(members.items()), mtime=0), mtime=0)


def _posix(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def classify_forbidden(rel: str, is_dir: bool = False) -> str | None:
    parts = Path(rel).parts
    name = Path(rel).name
    lower = rel.lower()
    if ".git" in parts or name == ".git":
        return "git"
    if (
        "__pycache__" in parts
        or "node_modules" in parts
        or ".cache" in parts
        or name == ".cache"
    ):
        return "caches"
    if name.endswith(".log"):
        return "logs"
    if "transcript" in lower or (name.endswith(".jsonl") and "session" in lower):
        return "transcripts"
    if name in {".env", "credentials.json", "secrets.json"}:
        return "credentials"
    if is_dir:
        return None
    return None


def scan_forbidden(root: Path) -> list[dict[str, str]]:
    hits: list[dict[str, str]] = []
    for dirpath, dirnames, filenames in os.walk(root):
        base = Path(dirpath)
        for dirname in list(dirnames):
            rel = _posix(base / dirname, root)
            klass = classify_forbidden(rel, is_dir=True)
            if klass:
                hits.append({"path": rel, "class": klass})
        for filename in filenames:
            path = base / filename
            rel = _posix(path, root)
            klass = classify_forbidden(rel)
            if klass is None:
                try:
                    sample = path.read_bytes()[:4096]
                except OSError:
                    sample = b""
                if SYNTHETIC_CREDENTIAL.encode("ascii") in sample:
                    klass = "credentials"
            if klass:
                hits.append({"path": rel, "class": klass})
    return hits


def scan_archive_hygiene(blob: bytes) -> list[dict[str, str]]:
    hits: list[dict[str, str]] = []
    for rel, data in extract_tar_gz(blob).items():
        klass = classify_forbidden(rel)
        if klass is None and SYNTHETIC_CREDENTIAL.encode("ascii") in data:
            klass = "credentials"
        if klass:
            hits.append({"path": rel, "class": klass})
    return hits


def plant_forbidden(staging: Path) -> dict[str, str]:
    plants = {
        "git": staging / ".git" / "config",
        "caches": staging / "__pycache__" / "x.pyc",
        "logs": staging / "debug.log",
        "transcripts": staging / "transcripts" / "session.jsonl",
        "credentials": staging / ".env",
    }
    plants["git"].parent.mkdir(parents=True, exist_ok=True)
    plants["git"].write_text("[core]\n\trepositoryformatversion = 0\n", encoding="utf-8")
    plants["caches"].parent.mkdir(parents=True, exist_ok=True)
    plants["caches"].write_bytes(b"\0PYC")
    plants["logs"].write_text("not a real log body\n", encoding="utf-8")
    plants["transcripts"].parent.mkdir(parents=True, exist_ok=True)
    plants["transcripts"].write_text('{"event":"fixture"}\n', encoding="utf-8")
    plants["credentials"].write_text(SYNTHETIC_CREDENTIAL + "\n", encoding="utf-8")
    return {klass: str(path.relative_to(staging).as_posix()) for klass, path in plants.items()}


def clone_fresh(src: Path, dest: Path, home: Path) -> None:
    if dest.exists():
        raise RuntimeError(f"clone dest already exists: {dest}")
    env = isolated_env(home)
    proc = subprocess.run(
        ["git", "clone", "--branch", RELEASE_TAG, "--", str(src), str(dest)],
        capture_output=True,
        env=env,
    )
    if proc.returncode != 0:
        err = (proc.stderr or b"").decode("utf-8", "replace")
        raise RuntimeError(f"git clone failed: {err[-500:]}")


def commit_one_byte(repo: Path, rel: str = "README.md") -> None:
    path = repo / rel
    path.write_bytes(flip_one_byte(path.read_bytes()))
    subprocess.run(
        ["git", *GIT_IDENT, "add", "--", rel],
        cwd=str(repo),
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", *GIT_IDENT, "commit", "-q", "-m", "CNF-0145 one-byte mutation"],
        cwd=str(repo),
        check=True,
        capture_output=True,
    )


def estate_facts() -> dict[str, Any]:
    return {
        "worktree_is_git": (REPO / ".git").exists(),
        "artifact_manifest_present": (
            REPO / "command-center" / "ARTIFACT-MANIFEST.json"
        ).is_file(),
        "pack_py_present": (REPO / "tools" / "plugin" / "pack.py").is_file(),
        "plugin_json_present": (REPO / ".claude-plugin" / "plugin.json").is_file(),
        "release_checklist_present": (
            REPO / "command-center" / "RELEASE-CHECKLIST.md"
        ).is_file(),
        "note": (
            "This worktree is not a git checkout and has no released plugin "
            "package. Confirmation runs on a disposable tagged fixture repo "
            "that exercises cat-file packing, hygiene, and fresh-clone rebuild."
        ),
    }


def load_schema() -> dict:
    path = REPO / "command-center/schema/reproduction-matrix.schema.json"
    return json.loads(path.read_text(encoding="utf-8"))


def validate_report(doc: dict) -> list[str]:
    import jsonschema

    schema = load_schema()
    jsonschema.Draft7Validator.check_schema(schema)
    errs = sorted(
        jsonschema.Draft7Validator(schema).iter_errors(doc),
        key=lambda e: list(e.path),
    )
    return [f"{list(e.path)}: {e.message}" for e in errs]


def schema_rejects_garbage() -> bool:
    import jsonschema

    validator = jsonschema.Draft7Validator(load_schema())
    garbage = [
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"unit_id": "CNF-0145", "state": "SUCCESS"},
        {"x": "x" * 2000},
    ]
    return all(list(validator.iter_errors(item)) for item in garbage)


def rmtree(path: Path) -> None:
    def _onerror(func: Any, p: str, _exc: Any) -> None:
        try:
            os.chmod(p, stat.S_IWRITE | stat.S_IREAD)
            func(p)
        except OSError:
            pass

    shutil.rmtree(path, onerror=_onerror)
