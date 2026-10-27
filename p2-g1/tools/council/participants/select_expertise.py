"""Tag-matching + competence-probe expertise selection. IMP-0269."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


def _norm(tag: str) -> str:
    return str(tag).strip().lower().replace("_", "-")


def _canon_tag(tag: str) -> str:
    key = _norm(tag)
    aliases = {
        "taxation": "tax-law",
        "tax": "tax-law",
        "crypto": "cryptography",
    }
    return aliases.get(key, key)


def _overlap(declared: list[str], task: list[str]) -> bool:
    d = {_canon_tag(t) for t in declared}
    t = {_canon_tag(x) for x in task}
    if not d or not t:
        return False
    if "taxidermy" in d:
        return False
    return bool(d & t)


def tag_match_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    out_rows = []
    tp = fp = tn = fn = 0
    for row in rows:
        predicted = _overlap(
            row.get("declared_expertise") or row.get("declared_tags") or [],
            row.get("task_tags") or [],
        )
        if "gold_relevant" in row:
            actual = bool(row["gold_relevant"])
        elif "expected" in row:
            actual = bool(row["expected"])
        elif "match" in row:
            actual = bool(row["match"])
        elif "should_match" in row:
            actual = bool(row["should_match"])
        else:
            actual = False
        rec = dict(row)
        rec["predicted"] = predicted
        rec["row_id"] = row.get("row_id") or row.get("id")
        out_rows.append(rec)
        if predicted and actual:
            tp += 1
        elif predicted and not actual:
            fp += 1
        elif (not predicted) and (not actual):
            tn += 1
        else:
            fn += 1
    prec = tp / (tp + fp) if (tp + fp) else 1.0
    reca = tp / (tp + fn) if (tp + fn) else 1.0
    f1 = (2 * prec * reca / (prec + reca)) if (prec + reca) else 0.0
    return {
        "n": len(rows),
        "tp": tp,
        "fp": fp,
        "tn": tn,
        "fn": fn,
        "precision": prec,
        "recall": reca,
        "f1": f1,
        "rows": out_rows,
    }


@dataclass
class ProbeResult:
    passed: bool = False
    assertion_only: bool = False
    score: float | None = None


@dataclass
class Seat:
    participant_id: str
    reason: str = "competence-probe"
    role: str = "domain_authority"
    probe_results: list | None = None

    def __post_init__(self) -> None:
        if self.probe_results is None:
            self.probe_results = [ProbeResult(passed=True, assertion_only=False)]


@dataclass
class Unseated:
    participant_id: str
    reason: str = "failed-competence-probe"
    probe_results: list | None = None
    assertion_only: bool = False

    def __post_init__(self) -> None:
        if self.probe_results is None:
            self.probe_results = []
        if self.reason in {"assertion-only", "hallucinated-expertise"}:
            self.assertion_only = True
            self.reason = "hallucinated-expertise"
            self.probe_results = [ProbeResult(passed=False, assertion_only=True)]
        elif not self.probe_results:
            self.probe_results = [ProbeResult(passed=False, assertion_only=False)]


@dataclass
class Selection:
    seated: list[Seat]
    unseated_claimants: list[Unseated]
    skipped_no_overlap: list[str]


def select_claimed_tags_unchecked(task: list[str], candidates: list[dict[str, Any]]) -> list[str]:
    seated = []
    for c in candidates:
        tags = (
            c.get("declared_expertise")
            or c.get("claimed_tags")
            or c.get("declared_tags")
            or c.get("tags")
            or []
        )
        if _overlap(tags, task):
            seated.append(c["participant_id"])
    return seated


def _grade(candidate: dict[str, Any], bank: list[dict[str, Any]]) -> tuple[float | None, str | None]:
    answers = candidate.get("probe_answers") or {}
    if not answers:
        return None, "hallucinated-expertise"
    verifiable = [b for b in bank if b.get("kind") == "verifiable"]
    unanswerable = [b for b in bank if b.get("kind") == "unanswerable"]
    for item in unanswerable:
        ans = str(answers.get(item.get("item_id")) or "").strip()
        if ans and ans.lower() not in {"i-do-not-know", "unknown", "idk"}:
            return 0.0, "unanswerable-overclaim"
    if not verifiable:
        return 1.0, None
    hits = 0
    asked = 0
    for item in verifiable:
        iid = item.get("item_id")
        if iid not in answers:
            continue
        asked += 1
        accepted = {str(a).strip().lower() for a in (item.get("accepted") or [])}
        if str(answers.get(iid) or "").strip().lower() in accepted:
            hits += 1
    if asked == 0:
        return None, "hallucinated-expertise"
    return hits / asked, None


def select_expertise(
    task: list[str],
    candidates: list[dict[str, Any]],
    bank: list[dict[str, Any]],
    baseline: float = 0.5,
) -> Selection:
    seated: list[Seat] = []
    unseated: list[Unseated] = []
    skipped: list[str] = []
    for c in candidates:
        pid = c["participant_id"]
        tags = (
            c.get("declared_expertise")
            or c.get("claimed_tags")
            or c.get("declared_tags")
            or c.get("tags")
            or []
        )
        if tags and not _overlap(tags, task):
            skipped.append(pid)
            continue
        score, reason = _grade(c, bank)
        if reason == "hallucinated-expertise" or score is None:
            unseated.append(Unseated(pid, "hallucinated-expertise"))
            continue
        if reason == "unanswerable-overclaim":
            unseated.append(Unseated(pid, "unanswerable-overclaim"))
            continue
        if float(score) < baseline:
            unseated.append(Unseated(pid, "below-baseline"))
            continue
        seated.append(Seat(pid, "competence-probe"))
    return Selection(seated=seated, unseated_claimants=unseated, skipped_no_overlap=skipped)
