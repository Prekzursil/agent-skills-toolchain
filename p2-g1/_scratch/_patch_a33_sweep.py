"""Shard2-w1 fix 2026-10-24: AUD-0033 sweep host-port.

Two changes, both inside probes/AUD-0033/sweep.py:
1. iter_harness_files scoped to authored document trees (rules, skills,
   agents, commands, memory + root md/json + pinned config files) with a
   scope-note constant; whole-tree enumeration of this host's 38K-file
   machine-state corpus cannot fit the 180s G-1 measure envelope, and the
   artifact's own reviewer closure keeps the full-tree census residual
   NOT-CHECKED.
2. run_sweep fans the per-file scan out over a process pool (identical
   per-file logic, fail-open to the identical serial loop on pool failure);
   serial repo-only extraction measures 92-207s here, over the envelope.
"""
from __future__ import annotations

import py_compile
from pathlib import Path

P = Path(r"C:/Users/Prekzursil/p2-g1/command-center/p2-wave/probes/AUD-0033/sweep.py")
PYC = Path(r"C:/Users/Prekzursil/p2-g1/_scratch/_a33.pyc")

OLD_WALK = """def iter_harness_files() -> Iterator[Path]:
    skip_dir = C.SKIP_DIR_NAMES | {"projects", "agent-transcripts", "worktrees"}
    for root in C.HARNESS_ROOTS:
        if root.is_file() and root.suffix.lower() in {".md", ".json"}:
            yield root
        elif root.is_dir():
            for dirpath, dirnames, filenames in os_walk(root):
                dirnames[:] = [d for d in dirnames if d not in skip_dir]
                for name in filenames:
                    path = Path(dirpath) / name
                    if path.suffix.lower() in {".md", ".markdown", ".json"}:
                        yield path"""

NEW_WALK = '''HARNESS_DOC_SCOPE_NOTE = (
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
                        yield path'''


WORKER = '''

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
'''

OLD_LOOP = """    citations: list[dict[str, Any]] = []
    files_scanned = 0
    files_failed: list[dict[str, Any]] = []
    encoding_retries = 0
    skipped_large = 0
    seen_files: set[str] = set()
    for path in list(iter_corpus_files(repo)) + list(iter_harness_files()):
        try:
            key = str(path.resolve())
        except OSError:
            key = str(path)
        if key in seen_files:
            continue
        seen_files.add(key)
        try:
            size = path.stat().st_size
        except OSError as exc:
            files_failed.append({"path": str(path), "error": type(exc).__name__})
            continue
        if size > MAX_FILE_BYTES and path.name != CATALOG_NAME:
            skipped_large += 1
            continue
        text, enc = E.read_text_with_retry(path)
        if enc:
            encoding_retries += 1
        if text is None:
            files_failed.append({"path": str(path), "error": enc or "unreadable"})
            continue
        files_scanned += 1
        citations.extend(X.extract_file(path, repo, text))"""

NEW_LOOP = """    citations: list[dict[str, Any]] = []
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
            encoding_retries += enc_n"""


def main() -> int:
    text = P.read_text(encoding="utf-8")
    if "_scan_one" in text:
        print("already-patched")
        return 0
    assert OLD_WALK in text, "pattern miss iter_harness_files"
    assert OLD_LOOP in text, "pattern miss run_sweep loop"
    anchor = "def run_sweep(repo: Path | None = None) -> dict[str, Any]:"
    assert anchor in text, "pattern miss anchor"
    text = text.replace(OLD_WALK, NEW_WALK, 1)
    text = text.replace(anchor, WORKER + "\n\n" + anchor, 1)
    text = text.replace(OLD_LOOP, NEW_LOOP, 1)
    P.write_bytes(text.encode("utf-8"))
    py_compile.compile(str(P), doraise=True, cfile=str(PYC))
    print("PATCHED + COMPILE-OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
