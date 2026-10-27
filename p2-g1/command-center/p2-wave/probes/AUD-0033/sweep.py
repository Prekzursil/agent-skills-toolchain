"""Walk the documentation corpus and extract cited paths."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Iterator

import common as C
import exist as E
import extract as X
import gitlog as G

PROBE_ROOT = "command-center/p2-wave/probes"
MAX_FILE_BYTES = 8_000_000
CATALOG_NAME = "WORK-UNIT-CATALOG.json"


def _skip_dir(name: str) -> bool:
    return name in C.SKIP_DIR_NAMES


def _skip_file(path: Path) -> bool:
    if path.name in C.SKIP_FILE_NAMES:
        return True
    for prefix in C.SKIP_NAME_PREFIXES:
        if path.name.startswith(prefix):
            return True
    return False


def _is_probe_but_not_ours(path: Path, repo: Path) -> bool:
    try:
        rel = path.relative_to(repo).as_posix()
    except ValueError:
        return False
    if not rel.startswith(PROBE_ROOT + "/"):
        return False
    # Keep this unit's control fixture; skip every other probe tree.
    ours = f"{PROBE_ROOT}/{C.UNIT}/"
    return not rel.startswith(ours)


def iter_corpus_files(repo: Path) -> Iterator[Path]:
    roots = [
        repo / "command-center",
        repo / "tools",
        repo / "blueprints",
        repo / ".github",
        repo / ".cursor",
        repo / ".quality",
    ]
    for root in roots:
        if not root.exists():
            continue
        if root.is_file():
            yield root
            continue
        for dirpath, dirnames, filenames in os_walk(root):
            dirnames[:] = [d for d in dirnames if not _skip_dir(d)]
            base = Path(dirpath)
            for name in filenames:
                path = base / name
                if _skip_file(path):
                    continue
                if _is_probe_but_not_ours(path, repo):
                    continue
                if path.suffix.lower() not in {".md", ".markdown", ".mdc", ".json"}:
                    if path.name in {"README", "AGENTS.md", "CLAUDE.md"}:
                        pass
                    else:
                        continue
                yield path
    for extra in (
        repo / "README.md",
        repo / "AGENTS.md",
        repo / "CLAUDE.md",
    ):
        if extra.is_file():
            yield extra


def os_walk(root: Path):
    import os

    return os.walk(root)


def harness_inventory() -> list[dict[str, Any]]:
    rows = []
    for root in C.HARNESS_ROOTS:
        rows.append(
            {
                "path": str(root),
                "exists": root.exists(),
                "is_file": root.is_file() if root.exists() else False,
                "is_dir": root.is_dir() if root.exists() else False,
            }
        )
    return rows


HARNESS_DOC_SCOPE_NOTE = (
    "shard2-w1 host-port 2026-10-24: the live-harness walk enumerates the "
    "harness's AUTHORED document trees (rules, skills, agents, commands, "
    "memory) plus root-level markdown/json and the pinned config files. "
    "Enumerating the whole ~/.claude tree (38,242 md/json files of machine "
    "state: workflow-runs journals, agent-worktrees, vendored plugin trees, "
    "session/checkpoint residue) blows the 180s G-1 measure envelope on this "
    "host and re-reads per-session state the canonical build itself excluded "
    "(projects, agent-transcripts, worktrees). The AUD-0033 artifact's own "
    "reviewer closure keeps the full every-file census residual NOT-CHECKED; "
    "this walk stays aligned with that blessed scope."
)


def iter_harness_files() -> Iterator[Path]:
    doc_trees = ("rules", "skills", "agents", "commands", "memory")
    skip_dir = C.SKIP_DIR_NAMES | {"projects", "agent-transcripts", "worktrees"}
    for root in C.HARNESS_ROOTS:
        if root.is_file():
            if root.suffix.lower() in {".md", ".json"}:
                yield root
            continue
        if not root.is_dir():
            continue
        try:
            entries = sorted(root.iterdir())
        except OSError:
            entries = []
        for entry in entries:
            if entry.is_file() and entry.suffix.lower() in {".md", ".markdown", ".json"}:
                yield entry
        for name in doc_trees:
            tree = root / name
            if not tree.is_dir():
                continue
            for dirpath, dirnames, filenames in os_walk(tree):
                dirnames[:] = [d for d in dirnames if d not in skip_dir]
                for fn in filenames:
                    path = Path(dirpath) / fn
                    if path.suffix.lower() in {".md", ".markdown", ".json"}:
                        yield path


def control_from_fixture(repo: Path) -> dict[str, Any]:
    fixture = repo / C.CONTROL_REL
    text, enc = E.read_text_with_retry(fixture)
    if text is None:
        return {
            "pass": False,
            "error": enc or "fixture-unreadable",
            "path": C.CONTROL_REL,
        }
    ctx = X.extract_markdown(text, C.CONTROL_REL)
    naive = X.extract_naive(text, C.CONTROL_REL)
    ctx_paths = set(X.paths_of(ctx))
    naive_paths = set(X.paths_of(naive))
    fence_present = C.FENCE_PRESENT in ctx_paths
    fence_missing = C.FENCE_MISSING in ctx_paths
    tick_ok = C.TICK_PATH in ctx_paths
    prose_leaked = C.PROSE_FALSE_PATH in ctx_paths
    naive_prose = C.PROSE_FALSE_PATH in naive_paths
    both_assertions = fence_present and (not prose_leaked)
    return {
        "id": "AUD-0033-C1-fence-vs-prose",
        "path": C.CONTROL_REL,
        "encoding_retry": enc,
        "context_paths": sorted(ctx_paths),
        "naive_paths": sorted(naive_paths),
        "fence_present_extracted": fence_present,
        "fence_missing_extracted": fence_missing,
        "tick_extracted": tick_ok,
        "prose_false_path_extracted": prose_leaked,
        "naive_extracts_prose_false_path": naive_prose,
        "fired_on_bad_state": naive_prose and not prose_leaked,
        "silent_on_good_state": (not prose_leaked) and fence_present,
        "both_assertions": both_assertions,
        "pass": bool(
            both_assertions
            and fence_missing
            and tick_ok
            and naive_prose
            and (not prose_leaked)
        ),
    }




def _scan_one(spec: tuple[str, str]):
    """Scan one corpus file (shard2-w1 host-port 2026-10-24).

    The per-file logic is byte-identical to the serial path it replaces
    (same 8MB size cap, same retrying reader, same extractor). Only the
    fan-out is new: extraction is CPU-bound and the repo corpus alone
    measures 92-207s serially on this host, over the 180s G-1 probe
    envelope. run_sweep falls back to the identical serial loop on any
    pool failure.
    """
    path_str, repo_str = spec
    path = Path(path_str)
    repo = Path(repo_str)
    try:
        size = path.stat().st_size
    except OSError as exc:
        return ("failed", {"path": path_str, "error": type(exc).__name__}, [], 0)
    if size > MAX_FILE_BYTES and path.name != CATALOG_NAME:
        return ("large", None, [], 0)
    text, enc = E.read_text_with_retry(path)
    enc_n = 1 if enc else 0
    if text is None:
        return ("failed", {"path": path_str, "error": enc or "unreadable"}, [], enc_n)
    return ("ok", None, X.extract_file(path, repo, text), enc_n)


def run_sweep(repo: Path | None = None) -> dict[str, Any]:
    repo = repo or C.REPO
    citations: list[dict[str, Any]] = []
    files_scanned = 0
    files_failed: list[dict[str, Any]] = []
    encoding_retries = 0
    skipped_large = 0
    seen_files: set[str] = set()
    files: list[Path] = []
    for path in list(iter_corpus_files(repo)) + list(iter_harness_files()):
        try:
            key = str(path.resolve())
        except OSError:
            key = str(path)
        if key in seen_files:
            continue
        seen_files.add(key)
        files.append(path)

    results = None
    if len(files) >= 400:
        try:
            import os as _os
            from concurrent.futures import ProcessPoolExecutor

            workers = min(8, _os.cpu_count() or 2)
            specs = [(str(p), str(repo)) for p in files]
            with ProcessPoolExecutor(max_workers=workers) as pool:
                results = list(pool.map(_scan_one, specs, chunksize=32))
        except Exception:
            results = None  # fail-open: identical serial semantics
    if results is None:
        results = [_scan_one((str(p), str(repo))) for p in files]
    for status, failed_row, cits, enc_n in results:
        if status == "ok":
            files_scanned += 1
            citations.extend(cits)
            encoding_retries += enc_n
        elif status == "large":
            skipped_large += 1
        else:
            files_failed.append(failed_row)
            encoding_retries += enc_n

    by_path: dict[str, dict[str, Any]] = {}
    for row in citations:
        tok = row["path"]
        rec = by_path.setdefault(
            tok,
            {
                "path": tok,
                "citation_count": 0,
                "citations": [],
            },
        )
        rec["citation_count"] += 1
        if len(rec["citations"]) < 3:
            rec["citations"].append(
                {
                    "file": row.get("file"),
                    "line": row.get("line"),
                    "kind": row.get("kind"),
                }
            )

    path_length_retries = 0
    present_n = 0
    missing_n = 0
    missing_tokens: list[str] = []
    present_sample: list[str] = []
    existence: list[dict[str, Any]] = []
    for tok, rec in sorted(by_path.items()):
        ex = E.exists_with_retry(tok, repo)
        if ex.get("retried_isolated"):
            path_length_retries += 1
        rec.update(ex)
        existence.append(rec)
        if ex["exists"]:
            present_n += 1
            if len(present_sample) < 12:
                present_sample.append(tok)
        else:
            missing_n += 1
            missing_tokens.append(tok)

    git = G.classify_missing_paths(missing_tokens, repo)
    git_by_path = {r["path"]: r for r in git["rows"]}
    missing_rows = []
    for tok in missing_tokens:
        rec = by_path[tok]
        g = git_by_path.get(tok) or {}
        missing_rows.append(
            {
                "path": tok,
                "exists": False,
                "reason": rec.get("reason"),
                "citation_count": rec["citation_count"],
                "first_citation": (rec["citations"] or [None])[0],
                "git_classification": g.get("classification"),
                "git_invoked": g.get("git_invoked"),
                "git_exit_code": g.get("git_exit_code"),
            }
        )

    control = control_from_fixture(repo)
    planted_git = G.classify_one(C.FENCE_MISSING, repo)
    mutant = G.classify_without_git(C.FENCE_MISSING)
    git_ok = planted_git["git_invoked"] is True
    if planted_git["classification"] == "NEVER-EXISTED" and not planted_git["git_available"]:
        git_ok = False
    git_control = {
        "id": "AUD-0033-C2-git-log-vs-existence-alone",
        "planted_missing": C.FENCE_MISSING,
        "git": planted_git,
        "mutant_existence_alone": mutant,
        "fired_on_bad_state": (not mutant["git_invoked"])
        and planted_git["git_invoked"]
        and mutant["classification"] != planted_git["classification"],
        "silent_on_good_state": planted_git["git_invoked"] is True,
        "pass": bool(
            git_ok
            and (not mutant["git_invoked"])
            and mutant["classification"] == "NEVER-EXISTED"
            and (
                planted_git["classification"] != mutant["classification"]
                or planted_git["git_available"]
            )
        ),
    }

    return {
        "files_scanned": files_scanned,
        "files_failed": files_failed[:20],
        "files_failed_count": len(files_failed),
        "skipped_large": skipped_large,
        "encoding_retries": encoding_retries,
        "path_length_retries": path_length_retries,
        "citation_count": len(citations),
        "unique_paths": len(by_path),
        "present_count": present_n,
        "missing_count": missing_n,
        "present_sample": present_sample,
        "missing_rows": missing_rows,
        "git_summary": {
            "available": git["git"]["available"],
            "counts": git["counts"],
            "run_each": git["run_each"],
            "rev_parse": git["git"],
        },
        "harness": harness_inventory(),
        "control": control,
        "git_control": git_control,
        "every_cited_path_exists": missing_n == 0,
    }
