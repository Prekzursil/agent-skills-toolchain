"""Unfavourable-evidence quota, quality floor, and padding detector."""
from __future__ import annotations

import hashlib
import math
import re
from pathlib import Path
from typing import Any

import contract as C

TOKEN_RE = re.compile(r"[a-z0-9]+")
STOP = frozenset(
    {
        "a",
        "an",
        "the",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "of",
        "to",
        "in",
        "that",
        "for",
        "on",
        "with",
        "as",
        "by",
        "at",
        "from",
        "or",
        "and",
        "this",
        "those",
        "these",
        "it",
        "its",
        "their",
        "they",
        "them",
        "also",
        "just",
        "like",
        "some",
        "any",
        "all",
        "every",
        "does",
        "do",
        "did",
        "has",
        "have",
        "had",
        "not",
        "no",
        "use",
        "used",
        "using",
    }
)
GROUPS: dict[str, frozenset[str]] = {
    "ratite": frozenset({"ostrich", "ostriches", "emu", "emus", "ratite", "ratites", "struthio"}),
    "penguin": frozenset({"penguin", "penguins", "spheniscidae", "spheniscus"}),
    "kiwi": frozenset({"kiwi", "kiwis", "apteryx"}),
    "moa": frozenset({"moa", "moas", "dinornithiformes", "aepyornis"}),
}
VACUOUS = (
    re.compile(r"\bmight\b"),
    re.compile(r"\bcould be (wrong|false|mistaken)\b"),
    re.compile(r"\bsome (people|sources) disagree\b"),
    re.compile(r"\bmore research (is )?needed\b"),
    re.compile(r"\bnot necessarily\b"),
    re.compile(r"\bperhaps\b"),
    re.compile(r"\bit depends\b"),
)
SHA_RE = re.compile(r"^[0-9a-f]{64}$")


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes()
    return sha256_bytes(raw), len(raw.replace(b"\r\n", b"\n"))


def tokens(text: str) -> set[str]:
    out: set[str] = set()
    for raw in TOKEN_RE.findall((text or "").lower()):
        tok = raw
        if tok.endswith("s") and len(tok) > 4:
            tok = tok[:-1]
        if tok in STOP or len(tok) < 2:
            continue
        out.add(tok)
    return out


def jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def group_set(text: str) -> frozenset[str]:
    toks = tokens(text)
    found = {name for name, members in GROUPS.items() if toks & members}
    return frozenset(found)


def mechanism_key(item: dict[str, Any]) -> frozenset[str]:
    declared = str(item.get("mechanism_id") or "").strip()
    derived = group_set(str(item.get("text") or "") + " " + str(item.get("falsifier") or ""))
    if declared:
        return frozenset({declared}) | derived
    return derived


def required_n(qualifying_total: int) -> int:
    share_need = math.ceil(C.MIN_SHARE * qualifying_total) if qualifying_total else C.MIN_N
    return max(C.MIN_N, share_need)


def lineage_ok(item: dict[str, Any], repo: Path) -> bool:
    path = str(item.get("path") or "").replace("\\", "/")
    sha = str(item.get("sha256") or "")
    url = str(item.get("url") or "")
    fetched = str(item.get("fetched_at") or "")
    if not path or not url or not fetched or not SHA_RE.match(sha):
        return False
    full = repo / path
    if not full.is_file():
        return False
    live, _ = sha256_file(full)
    return live == sha


def vacuous(item: dict[str, Any]) -> bool:
    text = f"{item.get('text') or ''} {item.get('falsifier') or ''}".lower()
    fals = str(item.get("falsifier") or "").strip()
    if len(fals) < 24:
        return True
    if any(rx.search(text) for rx in VACUOUS) and not group_set(text) and not str(item.get("mechanism_id") or "").strip():
        return True
    hedges = sum(1 for rx in VACUOUS if rx.search(text))
    if hedges >= 2 and not str(item.get("mechanism_id") or "").strip():
        return True
    return False


def restates_claim(item: dict[str, Any], claim: dict[str, Any]) -> bool:
    it = tokens(str(item.get("text") or ""))
    ct = tokens(str(claim.get("text") or ""))
    if not it or not ct:
        return False
    # High overlap with the claim itself, little leftover content.
    if jaccard(it, ct) >= 0.72:
        return True
    leftover = it - ct
    if jaccard(it, ct) >= 0.45 and len(leftover) <= 1:
        return True
    return False


def corpus_doc(claim: dict[str, Any], source_id: str) -> dict[str, Any] | None:
    for doc in claim.get("corpus") or []:
        if isinstance(doc, dict) and doc.get("id") == source_id:
            return doc
    return None


def padding_flags(
    item: dict[str, Any],
    accepted: list[dict[str, Any]],
    claim: dict[str, Any],
    repo: Path,
) -> list[str]:
    flags: list[str] = []
    polarity = str(item.get("polarity") or "")
    if polarity != "disconfirming":
        flags.append("PAD-POLARITY")
        return flags
    if vacuous(item):
        flags.append("PAD-VACUOUS")
    if restates_claim(item, claim):
        flags.append("PAD-RESTATE")
    if not lineage_ok(item, repo):
        flags.append("PAD-NO-LINEAGE")
    source_id = str(item.get("source_id") or "")
    doc = corpus_doc(claim, source_id)
    if doc is None:
        flags.append("PAD-NOT-IN-CORPUS")
    else:
        label = str(doc.get("label") or "").upper()
        if label != "DISCONFIRM":
            flags.append("PAD-SUPPORT-CITED-AS-DISCONFIRM")
        if str(item.get("path") or "").replace("\\", "/") != str(doc.get("path") or "").replace("\\", "/"):
            flags.append("PAD-NOT-IN-CORPUS")
    key = mechanism_key(item)
    itoks = tokens(str(item.get("text") or "") + " " + str(item.get("falsifier") or ""))
    for prev in accepted:
        prev_key = mechanism_key(prev)
        if key and prev_key and (key == prev_key or key <= prev_key or prev_key <= key):
            flags.append("PAD-MECH-COLLAPSE")
            break
        ptoks = tokens(str(prev.get("text") or "") + " " + str(prev.get("falsifier") or ""))
        if jaccard(itoks, ptoks) >= C.NEAR_DUP_JACCARD:
            flags.append("PAD-NEAR-DUP")
            break
    # unique preserve order
    seen: set[str] = set()
    out: list[str] = []
    for f in flags:
        if f not in seen:
            seen.add(f)
            out.append(f)
    return out


def attach_lineage(item: dict[str, Any], repo: Path) -> dict[str, Any]:
    row = dict(item)
    path = str(row.get("path") or "").replace("\\", "/")
    if path:
        full = repo / path
        if full.is_file():
            sha, size = sha256_file(full)
            row["sha256"] = sha
            row["bytes"] = size
            row["url"] = row.get("url") or f"file://{path}"
    return row


def qualify_disconfirming(
    items: list[dict[str, Any]],
    claim: dict[str, Any],
    repo: Path,
) -> dict[str, Any]:
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for raw in items:
        item = attach_lineage(raw, repo)
        if str(item.get("polarity") or "") != "disconfirming":
            continue
        flags = padding_flags(item, accepted, claim, repo)
        rec = dict(item)
        rec["padding_flags"] = flags
        rec["qualifies"] = not flags
        if flags:
            rejected.append(rec)
        else:
            accepted.append(rec)
    return {"accepted": accepted, "rejected": rejected}


def qualify_supporting(items: list[dict[str, Any]], repo: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for raw in items:
        if str(raw.get("polarity") or "") != "supporting":
            continue
        item = attach_lineage(raw, repo)
        path_ok = lineage_ok(item, repo)
        rec = dict(item)
        rec["qualifies"] = path_ok
        rec["padding_flags"] = [] if path_ok else ["PAD-NO-LINEAGE"]
        if path_ok:
            out.append(rec)
    return out


def evaluate_quota(run: dict[str, Any], repo: Path) -> dict[str, Any]:
    claim = run["claim"]
    items = list(run.get("items") or [])
    dis = qualify_disconfirming(items, claim, repo)
    sup = qualify_supporting(items, repo)
    u = len(dis["accepted"])
    f = len(sup)
    total = u + f
    need = required_n(total)
    exhausted = bool(run.get("search_exhausted"))
    padded_n = len(dis["rejected"])
    if u >= need and total > 0:
        verdict = C.QUOTA_MET
    elif exhausted:
        verdict = C.HONEST_VERDICT
    else:
        verdict = "UNDER-QUOTA-INCOMPLETE"
    share = (u / total) if total else 0.0
    filled = verdict == C.QUOTA_MET and padded_n > 0 and u == 0
    # filling means counting rejected items; engine never does that.
    return {
        "claim_id": claim.get("id"),
        "verdict": verdict,
        "qualifying_unfavorable": u,
        "qualifying_supporting": f,
        "qualifying_total": total,
        "required_n": need,
        "share": share,
        "min_share": C.MIN_SHARE,
        "min_n": C.MIN_N,
        "search_exhausted": exhausted,
        "padded_rejected": padded_n,
        "accepted_ids": [x.get("id") for x in dis["accepted"]],
        "rejected": [
            {"id": x.get("id"), "flags": x.get("padding_flags")} for x in dis["rejected"]
        ],
        "filled_with_padding": filled,
        "anti_suppression": True,
        "queries": list(run.get("queries") or []),
        "source_classes_exhausted": list(run.get("source_classes_exhausted") or []),
    }


def mutant_count_all_disconfirming(run: dict[str, Any]) -> dict[str, Any]:
    """Broken quota: any polarity=disconfirming sentence counts. Fills."""
    items = list(run.get("items") or [])
    fake_u = sum(1 for i in items if str(i.get("polarity") or "") == "disconfirming")
    fake_f = sum(1 for i in items if str(i.get("polarity") or "") == "supporting")
    total = fake_u + fake_f
    need = required_n(total) if total else C.MIN_N
    verdict = C.QUOTA_MET if fake_u >= need else C.HONEST_VERDICT
    return {
        "verdict": verdict,
        "qualifying_unfavorable": fake_u,
        "required_n": need,
        "filled_with_padding": verdict == C.QUOTA_MET,
        "name": "mutant-count-any-disconfirming-shape",
    }


def detector_both_states(
    genuine: list[dict[str, Any]],
    padded: list[dict[str, Any]],
    claim: dict[str, Any],
    repo: Path,
) -> dict[str, Any]:
    acc: list[dict[str, Any]] = []
    genuine_rows = []
    for raw in genuine:
        item = attach_lineage(raw, repo)
        flags = padding_flags(item, acc, claim, repo)
        genuine_rows.append({"id": item.get("id"), "flags": flags})
        if not flags:
            acc.append(item)
    padded_rows = []
    for raw in padded:
        item = attach_lineage(raw, repo)
        flags = padding_flags(item, acc, claim, repo)
        padded_rows.append({"id": item.get("id"), "flags": flags})
    genuine_unflagged = all(not r["flags"] for r in genuine_rows)
    padded_flagged = all(bool(r["flags"]) for r in padded_rows)
    return {
        "genuine": genuine_rows,
        "padded": padded_rows,
        "genuine_unflagged": genuine_unflagged,
        "padded_flagged": padded_flagged,
        "both_states": genuine_unflagged and padded_flagged,
        "n_genuine": len(genuine_rows),
        "n_padded": len(padded_rows),
    }


def schema_rejects_garbage(schema: dict[str, Any]) -> bool:
    import jsonschema

    errs = list(jsonschema.Draft7Validator(schema).iter_errors({}))
    return bool(errs)
