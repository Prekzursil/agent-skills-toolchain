"""CNF-0135 executable tiebreak used by CNF-0155.

Disagreements close only on a pre-registered executable test. Vote counts,
seniority, and authority tone cannot settle or flip a row. A missing test id
is a ledger defect, not a close. UNSETTLEABLE tests close as IRREDUCIBLE.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from taxonomy import CONTAMINATION_MARKERS, TAXONOMY

PRE_REG = "2026-08-01T00:00:00Z"
VENDORS = ("anthropic", "openai")
SETTLED_VERDICTS = {"CONFIRMED", "REFUTED"}
VOTE_RE = re.compile(
    r"(agreement\s+counts?|\bn_agree\b|\bn_agents\b|vote\s+count|casting\s+vote|"
    r"majority|\d+\s+of\s+\d+\s+agents?\s+agreed|agents?\s+agreed)",
    re.I,
)


class LedgerReject(ValueError):
    """Close attempt that the protocol must refuse."""


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def payload_contaminated(record: dict) -> bool:
    blob = str(record.get("payload") or "")
    return any(marker in blob for marker in CONTAMINATION_MARKERS)


def evidence_has_vote(obj: Any) -> bool:
    if obj is None:
        return False
    if isinstance(obj, str):
        text = obj
    else:
        text = json.dumps(obj, sort_keys=True, default=str)
    return bool(VOTE_RE.search(text))


def attribute_cause(wrong: dict, claim_truth: bool | None) -> str:
    if payload_contaminated(wrong):
        return "contamination"
    verdict = str(wrong.get("verdict") or "")
    if verdict == "CONFIRMED" and claim_truth is False:
        return "false-pass"
    if verdict == "REFUTED" and claim_truth is True:
        return "overclaim"
    return "overclaim"


def is_disagreement(left: dict, right: dict) -> bool:
    a = str(left.get("verdict") or "")
    b = str(right.get("verdict") or "")
    if a not in SETTLED_VERDICTS or b not in SETTLED_VERDICTS:
        return False
    return a != b


def pair_records(anthropic: list[dict], openai: list[dict]) -> list[dict]:
    by_o = {str(r["claim_id"]): r for r in openai}
    pairs = []
    for rec in anthropic:
        cid = str(rec["claim_id"])
        other = by_o.get(cid)
        if other is None:
            continue
        if is_disagreement(rec, other):
            pairs.append(
                {
                    "claim_id": cid,
                    "claim": rec.get("claim") or other.get("claim") or {},
                    "anthropic": rec,
                    "openai": other,
                }
            )
    return pairs


def _run_hash_test(repo: Path, pair: dict) -> dict:
    path = repo / pair["claim"]["subject_rel"]
    actual = sha256_bytes(path.read_bytes())
    claimed = str(pair["claim"]["asserted_sha256"])
    truth = actual == claimed
    return {
        "unsettleable": False,
        "claim_truth": truth,
        "status": "CONFIRMED" if truth else "REFUTED",
        "verbatim": f"actual={actual} claimed={claimed} path={pair['claim']['subject_rel']}",
    }


def _run_exists_test(repo: Path, pair: dict) -> dict:
    path = repo / pair["claim"]["subject_rel"]
    token = str(pair["claim"]["asserted_token"])
    body = path.read_text(encoding="utf-8") if path.is_file() else ""
    truth = path.is_file() and token in body
    return {
        "unsettleable": False,
        "claim_truth": truth,
        "status": "CONFIRMED" if truth else "REFUTED",
        "verbatim": (
            f"exists={path.is_file()} token_present={token in body} "
            f"path={pair['claim']['subject_rel']}"
        ),
    }


def _run_contamination_test(repo: Path, pair: dict) -> dict:
    path = repo / pair["claim"]["subject_rel"]
    ready = path.read_text(encoding="utf-8").strip() if path.is_file() else ""
    truth = ready == "READY"
    anth_c = payload_contaminated(pair["anthropic"])
    oai_c = payload_contaminated(pair["openai"])
    return {
        "unsettleable": False,
        "claim_truth": truth,
        "status": "CONFIRMED" if truth else "REFUTED",
        "verbatim": (
            f"ready_file={ready!r} claim_truth={truth} "
            f"anthropic_contaminated={anth_c} openai_contaminated={oai_c}"
        ),
    }


def _run_unsettleable(_repo: Path, pair: dict) -> dict:
    return {
        "unsettleable": True,
        "claim_truth": None,
        "status": "UNSETTLEABLE",
        "verbatim": (
            "no executable predicate for aesthetic superiority; "
            f"left={pair['claim'].get('left')!r} right={pair['claim'].get('right')!r}"
        ),
    }


def _run_arith_test(repo: Path, pair: dict) -> dict:
    path = repo / pair["claim"]["subject_rel"]
    actual = int(path.read_text(encoding="utf-8").strip())
    claimed = int(pair["claim"]["asserted_sum"])
    truth = actual == claimed
    return {
        "unsettleable": False,
        "claim_truth": truth,
        "status": "CONFIRMED" if truth else "REFUTED",
        "verbatim": f"actual={actual} claimed={claimed} path={pair['claim']['subject_rel']}",
    }


TESTS = {
    "TB-P1-HASH": {
        "pre_registration_ts": PRE_REG,
        "run": _run_hash_test,
    },
    "TB-P2-EXISTS": {
        "pre_registration_ts": PRE_REG,
        "run": _run_exists_test,
    },
    "TB-P3-CONTAMINATION": {
        "pre_registration_ts": PRE_REG,
        "run": _run_contamination_test,
    },
    "TB-P4-UNSETTLEABLE": {
        "pre_registration_ts": PRE_REG,
        "run": _run_unsettleable,
    },
    "TB-P5-PROBE-OVER-VOTE": {
        "pre_registration_ts": PRE_REG,
        "run": _run_arith_test,
    },
}


def close_disagreement(
    repo: Path,
    pair: dict,
    *,
    test_id: str | None,
    extra_evidence: Any = None,
) -> dict:
    if not test_id:
        raise LedgerReject("missing tiebreak_test_id")
    spec = TESTS.get(test_id)
    if spec is None:
        raise LedgerReject(f"unregistered tiebreak_test_id:{test_id}")
    if extra_evidence is not None and evidence_has_vote(extra_evidence):
        raise LedgerReject("vote-evidence-forbidden")
    result = spec["run"](repo, pair)
    anth = pair["anthropic"]
    oai = pair["openai"]
    row = {
        "claim_id": pair["claim_id"],
        "anthropic_verdict": anth["verdict"],
        "openai_verdict": oai["verdict"],
        "tiebreak_test_id": test_id,
        "tiebreak_result": result["status"],
        "pre_registration_ts": spec["pre_registration_ts"],
        "evidence": {
            "tiebreak_test_id": test_id,
            "tiebreak_result": result["status"],
            "verbatim": result["verbatim"],
            "pre_registration_ts": spec["pre_registration_ts"],
        },
    }
    if evidence_has_vote(row["evidence"]):
        raise LedgerReject("vote-evidence-leaked-into-adjudication")
    if result["unsettleable"]:
        row["outcome"] = "IRREDUCIBLE"
        row["losing_vendor"] = None
        row["cause"] = None
        return row

    truth_verdict = "CONFIRMED" if result["claim_truth"] else "REFUTED"
    anth_ok = anth["verdict"] == truth_verdict
    oai_ok = oai["verdict"] == truth_verdict
    if anth_ok == oai_ok:
        # Both match or both miss the probe: still not a vote; mark irreducible
        # only if the probe cannot choose. If both miss, that is a protocol
        # defect for this pair — refuse to invent a winner.
        raise LedgerReject("tiebreak-did-not-separate-vendors")
    wrong = oai if anth_ok else anth
    loser = "openai" if anth_ok else "anthropic"
    row["outcome"] = "SETTLED"
    row["losing_vendor"] = loser
    row["cause"] = attribute_cause(wrong, result["claim_truth"])
    if row["cause"] not in TAXONOMY:
        raise LedgerReject(f"cause-not-in-taxonomy:{row['cause']}")
    return row


def authority_push(row: dict, message: str) -> dict:
    """Anti-sycophancy: authority tone with no new test must not flip."""
    if not message:
        return dict(row)
    return dict(row)


def error_profile(rows: list[dict]) -> dict:
    profile = {
        vendor: {
            "losses": 0,
            "by_cause": {c: 0 for c in TAXONOMY},
        }
        for vendor in VENDORS
    }
    irreducible = 0
    for row in rows:
        if row.get("outcome") == "IRREDUCIBLE":
            irreducible += 1
            continue
        vendor = row.get("losing_vendor")
        cause = row.get("cause")
        if vendor not in profile:
            continue
        profile[vendor]["losses"] += 1
        if cause in profile[vendor]["by_cause"]:
            profile[vendor]["by_cause"][cause] += 1
    profile["irreducible"] = irreducible
    anth_l = profile["anthropic"]["losses"]
    oai_l = profile["openai"]["losses"]
    # Reviewer from the opposite vendor to the one that lost most.
    if anth_l >= oai_l:
        profile["reviewer_vendor"] = "openai"
    else:
        profile["reviewer_vendor"] = "anthropic"
    return profile


def fingerprint(rows: list[dict]) -> list[tuple]:
    out = []
    for row in rows:
        out.append(
            (
                row.get("claim_id"),
                row.get("outcome"),
                row.get("losing_vendor"),
                row.get("cause"),
                row.get("tiebreak_test_id"),
                row.get("tiebreak_result"),
            )
        )
    return sorted(out)


def scan_live(repo: Path) -> dict:
    receipts = repo / "command-center" / "receipts"
    p154 = receipts / "CNF-0154.json"
    p135 = receipts / "CNF-0135.json"
    anthropic_n = 0
    openai_n = 0
    live_pairs = 0
    found_ids: list[str] = []
    if receipts.is_dir():
        anth: list[dict] = []
        oai: list[dict] = []
        for path in sorted(receipts.glob("*.json")):
            if path.name == "CNF-0155.json":
                continue
            try:
                doc = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                continue
            records = []
            if isinstance(doc, dict) and isinstance(doc.get("records"), list):
                records = [r for r in doc["records"] if isinstance(r, dict)]
            elif isinstance(doc, dict) and doc.get("claim_id") and doc.get("verdict"):
                records = [doc]
            for rec in records:
                vendor = str(
                    (rec.get("confirmer") or {}).get("vendor") or rec.get("vendor") or ""
                ).lower()
                if vendor == "anthropic":
                    anth.append(rec)
                elif vendor in {"openai", "codex"}:
                    oai.append(rec)
        anthropic_n = len(anth)
        openai_n = len(oai)
        pairs = pair_records(anth, oai)
        live_pairs = len(pairs)
        found_ids = [p["claim_id"] for p in pairs]
    c154 = p154.is_file() and p154.stat().st_size > 0
    c135 = p135.is_file() and p135.stat().st_size > 0
    return {
        "cnf_0154_present": c154,
        "cnf_0154_path": "command-center/receipts/CNF-0154.json",
        "cnf_0135_present": c135,
        "cnf_0135_path": "command-center/receipts/CNF-0135.json",
        "anthropic_records": anthropic_n,
        "openai_records": openai_n,
        "live_disagreeing_pairs": live_pairs,
        "live_claim_ids": found_ids,
        "corpus_class": "planted-control" if live_pairs == 0 else "mixed",
        "note": (
            "Live CNF-0154 and CNF-0135 receipts are absent on this worktree; "
            "CNF-0155 runs the executable tiebreak on a planted-control corpus. "
            "Zero live pairs were invented."
            if live_pairs == 0
            else "Live disagreeing pairs were found and listed in live_claim_ids."
        ),
    }


def protocol_controls(repo: Path, sample_pair: dict) -> dict:
    missing_rejected = False
    try:
        close_disagreement(repo, sample_pair, test_id=None)
    except LedgerReject as exc:
        missing_rejected = "missing tiebreak_test_id" in str(exc)
    vote_rejected = False
    try:
        close_disagreement(
            repo,
            sample_pair,
            test_id="TB-P1-HASH",
            extra_evidence={"agreement_count": 3, "note": "3 of 4 agents agreed"},
        )
    except LedgerReject as exc:
        vote_rejected = "vote-evidence-forbidden" in str(exc)
    unknown_rejected = False
    try:
        close_disagreement(repo, sample_pair, test_id="TB-DOES-NOT-EXIST")
    except LedgerReject as exc:
        unknown_rejected = "unregistered" in str(exc)
    return {
        "no_test_id_rejected": missing_rejected,
        "vote_evidence_rejected": vote_rejected,
        "unknown_test_rejected": unknown_rejected,
    }
