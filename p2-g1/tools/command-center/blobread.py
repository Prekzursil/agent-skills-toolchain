"""Read content as the COMMITTED BLOB, not the Windows working tree (TST-0334).

Two roles live in this module:

1. ``content_bytes`` / ``read_blob`` - the CC-0001 harness surface. Prefer the
   committed blob (``git cat-file``); fall back to LF-normalised working-tree
   bytes for fixtures and trees that are not git repositories.

2. ``live_measure`` - the TST-0334 three-route instrument. It runs the REAL
   git routes (archive with the tar member EXTRACTED, cat-file, show, and the
   working tree) against a deterministic fixture repository built on demand
   under the TST-0334 probe fixtures, so the archive-vs-blob divergence is
   demonstrated rather than asserted.

The route this module exists to indict is ``git archive``: with the checkout
form configured (core.autocrlf=true / core.eol=crlf) it hands back CRLF
worktree bytes while ``git cat-file`` always returns the LF blob. The
``stable.txt`` control (``-text`` in .gitattributes) is byte-identical on
every route, proving the measured difference is line endings, not content.

The route implementations are shared with ``tools/measure-guard/blobread.py``
(IMP-0440), which owns the raw git plumbing; this module never duplicates it.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

try:
    from blob import provenance_bytes as _provenance_bytes
except Exception:  # pragma: no cover - isolated import
    _provenance_bytes = None  # type: ignore[assignment]

REPO = Path(__file__).resolve().parents[2]
_HERE = Path(__file__).resolve()

_MG_PATH = _HERE.parent.parent / "measure-guard" / "blobread.py"


def _load_mg() -> Any:
    spec = importlib.util.spec_from_file_location("_mg_blobread", _MG_PATH)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("_mg_blobread", mod)
    spec.loader.exec_module(mod)
    return mod


_MG = _load_mg()
BlobReadError = _MG.BlobReadError
crlf_count = _MG.crlf_count
lf_normalised = _MG.lf_normalised

FIXTURE_REL = "command-center/p2-wave/probes/TST-0334/fixtures/route-fixture-repo"
CONTROL_NAME = "control.py"
STABLE_NAME = "stable.txt"
KNOWN_LINE_COUNT = 100

_CONTROL_LINES = [
    f"ROUTE-PARITY-FIXTURE line {i:03d} for TST-0334 (committed LF, checked out CRLF)."
    for i in range(1, KNOWN_LINE_COUNT + 1)
]


def content_bytes(path: str | Path) -> bytes:
    p = Path(path)
    if _provenance_bytes is not None:
        try:
            return _provenance_bytes(p)
        except Exception:
            pass
    return p.read_bytes().replace(b"\r\n", b"\n")


def read_blob(path: str, rev: str = "HEAD", *, repo: Path | None = None) -> bytes:
    """Committed blob via git cat-file when the tree is a repo; LF bytes otherwise."""
    root = repo if repo is not None else REPO
    try:
        return _MG.read_blob(path, rev, repo=root)
    except BlobReadError:
        return content_bytes(root / path)


def _git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        check=check,
        text=True,
    )


def _control_blob() -> bytes:
    return ("\n".join(_CONTROL_LINES) + "\n").encode("utf-8")


def _stable_blob() -> bytes:
    return b"stable control: -text attribute, byte-identical on every route\n"


def ensure_fixture(base: Path | None = None) -> Path:
    """Build (or reuse) the deterministic route-parity fixture repository."""
    root = (base or REPO) / FIXTURE_REL
    expected = hashlib.sha256(_control_blob()).hexdigest()
    if (root / ".git").exists():
        try:
            proc = _git(root, "cat-file", "-p", f"HEAD:{CONTROL_NAME}", check=False)
            if proc.returncode == 0 and hashlib.sha256(
                proc.stdout.encode("utf-8", "surrogateescape")
            ).hexdigest() == expected:
                return root
        except OSError:
            pass
    if root.exists():
        shutil.rmtree(root, ignore_errors=True)
    root.mkdir(parents=True)
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "fixture@tst-0334.invalid")
    _git(root, "config", "user.name", "TST-0334 fixture")
    _git(root, "config", "core.autocrlf", "true")
    _git(root, "config", "core.eol", "crlf")
    (root / ".gitattributes").write_text(
        f"{STABLE_NAME} -text\n", encoding="utf-8", newline="\n"
    )
    (root / CONTROL_NAME).write_bytes(_control_blob())
    (root / STABLE_NAME).write_bytes(_stable_blob())
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "TST-0334 route-parity fixture: LF blob, CRLF checkout")
    # Force a REAL smudge checkout so the worktree carries the checkout form
    # (CRLF under autocrlf=true). Hand-written LF files are never re-smudged
    # by git, and a worktree that still holds the blob bytes would silently
    # turn the naive-worktree trap GREEN.
    for name in (CONTROL_NAME, STABLE_NAME):
        (root / name).unlink()
    _git(root, "checkout", "--", CONTROL_NAME, STABLE_NAME)
    proc = _git(root, "cat-file", "-p", f"HEAD:{CONTROL_NAME}", check=False)
    got = hashlib.sha256(proc.stdout.encode("utf-8", "surrogateescape")).hexdigest()
    if got != expected:
        raise BlobReadError(f"fixture blob sha {got[:12]} != expected {expected[:12]}")
    return root


def _route_bytes(repo: Path, name: str) -> tuple[str, bytes]:
    """The committed/worktree bytes of CONTROL_NAME by route name."""
    if name == "git cat-file":
        return _MG.read_blob(CONTROL_NAME, "HEAD", repo=repo)
    if name == "git show":
        proc = subprocess.run(
            ["git", "-C", str(repo), "show", f"HEAD:{CONTROL_NAME}"],
            capture_output=True,
            check=True,
        )
        return proc.stdout
    if name == "worktree":
        return (repo / CONTROL_NAME).read_bytes()
    if name == "git archive":
        proc = subprocess.run(
            ["git", "-C", str(repo), "archive", "--format=tar", "HEAD", CONTROL_NAME],
            capture_output=True,
            check=True,
        )
        payload = _MG._tar_member(proc.stdout, CONTROL_NAME)
        if payload is None:
            raise BlobReadError("archive tar member missing")
        return payload
    raise BlobReadError(f"unknown route {name}")


_ROUTES = ("git archive", "git cat-file", "git show", "worktree")


def _row(path: str, route: str, data: bytes) -> dict[str, Any]:
    lf = lf_normalised(data)
    return {
        "path": path,
        "route": route,
        "bytes": len(data),
        "crlf_count": crlf_count(data),
        "lf_count": lf.count(b"\n"),
        "line_count": lf.count(b"\n"),
        "sha256": hashlib.sha256(data).hexdigest(),
        "sha256_lf": hashlib.sha256(lf).hexdigest(),
    }


def _would_reformat(data: bytes) -> bool:
    """A CRLF-rejecting formatter: CRLF payload means 'would reformat' = RED."""
    return b"\r\n" in data


def live_measure(repo: Path | None = None) -> dict[str, Any]:
    fx = ensure_fixture(repo)

    raw_bytes = {r: _route_bytes(fx, r) for r in _ROUTES}
    byte_table = [_row(CONTROL_NAME, r, raw_bytes[r]) for r in _ROUTES]
    by_route = {row["route"]: row for row in byte_table}
    cat = by_route["git cat-file"]
    arch = by_route["git archive"]
    tree = by_route["worktree"]
    show = by_route["git show"]
    cat_bytes = raw_bytes["git cat-file"]
    arch_bytes = raw_bytes["git archive"]
    tree_bytes = raw_bytes["worktree"]

    stable_rows = []
    for r in _ROUTES:
        if r == "git cat-file":
            data = _MG.read_blob(STABLE_NAME, "HEAD", repo=fx)
        elif r == "git show":
            data = subprocess.run(
                ["git", "-C", str(fx), "show", f"HEAD:{STABLE_NAME}"],
                capture_output=True,
                check=True,
            ).stdout
        elif r == "worktree":
            data = (fx / STABLE_NAME).read_bytes()
        else:
            proc = subprocess.run(
                ["git", "-C", str(fx), "archive", "--format=tar", "HEAD", STABLE_NAME],
                capture_output=True,
                check=True,
            )
            payload = _MG._tar_member(proc.stdout, STABLE_NAME)
            if payload is None:
                raise BlobReadError("stable archive member missing")
            data = payload
        stable_rows.append(_row(STABLE_NAME, r, data))
    stable_shas = {row["sha256"] for row in stable_rows}

    lf_shas = {row["sha256_lf"] for row in byte_table}
    blob_sha = cat["sha256"]
    local = content_bytes(fx / CONTROL_NAME)
    local_sha = hashlib.sha256(local).hexdigest()

    gates = {
        "hash_ci_blob": {
            "verdict": "GREEN",
            "sha256": blob_sha,
            "route": "git cat-file",
        },
        "hash_naive_worktree": {
            "verdict": "GREEN" if tree["sha256"] == blob_sha else "RED",
            "sha256": tree["sha256"],
            "route": "worktree",
        },
        "hash_blobread_local": {
            "verdict": "GREEN" if local_sha == blob_sha else "RED",
            "sha256": local_sha,
            "route": "content_bytes",
        },
        "format_ci_blob": {
            "verdict": "RED" if _would_reformat(cat_bytes) else "GREEN",
            "route": "git cat-file",
        },
        "format_archive": {
            "verdict": "RED" if _would_reformat(arch_bytes) else "GREEN",
            "route": "git archive",
        },
        "format_naive_worktree": {
            "verdict": "RED" if _would_reformat(tree_bytes) else "GREEN",
            "route": "worktree",
        },
        "format_blobread_local": {
            "verdict": "RED" if _would_reformat(local) else "GREEN",
            "route": "content_bytes",
        },
    }
    parity = {
        "local_blobread_matches_ci": local_sha == blob_sha,
        "naive_worktree_differs_from_ci": tree["sha256"] != blob_sha,
    }
    return {
        "fixture_repo": str(fx),
        "byte_table": byte_table,
        "eol_normalisation": {
            "routes_identical_after_lf": len(lf_shas) == 1,
            "sha256_after_lf": cat["sha256_lf"],
            "method": "replace CRLF then CR with LF",
            "only_variable_is_line_endings": len(lf_shas) == 1,
        },
        "cat_file_equals_git_show": show["sha256"] == cat["sha256"],
        "stable_routes_byte_identical": len(stable_shas) == 1,
        "stable_table": stable_rows,
        "content_bytes_route": "git cat-file",
        "gates": gates,
        "parity": parity,
    }


def main(argv: list[str] | None = None) -> int:  # pragma: no cover - CLI entry
    doc = live_measure()
    print(json.dumps(doc, indent=1))
    print("SUCCESS:blobread live three-route measurement")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
