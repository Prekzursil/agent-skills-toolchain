"""Probe 1: literal search of surviving files for each deleted path string."""
from __future__ import annotations

from pathlib import Path

from classify import classify_hit
from inventory import DeletedPath, OUTPUT_REL, iter_surviving_files

MENTION_ONLY_CONTROL = "aud0094-retired/tree-agentbridge/file-15.py"
USE_CONTROL = "aud0094-retired/tree-agentbridge/file-00.py"
MAX_BYTES = 8_000_000


def _rel(repo: Path, path: Path) -> str:
    try:
        return path.relative_to(repo).as_posix()
    except ValueError:
        return path.as_posix()


def scan_literal(
    repo: Path,
    deleted: list[DeletedPath],
    *,
    mention_filter: bool = True,
    roots: list[Path] | None = None,
) -> dict:
    needles = [d.path for d in deleted]
    hits: list[dict] = []
    files_scanned = 0
    bytes_scanned = 0
    decode_errors = 0
    roots = roots or [repo]
    skip_names = {Path(OUTPUT_REL).name, "SUBAGENT-RETURN.json", "UNIT-ARTIFACT-MANIFEST.json"}
    impl_prefix = "command-center/p2-wave/probes/AUD-0094/"
    fixture_keep = "command-center/p2-wave/probes/AUD-0094/fixtures/"
    for root in roots:
        for path in iter_surviving_files(root):
            if path.name in skip_names:
                continue
            rel_early = _rel(repo, path)
            if rel_early.startswith(impl_prefix) and not rel_early.startswith(fixture_keep):
                continue
            try:
                size = path.stat().st_size
            except OSError:
                continue
            if size <= 0 or size > MAX_BYTES:
                continue
            try:
                raw = path.read_bytes()
            except OSError:
                continue
            if b"\0" in raw[:4096]:
                continue
            files_scanned += 1
            bytes_scanned += len(raw)
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError:
                text = raw.decode("utf-8", errors="replace")
                decode_errors += 1
            if not any(n in text for n in needles):
                continue
            rel = _rel(repo, path)
            for lineno, line in enumerate(text.splitlines(), 1):
                for needle in needles:
                    if needle not in line:
                        continue
                    kind = classify_hit(rel, line, needle)
                    if not mention_filter:
                        kind = "USE"
                    hits.append(
                        {
                            "deleted_path": needle,
                            "citing_path": rel,
                            "line": lineno,
                            "kind": kind,
                            "detector": "literal-string",
                            "snippet": line.strip()[:240],
                        }
                    )
    use_hits = [h for h in hits if h["kind"] == "USE"]
    mention_hits = [h for h in hits if h["kind"] == "MENTION"]
    dangling_paths = sorted({h["deleted_path"] for h in use_hits})
    mention_only = sorted(
        {
            h["deleted_path"]
            for h in mention_hits
            if h["deleted_path"] not in dangling_paths
        }
    )
    return {
        "files_scanned": files_scanned,
        "bytes_scanned": bytes_scanned,
        "decode_errors": decode_errors,
        "mention_filter": mention_filter,
        "hit_count": len(hits),
        "use_hit_count": len(use_hits),
        "mention_hit_count": len(mention_hits),
        "dangling_paths": dangling_paths,
        "mention_only_paths": mention_only,
        "hits": hits,
        "use_hits": use_hits,
        "mention_hits": mention_hits,
    }


def control_verdict(result: dict, mutant: dict) -> dict:
    dangling = set(result["dangling_paths"])
    mention_only = set(result["mention_only_paths"])
    mention_ok = MENTION_ONLY_CONTROL in mention_only and MENTION_ONLY_CONTROL not in dangling
    use_ok = USE_CONTROL in dangling
    mutant_fired = MENTION_ONLY_CONTROL in set(mutant["dangling_paths"])
    return {
        "mention_only_path": MENTION_ONLY_CONTROL,
        "use_path": USE_CONTROL,
        "mention_not_reported_as_dangling": mention_ok,
        "use_reported_as_dangling": use_ok,
        "mutant_without_filter_flags_changelog": mutant_fired,
        "pass": mention_ok and use_ok and mutant_fired,
    }
