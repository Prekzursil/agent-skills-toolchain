"""Survival math: source negatives vs synthesis, record-count ratios."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from extract import Record


@dataclass
class Drop:
    id: str
    reason: str
    source_path: str
    source_raw: str
    claim: str

    def as_dict(self) -> dict[str, str]:
        return {
            "id": self.id,
            "reason": self.reason,
            "source_path": self.source_path,
            "source_raw": self.source_raw,
            "claim": self.claim,
        }


@dataclass
class Survival:
    source_count: int
    surviving_count: int
    rate: float | None
    dropped: list[Drop]
    surviving_ids: list[str]
    synthesis_present: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "source_count": self.source_count,
            "surviving_count": self.surviving_count,
            "rate": self.rate,
            "denominators": {
                "source_negatives": self.source_count,
                "surviving_negatives": self.surviving_count,
            },
            "dropped": [d.as_dict() for d in self.dropped],
            "surviving_ids": self.surviving_ids,
            "synthesis_present": self.synthesis_present,
        }


@dataclass
class Ratios:
    corpus_positive: int
    corpus_negative: int
    synthesis_positive: int
    synthesis_negative: int
    corpus_ratio: float | None
    synthesis_ratio: float | None
    unit: str = "record"
    byte_weighted_refused: bool = True
    byte_corpus_ratio: float | None = None
    byte_synthesis_ratio: float | None = None
    diverges_from_bytes: bool = False
    finding: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "unit": self.unit,
            "corpus_positive": self.corpus_positive,
            "corpus_negative": self.corpus_negative,
            "synthesis_positive": self.synthesis_positive,
            "synthesis_negative": self.synthesis_negative,
            "corpus_ratio": self.corpus_ratio,
            "synthesis_ratio": self.synthesis_ratio,
            "byte_weighted_refused": self.byte_weighted_refused,
            "byte_corpus_ratio": self.byte_corpus_ratio,
            "byte_synthesis_ratio": self.byte_synthesis_ratio,
            "diverges_from_bytes": self.diverges_from_bytes,
            "finding": self.finding,
        }


def _div(num: int, den: int) -> float | None:
    if den <= 0:
        return None
    return num / den


def survive(source: list[Record], synthesis: list[Record] | None) -> Survival:
    src_neg = {r.id: r for r in source if r.polarity == "negative"}
    syn_present = synthesis is not None
    syn_list = synthesis or []
    syn_by_id = {r.id: r for r in syn_list}
    dropped: list[Drop] = []
    surviving: list[str] = []
    for rid, rec in src_neg.items():
        if not syn_present:
            dropped.append(
                Drop(
                    id=rid,
                    reason="synthesis-absent",
                    source_path=rec.path,
                    source_raw=rec.raw,
                    claim=rec.claim,
                )
            )
            continue
        syn = syn_by_id.get(rid)
        if syn is None:
            dropped.append(
                Drop(
                    id=rid,
                    reason="not-cited-in-synthesis",
                    source_path=rec.path,
                    source_raw=rec.raw,
                    claim=rec.claim,
                )
            )
            continue
        if syn.polarity == "negative":
            surviving.append(rid)
            continue
        if syn.polarity == "positive":
            dropped.append(
                Drop(
                    id=rid,
                    reason="polarity-flipped-to-positive",
                    source_path=rec.path,
                    source_raw=rec.raw,
                    claim=rec.claim,
                )
            )
            continue
        dropped.append(
            Drop(
                id=rid,
                reason=f"synthesis-polarity-unclassified:{syn.raw}",
                source_path=rec.path,
                source_raw=rec.raw,
                claim=rec.claim,
            )
        )
    n = len(src_neg)
    k = len(surviving)
    return Survival(
        source_count=n,
        surviving_count=k,
        rate=_div(k, n),
        dropped=dropped,
        surviving_ids=surviving,
        synthesis_present=syn_present,
    )


def _count(records: list[Record], polarity: str) -> int:
    return sum(1 for r in records if r.polarity == polarity)


def _bytes(records: list[Record], polarity: str) -> int:
    return sum(r.nbytes for r in records if r.polarity == polarity)


def ratios(source: list[Record], synthesis: list[Record]) -> Ratios:
    cp, cn = _count(source, "positive"), _count(source, "negative")
    sp, sn = _count(synthesis, "positive"), _count(synthesis, "negative")
    rec_c, rec_s = _div(cp, cn), _div(sp, sn)
    bp, bn = _bytes(source, "positive"), _bytes(source, "negative")
    sbp, sbn = _bytes(synthesis, "positive"), _bytes(synthesis, "negative")
    byte_c, byte_s = _div(bp, bn), _div(sbp, sbn)
    diverges = rec_c is not None and byte_c is not None and abs(rec_c - byte_c) > 1e-9
    finding = ""
    if rec_c is not None and rec_s is not None and rec_c > 0 and rec_s / rec_c >= 2.0:
        finding = (
            "favourable-result-bias: synthesis positive-to-negative ratio "
            f"{rec_s:.4f} is >= 2x the corpus ratio {rec_c:.4f}"
        )
    elif rec_c is not None and rec_s is not None and rec_s > rec_c * 1.5:
        finding = (
            "ratio-divergence: synthesis pos/neg "
            f"{rec_s:.4f} vs corpus {rec_c:.4f} (record units)"
        )
    return Ratios(
        corpus_positive=cp,
        corpus_negative=cn,
        synthesis_positive=sp,
        synthesis_negative=sn,
        corpus_ratio=rec_c,
        synthesis_ratio=rec_s,
        byte_corpus_ratio=byte_c,
        byte_synthesis_ratio=byte_s,
        diverges_from_bytes=diverges,
        finding=finding,
    )
