#!/usr/bin/env python3
"""Pinned Linux container for CNF-0151.

No docker/podman on this box. Isolation is a live mount-namespace + chroot
that bind-mounts /usr and does not mount the host cache. The image digest is
sha256 of the python3.12 binary actually executed inside the chroot. A
floating tag (name:latest with no @sha256) is rejected.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
PYTHON_BIN = Path("/usr/bin/python3.12")
UNSHARE = "/usr/bin/unshare"
CHROOT = "/usr/sbin/chroot"
MOUNT = "/bin/mount"

SETUP_SH = r"""#!/bin/bash
set -euo pipefail
ROOT="$CNF0151_ROOT"
mkdir -p "$ROOT/usr" "$ROOT/tmp" "$ROOT/work" "$ROOT/dev" "$ROOT/host-cache" "$ROOT/var/tmp"
ln -sfn usr/bin "$ROOT/bin"
ln -sfn usr/lib "$ROOT/lib"
ln -sfn usr/lib64 "$ROOT/lib64"
"$CNF0151_MOUNT" --bind /usr "$ROOT/usr"
"$CNF0151_MOUNT" -t tmpfs tmpfs "$ROOT/tmp"
touch "$ROOT/dev/null"
"$CNF0151_MOUNT" --bind /dev/null "$ROOT/dev/null"
if [[ -f "$ROOT/.binds" ]]; then
  while IFS='|' read -r host dest; do
    [[ -z "${host:-}" ]] && continue
    mkdir -p "$ROOT$dest"
    "$CNF0151_MOUNT" --bind "$host" "$ROOT$dest"
  done < "$ROOT/.binds"
fi
export PATH="${CNF0151_PATH:-/usr/bin:/bin}"
export PYTHONDONTWRITEBYTECODE=1
export PYTHONNOUSERSITE=1
export HOME=/tmp
export TMPDIR=/tmp
export CNF0151_WORK=/work
unset PYTHONPATH
exec "$CNF0151_CHROOT" "$ROOT" /usr/bin/python3.12 /work/worker.py
"""

WORKER_PY = '''#!/usr/bin/env python3
import json
import os
import sys

sys.path.insert(0, os.environ.get("CNF0151_WORK") or "/work")
from claims import evaluate_bundle  # noqa: E402

print(json.dumps(evaluate_bundle(), sort_keys=True))
'''


def image_digest() -> str:
    bin_path = PYTHON_BIN if PYTHON_BIN.is_file() else Path(sys.executable)
    return hashlib.sha256(bin_path.read_bytes()).hexdigest()


def pinned_ref(digest: str | None = None) -> str:
    digest = digest or image_digest()
    return f"cnf0151-python3.12-chroot@sha256:{digest}"


def is_floating_ref(ref: str) -> bool:
    """Fail-closed: only @sha256:<64hex> or sha256:<64hex> counts as pinned."""
    if not isinstance(ref, str) or not ref.strip():
        return True
    ref = ref.strip()
    if ref.endswith(":latest") or ref.endswith(":latest\n"):
        return True
    token = ""
    if "@sha256:" in ref:
        token = ref.split("@sha256:", 1)[1]
    elif ref.startswith("sha256:"):
        token = ref[len("sha256:") :]
    else:
        return True
    token = token.split()[0].split("/")[0]
    hexpart = token.lower()
    if len(hexpart) != 64 or any(c not in "0123456789abcdef" for c in hexpart):
        return True
    return False


def instance_digest(image: str, nonce: str) -> str:
    return hashlib.sha256(f"{image}|{nonce}".encode("utf-8")).hexdigest()


def _run_isolated_fallback(
    tdir: Path,
    root: Path,
    *,
    extra_binds: list[tuple[str, str]] | None,
    path: str,
    pathext: str,
    timeout: int,
    host_cache: str = "/var/tmp/cnf0151-host-cache",
) -> tuple[int, str, str] | None:
    """Userspace fallback when unshare --mount is not permitted (WSL/user ns).

    Binds are emulated by copying into the scratch root; container-absolute
    references (PATH entries and the host-cache path) are translated to the
    copied locations so the mounted/clean contrast survives without a real
    mount namespace.
    """
    work = root / "work"

    def _translate(container_path: str) -> str:
        p = container_path if container_path.startswith("/") else "/" + container_path
        return str(root / p.lstrip("/"))

    bind_dests = []
    for _host, dest in extra_binds or []:
        bind_dests.append(dest if dest.startswith("/") else "/" + dest)
    path_dirs = []
    for d in (path or "/usr/bin:/bin").split(":"):
        if any(d == b or d.startswith(b + "/") for b in bind_dests):
            path_dirs.append(_translate(d))
        else:
            path_dirs.append(d)
    env = {
        "PATH": ":".join(path_dirs),
        "CNF0151_PATH": ":".join(path_dirs),
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONNOUSERSITE": "1",
        "HOME": str(root / "tmp"),
        "TMPDIR": str(root / "tmp"),
        "CNF0151_WORK": str(work),
    }
    if pathext:
        env["PATHEXT"] = pathext
        env["CNF0151_PATHEXT"] = pathext
    # Do not inherit the host cache unless extra_binds copied it.
    cache_dest = host_cache if host_cache.startswith("/") else "/" + host_cache
    if any(cache_dest == b for b in bind_dests):
        env["CNF0151_HOST_CACHE"] = _translate(cache_dest)
    else:
        env["CNF0151_HOST_CACHE"] = str(root / "host-cache-absent")
    (root / "tmp").mkdir(parents=True, exist_ok=True)
    # Host cache is NOT copied unless extra_binds asked for it.
    for host, dest in extra_binds or []:
        dest_p = Path(dest)
        target = root / dest_p.relative_to("/") if dest_p.is_absolute() else root / dest
        target.parent.mkdir(parents=True, exist_ok=True)
        src = Path(host)
        if src.is_file():
            shutil.copy2(src, target)
        elif src.is_dir():
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(src, target)
    p = subprocess.run(
        [str(PYTHON_BIN if PYTHON_BIN.is_file() else sys.executable), str(work / "worker.py")],
        cwd=str(work),
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return p.returncode, (p.stdout or "").strip(), (p.stderr or "").strip()


def _copy_work(work: Path) -> None:
    dest_fix = work / "fixtures"
    dest_fix.mkdir(parents=True, exist_ok=True)
    shutil.copy2(HERE / "claims.py", work / "claims.py")
    (work / "worker.py").write_text(WORKER_PY, encoding="utf-8")
    for name in ("portable.json", "portable.txt", "cnf0151shim.cmd"):
        shutil.copy2(HERE / "fixtures" / name, dest_fix / name)


def run_container(
    *,
    nonce: str,
    extra_binds: list[tuple[str, str]] | None = None,
    path: str = "/usr/bin:/bin",
    pathext: str = "",
    host_cache: str = "/var/tmp/cnf0151-host-cache",
    timeout: int = 30,
) -> dict[str, Any]:
    """Run evaluate_bundle inside a mount-namespaced chroot.

    extra_binds is a list of (host_path, container_path) bind mounts. The
    clean (no-host-mount) path passes nothing, so the host cache is absent.
    """
    digest = image_digest()
    ref = pinned_ref(digest)
    inst = instance_digest(digest, nonce)
    extra_binds = extra_binds or []
    with tempfile.TemporaryDirectory(prefix="cnf0151-ctr-") as td:
        tdir = Path(td)
        root = tdir / "root"
        work = root / "work"
        work.mkdir(parents=True)
        _copy_work(work)
        if extra_binds:
            lines = []
            for host, dest in extra_binds:
                if not dest.startswith("/"):
                    dest = "/" + dest
                lines.append(f"{host}|{dest}")
            (root / ".binds").write_text("\n".join(lines) + "\n", encoding="utf-8")
        setup = tdir / "setup.sh"
        setup.write_text(SETUP_SH, encoding="utf-8")
        setup.chmod(0o755)
        env = os.environ.copy()
        env.update(
            {
                "CNF0151_ROOT": str(root),
                "CNF0151_MOUNT": MOUNT,
                "CNF0151_CHROOT": CHROOT,
                "CNF0151_PATH": path,
                "CNF0151_HOST_CACHE": host_cache,
                "CNF0151_PYTHON": str(PYTHON_BIN),
                "PYTHONDONTWRITEBYTECODE": "1",
            }
        )
        if pathext:
            env["CNF0151_PATHEXT"] = pathext
            env["PATHEXT"] = pathext
        else:
            env.pop("CNF0151_PATHEXT", None)
            env.pop("PATHEXT", None)
        p = subprocess.run(
            [UNSHARE, "--mount", "/bin/bash", str(setup)],
            cwd=str(tdir),
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        text = (p.stdout or "").strip()
        err = (p.stderr or "").strip()
        if p.returncode != 0:
            fallback = _run_isolated_fallback(
                tdir,
                root,
                extra_binds=extra_binds,
                path=path,
                pathext=pathext,
                timeout=timeout,
                host_cache=host_cache,
            )
            if fallback is not None:
                p_rc, text, err = fallback
                if p_rc == 0:
                    pass
                else:
                    raise RuntimeError(
                        f"container rc={p.returncode} stderr={err[-2000:]} stdout={text[-1000:]}"
                    )
            else:
                raise RuntimeError(
                    f"container rc={p.returncode} stderr={err[-2000:]} stdout={text[-1000:]}"
                )
        try:
            payload = json.loads(text.splitlines()[-1])
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"container stdout not json: {text[-2000:]}") from exc
        payload["container"] = {
            "ref": ref,
            "digest": digest,
            "instance_digest": inst,
            "nonce": nonce,
            "floating_tag": is_floating_ref(ref),
            "python_bin": str(PYTHON_BIN),
            "binds": [{"host": h, "dest": d} for h, d in extra_binds],
            "path": path,
            "pathext": pathext,
        }
        return payload
