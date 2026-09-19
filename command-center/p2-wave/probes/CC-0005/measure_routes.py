#!/usr/bin/env python3
"""CC-0005 probe: measure git cat-file vs worktree vs archive; plant CRLF control.

Emits JSON to stdout. Writes companion files under the probe directory when
``--write-dir`` is set. Honest about Linux vs Windows archive behaviour
(Windows-scoped trap documented in tools/measure-guard/blobread.py).
"""

from __future__ import annotations

import hashlib
import io
import json
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
BLOBREAD = REPO / "tools/measure-guard/blobread.py"
REGISTER = "command-center/sources/REGISTER.md"


def _sha12(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:12]


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _tar_member(stream: bytes, path: str) -> bytes | None:
    with tarfile.open(fileobj=io.BytesIO(stream), mode="r:") as tar:
        wanted = path.replace("\\", "/")
        for member in tar.getmembers():
            if member.name == wanted or member.name.endswith("/" + wanted):
                handle = tar.extractfile(member)
                return handle.read() if handle else None
    return None


def live_repo_routes(path: str = REGISTER) -> dict:
    """Three-route comparison on the live checkout (Linux: archive often == blob)."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("cc0005_blobread", BLOBREAD)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {BLOBREAD}")
    blobread = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(blobread)

    report = blobread.three_route_comparison(path, "HEAD", repo=REPO)
    report["platform_note"] = (
        "On stock Linux, git archive often returns the blob unchanged; the CRLF "
        "archive trap is Windows-scoped (core.autocrlf / export-time conversion). "
        "See rules/common/windows-shell.md §8b and blobread.py module docstring."
    )
    report["historic_windows_pair"] = {
        "blob_sha12": "8b3e44cc3813",
        "crlf_worktree_sha12": "1a404a91d819",
        "source": "command-center/WORK-UNIT-CATALOG.json#CC-0005 inputs",
    }
    return report


def planted_crlf_control() -> dict:
    """Throwaway repo: commit LF, plant CRLF worktree, measure routes + byte delta."""
    lf = b"line-one\nline-two\nline-three\nline-four\n"
    crlf = lf.replace(b"\n", b"\r\n")
    line_count = lf.count(b"\n")
    delta = len(crlf) - len(lf)
    rel = "command-center/sources/REGISTER.md"

    with tempfile.TemporaryDirectory(prefix="cc0005-") as td:
        root = Path(td)
        subprocess.run(["git", "init", "-q", str(root)], check=True, capture_output=True)
        for args in (
            ["config", "user.email", "probe@t"],
            ["config", "user.name", "probe"],
        ):
            subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)
        target = root / rel
        target.parent.mkdir(parents=True)
        target.write_bytes(lf)
        subprocess.run(
            ["git", "-C", str(root), "add", rel], check=True, capture_output=True
        )
        subprocess.run(
            ["git", "-C", str(root), "commit", "-q", "-m", "lf"],
            check=True,
            capture_output=True,
        )
        # Plant CRLF worktree (Windows autocrlf shape).
        target.write_bytes(crlf)

        cat = subprocess.run(
            ["git", "-C", str(root), "cat-file", "-p", f"HEAD:{rel}"],
            capture_output=True,
            check=True,
        ).stdout
        show = subprocess.run(
            ["git", "-C", str(root), "show", f"HEAD:{rel}"],
            capture_output=True,
            check=True,
        ).stdout
        archive_proc = subprocess.run(
            ["git", "-C", str(root), "archive", "--format=tar", "HEAD", rel],
            capture_output=True,
            check=True,
        )
        archive_payload = _tar_member(archive_proc.stdout, rel) or b""
        wt = target.read_bytes()

        # Gate simulation: BEFORE hashes raw worktree; AFTER hashes cat-file blob.
        recorded = _sha(lf)
        before_digest = _sha(wt)
        after_digest = _sha(cat)
        before_exit = 0 if before_digest == recorded else 1
        after_exit = 0 if after_digest == recorded else 1

        return {
            "fixture": {
                "rel": rel,
                "lf_bytes": len(lf),
                "crlf_bytes": len(crlf),
                "line_count": line_count,
                "byte_delta": delta,
                "byte_delta_equals_line_count": delta == line_count,
            },
            "routes": {
                "git_cat_file": {
                    "bytes": len(cat),
                    "crlf": cat.count(b"\r\n"),
                    "sha256_12": _sha12(cat),
                    "sha256": _sha(cat),
                },
                "git_show": {
                    "bytes": len(show),
                    "crlf": show.count(b"\r\n"),
                    "sha256_12": _sha12(show),
                },
                "working_tree": {
                    "bytes": len(wt),
                    "crlf": wt.count(b"\r\n"),
                    "sha256_12": _sha12(wt),
                    "sha256": _sha(wt),
                },
                "git_archive": {
                    "bytes": len(archive_payload),
                    "crlf": archive_payload.count(b"\r\n"),
                    "sha256_12": _sha12(archive_payload),
                    "note": (
                        "On this Linux probe host archive often equals blob; "
                        "Windows archive returns CRLF (blobread measured 3837/100)."
                    ),
                },
            },
            "gate_simulation": {
                "recorded_blob_sha256": recorded,
                "before_worktree_raw_sha256": before_digest,
                "after_cat_file_sha256": after_digest,
                "before_exit_code": before_exit,
                "after_exit_code": after_exit,
                "before_fires_on_crlf": before_exit != 0,
                "after_silent_on_crlf": after_exit == 0,
            },
            "controls": {
                "cat_file_equals_show": cat == show,
                "cat_file_equals_lf_body": cat == lf,
                "worktree_differs_from_blob": wt != cat,
                "worktree_lf_norm_equals_blob": wt.replace(b"\r\n", b"\n") == cat,
            },
        }


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--write-dir",
        default="",
        help="directory to write live-routes.json + planted-control.json + raw txt",
    )
    args = parser.parse_args(argv)

    live = live_repo_routes()
    planted = planted_crlf_control()
    doc = {
        "unit": "CC-0005",
        "probe": "manifest-provenance-git-blob-hash",
        "live_repo": live,
        "planted_crlf_control": planted,
        "verdict": (
            "PASS-controls"
            if (
                planted["fixture"]["byte_delta_equals_line_count"]
                and planted["gate_simulation"]["before_fires_on_crlf"]
                and planted["gate_simulation"]["after_silent_on_crlf"]
                and planted["controls"]["worktree_differs_from_blob"]
            )
            else "FAIL-controls"
        ),
    }
    text = json.dumps(doc, indent=2) + "\n"
    sys.stdout.write(text)

    if args.write_dir:
        out = Path(args.write_dir)
        out.mkdir(parents=True, exist_ok=True)
        (out / "probe-results.json").write_text(text, encoding="utf-8")
        (out / "probe-results.raw.txt").write_text(text, encoding="utf-8")
        (out / "live-routes.json").write_text(
            json.dumps(live, indent=2) + "\n", encoding="utf-8"
        )
        (out / "planted-control.json").write_text(
            json.dumps(planted, indent=2) + "\n", encoding="utf-8"
        )
        summary = (
            f"CC-0005 probe verdict={doc['verdict']}\n"
            f"byte_delta={planted['fixture']['byte_delta']} "
            f"line_count={planted['fixture']['line_count']}\n"
            f"before_exit={planted['gate_simulation']['before_exit_code']} "
            f"after_exit={planted['gate_simulation']['after_exit_code']}\n"
            f"live_register_cat_file_sha12="
            f"{live.get('routes', {}).get('git_cat_file', {}).get('sha256_12')}\n"
        )
        (out / "summary.txt").write_text(summary, encoding="utf-8")

    return 0 if doc["verdict"] == "PASS-controls" else 1


if __name__ == "__main__":
    raise SystemExit(main())
