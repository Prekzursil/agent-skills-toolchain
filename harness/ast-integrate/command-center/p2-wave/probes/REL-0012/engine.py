"""Build a fixture distributable, bind SLSA/in-toto provenance, locate UNSIGNED."""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path
from zipfile import ZIP_STORED, ZipFile, ZipInfo

from common import (
    BUILD_TYPE,
    BUILDER_ID,
    PREDICATE_TYPE,
    STATEMENT_TYPE,
    UNIT_ID,
    VERIFY_REL,
)

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
FIXTURES = HERE / "fixtures"
SRC = FIXTURES / "src"
NOTES_SRC = FIXTURES / "RELEASE-NOTES.md"
ZIP_FIXED_TIME = (2026, 8, 24, 0, 0, 0)
UNSIGNED_MARKERS = ("UNSIGNED:", "UNSIGNED ")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def sha1_hex(data: bytes) -> str:
    try:
        return hashlib.sha1(data, usedforsecurity=False).hexdigest()
    except TypeError:
        return hashlib.sha1(data).hexdigest()


def load_source_files() -> dict[str, bytes]:
    files: dict[str, bytes] = {}
    for path in sorted(SRC.rglob("*")):
        if path.is_file():
            rel = path.relative_to(SRC).as_posix()
            files[rel] = path.read_bytes()
    files["RELEASE-NOTES.md"] = NOTES_SRC.read_bytes()
    if not files:
        raise RuntimeError("REL-0012 fixture src is empty")
    return files


def source_commit(files: dict[str, bytes]) -> str:
    """Deterministic 40-hex id bound into .git/HEAD (not produced by git commit)."""
    acc = b""
    for name in sorted(files):
        blob = files[name]
        acc += name.encode("utf-8") + b"\0"
        acc += str(len(blob)).encode("ascii") + b"\0"
        acc += blob
    return sha1_hex(acc)


def write_git_ref(tree: Path, commit: str) -> None:
    git = tree / ".git"
    (git / "refs" / "heads").mkdir(parents=True, exist_ok=True)
    (git / "objects").mkdir(parents=True, exist_ok=True)
    (git / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    (git / "refs" / "heads" / "main").write_text(commit + "\n", encoding="utf-8")
    (git / "config").write_text(
        "[core]\n\trepositoryformatversion = 0\n\tfilemode = true\n\tbare = false\n",
        encoding="utf-8",
    )


def materialize_tree(dst: Path) -> tuple[str, dict[str, str]]:
    if dst.exists():
        shutil.rmtree(dst)
    files = load_source_files()
    commit = source_commit(files)
    materials: dict[str, str] = {}
    for name, blob in files.items():
        target = dst / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(blob)
        materials[name] = sha256_bytes(blob)
    write_git_ref(dst, commit)
    return commit, materials


def pack_zip(tree: Path, zip_path: Path) -> str:
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    names = []
    for path in sorted(tree.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(tree).as_posix()
        if rel.startswith(".git/") or rel == ".git":
            continue
        names.append((rel, path.read_bytes()))
    with ZipFile(zip_path, "w", compression=ZIP_STORED) as zf:
        for rel, blob in names:
            info = ZipInfo(rel)
            info.date_time = ZIP_FIXED_TIME
            info.compress_type = ZIP_STORED
            zf.writestr(info, blob)
    return sha256_file(zip_path)


def find_unsigned(path: Path) -> dict:
    lines = path.read_text(encoding="utf-8").splitlines()
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith(UNSIGNED_MARKERS) or stripped.startswith("UNSIGNED"):
            rel = path
            try:
                rel = path.relative_to(REPO)
            except ValueError:
                rel = path
            return {
                "path": rel.as_posix() if hasattr(rel, "as_posix") else str(rel),
                "line": i,
                "text": stripped,
            }
    raise RuntimeError(f"UNSIGNED declaration missing in {path}")


def unsigned_in_zip(zip_path: Path) -> dict:
    with ZipFile(zip_path, "r") as zf:
        if "RELEASE-NOTES.md" not in zf.namelist():
            raise RuntimeError("shipped zip lacks RELEASE-NOTES.md")
        text = zf.read("RELEASE-NOTES.md").decode("utf-8")
    for i, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith("UNSIGNED"):
            return {"entry": "RELEASE-NOTES.md", "line": i, "text": stripped}
    raise RuntimeError("UNSIGNED declaration missing from shipped RELEASE-NOTES.md")


def emit_provenance(
    *,
    artifact_name: str,
    artifact_sha256: str,
    commit: str,
    materials: dict[str, str],
    dest: Path,
) -> dict:
    stmt = {
        "_type": STATEMENT_TYPE,
        "subject": [
            {
                "name": artifact_name,
                "digest": {"sha256": artifact_sha256},
            }
        ],
        "predicateType": PREDICATE_TYPE,
        "predicate": {
            "buildDefinition": {
                "buildType": BUILD_TYPE,
                "externalParameters": {
                    "unit": UNIT_ID,
                    "releaseMode": "PR-ONLY",
                    "publicationBoundHalf": "OUT-OF-SCOPE",
                },
                "internalParameters": {
                    "unsigned": True,
                    "signing": (
                        "deferred: owner-held key not present; this unit "
                        "creates, uses, and rotates no key"
                    ),
                },
                "resolvedDependencies": [
                    {
                        "uri": "git+file:///rel-0012-build-tree",
                        "digest": {"gitCommit": commit},
                    }
                ]
                + [
                    {
                        "uri": f"file:///{name}",
                        "digest": {"sha256": digest},
                    }
                    for name, digest in sorted(materials.items())
                ],
            },
            "runDetails": {
                "builder": {"id": BUILDER_ID},
                "metadata": {
                    "reproducible": True,
                    "invocationId": f"rel-0012-{commit[:12]}",
                },
            },
        },
    }
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(
        json.dumps(stmt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return stmt


def tamper_one_byte(src: Path, dst: Path) -> None:
    data = bytearray(src.read_bytes())
    if not data:
        raise RuntimeError("cannot tamper empty artifact")
    data[0] = data[0] ^ 0x01
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(bytes(data))


def rel_to_repo(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO).as_posix()
    except ValueError:
        return str(path)


def verify_command(artifact: Path, provenance: Path, tree: Path, notes: Path) -> str:
    return (
        "PYTHONDONTWRITEBYTECODE=1 python3 -B "
        f"{VERIFY_REL} --artifact {rel_to_repo(artifact)} "
        f"--provenance {rel_to_repo(provenance)} "
        f"--build-tree {rel_to_repo(tree)} "
        f"--release-notes {rel_to_repo(notes)}"
    )


def run_verify(
    artifact: Path, provenance: Path, tree: Path, notes: Path
) -> tuple[int, str, str]:
    cmd = verify_command(artifact, provenance, tree, notes)
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, cmd, text


def build_all(out_dir: Path) -> dict:
    tree = out_dir / "build-tree"
    artifact = out_dir / "artifact.zip"
    provenance = out_dir / "provenance.json"
    notes = out_dir / "RELEASE-NOTES.md"
    commit, materials = materialize_tree(tree)
    shutil.copyfile(NOTES_SRC, notes)
    sha = pack_zip(tree, artifact)
    emit_provenance(
        artifact_name="artifact.zip",
        artifact_sha256=sha,
        commit=commit,
        materials=materials,
        dest=provenance,
    )
    unsigned_src = find_unsigned(NOTES_SRC)
    unsigned_shipped = unsigned_in_zip(artifact)
    unsigned_copy = find_unsigned(notes)
    return {
        "commit": commit,
        "artifact_sha256": sha,
        "builder_id": BUILDER_ID,
        "tree": tree,
        "artifact": artifact,
        "provenance": provenance,
        "notes": notes,
        "unsigned_src": unsigned_src,
        "unsigned_shipped": unsigned_shipped,
        "unsigned_copy": unsigned_copy,
        "materials": materials,
    }
