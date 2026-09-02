"""Materialize planted-bad and known-good council fixtures with live digests."""
from __future__ import annotations

import json
from pathlib import Path

from detector import sha256_bytes

HERE = Path(__file__).resolve().parent
GEN = HERE / "fixtures"


def _write_file(root: Path, rel: str, body: str) -> str:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = body.encode("utf-8")
    if not raw.endswith(b"\n"):
        raw += b"\n"
    path.write_bytes(raw)
    return sha256_bytes(raw)


def _dump_council(root: Path, doc: dict) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "council.json").write_text(
        json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _ballots(prefix: str, position: str, n: int, evidence: list | None) -> list[dict]:
    ev = list(evidence or [])
    return [
        {"voter_id": f"{prefix}{i}", "position": position, "evidence": ev}
        for i in range(1, n + 1)
    ]


def planted_empty(root: Path) -> Path:
    """7 evidence-free ADOPT vs 2 backed REJECT. Pathology present."""
    d = root / "planted-empty"
    digest = _write_file(
        d,
        "evidence/reject-anchor.txt",
        "Executable check REJECT-X: proposal X fails the load-bearing test.",
    )
    _dump_council(
        d,
        {
            "council_id": "CNL-0094-planted-empty",
            "question": "Adopt proposal X?",
            "positions": ["ADOPT", "REJECT"],
            "evidence_registry": {
                "E-REJECT-1": {
                    "path": "evidence/reject-anchor.txt",
                    "sha256": digest,
                    "supports": "REJECT",
                }
            },
            "ballots": _ballots("U", "ADOPT", 7, [])
            + _ballots("R", "REJECT", 2, [{"id": "E-REJECT-1"}]),
        },
    )
    return d


def planted_fabricated(root: Path) -> Path:
    """7 ADOPT citing an id that is not in the registry vs 2 backed REJECT."""
    d = root / "planted-fabricated"
    digest = _write_file(
        d,
        "evidence/reject-anchor.txt",
        "Executable check REJECT-Y: fabricated ids are not evidence.",
    )
    _dump_council(
        d,
        {
            "council_id": "CNL-0094-planted-fabricated",
            "question": "Adopt proposal Y?",
            "positions": ["ADOPT", "REJECT"],
            "evidence_registry": {
                "E-REJECT-1": {
                    "path": "evidence/reject-anchor.txt",
                    "sha256": digest,
                    "supports": "REJECT",
                }
            },
            "ballots": _ballots(
                "F", "ADOPT", 7, [{"id": "E-DOES-NOT-EXIST"}]
            )
            + _ballots("R", "REJECT", 2, [{"id": "E-REJECT-1"}]),
        },
    )
    return d


def planted_digest(root: Path) -> Path:
    """7 ADOPT citing a real file whose registry digest does not match bytes."""
    d = root / "planted-digest"
    _write_file(
        d,
        "evidence/adopt-stale.txt",
        "This file exists but the registry digest is stale on purpose.",
    )
    digest_ok = _write_file(
        d,
        "evidence/reject-anchor.txt",
        "Executable check REJECT-Z: stale digest is non-counting.",
    )
    _dump_council(
        d,
        {
            "council_id": "CNL-0094-planted-digest",
            "question": "Adopt proposal Z?",
            "positions": ["ADOPT", "REJECT"],
            "evidence_registry": {
                "E-ADOPT-STALE": {
                    "path": "evidence/adopt-stale.txt",
                    "sha256": "0" * 64,
                    "supports": "ADOPT",
                },
                "E-REJECT-1": {
                    "path": "evidence/reject-anchor.txt",
                    "sha256": digest_ok,
                    "supports": "REJECT",
                },
            },
            "ballots": _ballots("S", "ADOPT", 7, [{"id": "E-ADOPT-STALE"}])
            + _ballots("R", "REJECT", 2, [{"id": "E-REJECT-1"}]),
        },
    )
    return d


def planted_support_mismatch(root: Path) -> Path:
    """7 ADOPT citing evidence that supports REJECT — citations do not count."""
    d = root / "planted-support-mismatch"
    digest = _write_file(
        d,
        "evidence/reject-anchor.txt",
        "This node supports REJECT, not ADOPT.",
    )
    _dump_council(
        d,
        {
            "council_id": "CNL-0094-planted-support-mismatch",
            "question": "Adopt proposal W?",
            "positions": ["ADOPT", "REJECT"],
            "evidence_registry": {
                "E-REJECT-1": {
                    "path": "evidence/reject-anchor.txt",
                    "sha256": digest,
                    "supports": "REJECT",
                }
            },
            "ballots": _ballots("M", "ADOPT", 7, [{"id": "E-REJECT-1"}])
            + _ballots("R", "REJECT", 2, [{"id": "E-REJECT-1"}]),
        },
    )
    return d


def known_good_majority(root: Path) -> Path:
    """5 backed ADOPT vs 2 backed REJECT. Ordinary evidenced majority."""
    d = root / "known-good-majority"
    d_adopt = _write_file(
        d,
        "evidence/adopt-anchor.txt",
        "Executable check ADOPT-G: proposal G passes the load-bearing test.",
    )
    d_reject = _write_file(
        d,
        "evidence/reject-anchor.txt",
        "Executable check REJECT-G: recorded dissent, still evidenced.",
    )
    _dump_council(
        d,
        {
            "council_id": "CNL-0094-known-good-majority",
            "question": "Adopt proposal G?",
            "positions": ["ADOPT", "REJECT"],
            "evidence_registry": {
                "E-ADOPT-1": {
                    "path": "evidence/adopt-anchor.txt",
                    "sha256": d_adopt,
                    "supports": "ADOPT",
                },
                "E-REJECT-1": {
                    "path": "evidence/reject-anchor.txt",
                    "sha256": d_reject,
                    "supports": "REJECT",
                },
            },
            "ballots": _ballots("A", "ADOPT", 5, [{"id": "E-ADOPT-1"}])
            + _ballots("R", "REJECT", 2, [{"id": "E-REJECT-1"}]),
        },
    )
    return d


def known_good_unanimous(root: Path) -> Path:
    d = root / "known-good-unanimous"
    digest = _write_file(
        d,
        "evidence/adopt-anchor.txt",
        "Unanimous evidenced ADOPT.",
    )
    _dump_council(
        d,
        {
            "council_id": "CNL-0094-known-good-unanimous",
            "question": "Adopt proposal U?",
            "positions": ["ADOPT", "REJECT"],
            "evidence_registry": {
                "E-ADOPT-1": {
                    "path": "evidence/adopt-anchor.txt",
                    "sha256": digest,
                    "supports": "ADOPT",
                }
            },
            "ballots": _ballots("A", "ADOPT", 5, [{"id": "E-ADOPT-1"}]),
        },
    )
    return d


def known_good_mixed(root: Path) -> Path:
    """4 backed ADOPT + 1 empty ADOPT vs 2 backed REJECT.

    Raw majority is not assembled entirely from evidence-free votes.
    """
    d = root / "known-good-mixed"
    d_adopt = _write_file(d, "evidence/adopt-anchor.txt", "Mixed-majority ADOPT evidence.")
    d_reject = _write_file(d, "evidence/reject-anchor.txt", "Mixed-majority REJECT evidence.")
    _dump_council(
        d,
        {
            "council_id": "CNL-0094-known-good-mixed",
            "question": "Adopt proposal MIX?",
            "positions": ["ADOPT", "REJECT"],
            "evidence_registry": {
                "E-ADOPT-1": {
                    "path": "evidence/adopt-anchor.txt",
                    "sha256": d_adopt,
                    "supports": "ADOPT",
                },
                "E-REJECT-1": {
                    "path": "evidence/reject-anchor.txt",
                    "sha256": d_reject,
                    "supports": "REJECT",
                },
            },
            "ballots": _ballots("A", "ADOPT", 4, [{"id": "E-ADOPT-1"}])
            + _ballots("E", "ADOPT", 1, [])
            + _ballots("R", "REJECT", 2, [{"id": "E-REJECT-1"}]),
        },
    )
    return d


def known_good_close(root: Path) -> Path:
    d = root / "known-good-close"
    d_adopt = _write_file(d, "evidence/adopt-anchor.txt", "Close evidenced ADOPT.")
    d_reject = _write_file(d, "evidence/reject-anchor.txt", "Close evidenced REJECT.")
    _dump_council(
        d,
        {
            "council_id": "CNL-0094-known-good-close",
            "question": "Adopt proposal C?",
            "positions": ["ADOPT", "REJECT"],
            "evidence_registry": {
                "E-ADOPT-1": {
                    "path": "evidence/adopt-anchor.txt",
                    "sha256": d_adopt,
                    "supports": "ADOPT",
                },
                "E-REJECT-1": {
                    "path": "evidence/reject-anchor.txt",
                    "sha256": d_reject,
                    "supports": "REJECT",
                },
            },
            "ballots": _ballots("A", "ADOPT", 4, [{"id": "E-ADOPT-1"}])
            + _ballots("R", "REJECT", 3, [{"id": "E-REJECT-1"}]),
        },
    )
    return d


PLANTED = (
    planted_empty,
    planted_fabricated,
    planted_digest,
    planted_support_mismatch,
)
CLEAN = (
    known_good_majority,
    known_good_unanimous,
    known_good_mixed,
    known_good_close,
)


def build_all(root: Path | None = None) -> dict[str, Path]:
    dest = root or GEN
    dest.mkdir(parents=True, exist_ok=True)
    out: dict[str, Path] = {}
    for fn in PLANTED + CLEAN:
        path = fn(dest)
        out[path.name] = path
    return out


build_all = build_all
