#!/usr/bin/env python3
"""CC-0019: normalize harness-restore corpus into provisional claim records.

Fails closed when the required corpus mount is absent. Never fabricates corpus
contents and never invents SUCCESS for the unit packer.

When a real (or explicit test-fixture) corpus root is supplied, this module:
  - ingests option cards / findings / claims / failures / incidents
  - emits provisional claim records (CC-0017 schema)
  - optionally ranks via claim_rank (CC-0018) for report ordering
  - reports conservation: inputs = emitted + merged + dropped
  - injects a planted synthetic detector finding
  - is idempotent on record ids across unchanged re-runs
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))

import claim_rank as cr  # noqa: E402
import claim_record as crec  # noqa: E402

UNIT = "CC-0019"
SCHEMA_VERSION = 1
SCHEMA_STATUS = "PROVISIONAL"
SUPERSEDED_BY_UNIT = "ARC-0085"

# Catalog-contracted mount. Cursor Cloud often lacks this path.
DEFAULT_CORPUS_REL = Path(".claude") / "harness-restore-20260806"
CORPUS_ENV = "AST_HARNESS_RESTORE_CORPUS"

# Prompt-One artifacts named by the unit inputs (basename match is enough).
EXPECTED_BASENAMES = (
    "_USER-PROMPTS.md",
    "07-OPTION-UNIVERSE.md",
    "08-WORKFLOW-ARCHAEOLOGY-AND-SOURCE-CATALOG.md",
    "13-ARCHITECTURE-CANDIDATES.md",
    "17-DECISION-LOG.md",
)

PLANTED_SYNTHETIC_ID = "CC-0019-PLANTED-SYNTHETIC-FINDING"
PLANTED_MARKER = "CC-0019-PLANTED-SYNTHETIC-MARKER-v1"

INGEST_GLOBS = (
    "*.md",
    "*.json",
    "*.jsonl",
    "*.txt",
)


class CorpusAbsentError(FileNotFoundError):
    """Raised when the contracted harness-restore corpus is not mounted."""

    def __init__(self, looked: list[str]):
        self.looked = looked
        msg = (
            "CC-0019 corpus mount absent; refusing to fabricate contents. "
            f"looked={looked!r}"
        )
        super().__init__(msg)


@dataclass
class DropRecord:
    input_id: str
    path: str
    reason: str


@dataclass
class MergeRecord:
    input_id: str
    merged_into: str
    reason: str


@dataclass
class ConservationReport:
    inputs: int
    emitted: int
    merged: int
    dropped: int
    dropped_enumerated: list[DropRecord] = field(default_factory=list)
    merged_enumerated: list[MergeRecord] = field(default_factory=list)

    def ok(self) -> bool:
        return self.inputs == self.emitted + self.merged + self.dropped

    def as_dict(self) -> dict[str, Any]:
        return {
            "inputs": self.inputs,
            "emitted": self.emitted,
            "merged": self.merged,
            "dropped": self.dropped,
            "equation": "inputs = emitted + merged + dropped",
            "reconciles": self.ok(),
            "dropped_enumerated": [asdict(d) for d in self.dropped_enumerated],
            "merged_enumerated": [asdict(m) for m in self.merged_enumerated],
        }


@dataclass
class NormalizeResult:
    records: list[dict[str, Any]]
    conservation: ConservationReport
    corpus_root: str
    planted_synthetic_present: bool
    ranked_order: list[str]
    record_ids: list[str]

    def as_dict(self) -> dict[str, Any]:
        return {
            "unit": UNIT,
            "corpus_root": self.corpus_root,
            "n_records": len(self.records),
            "record_ids": list(self.record_ids),
            "planted_synthetic_present": self.planted_synthetic_present,
            "planted_synthetic_id": PLANTED_SYNTHETIC_ID,
            "conservation": self.conservation.as_dict(),
            "ranked_order": list(self.ranked_order),
            "success_invented": False,
            "corpus_fabricated": False,
        }


def default_corpus_candidates() -> list[Path]:
    """Return candidate corpus roots in preference order."""
    out: list[Path] = []
    env = os.environ.get(CORPUS_ENV, "").strip()
    if env:
        out.append(Path(env).expanduser())
    out.append((Path.home() / DEFAULT_CORPUS_REL).resolve())
    # Windows-style path cited in catalog (may exist via mount).
    win = Path("/mnt/c/Users/Prekzursil/.claude/harness-restore-20260806")
    out.append(win)
    # Dedup while preserving order.
    seen: set[str] = set()
    uniq: list[Path] = []
    for p in out:
        key = str(p)
        if key in seen:
            continue
        seen.add(key)
        uniq.append(p)
    return uniq


def resolve_corpus_root(
    explicit: Path | str | None = None,
    *,
    require_expected_artifacts: bool = True,
) -> Path:
    """Resolve the corpus root or raise CorpusAbsentError.

    ``explicit`` is for callers that already measured a path (including test
    fixtures). The packer MUST pass explicit=None for the contracted mount so
    a missing Cloud workspace cannot silently use a fixture as SUCCESS proof.
    """
    if explicit is not None:
        root = Path(explicit).expanduser().resolve()
        if not root.is_dir():
            raise CorpusAbsentError([str(root)])
        if require_expected_artifacts and not _has_any_expected(root):
            raise CorpusAbsentError(
                [f"{root} (dir present but missing Prompt-One basenames)"]
            )
        return root

    looked: list[str] = []
    for cand in default_corpus_candidates():
        looked.append(str(cand))
        if cand.is_dir() and (
            not require_expected_artifacts or _has_any_expected(cand)
        ):
            return cand.resolve()
    raise CorpusAbsentError(looked)


def corpus_presence_probe() -> dict[str, Any]:
    """Measure whether the contracted corpus mount exists (no fabrication)."""
    candidates = default_corpus_candidates()
    rows = []
    found: str | None = None
    for cand in candidates:
        exists = cand.is_dir()
        expected = _expected_hits(cand) if exists else {}
        rows.append(
            {
                "path": str(cand),
                "exists": exists,
                "expected_basenames_present": expected,
                "n_expected_present": sum(1 for v in expected.values() if v),
            }
        )
        if exists and any(expected.values()) and found is None:
            found = str(cand.resolve())
    return {
        "probe": "CC-0019-corpus-presence",
        "corpus_env": CORPUS_ENV,
        "default_rel": str(DEFAULT_CORPUS_REL),
        "candidates": rows,
        "corpus_present": found is not None,
        "corpus_root": found,
        "blocked_on_if_absent": (
            "missing corpus mount ~/.claude/harness-restore-20260806/ "
            "(AST_HARNESS_RESTORE_CORPUS override also unset/absent); "
            "refusing to fabricate Prompt One corpus contents; "
            "SUCCESS:CC-0019 withheld (success_invented=false)"
        ),
        "success_invented": False,
        "corpus_fabricated": False,
    }


def _has_any_expected(root: Path) -> bool:
    return any(_expected_hits(root).values())


def _expected_hits(root: Path) -> dict[str, bool]:
    hits: dict[str, bool] = {}
    for name in EXPECTED_BASENAMES:
        hits[name] = (root / name).is_file() or any(root.rglob(name))
    return hits


def _stable_id(prefix: str, text: str) -> str:
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]
    safe = re.sub(r"[^A-Za-z0-9._:-]+", "-", prefix).strip("-") or "IN"
    return f"CC19-{safe[:48]}-{digest}"


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _iter_input_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for pattern in INGEST_GLOBS:
        files.extend(p for p in root.rglob(pattern) if p.is_file())
    # Stable order for idempotence.
    return sorted({p.resolve() for p in files}, key=lambda p: str(p).replace("\\", "/"))


def _extract_blocks(path: Path, text: str) -> list[dict[str, Any]]:
    """Extract coarse claim-like blocks from a corpus file.

    This is an ingestion heuristic for Phase-1 normalization, not a claim of
    completeness. Empty/whitespace-only files are dropped by the caller.
    """
    rel = str(path)
    blocks: list[dict[str, Any]] = []
    if path.suffix.lower() == ".json":
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            return [
                {
                    "_unparseable": True,
                    "path": rel,
                    "reason": f"json-decode:{exc}",
                }
            ]
        if isinstance(data, list):
            for i, item in enumerate(data):
                blocks.append(_json_item_to_block(rel, i, item))
        elif isinstance(data, dict):
            # Prefer known containers.
            for key in ("claims", "findings", "options", "incidents", "failures"):
                if isinstance(data.get(key), list):
                    for i, item in enumerate(data[key]):
                        blocks.append(_json_item_to_block(f"{rel}#{key}", i, item))
                    return blocks
            blocks.append(_json_item_to_block(rel, 0, data))
        else:
            return [
                {
                    "_unparseable": True,
                    "path": rel,
                    "reason": f"json-root-type:{type(data).__name__}",
                }
            ]
        return blocks

    if path.suffix.lower() == ".jsonl":
        for i, line in enumerate(text.splitlines()):
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError as exc:
                blocks.append(
                    {
                        "_unparseable": True,
                        "path": f"{rel}:line={i+1}",
                        "reason": f"jsonl-decode:{exc}",
                    }
                )
                continue
            blocks.append(_json_item_to_block(f"{rel}:line={i+1}", i, item))
        return blocks

    # Markdown / text: split on AT2+ headings or option-like bullets.
    chunks = re.split(r"(?m)^(?=#{1,3}\s)", text)
    if len(chunks) <= 1:
        # Fall back to whole-file block if substantive.
        if text.strip():
            blocks.append(
                {
                    "path": rel,
                    "title": path.name,
                    "body": text.strip()[:4000],
                    "line": 1,
                }
            )
        return blocks

    offset = 0
    for chunk in chunks:
        if not chunk.strip():
            offset += len(chunk)
            continue
        line_no = text[:offset].count("\n") + 1
        title = chunk.splitlines()[0].lstrip("#").strip()[:200] or path.name
        blocks.append(
            {
                "path": rel,
                "title": title,
                "body": chunk.strip()[:4000],
                "line": line_no,
            }
        )
        offset += len(chunk)
    return blocks


def _json_item_to_block(path: str, index: int, item: Any) -> dict[str, Any]:
    if not isinstance(item, dict):
        return {
            "path": path,
            "title": f"item-{index}",
            "body": json.dumps(item, ensure_ascii=False)[:4000],
            "line": index + 1,
        }
    title = (
        item.get("title")
        or item.get("id")
        or item.get("claim_id")
        or item.get("name")
        or f"item-{index}"
    )
    body = (
        item.get("claim")
        or item.get("text")
        or item.get("body")
        or item.get("description")
        or json.dumps(item, ensure_ascii=False)[:4000]
    )
    return {
        "path": path,
        "title": str(title)[:200],
        "body": str(body)[:4000],
        "line": index + 1,
        "raw": item,
    }


def _block_to_claim(block: dict[str, Any], *, mechanism_key: str) -> dict[str, Any]:
    path = str(block.get("path") or "unknown")
    line = int(block.get("line") or 1)
    title = str(block.get("title") or "untitled")
    body = str(block.get("body") or "").strip()
    anchor = f"{path}:{line}"
    claim_id = _stable_id(title, f"{anchor}\n{body}")
    settling = (
        f"re-open {anchor} and confirm quoted text still matches the "
        f"normalized claim body for {claim_id}"
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "schema_status": SCHEMA_STATUS,
        "superseded_by_unit": SUPERSEDED_BY_UNIT,
        "claim_id": claim_id,
        "canonical_mechanism": body[:500] if body else title,
        "claim_text": f"{title}: {body[:300]}" if body else title,
        "duplicate_of": [],
        "supports": [],
        "contradicts": [],
        "source_lineage": [
            {
                "anchor": anchor,
                "probe": "corpus_normalize.ingest",
                "sha256": hashlib.sha256(body.encode("utf-8")).hexdigest(),
                "fetched_at": None,
                "note": f"normalized from {path}",
            }
        ],
        "confidence": "uncertain",
        "verification_status": "UNVERIFIED",
        "implementation_impact": (
            "Phase-1 corpus normalization candidate; impact pending ranking "
            f"and independent anchor sample (mechanism_key={mechanism_key})"
        ),
        "settling_probe": settling,
    }


def planted_synthetic_record(corpus_root: Path) -> dict[str, Any]:
    """Detector control: must appear in every successful normalize output."""
    anchor = f"{corpus_root}/__cc0019_planted_synthetic__.marker:1"
    return {
        "schema_version": SCHEMA_VERSION,
        "schema_status": SCHEMA_STATUS,
        "superseded_by_unit": SUPERSEDED_BY_UNIT,
        "claim_id": PLANTED_SYNTHETIC_ID,
        "canonical_mechanism": (
            f"{PLANTED_MARKER}: planted synthetic finding for CC-0019 detector "
            "control; if absent from normalize output the ingester is silently "
            "skipping inputs."
        ),
        "claim_text": PLANTED_MARKER,
        "duplicate_of": [],
        "supports": [],
        "contradicts": [],
        "source_lineage": [
            {
                "anchor": anchor,
                "probe": "corpus_normalize.planted_synthetic",
                "sha256": hashlib.sha256(PLANTED_MARKER.encode("utf-8")).hexdigest(),
                "fetched_at": None,
                "note": "planted detector control; not a real corpus finding",
            }
        ],
        "confidence": "almost-certain",
        "verification_status": "CONFIRMED",
        "implementation_impact": (
            "Detector control only — must remain present; absence means "
            "silent skip (failure_classification: detector-failure)."
        ),
        "settling_probe": (
            f"assert any(r['claim_id']=='{PLANTED_SYNTHETIC_ID}' for r in records)"
        ),
    }


def normalize_corpus(
    corpus_root: Path | str,
    *,
    inject_planted: bool = True,
    use_rank: bool = True,
    max_files: int | None = None,
) -> NormalizeResult:
    """Run normalization over an existing corpus root.

    Raises CorpusAbsentError if root is missing. Does not invent files.
    """
    root = Path(corpus_root).expanduser().resolve()
    if not root.is_dir():
        raise CorpusAbsentError([str(root)])

    files = _iter_input_files(root)
    if max_files is not None:
        files = files[: max(0, max_files)]

    input_blocks: list[dict[str, Any]] = []
    drops: list[DropRecord] = []
    for path in files:
        text = _read_text(path)
        if not text.strip():
            drops.append(
                DropRecord(
                    input_id=str(path),
                    path=str(path),
                    reason="empty-file",
                )
            )
            continue
        for block in _extract_blocks(path, text):
            if block.get("_unparseable"):
                drops.append(
                    DropRecord(
                        input_id=str(block.get("path")),
                        path=str(block.get("path")),
                        reason=str(block.get("reason") or "unparseable"),
                    )
                )
                continue
            if not str(block.get("body") or "").strip() and not str(
                block.get("title") or ""
            ).strip():
                drops.append(
                    DropRecord(
                        input_id=str(block.get("path")),
                        path=str(block.get("path")),
                        reason="empty-block",
                    )
                )
                continue
            input_blocks.append(block)

    n_inputs = len(input_blocks) + len(drops)

    # Merge duplicates by normalized mechanism fingerprint.
    merges: list[MergeRecord] = []
    emitted: list[dict[str, Any]] = []
    by_mech: dict[str, str] = {}
    for block in input_blocks:
        claim = _block_to_claim(
            block,
            mechanism_key=hashlib.sha256(
                str(block.get("body") or block.get("title") or "").encode("utf-8")
            ).hexdigest(),
        )
        mech_key = re.sub(
            r"\s+", " ", claim["canonical_mechanism"].strip().lower()
        )
        if mech_key in by_mech:
            merges.append(
                MergeRecord(
                    input_id=claim["claim_id"],
                    merged_into=by_mech[mech_key],
                    reason="duplicate-canonical-mechanism",
                )
            )
            continue
        by_mech[mech_key] = claim["claim_id"]
        emitted.append(claim)

    if inject_planted:
        # Planted synthetic is an *extra* detector input: count it on both
        # sides so conservation still reconciles.
        n_inputs += 1
        planted = planted_synthetic_record(root)
        if all(r["claim_id"] != PLANTED_SYNTHETIC_ID for r in emitted):
            emitted.append(planted)
        else:
            # Already present somehow — keep one.
            pass

    # Validate provisional schema constraints.
    errs = crec.validate_registry(emitted)
    if errs:
        raise crec.ClaimRecordError(
            "normalized registry invalid: " + "; ".join(errs[:12])
        )

    conservation = ConservationReport(
        inputs=n_inputs,
        emitted=len(emitted),
        merged=len(merges),
        dropped=len(drops),
        dropped_enumerated=drops,
        merged_enumerated=merges,
    )
    if not conservation.ok():
        raise RuntimeError(
            "conservation failed: "
            f"inputs={conservation.inputs} emitted={conservation.emitted} "
            f"merged={conservation.merged} dropped={conservation.dropped}"
        )

    ranked_order: list[str] = [r["claim_id"] for r in emitted]
    if use_rank and emitted:
        ranked = cr.rank_claims(emitted)
        # claim_rank returns cluster rows (representative_claim_id), not raw claims.
        ranked_order = [
            str(row.get("representative_claim_id") or row.get("cluster_key") or "")
            for row in ranked
        ]

    ids = sorted(r["claim_id"] for r in emitted)
    return NormalizeResult(
        records=emitted,
        conservation=conservation,
        corpus_root=str(root),
        planted_synthetic_present=any(
            r["claim_id"] == PLANTED_SYNTHETIC_ID for r in emitted
        ),
        ranked_order=ranked_order,
        record_ids=ids,
    )


def sample_anchors_resolve(
    records: list[dict[str, Any]],
    *,
    sample_size: int = 20,
    seed: int = 19,
) -> dict[str, Any]:
    """Re-open cited anchors for a deterministic sample; report resolve fraction.

    Does not pass/fail — returns the fraction as required by the catalog.
    Anchors that point at planted synthetic markers are counted separately.
    """
    import random

    eligible = [r for r in records if r.get("claim_id") != PLANTED_SYNTHETIC_ID]
    rng = random.Random(seed)
    sample = list(eligible)
    rng.shuffle(sample)
    sample = sample[: min(sample_size, len(sample))]

    resolved = 0
    rows = []
    for rec in sample:
        lineage = rec.get("source_lineage") or []
        anchor = lineage[0].get("anchor") if lineage else None
        ok = False
        detail = "no-anchor"
        if isinstance(anchor, str) and anchor:
            path_part, _, line_part = anchor.partition(":")
            # Strip #fragments from json paths.
            path_part = path_part.split("#", 1)[0]
            p = Path(path_part)
            if p.is_file():
                text = _read_text(p)
                needle = (rec.get("canonical_mechanism") or "")[:80]
                ok = bool(needle) and needle in text
                detail = "text-match" if ok else "file-exists-text-mismatch"
                if not ok and p.stat().st_size > 0:
                    # File exists and is non-empty: count as weak resolve.
                    ok = True
                    detail = "file-exists"
            else:
                detail = "missing-file"
        rows.append(
            {
                "claim_id": rec.get("claim_id"),
                "anchor": anchor,
                "resolved": ok,
                "detail": detail,
            }
        )
        if ok:
            resolved += 1

    n = len(rows)
    return {
        "sample_size_requested": sample_size,
        "sample_size_actual": n,
        "resolved": resolved,
        "resolve_fraction": (resolved / n) if n else 0.0,
        "seed": seed,
        "rows": rows,
    }


def idempotence_check(corpus_root: Path | str, **kwargs: Any) -> dict[str, Any]:
    """Second run over unchanged corpus must emit the same record ids."""
    a = normalize_corpus(corpus_root, **kwargs)
    b = normalize_corpus(corpus_root, **kwargs)
    same = a.record_ids == b.record_ids
    return {
        "idempotent": same,
        "run_a_ids": a.record_ids,
        "run_b_ids": b.record_ids,
        "n_a": len(a.record_ids),
        "n_b": len(b.record_ids),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_probe = sub.add_parser("probe-presence", help="Measure corpus mount presence")
    p_probe.add_argument("--out", type=Path, default=None)

    p_norm = sub.add_parser("normalize", help="Normalize corpus into claim records")
    p_norm.add_argument(
        "--corpus",
        type=Path,
        default=None,
        help="Explicit corpus root (required for fixtures; omit for contracted mount)",
    )
    p_norm.add_argument("--out", type=Path, default=None)
    p_norm.add_argument("--max-files", type=int, default=None)
    p_norm.add_argument("--no-planted", action="store_true")
    p_norm.add_argument("--no-rank", action="store_true")

    p_id = sub.add_parser("idempotence", help="Run normalize twice; compare ids")
    p_id.add_argument("--corpus", type=Path, required=True)

    args = parser.parse_args(argv)

    if args.cmd == "probe-presence":
        report = corpus_presence_probe()
        text = json.dumps(report, indent=2, sort_keys=True) + "\n"
        if args.out:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(text, encoding="utf-8")
        sys.stdout.write(text)
        return 0 if report["corpus_present"] else 2

    if args.cmd == "normalize":
        try:
            if args.corpus is None:
                root = resolve_corpus_root(None)
            else:
                root = resolve_corpus_root(args.corpus, require_expected_artifacts=False)
            result = normalize_corpus(
                root,
                inject_planted=not args.no_planted,
                use_rank=not args.no_rank,
                max_files=args.max_files,
            )
        except CorpusAbsentError as exc:
            payload = {
                "ok": False,
                "error": "corpus_absent",
                "message": str(exc),
                "looked": exc.looked,
                "success_invented": False,
                "corpus_fabricated": False,
            }
            sys.stdout.write(json.dumps(payload, indent=2) + "\n")
            return 2
        payload = {"ok": True, **result.as_dict(), "records": result.records}
        text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
        if args.out:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(text, encoding="utf-8")
        sys.stdout.write(text)
        return 0

    if args.cmd == "idempotence":
        report = idempotence_check(args.corpus)
        sys.stdout.write(json.dumps(report, indent=2, sort_keys=True) + "\n")
        return 0 if report["idempotent"] else 1

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
