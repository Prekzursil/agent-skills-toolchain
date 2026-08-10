"""Live deployment synchronisation: per-file provenance and a TWO-DIRECTIONAL drift classifier.

The measured lesson this module exists to encode: six independent agents classified 338 files as
"safe to overwrite" at 86% accuracy, and **100% of their errors pointed at data loss** — every one
was the DIVERGED case, both sides holding unique content, misread as safe. The blind spot was
structural: they checked whether one side had extra content and stopped. So the classifier here is
deliberately mechanical and reads BOTH directions against a recorded provenance hash:

| class | live vs provenance | source vs provenance | action |
|---|---|---|---|
| ``unchanged`` | same | same | nothing |
| ``upstream_only`` | same | differs | deploy (safe) |
| ``live_only`` | differs | same | keep live (user override) |
| ``diverged`` | differs | differs | **never auto-resolve** — decision packet |
| ``live_absent`` | missing | any | deploy |
| ``untracked_live`` | no provenance | n/a | treat as diverged |

All hashing is EOL-normalised (``fsops.content_hash``): Git stores LF and Windows checks out CRLF,
so a raw-byte comparison manufactures phantom drift on every text file.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path

from .errors import PluginError
from .fsops import atomic_write_bytes, content_hash, iter_files, relposix, safe_join
from .journal import Prefix, Transaction
from .manifest import Manifest

PROVENANCE_NAME = "deploy-provenance.json"

CLASS_UNCHANGED = "unchanged"
CLASS_UPSTREAM_ONLY = "upstream_only"
CLASS_LIVE_ONLY = "live_only"
CLASS_DIVERGED = "diverged"
CLASS_LIVE_ABSENT = "live_absent"
CLASS_UNTRACKED_LIVE = "untracked_live"

#: Classes safe to write without an owner decision.
DEPLOYABLE = frozenset({CLASS_UNCHANGED, CLASS_UPSTREAM_ONLY, CLASS_LIVE_ABSENT})
#: Classes that hold content only the live tree has. `repair` must never touch these.
LIVE_UNIQUE = frozenset({CLASS_LIVE_ONLY, CLASS_DIVERGED, CLASS_UNTRACKED_LIVE})


@dataclass
class ProvenanceRecord:
    live_path: str
    source_path: str
    version: str
    content_sha256: str
    deployed_at: float
    mode: str

    def as_dict(self) -> dict[str, object]:
        return {
            "live_path": self.live_path,
            "source_path": self.source_path,
            "version": self.version,
            "content_sha256": self.content_sha256,
            "deployed_at": self.deployed_at,
            "mode": self.mode,
        }


@dataclass
class Provenance:
    path: Path
    records: dict[str, ProvenanceRecord] = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path) -> Provenance:
        p = cls(path=path)
        if not path.exists():
            return p
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise PluginError("E_TXN", f"deploy provenance is corrupt: {exc}") from exc
        for rec in doc.get("records", []):
            p.records[rec["live_path"]] = ProvenanceRecord(
                live_path=rec["live_path"],
                source_path=rec["source_path"],
                version=rec["version"],
                content_sha256=rec["content_sha256"],
                deployed_at=float(rec.get("deployed_at", 0.0)),
                mode=rec.get("mode", "copy"),
            )
        return p

    def save(self) -> None:
        doc = {
            "artifact": "deploy-provenance",
            "record_count": len(self.records),
            "records": [
                r.as_dict()
                for r in sorted(self.records.values(), key=lambda r: r.live_path)
            ],
        }
        atomic_write_bytes(
            self.path, (json.dumps(doc, indent=2, sort_keys=True) + "\n").encode()
        )

    def as_document(self) -> dict[str, object]:
        return {
            "artifact": "deploy-provenance",
            "record_count": len(self.records),
            "records": [
                r.as_dict()
                for r in sorted(self.records.values(), key=lambda r: r.live_path)
            ],
        }


@dataclass
class DriftEntry:
    live_path: str
    source_path: str | None
    classification: str
    live_hash: str | None
    source_hash: str | None
    provenance_hash: str | None
    reason: str

    def as_dict(self) -> dict[str, object]:
        return {
            "live_path": self.live_path,
            "source_path": self.source_path,
            "classification": self.classification,
            "live_sha256": self.live_hash,
            "source_sha256": self.source_hash,
            "provenance_sha256": self.provenance_hash,
            "reason": self.reason,
        }


def _target_pairs(
    manifest: Manifest, version_root: Path, live_root: Path
) -> list[tuple[Path, str, str]]:
    """(source file, live-relative path, mode) for every file every deploy target covers."""
    pairs: list[tuple[Path, str, str]] = []
    for target in manifest.deploy_targets:
        src_root = (
            safe_join(version_root, target.source)
            if target.source not in (".", "")
            else version_root
        )
        if not src_root.exists():
            continue
        if src_root.is_file():
            pairs.append((src_root, target.target, target.mode))
            continue
        for f in iter_files(src_root):
            rel = relposix(src_root, f)
            live_rel = (
                f"{target.target.rstrip('/')}/{rel}"
                if target.target not in (".", "")
                else rel
            )
            pairs.append((f, live_rel, target.mode))
    return pairs


def classify(
    manifest: Manifest, version_root: Path, live_root: Path, provenance: Provenance
) -> list[DriftEntry]:
    """The two-directional classifier. Reads live, source, and the recorded provenance hash."""
    entries: list[DriftEntry] = []
    covered: set[str] = set()
    for src, live_rel, _mode in _target_pairs(manifest, version_root, live_root):
        covered.add(live_rel)
        src_hash = content_hash(src)
        live_file = safe_join(live_root, live_rel)
        prov = provenance.records.get(live_rel)
        prov_hash = prov.content_sha256 if prov else None
        if not live_file.exists():
            entries.append(
                DriftEntry(
                    live_rel,
                    relposix(version_root, src),
                    CLASS_LIVE_ABSENT,
                    None,
                    src_hash,
                    prov_hash,
                    "live file does not exist",
                )
            )
            continue
        live_hash = content_hash(live_file)
        if prov_hash is None:
            entries.append(
                DriftEntry(
                    live_rel,
                    relposix(version_root, src),
                    CLASS_UNCHANGED if live_hash == src_hash else CLASS_UNTRACKED_LIVE,
                    live_hash,
                    src_hash,
                    None,
                    "identical to source, adoptable"
                    if live_hash == src_hash
                    else "live file has no provenance record; its origin is unknown",
                )
            )
            continue
        live_moved = live_hash != prov_hash
        source_moved = src_hash != prov_hash
        if not live_moved and not source_moved:
            klass, reason = CLASS_UNCHANGED, "live, source and provenance agree"
        elif not live_moved and source_moved:
            klass, reason = (
                CLASS_UPSTREAM_ONLY,
                "only the source advanced; live is untouched",
            )
        elif live_moved and not source_moved:
            klass, reason = (
                CLASS_LIVE_ONLY,
                "only live changed; this is a user override",
            )
        elif live_hash == src_hash:
            klass, reason = CLASS_UNCHANGED, "both advanced to the same content"
        else:
            klass, reason = CLASS_DIVERGED, "live AND source both hold unique content"
        entries.append(
            DriftEntry(
                live_rel,
                relposix(version_root, src),
                klass,
                live_hash,
                src_hash,
                prov_hash,
                reason,
            )
        )
    # Provenance rows whose source vanished from this version: live-side orphans.
    for live_rel, prov in provenance.records.items():
        if live_rel in covered:
            continue
        live_file = safe_join(live_root, live_rel)
        if not live_file.exists():
            continue
        live_hash = content_hash(live_file)
        klass = CLASS_UNCHANGED if live_hash == prov.content_sha256 else CLASS_LIVE_ONLY
        entries.append(
            DriftEntry(
                live_rel,
                None,
                klass,
                live_hash,
                None,
                prov.content_sha256,
                "source no longer ships this path"
                + ("" if klass == CLASS_UNCHANGED else "; live content was edited"),
            )
        )
    entries.sort(key=lambda e: e.live_path)
    return entries


def drift_document(entries: list[DriftEntry]) -> dict[str, object]:
    """The drift-classification artifact (tools/plugin/schema/drift-classification.schema.json)."""
    counts: dict[str, int] = {}
    for e in entries:
        counts[e.classification] = counts.get(e.classification, 0) + 1
    return {
        "artifact": "drift-classification",
        "bidirectional": True,
        "hash_algorithm": "sha256-over-LF-normalised-bytes",
        "counts": {
            k: counts.get(k, 0)
            for k in sorted(
                {
                    CLASS_UNCHANGED,
                    CLASS_UPSTREAM_ONLY,
                    CLASS_LIVE_ONLY,
                    CLASS_DIVERGED,
                    CLASS_LIVE_ABSENT,
                    CLASS_UNTRACKED_LIVE,
                }
            )
        },
        "entries": [e.as_dict() for e in entries],
    }


def divergence_decisions(entries: list[DriftEntry]) -> dict[str, object]:
    """Decision packet for the diverged set (tools/plugin/schema/divergence-decision.schema.json).

    Never auto-resolves. Each row states what each side holds and enumerates the options; the
    ``chosen`` field is deliberately null so an unreviewed packet cannot be mistaken for a
    resolution.
    """
    diverged = [
        e for e in entries if e.classification in {CLASS_DIVERGED, CLASS_UNTRACKED_LIVE}
    ]
    return {
        "artifact": "divergence-decision",
        "auto_resolved": False,
        "decision_required": len(diverged),
        "decisions": [
            {
                "live_path": e.live_path,
                "source_path": e.source_path,
                "live_sha256": e.live_hash,
                "source_sha256": e.source_hash,
                "provenance_sha256": e.provenance_hash,
                "reason": e.reason,
                "options": ["keep_live", "take_source", "merge_manually"],
                "chosen": None,
            }
            for e in diverged
        ],
    }


@dataclass
class SyncResult:
    written: list[str] = field(default_factory=list)
    kept: list[str] = field(default_factory=list)
    needs_decision: list[str] = field(default_factory=list)
    dry_run: bool = False
    entries: list[DriftEntry] = field(default_factory=list)

    def as_dict(self) -> dict[str, object]:
        return {
            "artifact": "sync-result",
            "dry_run": self.dry_run,
            "written": self.written,
            "kept_live_override": self.kept,
            "needs_decision": self.needs_decision,
        }


def sync(
    manifest: Manifest,
    version_root: Path,
    live_root: Path,
    prefix: Prefix,
    *,
    txn: Transaction | None = None,
    dry_run: bool = False,
    force_source: bool = False,
) -> SyncResult:
    """Deploy the deployable classes; keep live overrides; refuse to resolve divergence."""
    provenance = Provenance.load(prefix.state / PROVENANCE_NAME)
    entries = classify(manifest, version_root, live_root, provenance)
    result = SyncResult(dry_run=dry_run, entries=entries)
    mode_by_path = {
        live_rel: mode
        for _, live_rel, mode in _target_pairs(manifest, version_root, live_root)
    }
    src_by_path = {
        live_rel: src
        for src, live_rel, _ in _target_pairs(manifest, version_root, live_root)
    }

    for entry in entries:
        if entry.classification in LIVE_UNIQUE and not force_source:
            (
                result.needs_decision
                if entry.classification != CLASS_LIVE_ONLY
                else result.kept
            ).append(entry.live_path)
            continue
        if entry.source_path is None:
            continue
        if (
            entry.classification == CLASS_UNCHANGED
            and entry.provenance_hash == entry.source_hash
        ):
            continue
        src = src_by_path.get(entry.live_path)
        if src is None:
            continue
        target = safe_join(live_root, entry.live_path)
        if dry_run:
            result.written.append(entry.live_path)
            continue
        previous = target.read_bytes() if target.exists() else None

        def _undo(t: Path = target, prev: bytes | None = previous) -> None:
            if prev is None:
                if t.exists():
                    t.unlink()
            else:
                atomic_write_bytes(t, prev)

        if txn is not None:
            txn.add(
                "deploy_file",
                {"live_path": entry.live_path, "class": entry.classification},
                _undo,
            )
        atomic_write_bytes(target, src.read_bytes())
        provenance.records[entry.live_path] = ProvenanceRecord(
            live_path=entry.live_path,
            source_path=entry.source_path,
            version=manifest.version,
            content_sha256=content_hash(target),
            deployed_at=round(time.time(), 3),
            mode=mode_by_path.get(entry.live_path, "copy"),
        )
        result.written.append(entry.live_path)

    if not dry_run:
        provenance.save()
    return result


def repair(
    manifest: Manifest,
    version_root: Path,
    live_root: Path,
    prefix: Prefix,
    *,
    dry_run: bool = False,
) -> SyncResult:
    """Restore ONLY files with no live-unique content. `live_only`/`diverged` are never touched."""
    provenance = Provenance.load(prefix.state / PROVENANCE_NAME)
    entries = classify(manifest, version_root, live_root, provenance)
    result = SyncResult(dry_run=dry_run, entries=entries)
    src_by_path = {
        live_rel: src
        for src, live_rel, _ in _target_pairs(manifest, version_root, live_root)
    }
    for entry in entries:
        if entry.classification in LIVE_UNIQUE:
            (
                result.needs_decision
                if entry.classification != CLASS_LIVE_ONLY
                else result.kept
            ).append(entry.live_path)
            continue
        if entry.live_hash == entry.source_hash and entry.live_hash is not None:
            continue  # already correct
        src = src_by_path.get(entry.live_path)
        if src is None:
            continue
        if dry_run:
            result.written.append(entry.live_path)
            continue
        target = safe_join(live_root, entry.live_path)
        atomic_write_bytes(target, src.read_bytes())
        provenance.records[entry.live_path] = ProvenanceRecord(
            live_path=entry.live_path,
            source_path=entry.source_path or entry.live_path,
            version=manifest.version,
            content_sha256=content_hash(target),
            deployed_at=round(time.time(), 3),
            mode="copy",
        )
        result.written.append(entry.live_path)
    if not dry_run:
        provenance.save()
    return result


def projection_map(
    manifest: Manifest, version_root: Path, live_root: Path
) -> dict[str, object]:
    """Manifest-to-live-config projection (IMP-0010), with the per-OS argv of every entrypoint.

    This is the auditable answer to "what will installing this actually put where, and what will
    it run" — computed from the manifest alone, without executing anything.
    """
    from .proc import launch_argv

    counts: dict[tuple[str, str, str], int] = {}
    for _src, live_rel, mode in _target_pairs(manifest, version_root, live_root):
        for target in manifest.deploy_targets:
            if target.mode == mode and live_rel.startswith(target.target.rstrip("/")):
                counts[(target.source, target.target, target.mode)] = (
                    counts.get((target.source, target.target, target.mode), 0) + 1
                )
                break
    entrypoints: list[dict[str, object]] = []
    for ep in manifest.entrypoints:
        launch: dict[str, list[str]] = {}
        for osn in manifest.platforms:
            if ep.interpreter:
                launch[osn] = launch_argv(
                    ep.interpreter, version_root / ep.path, list(ep.args), os_name=osn
                )
            else:
                launch[osn] = []
        entrypoints.append(
            {
                "id": ep.ident,
                "kind": ep.kind,
                "path": ep.path,
                "interpreter": ep.interpreter,
                "launch": launch,
            }
        )
    return {
        "artifact": "projection-map",
        "plugin": manifest.name,
        "version": manifest.version,
        "targets": [
            {
                "source": t.source,
                "target": t.target,
                "mode": t.mode,
                "file_count": counts.get((t.source, t.target, t.mode), 0),
            }
            for t in manifest.deploy_targets
        ],
        "entrypoints": entrypoints,
    }


def three_way_merge(
    base: str, live: str, incoming: str
) -> tuple[str | None, list[str]]:
    """Line-wise three-way merge (IMP-0031). Returns (merged text or None, conflict summaries).

    A ``None`` result means the hunks overlap and no merge is safe — the caller must escalate to a
    decision packet rather than pick a side.
    """
    import difflib

    base_lines = base.splitlines(keepends=True)
    live_lines = live.splitlines(keepends=True)
    inc_lines = incoming.splitlines(keepends=True)
    live_ops = [
        op
        for op in difflib.SequenceMatcher(None, base_lines, live_lines).get_opcodes()
        if op[0] != "equal"
    ]
    inc_ops = [
        op
        for op in difflib.SequenceMatcher(None, base_lines, inc_lines).get_opcodes()
        if op[0] != "equal"
    ]
    conflicts: list[str] = []
    for lo in live_ops:
        for io in inc_ops:
            if lo[1] < io[2] and io[1] < lo[2]:
                conflicts.append(
                    f"overlapping hunk base[{max(lo[1], io[1])}:{min(lo[2], io[2])}]"
                )
    if conflicts:
        return None, sorted(set(conflicts))
    # Non-overlapping: apply both edit sets against the base, live first (higher line numbers last).
    merged = list(base_lines)
    for tag, i1, i2, j1, j2 in sorted(live_ops + inc_ops, key=lambda o: -o[1]):
        replacement = (live_lines if (tag, i1, i2, j1, j2) in live_ops else inc_lines)[
            j1:j2
        ]
        merged[i1:i2] = replacement
    return "".join(merged), []
