"""Independent line-set differ (does not import classify_pair)."""
from __future__ import annotations

import hashlib
from pathlib import Path


IDENTICAL = "IDENTICAL"
IDENTICAL_MODULO_EOL = "IDENTICAL-MODULO-EOL"
REPO_AHEAD = "REPO-AHEAD"
LIVE_AHEAD = "LIVE-AHEAD"
DIVERGED = "DIVERGED"


def _as_bytes(data) -> bytes:
    if data is None:
        return b""
    if isinstance(data, bytes):
        return data
    if isinstance(data, bytearray):
        return bytes(data)
    if isinstance(data, str):
        return data.encode("utf-8")
    return bytes(data)


def _sha(data: bytes) -> str:
    return hashlib.sha256(_as_bytes(data)).hexdigest()


def _lines(data: bytes) -> list[bytes]:
    return _norm(data).split(b"\n")


def _norm(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def classify_pair_independent(repo_b: bytes | None, live_b: bytes | None) -> dict:
    rb = _as_bytes(repo_b)
    lb = _as_bytes(live_b)
    return {
        "classification": classify_independent(rb, lb),
        "repo_sha256": _sha(rb),
        "live_sha256": _sha(lb),
    }


def unique_line_sets_via_hash(repo_text: str, live_text: str) -> tuple[set[str], set[str]]:
    def hashed(text: str) -> dict[str, str]:
        out: dict[str, str] = {}
        for line in (text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n"):
            digest = hashlib.blake2s(line.encode("utf-8"), digest_size=16).hexdigest()
            out.setdefault(digest, line)
        return out

    rh = hashed(repo_text)
    lh = hashed(live_text)
    ru = {rh[h] for h in rh.keys() - lh.keys()}
    lu = {lh[h] for h in lh.keys() - rh.keys()}
    return ru, lu


def classify_independent(repo_b: bytes, live_b: bytes) -> str:
    repo_b = _as_bytes(repo_b)
    live_b = _as_bytes(live_b)
    if _sha(repo_b) == _sha(live_b):
        return IDENTICAL
    if _sha(_norm(repo_b)) == _sha(_norm(live_b)):
        return IDENTICAL_MODULO_EOL
    rl = _lines(repo_b)
    ll = _lines(live_b)
    rs = sorted(rl)
    ls = sorted(ll)
    i = j = 0
    only_r = only_l = False
    while i < len(rs) and j < len(ls):
        if rs[i] == ls[j]:
            i += 1
            j += 1
        elif rs[i] < ls[j]:
            only_r = True
            i += 1
        else:
            only_l = True
            j += 1
    if i < len(rs):
        only_r = True
    if j < len(ls):
        only_l = True
    if only_r and only_l:
        return DIVERGED
    if only_r:
        return REPO_AHEAD
    if only_l:
        return LIVE_AHEAD
    return IDENTICAL_MODULO_EOL


def classify_trees_independent(repo_root: Path | str, live_root: Path | str) -> list[dict]:
    repo = Path(repo_root)
    live = Path(live_root)

    def files(root: Path) -> dict[str, Path]:
        out = {}
        if root.is_dir():
            for p in root.rglob("*"):
                if p.is_file():
                    out[p.relative_to(root).as_posix()] = p
        return out

    a, b = files(repo), files(live)
    rows = []
    for rel in sorted(set(a) | set(b)):
        rb = a[rel].read_bytes() if rel in a else b""
        lb = b[rel].read_bytes() if rel in b else b""
        if rel not in a:
            klass = LIVE_AHEAD
        elif rel not in b:
            klass = REPO_AHEAD
        else:
            klass = classify_independent(rb, lb)
        rows.append({"path": rel, "classification": klass})
    return rows
