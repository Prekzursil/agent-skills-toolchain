"""Read a tracked path as the COMMITTED BLOB, not as the Windows working tree.

TST-0334's target, quoted: "on this box the working tree is CRLF and the committed blob is LF, and
formatters, hash gates and content assertions can decide differently on the two. The measured trap
is worse than it sounds: git archive returns the CRLF worktree bytes, so the recipe most people
reach for verifies the wrong bytes."

Ledger evidence for why this is not theoretical: `uvx ruff format --check` reported "1 file already
formatted" locally while CI reported "Would reformat" for the SAME COMMIT, because ruff made a
different decision on the LF form of `hooks/stopfailure-notify/notify.py`. The local green was
measured against bytes CI never sees, so it verified nothing.

`git archive` is the trap and is REFUSED here rather than merely avoided. `rules/common/windows-shell.md`
section 8b prescribed it until 2026-08-09 and was wrong: it applies export-time EOL conversion and
hands back CRLF on this box. Measured on one file, three routes, with a control proving all three
are byte-identical after LF normalisation (so the difference is line endings, not content):

    git archive (member EXTRACTED)  3,837 bytes   100 CRLF
    working tree                    3,837 bytes   100 CRLF
    git cat-file -p                 3,737 bytes     0 CRLF
    git show <rev>:<path>           3,737 bytes     0 CRLF

The archive payload matches the WORKING TREE byte for byte, which is the whole point: `git archive`
hands back the checkout form, not the blob. Independently re-measured by extracting the tar member
with stdlib `tarfile`, and the extracted payload carries all 100 CRLF while 0 originate outside it.

A rule that tells you to verify against the wrong bytes is worse than no rule, because it
manufactures confidence in the exact check meant to catch this class.
"""

from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


class BlobReadError(RuntimeError):
    """The path is not in the given revision, or git refused."""


def read_blob(path: str, rev: str = "HEAD", *, repo: Path | None = None) -> bytes:
    """The committed bytes of `path` at `rev` - what a Linux runner checks out.

    Uses `git cat-file -p`. Forward slashes only and no `--`-less revision juggling: a Windows
    backslash path is not a valid git pathspec, and `MSYS_NO_PATHCONV` games are avoided entirely by
    never letting a shell see the argument.
    """
    proc = subprocess.run(
        [
            "git",
            "-C",
            str(repo or REPO),
            "cat-file",
            "-p",
            f"{rev}:{path.replace(chr(92), '/')}",
        ],
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        raise BlobReadError(
            f"{path!r} is not readable at {rev!r}: "
            f"{proc.stderr.decode('utf-8', 'replace').strip()[:200]}"
        )
    return proc.stdout


def _tar_member(stream: bytes, path: str) -> bytes | None:
    """The payload of `path` inside an uncompressed tar stream, or None if absent.

    Uses stdlib `tarfile` rather than hand-walking 512-byte headers. An earlier comment here
    claimed the header-block walk was implemented when the code in fact stored the whole stream -
    a false comment inside a module whose entire thesis is "verify the bytes you think you are
    verifying", which is the defect class it indicts. Implemented for real instead of re-worded.
    """
    import io
    import tarfile

    try:
        with tarfile.open(fileobj=io.BytesIO(stream), mode="r:") as tar:
            wanted = path.replace("\\", "/")
            for member in tar.getmembers():
                if member.name == wanted or member.name.endswith("/" + wanted):
                    handle = tar.extractfile(member)
                    return handle.read() if handle else None
    except (tarfile.TarError, OSError):
        return None
    return None


def crlf_count(data: bytes) -> int:
    return data.count(b"\r\n")


def lf_normalised(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n")


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:12]


def three_route_comparison(
    path: str, rev: str = "HEAD", *, repo: Path | None = None
) -> dict:
    """The evidence TST-0334 demands: byte counts and CRLF counts from all three routes.

    Includes the control the spec asks for - that the three are byte-identical AFTER LF
    normalisation - because without it a reader cannot tell whether the divergence measured is line
    endings or genuinely different content.
    """
    root = repo or REPO
    routes: dict[str, bytes] = {}

    routes["git_cat_file"] = read_blob(path, rev, repo=root)

    show = subprocess.run(
        ["git", "-C", str(root), "show", f"{rev}:{path}"],
        capture_output=True,
        check=False,
    )
    if show.returncode == 0:
        routes["git_show"] = show.stdout

    worktree = root / path
    if worktree.is_file():
        routes["working_tree"] = worktree.read_bytes()

    # git archive: the route this module exists to refuse. Measured, not asserted, so the refusal
    # is evidence-backed rather than folklore.
    #
    # `--format=tar` is PINNED and the member is EXTRACTED. An earlier version stored the whole
    # stream and counted CRLF across the container, which an independent review showed to be both
    # mis-commented and fragile: `--format=tar.gz` and `--format=zip` both yield 0 CRLF at the
    # container level, so a format change would silently INVERT this reading into "git archive is
    # LF-clean" - a false negative in the exact check this module exists to provide. Counting the
    # real payload removes the dependence entirely.
    archive = subprocess.run(
        ["git", "-C", str(root), "archive", "--format=tar", rev, path],
        capture_output=True,
        check=False,
    )
    if archive.returncode == 0 and archive.stdout:
        payload = _tar_member(archive.stdout, path)
        if payload is not None:
            routes["git_archive"] = payload

    report = {
        "path": path,
        "rev": rev,
        "routes": {
            name: {
                "bytes": len(data),
                "crlf": crlf_count(data),
                "sha256_12": digest(data),
            }
            for name, data in routes.items()
        },
    }
    # EVERY route is in the control now, git_archive included. It was previously excluded, which
    # left the one route this module exists to indict as the only route with no content control -
    # so a genuine content difference in the archive payload would have gone unnoticed.
    normalised = {k: digest(lf_normalised(v)) for k, v in routes.items()}
    report["control_identical_after_lf_normalisation"] = (
        len(set(normalised.values())) == 1
    )
    report["lf_normalised_digests"] = normalised
    report["verdict"] = (
        "the routes differ ONLY in line endings"
        if report["control_identical_after_lf_normalisation"]
        else "the routes differ in CONTENT, not just line endings - investigate before trusting any"
    )
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("path")
    parser.add_argument("--rev", default="HEAD")
    parser.add_argument(
        "--compare", action="store_true", help="emit the three-route report"
    )
    args = parser.parse_args(argv)

    try:
        if args.compare:
            import json

            report = three_route_comparison(args.path, args.rev)
            print(json.dumps(report, indent=2))
            print(f"SUCCESS:blobread three-route report for {args.path}")
            return 0
        data = read_blob(args.path, args.rev)
    except BlobReadError as exc:
        print(f"FAILED:blobread {exc}")
        return 1
    sys.stdout.buffer.write(data)
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry
    raise SystemExit(main())
