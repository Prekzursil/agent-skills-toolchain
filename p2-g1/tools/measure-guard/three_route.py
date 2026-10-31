"""Three-route blob vs archive comparison for IMP-0440."""
from __future__ import annotations

import subprocess
from pathlib import Path

import blobread as B


def _run(root: Path, args: list[str]) -> bytes:
    p = subprocess.run(["git", "-C", str(root), *args], capture_output=True, check=False)
    if p.returncode != 0:
        raise RuntimeError(p.stderr.decode("utf-8", "replace")[:400])
    return p.stdout


def three_route(root: str | Path, path: str, rev: str = "HEAD") -> dict:
    root = Path(root)
    helper = B.blob_bytes(rev, path, repo=root)
    cat = B.read_blob(path, rev, repo=root)
    show = _run(root, ["show", f"{rev}:{path.replace(chr(92), '/')}"])
    archive = _run(root, ["archive", "--format=tar", rev, path])
    extracted = B._tar_member(archive, path) or b""
    routes = {
        "git archive + tar -x": {
            "bytes": len(extracted),
            "crlf": B.crlf_count(extracted),
        },
        "blob_bytes helper": {
            "bytes": len(helper),
            "crlf": B.crlf_count(helper),
        },
        "git cat-file -p": {
            "bytes": len(cat),
            "crlf": B.crlf_count(cat),
        },
        "git show": {
            "bytes": len(show),
            "crlf": B.crlf_count(show),
        },
    }
    norms = {
        "archive": B.digest(B.lf_normalised(extracted)),
        "helper": B.digest(B.lf_normalised(helper)),
        "cat": B.digest(B.lf_normalised(cat)),
        "show": B.digest(B.lf_normalised(show)),
    }
    return {
        "path": path,
        "rev": rev,
        "archive_differs_from_blob": extracted != helper,
        "helper_equals_cat_file": helper == cat,
        "cat_file_equals_show": cat == show,
        "identical_after_lf_normalisation": len(set(norms.values())) == 1,
        "routes": routes,
        "helper_bytes": helper,
    }


__all__ = ["three_route"]
