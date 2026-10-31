"""Nominal Group Technique session: silent generation then private ranking."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


def _catalog_block(rows: list[dict[str, str]]) -> str:
    lines = ["CATALOG"]
    for row in rows:
        lines.append(f"{row['idea_id']}: {row['text']}")
    return "\n".join(lines)


@dataclass
class NgtSession:
    question: str
    participants: list[str]
    pending_ideas: dict[str, list[str]] = field(default_factory=dict)
    catalog: list[dict[str, str]] = field(default_factory=list)
    generation_closed: bool = False
    _gen_prompts: dict[str, dict[str, Any]] = field(default_factory=dict)
    _rank_prompts: dict[str, dict[str, Any]] = field(default_factory=dict)
    _rankings: dict[str, list[str]] = field(default_factory=dict)
    _ballots: dict[str, dict[str, Any]] = field(default_factory=dict)
    _idea_seq: int = 0

    def deliver_generation_prompt(self, pid: str) -> dict[str, Any]:
        body = (
            f"NGT silent generation for {pid}.\n"
            f"Question: {self.question}\n"
            "Do not reveal peer ideas. Submit your own ideas only.\n"
        )
        rec = {"pid": pid, "body": body, "phase": "generation"}
        self._gen_prompts[pid] = rec
        return rec

    def submit_ideas(self, pid: str, ideas: list[str]) -> None:
        self.pending_ideas[pid] = list(ideas)
        for text in ideas:
            self._idea_seq += 1
            self.catalog.append(
                {
                    "idea_id": f"I-{self._idea_seq:02d}",
                    "text": text,
                    "author_id": pid,
                }
            )

    def close_generation(self) -> None:
        self.generation_closed = True

    def ranking_catalog_rows(self) -> list[dict[str, str]]:
        return [{"idea_id": r["idea_id"], "text": r["text"]} for r in self.catalog]

    def ranking_prompt_catalog_sections(self) -> dict[str, str]:
        block = _catalog_block(self.ranking_catalog_rows())
        return {pid: block for pid in self.participants}

    def deliver_ranking_prompt(self, pid: str) -> dict[str, Any]:
        block = _catalog_block(self.ranking_catalog_rows())
        body = (
            f"NGT private ranking for {pid}.\n"
            "Rank the catalog. Do not include author identities.\n"
            f"{block}\n"
        )
        rec = {"pid": pid, "body": body, "phase": "ranking", "catalog": block}
        self._rank_prompts[pid] = rec
        return rec

    def submit_ranking(self, pid: str, ranking: list[str]) -> None:
        self._rankings[pid] = list(ranking)
        self._ballots[pid] = {
            "ranking": list(ranking),
            "needles": [f"ballot:{pid}", f"NEEDLE-{pid}-RANK"],
        }

    def leak_ranking_into_prompt(self, source: str, dest: str) -> dict[str, Any]:
        leaked = list(self._rankings.get(source) or [])
        rec = self._rank_prompts.get(dest) or {"pid": dest, "body": "", "phase": "ranking"}
        rec["body"] = (rec.get("body") or "") + f"\nballot:{source} {leaked}\n"
        self._rank_prompts[dest] = rec
        return {"source": source, "dest": dest, "leaked": leaked}

    @property
    def participant_ids(self) -> list[str]:
        return list(self.participants)

    @property
    def ballots(self) -> dict[str, dict[str, Any]]:
        return self._ballots

    def raw_ballots(self) -> dict[str, list[str]]:
        return {pid: list(ranking) for pid, ranking in self._rankings.items()}

    def catalog_ids(self) -> list[str]:
        return [row["idea_id"] for row in self.catalog]

    def aggregate(self) -> dict[str, Any]:
        return aggregate_ballots(self)


def catalog_block(rows: list[dict[str, str]]) -> str:
    return _catalog_block(rows)


def scan_generation_privacy(session: NgtSession) -> dict[str, Any]:
    findings = []
    pending = session.pending_ideas
    for pid, rec in session._gen_prompts.items():
        body = rec.get("body") or ""
        for other, ideas in pending.items():
            if other == pid:
                continue
            for text in ideas:
                if text and text in body:
                    findings.append({"pid": pid, "leaked": text})
    return {"fired": bool(findings), "findings": findings}


def scan_delivered_prompts(session: NgtSession, before_aggregation: bool = True) -> dict[str, Any]:
    findings = []
    seen: set[tuple[str, str]] = set()
    for pid, rec in session._rank_prompts.items():
        body = rec.get("body") or ""
        if "author_id" in body or "author=" in body:
            findings.append(
                {
                    "pid": pid,
                    "kind": "author",
                    "recipient_id": pid,
                    "source_id": None,
                }
            )
        for other in session._rankings:
            if other == pid:
                continue
            needle = f"ballot:{other}"
            if needle in body and (other, pid) not in seen:
                seen.add((other, pid))
                findings.append(
                    {
                        "pid": pid,
                        "kind": "ballot",
                        "other": other,
                        "source_id": other,
                        "recipient_id": pid,
                    }
                )
    return {
        "fired": bool(findings),
        "findings": findings,
        "reason_id": "ranking-ballot-leak" if findings else None,
        "scanned_prompt_count": len(session._rank_prompts),
    }


def aggregate_ballots(ids_or_session: Any, rankings: dict[str, list[str]] | None = None) -> dict[str, Any]:
    if rankings is None:
        session = ids_or_session
        ids = [row["idea_id"] for row in session.catalog]
        rankings = session._rankings
        used = len(session._rankings)
    else:
        ids = list(ids_or_session)
        used = len(rankings)
    n = len(ids)
    scores = {i: 0 for i in ids}
    for ranking in rankings.values():
        for place, idea_id in enumerate(ranking):
            if idea_id in scores:
                scores[idea_id] += n - place
    order = sorted(ids, key=lambda i: (-scores[i], i))
    return {
        "method": "borda",
        "ballots_used": used,
        "scores": scores,
        "order": order,
    }
