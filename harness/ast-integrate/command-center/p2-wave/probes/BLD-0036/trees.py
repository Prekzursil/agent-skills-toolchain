#!/usr/bin/env python3
"""Host-tree search plus a catalog-shaped 88-file fixture pair.

This Linux worktree may have a repo `rules/` tree; live `~/.claude/rules`
is absent. ADV-0017 is consumed, not rebuilt. The catalog-pinned detection
shape (5 identical / 55 EOL-only / 28 content-differing = 25 repo-larger +
3 named live-larger) is encoded as fixtures. This unit contributes per-file
authority plus a merge plan, which detection cannot supply.

Generated trees live only under probes/BLD-0036/fixtures/. Host trees are
never created or mutated.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
FIX = HERE / "fixtures"
REPO_ROOT = FIX / "repo"
LIVE_ROOT = FIX / "live"
LEDGER_PATH = FIX / "repo-committer-ledger.json"

PLANTED = "rules/planted/two-directional.md"
OWNER_OPS = "rules/common/owner-ops-authorization.md"
PERFORMANCE = "rules/common/performance.md"
SECURITY = "rules/common/security.md"
LIVE_LARGER = (OWNER_OPS, PERFORMANCE, SECURITY)

IDENTICAL_N = 5
EOL_N = 55
REPO_SUPERSET_N = 24
# 24 repo-superset + 1 planted both-unique = 25 repo-larger
# + 3 live-larger = 28 content-differing
# + 5 identical + 55 eol = 88


def host_candidates() -> list[dict]:
    rows = []
    for p in (
        REPO / "rules",
        Path.home() / ".claude",
        Path.home() / ".claude" / "rules",
        Path.home() / ".claude",
        Path.home() / ".claude" / "rules",
        Path.home() / ".cursor" / "rules",
    ):
        rows.append(
            {
                "path": str(p),
                "exists": p.exists(),
                "is_dir": p.is_dir(),
                "file_count": (
                    sum(1 for q in p.rglob("*") if q.is_file()) if p.is_dir() else 0
                ),
            }
        )
    return rows


def _wipe(root: Path) -> None:
    if not root.exists():
        return
    for p in sorted(root.rglob("*"), reverse=True):
        if p.is_file():
            p.unlink()
        elif p.is_dir():
            try:
                p.rmdir()
            except OSError:
                pass


def _write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def _write_lf(path: Path, text: str) -> None:
    if not text.endswith("\n"):
        text += "\n"
    _write_bytes(path, text.encode("utf-8"))


def _live_block(tag: str, n_bytes: int) -> str:
    """Policy lines plus exact-size filler so live-minus-repo matches the pin."""
    if n_bytes < 1:
        return ""
    parts: list[str] = []
    used = 0
    i = 0
    while True:
        i += 1
        line = (
            f"LIVE-ONLY {tag} policy: unique live behaviour; a one-directional "
            f"repo-over-live Copy-Item would drop this. #{i}\n"
        )
        lb = len(line.encode("utf-8"))
        if used + lb > n_bytes:
            break
        parts.append(line)
        used += lb
        if used == n_bytes:
            return "".join(parts)
    remain = n_bytes - used
    if remain <= 0:
        return "".join(parts)
    return "".join(parts) + ("x" * remain)


def _delta_pair(
    shared: str, repo_extra: str, live_head: str, live_minus_repo: int
) -> tuple[str, str]:
    repo = shared + repo_extra
    live_prefix = shared + live_head
    pad_n = live_minus_repo - len(live_prefix.encode("utf-8")) + len(repo.encode("utf-8"))
    if pad_n < 0:
        raise SystemExit(
            f"BLD-0036 fixture delta too small: pad_n={pad_n} tag={live_head[:40]!r}"
        )
    tag = live_head.split()[0] if live_head.split() else "live"
    live = live_prefix + _live_block(tag, pad_n)
    if len(live.encode("utf-8")) - len(repo.encode("utf-8")) != live_minus_repo:
        raise SystemExit("BLD-0036 fixture byte-delta mismatch")
    return repo, live


def build_fixtures() -> dict:
    _wipe(REPO_ROOT)
    _wipe(LIVE_ROOT)
    REPO_ROOT.mkdir(parents=True, exist_ok=True)
    LIVE_ROOT.mkdir(parents=True, exist_ok=True)
    ledger: dict[str, str] = {}

    identical = [f"rules/identical/file-{i:02d}.md" for i in range(IDENTICAL_N)]
    eol = [f"rules/eol/file-{i:02d}.md" for i in range(EOL_N)]
    repo_superset = [f"rules/repo-larger/file-{i:02d}.md" for i in range(REPO_SUPERSET_N)]

    for rel in identical:
        body = f"# {rel}\nidentical body for both trees\nbyte-identical control\n"
        _write_lf(REPO_ROOT / rel, body)
        _write_lf(LIVE_ROOT / rel, body)
        ledger[rel] = "2026-06-15T12:00:00Z"

    for i, rel in enumerate(eol):
        body = f"# {rel}\nshared body after LF normalisation\nline {i}\n"
        _write_lf(REPO_ROOT / rel, body)
        crlf = body.replace("\n", "\r\n").encode("utf-8")
        _write_bytes(LIVE_ROOT / rel, crlf)
        ledger[rel] = "2026-06-16T12:00:00Z"

    for i, rel in enumerate(repo_superset):
        live = f"# {rel}\nshared prefix\n"
        repo = live + f"REPO-ONLY unique behaviour line {i}.\n" + ("repo extra\n" * (i + 1))
        _write_lf(LIVE_ROOT / rel, live)
        _write_lf(REPO_ROOT / rel, repo)
        ledger[rel] = "2026-08-05T08:00:00Z"

    planted_live = (
        "# planted two-directional control\n"
        "shared prefix\n"
        "LIVE-ONLY unique behaviour: session-local allowlist.\n"
    )
    planted_repo = (
        "# planted two-directional control\n"
        "shared prefix\n"
        "REPO-ONLY unique behaviour: squash-merge detector pin.\n"
        + ("repo padding line to keep this file repo-larger\n" * 4)
    )
    if len(planted_repo.encode()) <= len(planted_live.encode()):
        raise SystemExit("planted control is not repo-larger")
    _write_lf(REPO_ROOT / PLANTED, planted_repo)
    _write_lf(LIVE_ROOT / PLANTED, planted_live)
    ledger[PLANTED] = "2026-08-04T09:00:00Z"

    shared_auth = (
        "# Owner ops authorization\n"
        "H1. Do not mutate git history.\n"
        "H2. Do not print secrets.\n"
        "H3. Fail closed on missing evidence.\n"
    )
    auth_repo, auth_live = _delta_pair(
        shared_auth,
        "REPO-ONLY: reconstructed catalog pin; do not drop on a live-to-repo copy.\n",
        "LIVE-ONLY: additional hard bans observed as live-ahead.\n",
        1001,
    )
    _write_bytes(REPO_ROOT / OWNER_OPS, auth_repo.encode("utf-8"))
    _write_bytes(LIVE_ROOT / OWNER_OPS, auth_live.encode("utf-8"))
    ledger[OWNER_OPS] = "2026-07-11T15:02:00Z"

    shared_perf = "# Performance\nPrefer incremental scans.\nAvoid full-tree reread on each probe.\n"
    perf_repo, perf_live = _delta_pair(
        shared_perf,
        "",
        "LIVE-ONLY performance: cache scan results across probes.\n",
        178,
    )
    _write_bytes(REPO_ROOT / PERFORMANCE, perf_repo.encode("utf-8"))
    _write_bytes(LIVE_ROOT / PERFORMANCE, perf_live.encode("utf-8"))
    ledger[PERFORMANCE] = "2026-07-18T09:41:00Z"

    shared_sec = "# Security\nNo wildcard tool grants.\nRe-validate declarations after edit.\n"
    sec_repo, sec_live = _delta_pair(
        shared_sec,
        "",
        "LIVE-ONLY security: deny wildcard tool grants in live sessions.\n",
        97,
    )
    _write_bytes(REPO_ROOT / SECURITY, sec_repo.encode("utf-8"))
    _write_bytes(LIVE_ROOT / SECURITY, sec_live.encode("utf-8"))
    ledger[SECURITY] = "2026-07-20T11:08:00Z"

    live_base = datetime(2026, 8, 9, 16, 0, 0, tzinfo=timezone.utc).timestamp()
    repo_base = datetime(2026, 6, 1, 8, 0, 0, tzinfo=timezone.utc).timestamp()
    all_rels = identical + eol + repo_superset + [PLANTED, OWNER_OPS, PERFORMANCE, SECURITY]
    for i, rel in enumerate(all_rels):
        rp, lp = REPO_ROOT / rel, LIVE_ROOT / rel
        rt = repo_base + i * 60
        lt = live_base + i * 60
        import os

        os.utime(rp, (rt, rt))
        os.utime(lp, (lt, lt))

    LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
    LEDGER_PATH.write_text(json.dumps(ledger, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    counts = _count_shape()
    expected = {
        "union_files": 88,
        "identical": IDENTICAL_N,
        "eol_only": EOL_N,
        "content_differing": 28,
        "repo_larger": 25,
        "live_larger": 3,
    }
    for k, v in expected.items():
        if counts[k] != v:
            raise SystemExit(f"BLD-0036 fixture shape {k}={counts[k]} expected {v}")
    for rel, delta in ((OWNER_OPS, 1001), (PERFORMANCE, 178), (SECURITY, 97)):
        rb = (REPO_ROOT / rel).stat().st_size
        lb = (LIVE_ROOT / rel).stat().st_size
        if lb - rb != delta:
            raise SystemExit(f"{rel} live-minus-repo={lb - rb} expected {delta}")
    return {
        "repo_root": str(REPO_ROOT),
        "live_root": str(LIVE_ROOT),
        "ledger_path": str(LEDGER_PATH),
        "ledger": ledger,
        "counts": counts,
        "planted": PLANTED,
        "live_larger": list(LIVE_LARGER),
        "cited_2026_08_09_5_of_88_on_host": False,
    }


def iter_rel(root: Path) -> dict[str, Path]:
    out: dict[str, Path] = {}
    if not root.is_dir():
        return out
    for p in root.rglob("*"):
        if p.is_file():
            out[p.relative_to(root).as_posix()] = p
    return out


def _count_shape() -> dict:
    repo = iter_rel(REPO_ROOT)
    live = iter_rel(LIVE_ROOT)
    keys = sorted(set(repo) | set(live))
    identical = eol_only = repo_larger = live_larger = content = 0
    for rel in keys:
        rp, lp = repo.get(rel), live.get(rel)
        if rp is None or lp is None:
            content += 1
            continue
        rb, lb = rp.read_bytes(), lp.read_bytes()
        if rb == lb:
            identical += 1
            continue
        rt, lt = rb.decode("utf-8"), lb.decode("utf-8")
        if rt.replace("\r\n", "\n").replace("\r", "\n") == lt.replace("\r\n", "\n").replace(
            "\r", "\n"
        ):
            eol_only += 1
            continue
        content += 1
        if len(rb) > len(lb):
            repo_larger += 1
        elif len(lb) > len(rb):
            live_larger += 1
    return {
        "union_files": len(keys),
        "identical": identical,
        "eol_only": eol_only,
        "content_differing": content,
        "repo_larger": repo_larger,
        "live_larger": live_larger,
    }


def tree_fingerprint(root: Path) -> dict[str, dict]:
    rows = {}
    for rel, path in iter_rel(root).items():
        st = path.stat()
        rows[rel] = {
            "mtime_ns": st.st_mtime_ns,
            "size": st.st_size,
            "sha256": _sha(path.read_bytes()),
        }
    return rows


def _sha(data: bytes) -> str:
    import hashlib

    return hashlib.sha256(data).hexdigest()
