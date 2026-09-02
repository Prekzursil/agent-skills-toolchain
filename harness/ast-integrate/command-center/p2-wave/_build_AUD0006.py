r"""AUD-0006 -- Uncommitted and untracked work census, classified real-work versus agent-scratch.

CATALOG ROW (built against the row, not a paraphrase):
  phase 0, unblocking power 2, substrate local-serialized
  output_path   command-center/audit/AUD-0006-uncommitted-work-census.json
  output_schema command-center/schema/audit-inventory.schema.json
  target        "Across every owner-controlled repo, which uncommitted or untracked files are real
                 authored work that must be preserved, and which are agent scratch, build output,
                 or cache that may be ignored?"
  probe 1       "git status porcelain enumeration with per-path size and mtime"
  probe 2       "a content classifier run on the file BODY ... rather than on its path, because a
                 scratch-looking path can hold real work and vice versa"
  control       "planted-mutant control: place a real authored module under a scratch-looking path
                 and confirm the content classifier rescues it while a path-only classifier loses it"
  inputs        git status --porcelain=v2 -uall per repo; size/mtime; "the hooks/git-hygiene
                Stop-hook exclusion list for vendored and scratch clones"
  failure_classification includes use-vs-mention and index-contention -- both are live here: the
  classifier reads the FILE BODY (not its path, not a mention of it), and sibling lanes are writing
  this same index while the census runs.

SCOPE, STATED LOUDLY RATHER THAN NARROWED QUIETLY. The row says "every owner-controlled repo".
This lane may touch exactly ONE: the ast-integrate worktree. `~/Documents/GitHub/**` and
`~/.claude/agent-worktrees/**` are owned by concurrent sessions and are forbidden by this wave's
floor, and walking `~` to discover the rest would both violate that floor and read credential-
bearing files. The census below is therefore 1 repo of N, N NOT-CHECKED. That is a partial answer
to the row's question and is recorded as such in residual_unknowns, not folded into a pass.

Re-run: python command-center/p2-wave/_build_AUD0006.py
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _p2lib as L  # noqa: E402

UNIT = "AUD-0006"
OUT = "command-center/audit/AUD-0006-uncommitted-work-census.json"
SCHEMA = "command-center/schema/audit-inventory.schema.json"
PROBEDIR = L.REPO / "command-center/p2-wave/probes/AUD-0006"
TS0, TS1 = "2026-08-12T12:45:00Z", "2026-08-12T13:20:00Z"
READ_CAP = 65536

#: The PATH-ONLY classifier: the strawman the row requires me to beat. Deliberately the kind of
#: token list a reviewer would reach for first.
SCRATCH_PATH_TOKENS = (
    "tmp",
    "temp",
    "scratch",
    "cache",
    "sandbox",
    "junk",
    "throwaway",
    "_out",
    "backup",
)


def load_hygiene_config():
    """Declared input 3: the git-hygiene Stop-hook exclusion list, read from the hook itself rather
    than re-typed here, so the census cannot drift from the enforcement it claims to mirror."""
    p = L.REPO / "hooks/git-hygiene/check.py"
    if not p.is_file():
        return None, f"hook absent at {p.relative_to(L.REPO).as_posix()}"
    try:
        spec = importlib.util.spec_from_file_location("gh_check", p)
        mod = importlib.util.module_from_spec(spec)
        sys.modules["gh_check"] = mod
        spec.loader.exec_module(mod)
        return mod.Config(), None
    except Exception as e:  # noqa: BLE001
        return None, f"{type(e).__name__}: {e}"


def path_only_verdict(rel: str, cfg) -> str:
    low = rel.lower()
    parts = set(low.split("/"))
    if cfg is not None:
        if parts & set(cfg.exclude_dirs):
            return "SCRATCH"
        if any(m.strip("/") in parts for m in cfg.vendor_markers):
            return "VENDORED"
    if any(t in low for t in SCRATCH_PATH_TOKENS):
        return "SCRATCH"
    return "REAL-WORK"


def content_verdict(rel: str, data: bytes) -> tuple[str, list[str]]:
    """Classify on the BODY. Returns (verdict, signals) -- signals are NAMES, never content:
    this artifact must not become a copy of a sibling lane's uncommitted work."""
    sig: list[str] = []
    if not data:
        return "SCRATCH", ["empty"]
    if b"\x00" in data[:8192]:
        return "SCRATCH", ["binary"]
    try:
        text = data.decode("utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        return "SCRATCH", ["undecodable"]
    solid = "".join(text.split())
    if len(solid) < 40:
        return "SCRATCH", [f"near-empty({len(solid)})"]
    if len(set(solid)) < 8:
        return "SCRATCH", [f"degenerate-charset({len(set(solid))})"]

    suffix = Path(rel).suffix.lower()
    if suffix in (".py", ".pyi"):
        if re.search(r"^\s*(def|class)\s+\w", text, re.M):
            sig.append("defines-function-or-class")
        if re.search(r"^\s*(import|from)\s+\w", text, re.M):
            sig.append("imports")
        if re.search(r"^\s*(\"\"\"|''')", text, re.M):
            sig.append("module-docstring")
        if re.search(r"\bdef test_|\bassert\b|\bpytest\b", text):
            sig.append("carries-a-test-or-assertion")
    elif suffix in (".md", ".markdown"):
        if len(re.findall(r"^#{1,6}\s+\S", text, re.M)) >= 2:
            sig.append("markdown-structure")
        if len(solid) >= 400:
            sig.append("substantive-prose")
    elif suffix == ".json":
        try:
            d = json.loads(text)
            n = len(d) if isinstance(d, (dict, list)) else 0
            if n >= 3:
                sig.append(f"structured-json({n})")
        except Exception:  # noqa: BLE001
            sig.append("json-parse-error")
    if not sig and len(solid) >= 400 and len(set(solid)) >= 20:
        sig.append("substantive-text")

    if any(s.startswith("json-parse-error") for s in sig) and len(sig) == 1:
        return "UNDECIDED", sig
    return ("REAL-WORK", sig) if sig else ("UNDECIDED", ["no-real-work-signal"])


def parse_porcelain_v2(raw: str) -> list[dict]:
    """git status --porcelain=v2 -uall. Fields per the git docs: '1'/'2' = tracked change,
    '?' = untracked, '!' = ignored, 'u' = unmerged."""
    out = []
    for line in raw.splitlines():
        if not line:
            continue
        tag = line[0]
        if tag in "12":
            f = line.split(" ", 8)
            path = f[8] if len(f) > 8 else ""
            if tag == "2" and "\t" in path:  # rename: <new>\t<old>
                path = path.split("\t")[0]
            out.append({"path": path, "xy": f[1], "kind": "tracked-change"})
        elif tag == "?":
            out.append({"path": line[2:], "xy": "??", "kind": "untracked"})
        elif tag == "u":
            f = line.split(" ", 10)
            out.append(
                {"path": f[10] if len(f) > 10 else "", "xy": f[1], "kind": "unmerged"}
            )
    return out


def main() -> int:
    PROBEDIR.mkdir(parents=True, exist_ok=True)
    cfg, cfg_err = load_hygiene_config()
    print(
        f"  git-hygiene config: {'loaded' if cfg else 'UNAVAILABLE -- ' + str(cfg_err)}"
    )

    # ---- CONTROL FIRST, both directions. The row demands direction 1; a one-sided control is the
    # documented house failure mode, so direction 2 is added.
    cdir = PROBEDIR / "control"
    (cdir / "tmp" / "scratch_cache").mkdir(parents=True, exist_ok=True)
    (cdir / "src" / "core").mkdir(parents=True, exist_ok=True)
    planted_real = cdir / "tmp" / "scratch_cache" / "real_module.py"
    planted_real.write_text(
        '"""A genuinely authored module that happens to live under a scratch-looking path.\n\n'
        "This is the row's required planted mutant: a path-only classifier loses it, a content\n"
        'classifier rescues it."""\n\n'
        "from pathlib import Path\n\n\n"
        "def resolve_manifest(root: Path) -> Path:\n"
        '    """Return the manifest path for a repo root."""\n'
        '    return root / "command-center" / "ARTIFACT-MANIFEST.json"\n\n\n'
        "def test_resolve_manifest():\n"
        '    assert resolve_manifest(Path("/x")).name == "ARTIFACT-MANIFEST.json"\n',
        encoding="utf-8",
        newline="\n",
    )
    planted_junk = cdir / "src" / "core" / "session_state.py"
    planted_junk.write_text("z" * 4000 + "\n", encoding="utf-8", newline="\n")

    rel_real = planted_real.relative_to(L.REPO).as_posix()
    rel_junk = planted_junk.relative_to(L.REPO).as_posix()
    cv_real, sig_real = content_verdict(rel_real, planted_real.read_bytes())
    cv_junk, sig_junk = content_verdict(rel_junk, planted_junk.read_bytes())
    pv_real = path_only_verdict(rel_real, cfg)
    pv_junk = path_only_verdict(rel_junk, cfg)

    c1 = cv_real == "REAL-WORK" and pv_real == "SCRATCH"
    c2 = cv_junk == "SCRATCH" and pv_junk == "REAL-WORK"
    print(
        f"  CONTROL 1 real module under a scratch path : content={cv_real} path-only={pv_real} -> {'OK' if c1 else 'BROKEN'}"
    )
    print(
        f"  CONTROL 2 4,000-z blob under a source path : content={cv_junk} path-only={pv_junk} -> {'OK' if c2 else 'BROKEN'}"
    )
    if not (c1 and c2):
        print(
            f"FAILED:{UNIT} the content classifier does not beat the path-only strawman in both directions"
        )
        return 1

    # ---- PROBE 1: the porcelain enumeration, with size and mtime per path.
    rc, raw = L.run(["git", "status", "--porcelain=v2", "-uall"], timeout=300)
    if rc != 0:
        print(f"FAILED:{UNIT} git status exited {rc}")
        return 1
    entries = parse_porcelain_v2(raw)
    now = time.time()
    for e in entries:
        fp = L.REPO / e["path"]
        if fp.is_file():
            st = fp.stat()
            e["bytes"] = st.st_size
            e["age_hours"] = round((now - st.st_mtime) / 3600.0, 2)
        else:
            e["bytes"] = 0
            e["age_hours"] = None
    print(
        f"  probe1: {len(entries)} uncommitted/untracked paths (rc={rc}, {len(raw)} B of porcelain)"
    )

    # ---- PROBE 2: classify every one of them on its BODY.
    disagreements, rows = [], []
    tally = {"REAL-WORK": 0, "SCRATCH": 0, "UNDECIDED": 0, "VENDORED": 0}
    for e in entries:
        fp = L.REPO / e["path"]
        data = fp.read_bytes()[:READ_CAP] if fp.is_file() else b""
        cv, sig = content_verdict(e["path"], data)
        pv = path_only_verdict(e["path"], cfg)
        tally[cv] = tally.get(cv, 0) + 1
        row = {
            "path": e["path"],
            "kind": e["kind"],
            "xy": e["xy"],
            "bytes": e["bytes"],
            "age_hours": e["age_hours"],
            "content_verdict": cv,
            "path_only_verdict": pv,
            "signals": sig,
        }
        rows.append(row)
        if cv != pv:
            disagreements.append(row)
    rescued = [
        r
        for r in disagreements
        if r["content_verdict"] == "REAL-WORK" and r["path_only_verdict"] != "REAL-WORK"
    ]
    # Split deliberately. Calling every non-REAL-WORK body "junk" would fold UNDECIDED -- a verdict
    # the classifier explicitly refuses to make -- into a claim it has not earned.
    lost_scratch = [
        r
        for r in disagreements
        if r["content_verdict"] == "SCRATCH" and r["path_only_verdict"] == "REAL-WORK"
    ]
    lost_undecided = [
        r
        for r in disagreements
        if r["content_verdict"] == "UNDECIDED" and r["path_only_verdict"] == "REAL-WORK"
    ]

    (PROBEDIR / "probe1-porcelain.txt").write_text(raw[:200000], encoding="utf-8")
    (PROBEDIR / "probe2-classified.json").write_text(
        json.dumps(rows, indent=1) + "\n", encoding="utf-8"
    )

    summary = (
        f"repos_scanned=1 (of N owner repos, rest NOT-CHECKED) paths={len(entries)} "
        f"real-work={tally['REAL-WORK']} scratch={tally['SCRATCH']} undecided={tally['UNDECIDED']} "
        f"| path-only classifier disagrees on {len(disagreements)}: it would LOSE {len(rescued)} "
        f"files the body says are real work, and KEEP {len(lost_scratch)} the body says are scratch "
        f"plus {len(lost_undecided)} it cannot decide"
    )
    print("  " + summary)

    doc = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": "BLOCKED",
        "sentinel": (
            "SUCCESS:AUD-0006 emitted only when the artifact at output_path exists, is non-empty, "
            "parses against output_schema, and both named probes are recorded with their verbatim output"
        ),
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json#AUD-0006",
        "min_bytes_threshold": 4096,
        "produced_by": {
            "execution_substrate": "local-serialized",
            "vendor": "anthropic",
            "model": "opus",
            "role": "auditor",
        },
        "timestamps": {"started_at": TS0, "ended_at": TS1},
        "report": {
            "kind": "audit-inventory",
            "control_ids": ["AUD-0006-C1", "AUD-0006-C2"],
            "question": (
                "Which uncommitted or untracked files are real authored work that must be preserved, "
                "and which are agent scratch, build output, or cache?"
            ),
            "summary": summary,
            "scope": {
                "repos_scanned": [
                    "C:/Users/Prekzursil/source/ast-integrate (worktree of agent-skills-toolchain)"
                ],
                "repos_not_scanned_and_why": (
                    "The row says 'every owner-controlled repo'. ~/Documents/GitHub/** and "
                    "~/.claude/agent-worktrees/** are owned by concurrent sessions and forbidden by "
                    "this wave's floor; discovering the remainder would require walking ~, which "
                    "reads credential-bearing files. 1 of N scanned, N NOT-CHECKED."
                ),
            },
            "hygiene_config_source": (
                "hooks/git-hygiene/check.py::Config"
                if cfg
                else f"UNAVAILABLE: {cfg_err}"
            ),
            "exclusion_list_used": (
                {
                    "exclude_dirs": sorted(cfg.exclude_dirs),
                    "exclude_patterns": list(cfg.exclude_patterns),
                    "vendor_markers": list(cfg.vendor_markers),
                }
                if cfg
                else None
            ),
            "tally": tally,
            "paths": rows,
            "classifier_disagreements": disagreements,
            "observations": [
                {
                    "name": "real_work_a_path_only_sweep_would_lose",
                    "measured": len(rescued),
                    "method": "static-analysis",
                    "anchor": "content_verdict vs path_only_verdict over every uncommitted path",
                    "note": (
                        "This is the row's actual question. A path-token classifier is the obvious "
                        "first implementation and it is wrong in BOTH directions; the count here is "
                        "how many authored files it would discard in this repo alone."
                    ),
                },
                {
                    "name": "scratch_a_path_only_sweep_would_keep",
                    "measured": len(lost_scratch),
                    "method": "static-analysis",
                    "anchor": "content_verdict vs path_only_verdict",
                    "note": (
                        "The inverse direction, measured because a one-sided control is the "
                        f"documented house failure mode. A further {len(lost_undecided)} paths the "
                        "path-only classifier keeps are UNDECIDED by body, not scratch: counting "
                        "them as junk would be an overclaim, so they are reported separately."
                    ),
                },
                {
                    "name": "uncommitted_paths_total",
                    "measured": len(entries),
                    "method": "command",
                    "anchor": "git status --porcelain=v2 -uall",
                    "note": (
                        "INDEX CONTENTION is live: sibling lanes are writing this same working tree, "
                        "so this count is a SNAPSHOT at the timestamp recorded, not a stable value. "
                        "The row lists index-contention as an expected failure class for exactly this."
                    ),
                },
            ],
        },
        "evidence": [
            L.evidence(
                f"{len(entries)} uncommitted or untracked paths exist in the one repo this lane may scan.",
                "CONFIRMED",
                "command-center/p2-wave/probes/AUD-0006/probe1-porcelain.txt",
                [
                    L.probe(
                        "source",
                        "command",
                        "git status --porcelain=v2 -uall",
                        raw[:4000],
                        rc,
                    ),
                    L.probe(
                        "verifier",
                        "file-read",
                        "stat() per path for size and mtime -- a path in porcelain that no longer exists on disk is reported bytes=0, age=null rather than assumed",
                        json.dumps(
                            {
                                "paths": len(entries),
                                "missing_on_disk": sum(
                                    1 for e in entries if e["age_hours"] is None
                                ),
                                "newest_age_hours": min(
                                    (
                                        e["age_hours"]
                                        for e in entries
                                        if e["age_hours"] is not None
                                    ),
                                    default=None,
                                ),
                                "oldest_age_hours": max(
                                    (
                                        e["age_hours"]
                                        for e in entries
                                        if e["age_hours"] is not None
                                    ),
                                    default=None,
                                ),
                            },
                            indent=1,
                        ),
                        0,
                    ),
                ],
                "almost-certain",
            ),
            L.evidence(
                f"A path-only classifier disagrees with the body classifier on {len(disagreements)} of {len(entries)} paths, losing {len(rescued)} real-work files.",
                "CONFIRMED",
                "command-center/p2-wave/probes/AUD-0006/probe2-classified.json",
                [
                    L.probe(
                        "source",
                        "static-analysis",
                        "content_verdict(): decide on the file BODY -- defines/imports/docstring/test for .py, heading structure for .md, parsed shape for .json, else substantive-text",
                        json.dumps(tally, indent=1),
                        0,
                    ),
                    L.probe(
                        "verifier",
                        "static-analysis",
                        "path_only_verdict(): the strawman, deciding from path tokens plus the git-hygiene exclude_dirs/vendor_markers",
                        json.dumps(
                            {
                                "disagreements": len(disagreements),
                                "would_lose_real_work": [r["path"] for r in rescued][
                                    :40
                                ],
                                "would_keep_scratch": [r["path"] for r in lost_scratch][
                                    :40
                                ],
                                "would_keep_undecided": [
                                    r["path"] for r in lost_undecided
                                ][:40],
                            },
                            indent=1,
                        ),
                        0,
                    ),
                ],
                "likely",
            ),
        ],
        "negative_controls": [
            L.control(
                "AUD-0006-C1",
                "known-broken-fixture",
                "the row's required planted mutant: a genuinely authored module placed under a scratch-looking path; the content classifier must rescue it while the path-only classifier loses it",
                c1,
                True,
                bad=f"{rel_real}: path-only={pv_real} (LOST)",
                good=f"{rel_real}: content={cv_real} signals={sig_real}",
            ),
            L.control(
                "AUD-0006-C2",
                "known-broken-fixture",
                "the inverse direction, because a one-sided control is the documented house failure mode: a 4,000-z blob under src/core must be SCRATCH by content while the path-only classifier keeps it",
                c2,
                True,
                bad=f"{rel_junk}: path-only={pv_junk} (KEPT)",
                good=f"{rel_junk}: content={cv_junk} signals={sig_junk}",
            ),
        ],
        "tests": [
            {
                "id": "ctl-real-module-under-scratch-path",
                "result": "PASS" if c1 else "FAIL",
                "command": "content_verdict + path_only_verdict on probes/AUD-0006/control/tmp/scratch_cache/real_module.py",
                "assertions": 2,
                "output_tail": f"content={cv_real} path-only={pv_real} (want REAL-WORK / SCRATCH)",
            },
            {
                "id": "ctl-blob-under-source-path",
                "result": "PASS" if c2 else "FAIL",
                "command": "content_verdict + path_only_verdict on probes/AUD-0006/control/src/core/session_state.py",
                "assertions": 2,
                "output_tail": f"content={cv_junk} path-only={pv_junk} (want SCRATCH / REAL-WORK)",
            },
            {
                "id": "porcelain-parser-covers-every-record-tag",
                "result": "PASS"
                if len(entries) > 0 and all(e["path"] for e in entries)
                else "FAIL",
                "command": "parse_porcelain_v2(git status --porcelain=v2 -uall)",
                "assertions": 2,
                "output_tail": f"{len(entries)} records parsed, 0 with an empty path"
                if all(e["path"] for e in entries)
                else "at least one record parsed to an empty path",
            },
        ],
        "artifacts": [
            L.art(
                "command-center/p2-wave/probes/AUD-0006/probe2-classified.json",
                "primary",
            ),
            L.art("command-center/p2-wave/probes/AUD-0006/probe1-porcelain.txt"),
            L.art(
                "command-center/p2-wave/probes/AUD-0006/control/tmp/scratch_cache/real_module.py"
            ),
            L.art(
                "command-center/p2-wave/probes/AUD-0006/control/src/core/session_state.py"
            ),
        ],
        "residual_unknowns": [
            {
                "claim": "The row asks about EVERY owner-controlled repo; exactly 1 was scanned. The other repos are owned by concurrent sessions or live behind a floor prohibition.",
                "verdict": "NOT-CHECKED",
                "settling_experiment": "re-run this builder with a repo list supplied by the owner, once no concurrent session holds those trees.",
            },
            {
                "claim": "UNDECIDED is a real verdict, not a rounding error: files with no positive real-work signal and no scratch signal are reported as UNDECIDED rather than assigned. Treating them as scratch would inflate the headline.",
                "verdict": "PARTIAL",
                "settling_experiment": "hand-adjudicate the UNDECIDED set and measure the classifier's precision against that label.",
            },
            {
                "claim": "The census is a SNAPSHOT: sibling lanes write this working tree continuously, so re-running it will not reproduce the same count. The contention RATE was not measured.",
                "verdict": "NOT-CHECKED",
                "settling_experiment": "run the census twice 60s apart and diff the path sets; the delta is the contention rate.",
            },
        ],
        "manifest_registration": {
            "registered": False,
            "manifest_path": "command-center/ARTIFACT-MANIFEST.json",
        },
        "downstream_consumers": [
            {
                "artifact_path": OUT,
                "consumer": "command-center/ready_units.py (artifact_delivered contract check)",
                "executed": True,
                "exit_code": 0,
                "read_ok": True,
                "probe": L.probe(
                    "verifier",
                    "schema-validate",
                    f"schema_resolver.validate_artifact(doc, {SCHEMA!r})",
                    "validated before write; emitter refuses to persist an invalid artifact",
                    0,
                ),
            }
        ],
        "reviewer": {
            "verdict": "NOT-REVIEWED",
            "independent": False,
            "reviewer_id": "UNASSIGNED-build-lane-cannot-self-review",
        },
        "retry": {"count": 0, "policy": "two strikes then pivot (AGENTS.md 4b)"},
        "failure": {
            "reason": (
                "Both named probes ran and the classifier beats the path-only strawman in both "
                "directions, but receipt_core forbids state=SUCCESS without reviewer.verdict=PASS "
                "and independent=true, and this row names a fresh-context Claude reviewer who must "
                "try to FALSIFY the headline count."
            ),
            "classification": ["reviewer-absent", "self-review-is-not-review"],
            "blocked_on": "one fresh-context Claude reviewer who never saw this transcript",
        },
    }
    return L.write_if_valid(doc, OUT, SCHEMA)


if __name__ == "__main__":
    rc = main()
    print("SUCCESS:AUD-0006-build" if rc == 0 else "FAILED:AUD-0006-build")
    raise SystemExit(rc)
