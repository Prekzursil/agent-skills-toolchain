#!/usr/bin/env python3
"""Run a clean install inside a Linux user-ns chroot that cannot see the repo."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
INNER_FLAG = "--cnf0097-inner"

REPO_MARKERS = (
    ".git",
    "WORK-UNIT-CATALOG.json",
    ".gitmodules",
    "ast-integrate",
)


def _bind(src: Path, dst: Path) -> None:
    dst.mkdir(parents=True, exist_ok=True)
    for args in (
        ["mount", "--bind", str(src), str(dst)],
        ["mount", "--rbind", str(src), str(dst)],
    ):
        proc = subprocess.run(args, capture_output=True, text=True)
        if proc.returncode == 0:
            return
    # WSL overlay /usr often rejects bind. Copy children the installer needs.
    if src.name == "usr":
        for child in ("bin", "lib", "lib64", "local"):
            csrc = src / child
            if csrc.exists():
                cdst = dst / child
                cdst.mkdir(parents=True, exist_ok=True)
                proc = subprocess.run(
                    ["mount", "--bind", str(csrc), str(cdst)],
                    capture_output=True,
                    text=True,
                )
                if proc.returncode != 0:
                    subprocess.run(["cp", "-a", str(csrc), str(cdst)], check=False)
        py = Path(sys.executable)
        if py.is_file():
            dest_py = dst / "bin" / py.name
            dest_py.parent.mkdir(parents=True, exist_ok=True)
            if not dest_py.exists():
                subprocess.run(["cp", "-a", str(py), str(dest_py)], check=False)
        return
    proc = subprocess.run(["cp", "-a", str(src) + "/.", str(dst)], capture_output=True, text=True)
    if proc.returncode != 0:
        shutil.copytree(src, dst, dirs_exist_ok=True)


def _scan_tree_for_markers(tree: Path, prefix: str) -> list[str]:
    found: list[str] = []
    if not tree.exists():
        return found
    for dirpath, dirnames, filenames in os.walk(tree):
        names = set(dirnames) | set(filenames)
        rel_dir = Path(dirpath)
        for marker in REPO_MARKERS:
            if marker in names:
                found.append(f"{prefix}/{marker}" if prefix != "/" else f"/{marker}")
        if "WORK-UNIT-CATALOG.json" in filenames:
            rel = (rel_dir / "WORK-UNIT-CATALOG.json").as_posix()
            found.append(rel if rel.startswith("/") else f"{prefix}/{rel}")
        # do not descend into bound OS trees
        for skip in ("usr", "bin", "lib", "lib64", "etc", "proc", "dev", "sys"):
            if skip in dirnames:
                dirnames.remove(skip)
    return found


def _repo_markers(root: Path) -> list[str]:
    found: list[str] = []
    listing = sorted(p.name for p in root.iterdir())
    if "opt" in listing:
        found.append("/opt")
    if ".git" in listing:
        found.append("/.git")
    if "command-center" in listing:
        found.append("/command-center")
    if (root / "opt" / "p2" / "ast-integrate").exists():
        found.append("/opt/p2/ast-integrate")
    found.extend(_scan_tree_for_markers(root / "artifact", "/artifact"))
    found.extend(_scan_tree_for_markers(root / "install-prefix", "/install-prefix"))
    seen: set[str] = set()
    out: list[str] = []
    for item in found:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def inner_main(argv: list[str]) -> int:
    root = Path(argv[argv.index("--root") + 1])
    tarball = Path(argv[argv.index("--tarball") + 1])
    results = Path(argv[argv.index("--results") + 1])
    subprocess.run(["mount", "--make-rprivate", "/"], check=False, capture_output=True)
    _bind(Path("/usr"), root / "usr")
    _bind(Path("/bin"), root / "bin")
    if Path("/lib64").is_dir():
        _bind(Path("/lib64"), root / "lib64")
    if Path("/lib").is_dir():
        _bind(Path("/lib"), root / "lib")
    _bind(Path("/etc"), root / "etc")
    _bind(results, root / "results")
    artifact_dir = root / "artifact"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(tarball, artifact_dir / tarball.name)
    os.chroot(str(root))
    os.chdir("/")
    os.environ["PATH"] = "/usr/bin:/bin"
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    os.environ["PYTHONNOUSERSITE"] = "1"
    root_listing_pre = sorted(os.listdir("/"))
    artifact_listing_pre = sorted(os.listdir("/artifact"))
    transcript: list[str] = []
    health_out: list[str] = []
    install_rc = 2
    health_rc = 2
    copied_files: list[str] = []
    try:
        src = Path("/artifact/src")
        src.mkdir(parents=True, exist_ok=True)
        with tarfile.open(f"/artifact/{tarball.name}", "r:gz") as tar:
            tar.extractall(path=src, filter="data")
        pkg = src / "harness-plugin-1.0.0"
        installer = pkg / "install.py"
        health = pkg / "health_check.py"
        prefix = Path("/install-prefix")
        transcript.append(f"extracted {tarball.name} -> {pkg.as_posix()}")
        proc = subprocess.run(
            [sys.executable, "-B", str(installer), "--prefix", str(prefix)],
            capture_output=True,
            text=True,
            env=os.environ.copy(),
        )
        install_rc = proc.returncode
        transcript.extend((proc.stdout or "").splitlines())
        if proc.stderr:
            transcript.extend(f"stderr:{line}" for line in proc.stderr.splitlines())
        receipt_path = prefix / "install-receipt.json"
        if receipt_path.is_file():
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            copied_files = list(receipt.get("copied_files") or [])
        proc2 = subprocess.run(
            [sys.executable, "-B", str(health), "--prefix", str(prefix)],
            capture_output=True,
            text=True,
            env=os.environ.copy(),
        )
        health_rc = proc2.returncode
        health_out.extend((proc2.stdout or "").splitlines())
        if proc2.stderr:
            health_out.extend(f"stderr:{line}" for line in proc2.stderr.splitlines())
    except Exception as exc:  # pragma: no cover - captured into results
        transcript.append(f"EXC:{type(exc).__name__}:{exc}")
    markers = _repo_markers(Path("/"))
    root_listing = sorted(os.listdir("/"))
    artifact_listing = sorted(os.listdir("/artifact"))
    prefix_listing: list[str] = []
    prefix_path = Path("/install-prefix")
    if prefix_path.is_dir():
        prefix_listing = sorted(
            p.relative_to(prefix_path).as_posix()
            for p in prefix_path.rglob("*")
            if p.is_file()
        )
    uname = os.uname()
    identity = {
        "artifact_name": tarball.name,
        "machine": uname.machine,
        "python": sys.version.split()[0],
        "release": uname.release,
        "runtime": "linux-user-ns-chroot",
        "sysname": uname.sysname,
    }
    ident_raw = json.dumps(identity, sort_keys=True, separators=(",", ":")).encode("utf-8")
    doc = {
        "artifact_listing": artifact_listing,
        "artifact_listing_pre_install": artifact_listing_pre,
        "copied_files": copied_files,
        "health_exit_code": health_rc,
        "health_output": health_out,
        "image_digest": "sha256:" + hashlib.sha256(ident_raw).hexdigest(),
        "image_identity": identity,
        "install_exit_code": install_rc,
        "install_success": install_rc == 0,
        "install_transcript": transcript,
        "prefix_listing": prefix_listing,
        "python": sys.version,
        "repo_checkout_present": bool(markers),
        "repo_markers_found": markers,
        "root_listing": root_listing,
        "root_listing_pre_install": root_listing_pre,
        "runtime": "linux-user-ns-chroot",
        "healthy": health_rc == 0,
        "uname": {
            "machine": uname.machine,
            "release": uname.release,
            "sysname": uname.sysname,
            "version": uname.version,
        },
    }
    Path("/results/container.json").write_text(
        json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return 0 if install_rc == 0 and health_rc == 0 and not markers else 1


def run(tarball: Path) -> dict:
    tarball = tarball.resolve()
    if not tarball.is_file():
        raise FileNotFoundError(tarball)
    scratch = Path(tempfile.mkdtemp(prefix="cnf0097-ctr-", dir="/tmp"))
    root = scratch / "root"
    results = scratch / "results"
    try:
        for name in ("bin", "usr", "lib", "lib64", "etc", "artifact", "tmp", "dev", "results"):
            (root / name).mkdir(parents=True, exist_ok=True)
        results.mkdir(parents=True, exist_ok=True)
        cmd = [
            "unshare",
            "--user",
            "--map-root-user",
            "--mount",
            "--fork",
            "--",
            sys.executable,
            "-B",
            str(Path(__file__).resolve()),
            INNER_FLAG,
            "--root",
            str(root),
            "--tarball",
            str(tarball),
            "--results",
            str(results),
        ]
        env = os.environ.copy()
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        proc = subprocess.run(cmd, capture_output=True, text=True, env=env)
        result_path = results / "container.json"
        if not result_path.is_file():
            raise RuntimeError(
                f"container produced no results rc={proc.returncode} "
                f"stdout={proc.stdout[-2000:]!r} stderr={proc.stderr[-2000:]!r}"
            )
        doc = json.loads(result_path.read_text(encoding="utf-8"))
        doc["unshare_exit_code"] = proc.returncode
        doc["unshare_stderr"] = (proc.stderr or "").strip()
        doc["unshare_stdout"] = (proc.stdout or "").strip()
        return doc
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def main() -> int:
    if INNER_FLAG in sys.argv:
        return inner_main(sys.argv)
    tarball = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "dist" / "harness-plugin-1.0.0.tar.gz"
    doc = run(tarball)
    print(json.dumps(doc, indent=2, sort_keys=True))
    if doc.get("repo_checkout_present"):
        print("FAILED:container repo checkout visible")
        return 1
    if not doc.get("install_success") or not doc.get("healthy"):
        print("FAILED:container install/health")
        return 1
    print("SUCCESS:container")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
