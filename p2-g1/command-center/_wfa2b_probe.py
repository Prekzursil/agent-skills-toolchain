"""build/wfa-2 archaeology probe: measure candidates 33-64, do not trust doc 08.

Filename note: `_wfa2_probe.py` is an UNRELATED pre-existing file from a 20:19
Phase-0 catalog-slice wave ("WFA-2of2 bucket B04"), so this unit uses the
`_wfa2b_` prefix to avoid clobbering a sibling's artifact.

Three probe families, each with a detector control:
  C) 7 repo tools at pinned ref 07f465f3 via the bare mirror -> existence, LOC, tests, license
  D) 6 harness runtime files live + repo counterpart         -> LOC, mtime, drift direction
  E) 19 agent definitions (repo + live)                      -> frontmatter, LOC, pairwise Jaccard

Emits _wfa2b_probe_out.json. Read-only against every tree it touches.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path

MIRROR = Path(r"C:/Users/Prekzursil/.claude/harness-restore-20260806/main-mirror.git")
REF = "07f465f37d49710f7060dcc7b567d6c58213177b"
LIVE_HARNESS = Path(r"C:/Users/Prekzursil/.agents/harness")
LIVE_AGENTS = Path(r"C:/Users/Prekzursil/.claude/agents")
OUT = Path(
    r"C:/Users/Prekzursil/source/ast-integrate/command-center/_wfa2b_probe_out.json"
)

TOOLS = [
    "tools/search-expansion",
    "tools/taskwatch_monitor",
    "tools/plugin-cache-reaper",
    "tools/glob-argv-guard",
    "tools/gitcrypt-worktree",
    "tools/stdin-server",
    "tools/harness-corpus-mirror-ci",
]
HARNESS = [
    "dispatcher.py",
    "ledger.py",
    "modules.py",
    "adapters.py",
    "recall_index.py",
    "registration.py",
]
AGENTS = [
    "architect",
    "planner",
    "chief-of-staff",
    "code-reviewer",
    "python-reviewer",
    "typescript-reviewer",
    "security-reviewer",
    "agent-as-judge",
    "intent-drift-sentinel",
    "harness-optimizer",
    "loop-operator",
    "build-error-resolver",
    "refactor-cleaner",
    "doc-updater",
    "docs-lookup",
    "e2e-runner",
    "tdd-guide",
    "codex",
]


def git(*args: str) -> tuple[int, str]:
    p = subprocess.run(
        ["git", "--git-dir", str(MIRROR), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def ls_tree(path: str) -> list[str]:
    rc, out = git("ls-tree", "-r", "--name-only", REF, "--", path)
    if rc != 0:
        return []
    return [ln for ln in out.splitlines() if ln.strip()]


def cat(path: str) -> str | None:
    rc, out = git("cat-file", "-p", f"{REF}:{path}")
    return out if rc == 0 else None


def last_commit(path: str) -> dict | None:
    rc, out = git(
        "log", "-1", "--format=%H%x1f%ad%x1f%an%x1f%s", "--date=short", REF, "--", path
    )
    if rc != 0 or not out.strip():
        return None
    sha, date, author, subj = out.strip().split("\x1f", 3)
    return {"sha": sha[:12], "date": date, "author": author, "subject": subj}


def commit_count(path: str) -> int:
    rc, out = git("rev-list", "--count", REF, "--", path)
    return int(out.strip()) if rc == 0 and out.strip().isdigit() else 0


LICENSE_PAT = re.compile(
    r"\b(MIT|Apache[- ]2\.0|BSD[- ]?[23]?|GPLv?[23]?|LGPL|MPL|ISC|Unlicense|"
    r"CC BY|CC0|SPDX-License-Identifier)\b"
)
BORROW_PAT = re.compile(
    r"\b(borrow(ed|s|ing)? from|adapted from|derived from|vendored|upstream|"
    r"port of|based on|inspired by|clean[- ]room)\b",
    re.I,
)
URL_PAT = re.compile(r"https?://[^\s)\]<>\"',]+")


def probe_tools() -> list[dict]:
    rows = []
    for t in TOOLS:
        files = ls_tree(t)
        loc = 0
        tests = 0
        license_hits: list[str] = []
        borrow_hits: list[str] = []
        urls: list[str] = []
        readme = None
        entry_docstrings: dict[str, str] = {}
        for f in files:
            body = cat(f)
            if body is None:
                continue
            n = len(body.splitlines())
            loc += n
            base = f.rsplit("/", 1)[-1]
            if base.startswith("test_") or "/tests/" in f:
                tests += 1
            if base.lower() == "readme.md":
                readme = {"path": f, "lines": n, "head": body[:2600]}
            elif base.endswith(".py") and not base.startswith("test_"):
                entry_docstrings[f] = body[:900]
            head = body[:8000]
            license_hits.extend(LICENSE_PAT.findall(head))
            for m in BORROW_PAT.finditer(head):
                s = max(0, m.start() - 110)
                borrow_hits.append(f"{f}: ...{head[s : m.end() + 150]}...")
            urls.extend(URL_PAT.findall(head))
        rows.append(
            {
                "path": t,
                "exists_at_ref": bool(files),
                "n_files": len(files),
                "files": files,
                "loc": loc,
                "test_files": tests,
                "commits": commit_count(t),
                "last_commit": last_commit(t),
                "license_tokens": sorted(
                    {h if isinstance(h, str) else h[0] for h in license_hits}
                ),
                "borrow_evidence": borrow_hits[:6],
                "urls": sorted(set(urls))[:12],
                "readme": readme,
                "entry_docstrings": dict(list(entry_docstrings.items())[:4]),
            }
        )
    return rows


def probe_harness() -> list[dict]:
    rows = []
    for f in HARNESS:
        live = LIVE_HARNESS / f
        live_txt = (
            live.read_text(encoding="utf-8", errors="replace")
            if live.exists()
            else None
        )
        repo_path = f"agent-self/harness/{f}"
        repo_txt = cat(repo_path)
        alt = None
        if repo_txt is None:
            for cand in (f"ci/harness/{f}", f"harness/{f}"):
                repo_txt = cat(cand)
                if repo_txt is not None:
                    alt = cand
                    break
        live_lines = live_txt.splitlines() if live_txt else []
        repo_lines = repo_txt.splitlines() if repo_txt else []
        ls, rs = set(live_lines), set(repo_lines)
        # mechanism keywords, measured on the LIVE body
        body = live_txt or ""
        rows.append(
            {
                "file": f,
                "live_path": str(live),
                "live_exists": live.exists(),
                "live_loc": len(live_lines),
                "live_bytes": live.stat().st_size if live.exists() else 0,
                "live_mtime": (
                    datetime.fromtimestamp(live.stat().st_mtime, tz=timezone.utc)
                    .date()
                    .isoformat()
                    if live.exists()
                    else None
                ),
                "repo_path": alt or repo_path,
                "repo_exists": repo_txt is not None,
                "repo_loc": len(repo_lines),
                "live_unique_lines": len(ls - rs),
                "repo_unique_lines": len(rs - ls),
                "identical": bool(live_txt is not None and live_txt == repo_txt),
                "repo_last_commit": last_commit(alt or repo_path),
                "n_defs": len(re.findall(r"^\s*def\s+\w+", body, re.M)),
                "n_classes": len(re.findall(r"^\s*class\s+\w+", body, re.M)),
                "mechanism_hits": {
                    k: len(re.findall(p, body))
                    for k, p in {
                        "threading": r"\bthread(ing)?\b",
                        "budget/timeout": r"\b(budget|timeout|deadline)\b",
                        "fail-open": r"fail[-_ ]?open|except Exception",
                        "os._exit": r"os\._exit",
                        "exit2_block": r"\bexit\(2\)|exit_code\s*=\s*2|\bEXIT_BLOCK\b",
                        "additionalContext": r"additionalContext",
                        "session_id": r"session_?id",
                        "receipt/ledger": r"\breceipt|ledger\b",
                        "hmac/sign": r"\bhmac\b|signature|sha256",
                        "sentinel": r"sentinel",
                    }.items()
                },
                "docstring": body[:800],
            }
        )
    return rows


FM = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.S)


def parse_fm(text: str) -> dict:
    m = FM.match(text)
    if not m:
        return {}
    out: dict[str, str] = {}
    key = None
    for ln in m.group(1).splitlines():
        mm = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", ln)
        if mm:
            key = mm.group(1)
            out[key] = mm.group(2).strip()
        elif key and ln.strip():
            out[key] = (out[key] + " " + ln.strip()).strip()
    return out


def norm_lines(text: str) -> set[str]:
    body = FM.sub("", text)
    return {
        re.sub(r"\s+", " ", ln).strip().lower()
        for ln in body.splitlines()
        if len(ln.strip()) > 12
    }


def probe_agents() -> dict:
    rows = []
    corpora: dict[str, set[str]] = {}
    for a in AGENTS:
        live = LIVE_AGENTS / f"{a}.md"
        bak = LIVE_AGENTS / f"{a}.md.bak-gembuild-agent-definitions-batch"
        live_txt = (
            live.read_text(encoding="utf-8", errors="replace")
            if live.exists()
            else None
        )
        repo_txt = cat(f"agents/{a}.md")
        bak_txt = (
            bak.read_text(encoding="utf-8", errors="replace") if bak.exists() else None
        )
        fm = parse_fm(live_txt or repo_txt or "")
        if live_txt:
            corpora[a] = norm_lines(live_txt)
        bak_j = None
        if bak_txt and live_txt:
            x, y = norm_lines(bak_txt), norm_lines(live_txt)
            bak_j = round(len(x & y) / len(x | y), 4) if (x | y) else 0.0
        rows.append(
            {
                "agent": a,
                "live_path": str(live),
                "live_exists": live.exists(),
                "live_loc": len((live_txt or "").splitlines()),
                "live_bytes": live.stat().st_size if live.exists() else 0,
                "live_mtime": (
                    datetime.fromtimestamp(live.stat().st_mtime, tz=timezone.utc)
                    .date()
                    .isoformat()
                    if live.exists()
                    else None
                ),
                "repo_path": f"agents/{a}.md",
                "repo_exists": repo_txt is not None,
                "repo_loc": len((repo_txt or "").splitlines()),
                "repo_identical_to_live": bool(
                    live_txt is not None and live_txt == repo_txt
                ),
                "repo_last_commit": last_commit(f"agents/{a}.md"),
                "repo_commits": commit_count(f"agents/{a}.md"),
                "fm_name": fm.get("name"),
                "fm_model": fm.get("model"),
                "fm_tools": fm.get("tools"),
                "fm_description": (fm.get("description") or "")[:700],
                "has_bak": bak.exists(),
                "bak_jaccard_vs_live": bak_j,
                "bak_loc": len((bak_txt or "").splitlines()) if bak_txt else 0,
            }
        )
    pairs = []
    for a, b in combinations(sorted(corpora), 2):
        x, y = corpora[a], corpora[b]
        if not (x | y):
            continue
        j = len(x & y) / len(x | y)
        if j >= 0.15:
            pairs.append({"a": a, "b": b, "jaccard": round(j, 4)})
    pairs.sort(key=lambda r: -r["jaccard"])
    # DETECTOR CONTROL for the near-duplicate scan: a planted exact clone must
    # score 1.0, and a planted disjoint doc must score ~0.
    ctl = {}
    if "architect" in corpora:
        clone = set(corpora["architect"])
        disjoint = {f"zzz totally unrelated line number {i} lorem" for i in range(60)}
        u = corpora["architect"] | clone
        ctl["clone_jaccard"] = round(len(corpora["architect"] & clone) / len(u), 4)
        u2 = corpora["architect"] | disjoint
        ctl["disjoint_jaccard"] = round(
            len(corpora["architect"] & disjoint) / len(u2), 4
        )
    return {
        "agents": rows,
        "near_duplicate_pairs": pairs,
        "dup_detector_control": ctl,
    }


def detector_controls() -> dict:
    return {
        "ls_tree_known_present": {
            "path": "tools/fanout-schema",
            "n": len(ls_tree("tools/fanout-schema")),
        },
        "ls_tree_known_absent": {
            "path": "tools/__definitely_not_a_real_tool__",
            "n": len(ls_tree("tools/__definitely_not_a_real_tool__")),
        },
        "cat_known_present": {
            "path": "agents/architect.md",
            "ok": cat("agents/architect.md") is not None,
        },
        "cat_known_absent": {
            "path": "agents/__nope__.md",
            "ok": cat("agents/__nope__.md") is not None,
        },
        "harness_mirror_paths": {
            "ci/harness": len(ls_tree("ci/harness")),
            "agent-self/harness": len(ls_tree("agent-self/harness")),
            "tools/harness-corpus-mirror-ci": len(
                ls_tree("tools/harness-corpus-mirror-ci")
            ),
            "tools/harness-corpus": len(ls_tree("tools/harness-corpus")),
        },
        "tools_dir_total": len({p.split("/")[1] for p in ls_tree("tools") if "/" in p}),
    }


def main() -> int:
    data = {
        "unit": "build/wfa-2",
        "ref": REF,
        "mirror": str(MIRROR),
        "generated_utc": datetime.now(tz=timezone.utc).isoformat(timespec="seconds"),
        "detector_controls": detector_controls(),
        "tools": probe_tools(),
        "harness": probe_harness(),
        "agents_block": probe_agents(),
    }
    # newline="\n" is load-bearing on Windows: write_text/open in text mode
    # translates to CRLF, and every sibling artifact under platform/ is CRLF=0.
    with OUT.open("w", encoding="utf-8", newline="\n") as fh:
        json.dump(data, fh, indent=2)
        fh.write("\n")

    dc = data["detector_controls"]
    print("--- DETECTOR CONTROLS ---")
    print(
        f"  ls-tree known-PRESENT tools/fanout-schema  n={dc['ls_tree_known_present']['n']}"
        "   (must be > 0)"
    )
    print(
        f"  ls-tree known-ABSENT  bogus path           n={dc['ls_tree_known_absent']['n']}"
        "   (must be 0)"
    )
    print(
        f"  cat known-PRESENT agents/architect.md   ok={dc['cat_known_present']['ok']}"
    )
    print(
        f"  cat known-ABSENT  agents/__nope__.md    ok={dc['cat_known_absent']['ok']}"
    )
    print(f"  harness mirror paths: {json.dumps(dc['harness_mirror_paths'])}")
    print(f"  distinct dirs under tools/ at ref: {dc['tools_dir_total']}")

    print("\n--- C. TOOLS (candidates 33-39) ---")
    for r in data["tools"]:
        print(
            f"  {r['path']:<38} exists={str(r['exists_at_ref']):<5} "
            f"files={r['n_files']:<3} loc={r['loc']:<6} tests={r['test_files']:<3} "
            f"commits={r['commits']:<3} last={(r['last_commit'] or {}).get('date')} "
            f"lic={r['license_tokens']}"
        )
    print("\n--- D. HARNESS (candidates 40-45) ---")
    for r in data["harness"]:
        print(
            f"  {r['file']:<16} live_loc={r['live_loc']:<6} repo={r['repo_path']:<30} "
            f"repo_loc={r['repo_loc']:<6} live_uniq={r['live_unique_lines']:<5} "
            f"repo_uniq={r['repo_unique_lines']:<5} mtime={r['live_mtime']}"
        )
    print("\n--- E. AGENTS (candidates 46-64) ---")
    for r in data["agents_block"]["agents"]:
        print(
            f"  {r['agent']:<22} live={r['live_loc']:<5} repo={r['repo_loc']:<5} "
            f"same={str(r['repo_identical_to_live']):<5} "
            f"model={str(r['fm_model']):<10} bak={str(r['has_bak']):<5} "
            f"bakJ={r['bak_jaccard_vs_live']} commits={r['repo_commits']}"
        )
    print(f"\n  dup-detector control: {data['agents_block']['dup_detector_control']}")
    print("  near-duplicate pairs (Jaccard >= 0.15):")
    for p in data["agents_block"]["near_duplicate_pairs"]:
        print(f"    {p['jaccard']:.4f}  {p['a']}  <->  {p['b']}")
    if not data["agents_block"]["near_duplicate_pairs"]:
        print("    (none)")
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
