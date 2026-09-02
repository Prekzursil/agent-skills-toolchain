"""Two-tree rules comparison using IMP-0035 EOL-normalised hashing."""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from paths import LIVE_RULES, REPO, REPO_RULES

sys.path.insert(0, str(REPO / "tools" / "plugin"))
import eol_hash as EH  # noqa: E402


def iter_rels(root: Path) -> dict[str, Path]:
    out: dict[str, Path] = {}
    if not root.is_dir():
        return out
    for p in root.rglob("*"):
        if p.is_file():
            out[p.relative_to(root).as_posix()] = p
    return out


def lines_of(data: bytes) -> list[str]:
    text = EH.bytes_for_hash(data).decode("utf-8")
    parts = text.split("\n")
    if parts and parts[-1] == "":
        parts = parts[:-1]
    return parts


def line_set(data: bytes) -> set[str]:
    return set(lines_of(data))


def content_shape(repo: bytes, live: bytes) -> str:
    """Subdivide DIVERGED pairs. Never uses byte length."""
    rs, ls = line_set(repo), line_set(live)
    if rs == ls:
        return "LINESET-EQUAL"
    if rs < ls:
        return "LIVE-SUPERSET"
    if ls < rs:
        return "REPO-SUPERSET"
    return "BOTH-UNIQUE"


def classify_pair(repo: bytes, live: bytes) -> dict:
    eol_cls = EH.classify_pair(repo, live)
    rec = {
        "eol_class": eol_cls,
        "repo_bytes": len(repo),
        "live_bytes": len(live),
        "size_delta_live_minus_repo": len(live) - len(repo),
        "repo_sha_raw": EH.sha256_raw(repo),
        "live_sha_raw": EH.sha256_raw(live),
        "repo_sha_norm": EH.sha256_normalised(repo),
        "live_sha_norm": EH.sha256_normalised(live),
        "repo_unique_lines": [],
        "live_unique_lines": [],
        "shape": "IDENTICAL",
    }
    if eol_cls == EH.IDENTICAL:
        rec["shape"] = "IDENTICAL"
        return rec
    if eol_cls == EH.IDENTICAL_MODULO_EOL:
        rec["shape"] = "IDENTICAL-MODULO-EOL"
        return rec
    rs, ls = line_set(repo), line_set(live)
    rec["repo_unique_lines"] = sorted(rs - ls)
    rec["live_unique_lines"] = sorted(ls - rs)
    rec["shape"] = content_shape(repo, live)
    rec["eol_class"] = "CONTENT-DIVERGED"
    return rec


def census(repo_root: Path | None = None, live_root: Path | None = None) -> dict:
    repo_root = repo_root or REPO_RULES
    live_root = live_root or LIVE_RULES
    repo = iter_rels(repo_root)
    live = iter_rels(live_root)
    keys = sorted(set(repo) | set(live))
    rows = []
    counts = {
        "files": len(keys),
        "identical": 0,
        "identical_modulo_eol": 0,
        "content_diverged": 0,
        "live_superset": 0,
        "repo_superset": 0,
        "both_unique": 0,
        "repo_only": 0,
        "live_only": 0,
        "live_larger_bytes": 0,
        "repo_larger_bytes": 0,
    }
    for rel in keys:
        rp, lp = repo.get(rel), live.get(rel)
        row = {"path": rel}
        if rp is None or lp is None:
            row["shape"] = "LIVE-ONLY" if rp is None else "REPO-ONLY"
            counts["live_only" if rp is None else "repo_only"] += 1
            counts["content_diverged"] += 1
            rows.append(row)
            continue
        rec = classify_pair(rp.read_bytes(), lp.read_bytes())
        row.update(rec)
        if rec["shape"] == "IDENTICAL":
            counts["identical"] += 1
        elif rec["shape"] == "IDENTICAL-MODULO-EOL":
            counts["identical_modulo_eol"] += 1
        else:
            counts["content_diverged"] += 1
            if rec["shape"] == "LIVE-SUPERSET":
                counts["live_superset"] += 1
            elif rec["shape"] == "REPO-SUPERSET":
                counts["repo_superset"] += 1
            else:
                counts["both_unique"] += 1
        if rec["size_delta_live_minus_repo"] > 0:
            counts["live_larger_bytes"] += 1
        elif rec["size_delta_live_minus_repo"] < 0:
            counts["repo_larger_bytes"] += 1
        rows.append(row)
    return {"repo_root": str(repo_root), "live_root": str(live_root), "counts": counts, "rows": rows}
