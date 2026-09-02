"""Independent secret scanner: GNU grep -f against unpacked artifact bytes.

Never prints matched secret text. Known-broken control uses Amazon's documented
example access-key *pattern* (AKIA + 16 A-Z0-9), not a live credential.
"""
from __future__ import annotations

import gzip
import io
import tarfile
from pathlib import Path

from tools import GREP, run

# Pattern ids only. The planted control uses a well-known AWS documentation
# example shape; grep output is not echoed.
PATTERN_FILE_NAME = "secret-patterns.txt"
PATTERNS = """\
AKIA[0-9A-Z]{16}
-----BEGIN (RSA |OPENSSH |EC |DSA )?PRIVATE KEY-----
xox[baprs]-[A-Za-z0-9-]{10,}
sk-proj-[A-Za-z0-9]{20,}
Bearer [A-Za-z0-9._\\-]{24,}
(aws_secret_access_key|api_key|apikey)[[:space:]]*[=:][[:space:]]*[^[:space:]]+
"""

# Amazon documentation example access-key *id shape* (not a live key).
PLANTED_EXAMPLE = "AKIAIOSFODNN7EXAMPLE"


def write_pattern_file(path: Path) -> Path:
    path.write_text(PATTERNS, encoding="utf-8")
    return path


def unpack_artifact(artifact: Path, dest: Path) -> Path:
    dest.mkdir(parents=True, exist_ok=True)
    raw = gzip.decompress(artifact.read_bytes())
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:") as tf:
        tf.extractall(dest, filter="data")
    return dest


def grep_scan(root: Path, pattern_file: Path) -> tuple[bool, int, str]:
    """Return (hits, rc, summary_without_match_text)."""
    p = run(
        [
            GREP,
            "-aREn",
            "-f",
            str(pattern_file),
            str(root),
        ]
    )
    # grep: 0=match, 1=no match, 2=error
    if p.returncode not in (0, 1):
        return False, p.returncode, f"grep-error rc={p.returncode}"
    lines = [ln for ln in (p.stdout or "").splitlines() if ln.strip()]
    # Do not keep matched text. Count hits only.
    hits = len(lines)
    found = p.returncode == 0
    return found, p.returncode, f"hits={hits} rc={p.returncode}"


def plant_example(root: Path) -> Path:
    planted = root / "planted-example.txt"
    planted.write_text(
        f"documentation-example-id={PLANTED_EXAMPLE}\n", encoding="utf-8"
    )
    return planted
