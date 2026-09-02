#!/usr/bin/env python3
"""Disposable Linux isolation for CNF-0018.

docker/podman/modal are absent on this host. Isolation is:
  1. a deterministic tar "image" of the files under test (digest = image id)
  2. extract to a throwaway directory
  3. unshare --user --map-root-user --pid --fork, else a cleaned env in that tree

The image is not an OCI runtime. It is a hashed, disposable root whose digest
is recorded so a later probe re-run can prove it used the same bytes.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
MARKER = "CNF-0018-MEASURE-JSON:"

# Files the isolated measure.py actually imports. receipt_gate.py is not in
# this worktree and current validate.py does not import it (the prior
# ModuleNotFoundError was from an older validate.py). Listing a missing file
# made build_image_tar raise FileNotFoundError before measure could run.
IMAGE_RELS = [
    "command-center/p2-wave/probes/CNF-0018/measure.py",
    "command-center/p2-wave/probes/CNF-0018/fixtures/register.md",
    "command-center/p2-wave/probes/CNF-0018/fixtures/overlay.json",
    "tools/command-center/validate.py",
    "tools/command-center/seed.py",
    "tools/command-center/render.py",
    "tools/command-center/catalog.py",
    "tools/command-center/register_parse.py",
    "tools/command-center/phase_graph.py",
    # catalog.py now loads its sibling id_normalize.py by path; without it
    # the extracted image raises FileNotFoundError before measure can run.
    "tools/command-center/id_normalize.py",
]


def which(name: str) -> str | None:
    return shutil.which(name)


def digest_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def source_tree_sha() -> str:
    h = hashlib.sha256()
    for rel in IMAGE_RELS:
        path = REPO / rel
        raw = path.read_bytes().replace(b"\r\n", b"\n") if path.is_file() else b""
        h.update(rel.encode("utf-8"))
        h.update(b"\0")
        h.update(digest_bytes(raw).encode("ascii"))
        h.update(b"\n")
    return h.hexdigest()


def build_image_tar() -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tar:
        for rel in IMAGE_RELS:
            path = REPO / rel
            if not path.is_file():
                raise FileNotFoundError(rel)
            info = tarfile.TarInfo(name=rel)
            data = path.read_bytes()
            info.size = len(data)
            info.mtime = 0
            info.mode = 0o644
            info.uid = 0
            info.gid = 0
            info.uname = "root"
            info.gname = "root"
            tar.addfile(info, io.BytesIO(data))
    return buf.getvalue()


def parse_measure_stdout(text: str) -> dict:
    for line in text.splitlines():
        if line.startswith(MARKER):
            return json.loads(line[len(MARKER) :])
    raise ValueError("measure.py did not emit CNF-0018-MEASURE-JSON")


def _clean_env(root: Path) -> dict[str, str]:
    path = os.environ.get("PATH", "/usr/bin:/bin")
    return {
        "PATH": path,
        "HOME": str(root / "home"),
        "TMPDIR": str(root / "tmp"),
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONPATH": str(root / "tools" / "command-center"),
    }


def _run(cmd: list[str], root: Path, env: dict[str, str], kind: str) -> tuple[int, str, str]:
    try:
        p = subprocess.run(
            cmd,
            cwd=str(root),
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
        )
        return p.returncode, (p.stdout or "") + (p.stderr or ""), kind
    except subprocess.TimeoutExpired:
        return 124, "TIMEOUT", kind


def run_isolated(root: Path) -> tuple[int, str, str]:
    (root / "home").mkdir(exist_ok=True)
    (root / "tmp").mkdir(exist_ok=True)
    script = root / "command-center/p2-wave/probes/CNF-0018/measure.py"
    py = sys.executable
    env = _clean_env(root)
    direct = [py, "-B", str(script)]
    unshare = which("unshare")
    if unshare:
        cmd = [
            unshare,
            "--user",
            "--map-root-user",
            "--pid",
            "--fork",
            py,
            "-B",
            str(script),
        ]
        code, text, kind = _run(
            cmd, root, env, "unshare-user-pid+extracted-tar-image"
        )
        if MARKER not in text:
            code, text, kind = _run(direct, root, env, "extracted-tar-image")
        return code, text, kind
    return _run(direct, root, env, "extracted-tar-image")


def run_container() -> dict:
    image = build_image_tar()
    image_digest = digest_bytes(image)
    docker = which("docker") or which("podman") or which("nerdctl")
    with tempfile.TemporaryDirectory(prefix="cnf0018-img-") as td:
        root = Path(td) / "root"
        root.mkdir()
        with tarfile.open(fileobj=io.BytesIO(image), mode="r") as tar:
            tar.extractall(root, filter="data")
        code, text, kind = run_isolated(root)
        if code != 0:
            raise RuntimeError(f"container measure rc={code}\n{text[-4000:]}")
        measured = parse_measure_stdout(text)
    return {
        "container": {
            "kind": kind,
            "image_digest": image_digest,
            "image_bytes": len(image),
            "uname": platform.uname().system
            + " "
            + platform.uname().release
            + " "
            + platform.uname().machine,
            "python": sys.version.split()[0],
            "docker_available": bool(docker),
            "git_available": (REPO / ".git").exists(),
            "modal_sandbox_available": False,
            "note": (
                "docker/podman/modal absent; isolation is a hashed tar image "
                "extracted into a throwaway root and executed under unshare "
                "user+pid when available"
            ),
        },
        "checkout": {
            "git_available": False,
            "sha": source_tree_sha(),
            "reason": "worktree has no .git; sha is sha256 of the measured file set",
            "image_digest": image_digest,
        },
        "measure": measured,
        "raw_tail": text[-2000:],
    }


def main() -> int:
    doc = run_container()
    m = doc["measure"]
    print(
        json.dumps(
            {
                "image_digest": doc["container"]["image_digest"],
                "checkout_sha": doc["checkout"]["sha"],
                "kind": doc["container"]["kind"],
                "ok": m.get("ok"),
                "known_failure_reproduced": m.get("known_failure_reproduced"),
                "crlf_pass_in_container": m.get("crlf_pass_in_container"),
            },
            sort_keys=True,
        )
    )
    if not m.get("ok"):
        print("FAILED:CNF-0018-container")
        return 1
    print("SUCCESS:CNF-0018-container")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
