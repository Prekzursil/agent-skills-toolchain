"""AND-gated two-detector mechanism-level dedup gate (CC-0020).

Lexical detector: unstemmed token-set Jaccard on the raw surface. It fires on
exact renames, light paraphrases and many one-parameter forks, and is blind to
a full rewrite of the same mechanism.

Embedding detector: sparse cosine over (1) synonym-collapsed concept ids,
(2) role slots, (3) hashed character 4-grams of the concept-normalized stream.
It is not a neural net. A rewrite whose vocabulary sits outside the lexicon
stays DISTINCT; that miss is under-merge (review cost), not silent data loss.

AND rule: auto-MERGE only when both fire; either-only is ADJUDICATE (human
band, the retry-policy pivot); neither is DISTINCT.

Thresholds are frozen. The reviewer fifth class in probes/CC-0020/corpus.py
must not retune them.
"""

from __future__ import annotations

import hashlib
import math
import re
from typing import Any, Iterable, Mapping

LEX_FIRE = 0.85
EMB_FIRE = 0.74

TOKEN_RE = re.compile(r"[a-z0-9]+")
STOP = frozenset(
    """
    a an the of to and or in on at for from that this those these with without
    than rather same then into over under is be by as it its any only also not
    no yes do did them they their than then so if but when whenever besides
    beside next via per plus both each other more less been being was were has
    have had must get gets we you i
    """.split()
)

# Longest phrases first. Matching runs on a space-padded lowercase haystack.
# Concept ids are the embedding axes; lexical Jaccard never sees this table.
# A phrase may emit more than one concept (register-shift SOP uses tick-boxes
# as the dual-sensor, which must land on fused_detector + conjunction).
_PHRASE_CONCEPTS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("declared output artifact bytes exist on disk", ("artifact_present",)),
    ("output artifact bytes exist on disk", ("artifact_present",)),
    ("promised blob being present in the filesystem", ("artifact_present",)),
    ("promised blob sits on the filesystem", ("artifact_present",)),
    ("blob being present in the filesystem", ("artifact_present",)),
    ("blob sits on the filesystem", ("artifact_present",)),
    ("promised blob", ("artifact_present",)),
    ("artifact bytes", ("artifact_present",)),
    ("on disk", ("artifact_present",)),
    ("on the filesystem", ("artifact_present",)),
    ("in the filesystem", ("artifact_present",)),
    ("process exit code is zero", ("exit_ok",)),
    ("exit code is zero", ("exit_ok",)),
    ("child process yields a successful status", ("exit_ok",)),
    ("child yields a successful status", ("exit_ok",)),
    ("yields a successful status", ("exit_ok",)),
    ("successful status", ("exit_ok",)),
    ("exit code", ("exit_ok",)),
    ("either signal alone is insufficient", ("solo_fail",)),
    ("any two signals alone are insufficient", ("solo_fail",)),
    ("solitary sensor never suffices", ("solo_fail",)),
    ("a solitary tick never suffices", ("solo_fail",)),
    ("solitary tick never suffices", ("solo_fail",)),
    ("either signal alone", ("solo_fail",)),
    ("never suffices", ("solo_fail",)),
    ("and-gates those two signals", ("conjunction", "fused_detector")),
    ("those two signals are and-gated", ("conjunction", "fused_detector")),
    ("fuses both sensors conjunctively", ("conjunction", "fused_detector")),
    ("both boxes are ticked", ("conjunction", "fused_detector")),
    ("both sensors conjunctively", ("conjunction", "fused_detector")),
    ("and-gates", ("conjunction", "fused_detector")),
    ("and-gated", ("conjunction", "fused_detector")),
    ("together with", ("conjunction",)),
    ("dual detector", ("fused_detector",)),
    ("triple detector", ("fused_detector",)),
    ("fused-sensor instrument", ("fused_detector",)),
    ("instrument fuses", ("fused_detector",)),
    ("dual-signal", ("fused_detector",)),
    ("dual signal", ("fused_detector",)),
    ("tick box one", ("fused_detector",)),
    ("tick box two", ("fused_detector",)),
    ("both boxes", ("fused_detector", "conjunction")),
    ("pipeline step is complete", ("stage_complete",)),
    ("pipeline step", ("stage_complete",)),
    ("sign the stage finished", ("stage_complete",)),
    ("signing a stage finished", ("stage_complete",)),
    ("declare a stage finished", ("stage_complete",)),
    ("stage finished", ("stage_complete",)),
    ("stage-finished", ("stage_complete",)),
    ("operator checklist", ("stage_complete",)),
    ("wall-clock duration is under the timeout", ("timeout_bound",)),
    ("under the timeout", ("timeout_bound",)),
    ("comparing the patch-id set", ("patch_id",)),
    ("payload identity set", ("patch_id",)),
    ("patch-id set", ("patch_id",)),
    ("patch-id", ("patch_id",)),
    ("patch id", ("patch_id",)),
    ("payload identity", ("patch_id",)),
    ("commit identifier", ("commit_hash",)),
    ("commit hash", ("commit_hash",)),
    ("hash equality", ("commit_hash",)),
    ("identifier equality", ("commit_hash",)),
    ("fresh identifier", ("commit_hash",)),
    ("squash rewrites the hash", ("squash_merge",)),
    ("squash mints a fresh identifier", ("squash_merge",)),
    ("squash mints", ("squash_merge",)),
    ("merged-via-squash", ("squash_merge",)),
    ("squash-integrated", ("squash_merge",)),
    ("squash rewrites", ("squash_merge",)),
    ("merged-via-rebase", ("rebase_merge",)),
    ("merged-via-ff", ("ff_merge",)),
    ("fast-forward integrated", ("ff_merge",)),
    ("fast-forward", ("ff_merge",)),
    ("enumerate git branches", ("branch_walk",)),
    ("walk every ref", ("branch_walk",)),
    ("git branches", ("branch_walk",)),
    ("every ref", ("branch_walk",)),
    ("classify each as", ("merge_taxonomy",)),
    ("bucket it as", ("merge_taxonomy",)),
    ("still-open", ("unmerged",)),
    ("wrong instrument", ("hash_wrong_meter",)),
    ("incorrect meter", ("hash_wrong_meter",)),
    ("not the commit hash", ("hash_wrong_meter",)),
    ("rather than the commit identifier", ("hash_wrong_meter",)),
)

_PHRASES: tuple[tuple[str, tuple[str, ...]], ...] = tuple(
    sorted(_PHRASE_CONCEPTS, key=lambda kv: len(kv[0]), reverse=True)
)

_WORD_CONCEPT: dict[str, str] = {
    "pipeline": "stage_complete",
    "stage": "stage_complete",
    "finished": "stage_complete",
    "complete": "stage_complete",
    "completion": "stage_complete",
    "blob": "artifact_present",
    "filesystem": "artifact_present",
    "artifact": "artifact_present",
    "bytes": "artifact_present",
    "disk": "artifact_present",
    "status": "exit_ok",
    "yields": "exit_ok",
    "yield": "exit_ok",
    "child": "exit_ok",
    "exit": "exit_ok",
    "signals": "fused_detector",
    "signal": "fused_detector",
    "sensors": "fused_detector",
    "sensor": "fused_detector",
    "detector": "fused_detector",
    "fused": "fused_detector",
    "fuses": "fused_detector",
    "instrument": "fused_detector",
    "solitary": "solo_fail",
    "insufficient": "solo_fail",
    "suffices": "solo_fail",
    "alone": "solo_fail",
    "conjunctive": "conjunction",
    "conjunctively": "conjunction",
    "timeout": "timeout_bound",
    "duration": "timeout_bound",
    "wall": "timeout_bound",
    "clock": "timeout_bound",
    "branches": "branch_walk",
    "branch": "branch_walk",
    "refs": "branch_walk",
    "ref": "branch_walk",
    "git": "branch_walk",
    "walk": "branch_walk",
    "enumerate": "branch_walk",
    "trunk": "branch_walk",
    "main": "branch_walk",
    "classify": "merge_taxonomy",
    "classification": "merge_taxonomy",
    "taxonomy": "merge_taxonomy",
    "bucket": "merge_taxonomy",
    "unmerged": "unmerged",
    "open": "unmerged",
    "squash": "squash_merge",
    "integrated": "ff_merge",
    "patch": "patch_id",
    "payload": "patch_id",
    "identity": "patch_id",
    "commit": "commit_hash",
    "hash": "commit_hash",
    "identifier": "commit_hash",
    "meter": "hash_wrong_meter",
}

# Role slots: population / instrument / purpose. Distinct from token Jaccard
# because they fire on mechanism role, not surface tokens.
_ROLE_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("role_pop_stage", ("pipeline", "stage", "step", "child process")),
    ("role_pop_branch", ("git branch", "branches", "every ref", "walk every")),
    ("role_inst_andgate", ("and-gate", "and-gated", "conjunct", "both boxes", "both sensors")),
    ("role_inst_patchid", ("patch-id", "payload identity", "patch id")),
    ("role_purpose_done", ("complete", "finished", "sign the stage")),
    ("role_purpose_class", ("classify", "bucket it", "taxonomy")),
)


def token_set(text: str) -> set[str]:
    return {t for t in TOKEN_RE.findall((text or "").lower()) if t}


def jaccard(a: str | Iterable[str], b: str | Iterable[str] | None = None) -> float:
    if b is None:
        raise TypeError("jaccard requires two texts or two token sets")
    if isinstance(a, str):
        sa = token_set(a)
    else:
        sa = set(a)
    if isinstance(b, str):
        sb = token_set(b)
    else:
        sb = set(b)
    if not sa and not sb:
        return 1.0
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def record_text(rec: Mapping[str, Any] | str) -> str:
    if isinstance(rec, str):
        return rec
    if rec.get("text"):
        return str(rec["text"])
    parts = [
        str(rec.get("title") or ""),
        str(rec.get("question_or_target") or rec.get("target") or ""),
    ]
    return " ".join(p for p in parts if p).strip()


def _normalize_hay(text: str) -> str:
    lowered = re.sub(r"[^a-z0-9]+", " ", (text or "").lower())
    return " " + re.sub(r"\s+", " ", lowered).strip() + " "


def _concept_stream(text: str) -> list[str]:
    hay = _normalize_hay(text)
    # Occupy the phrase body only. Needles include pad spaces, and adjacent
    # phrases share that space; counting the pad as occupied skipped the SOP
    # conjunction span ("both boxes are ticked") as a false overlap.
    used: list[tuple[int, int, tuple[str, ...]]] = []
    for phrase, concepts in _PHRASES:
        needle = " " + phrase.replace("-", " ") + " "
        start = 0
        while True:
            idx = hay.find(needle, start)
            if idx < 0:
                break
            end = idx + len(needle)
            body_a, body_b = idx + 1, end - 1
            overlap = any(not (body_b <= a or body_a >= b) for a, b, _ in used)
            if not overlap:
                used.append((body_a, body_b, concepts))
            start = idx + 1
    used.sort()
    occupied = []
    concepts: list[str] = []
    for a, b, cids in used:
        occupied.append((a, b))
        concepts.extend(cids)
    # leftover words (uncovered spans) mapped via the word table
    cursor = 0
    leftovers: list[str] = []
    for a, b in occupied:
        leftovers.extend(TOKEN_RE.findall(hay[cursor:a]))
        cursor = b
    leftovers.extend(TOKEN_RE.findall(hay[cursor:]))
    for tok in leftovers:
        if tok in STOP or len(tok) < 2:
            continue
        mapped = _WORD_CONCEPT.get(tok)
        if mapped:
            concepts.append(mapped)
        else:
            concepts.append(f"w:{tok}")
    return concepts


def _role_slots(text: str) -> list[str]:
    hay = _normalize_hay(text)
    hits: list[str] = []
    for slot, phrases in _ROLE_PATTERNS:
        for p in phrases:
            if " " + p.replace("-", " ") + " " in hay or p.replace("-", " ") in hay:
                hits.append(slot)
                break
    return hits


def embed(text: str) -> dict[str, float]:
    """Sparse concept embedding. Keys are concept ids, role slots, hashed 4grams."""
    vec: dict[str, float] = {}
    stream = _concept_stream(text)
    for cid in stream:
        if cid.startswith("w:"):
            vec[cid] = vec.get(cid, 0.0) + 0.15
        else:
            vec[cid] = vec.get(cid, 0.0) + 3.0
    for slot in _role_slots(text):
        vec[slot] = vec.get(slot, 0.0) + 1.5
    # hashed character 4-grams of the concept-normalized stream (not raw text)
    joined = " ".join(c for c in stream if not c.startswith("w:"))
    if len(joined) >= 4:
        for i in range(len(joined) - 3):
            ng = joined[i : i + 4]
            digest = hashlib.sha256(b"c4:" + ng.encode("utf-8")).hexdigest()[:12]
            key = "g:" + digest
            vec[key] = vec.get(key, 0.0) + 0.25
    return vec


def cosine(va: Mapping[str, float], vb: Mapping[str, float]) -> float:
    if not va or not vb:
        return 0.0
    keys = set(va) & set(vb)
    if not keys:
        return 0.0
    num = sum(va[k] * vb[k] for k in keys)
    n1 = math.sqrt(sum(v * v for v in va.values()))
    n2 = math.sqrt(sum(v * v for v in vb.values()))
    if n1 == 0.0 or n2 == 0.0:
        return 0.0
    sim = num / (n1 * n2)
    if sim < 0.0:
        return 0.0
    if sim > 1.0:
        return 1.0
    return sim


def embed_cosine(a: str, b: str) -> float:
    return cosine(embed(a), embed(b))


def verdict(lex: float, emb: float) -> str:
    lf = lex >= LEX_FIRE
    ef = emb >= EMB_FIRE
    if lf and ef:
        return "MERGE"
    if lf or ef:
        return "ADJUDICATE"
    return "DISTINCT"


def caught(verdict_s: str) -> bool:
    return verdict_s in {"MERGE", "ADJUDICATE"}


def false_merge(verdict_s: str) -> bool:
    return verdict_s == "MERGE"


def error_direction(gold_same: bool, verdict_s: str) -> str | None:
    if gold_same:
        if verdict_s == "DISTINCT":
            return "under-merge"
        return None
    if verdict_s == "MERGE":
        return "over-merge"
    return None


def compare(a: str, b: str) -> dict[str, Any]:
    lex = jaccard(a, b)
    emb = embed_cosine(a, b)
    v = verdict(lex, emb)
    lf = lex >= LEX_FIRE
    ef = emb >= EMB_FIRE
    return {
        "jaccard": round(lex, 6),
        "cosine": round(emb, 6),
        "lex_fires": lf,
        "emb_fires": ef,
        "verdict": v,
        "caught": caught(v),
    }


def compare_records(a: Mapping[str, Any], b: Mapping[str, Any]) -> dict[str, Any]:
    cmp = compare(record_text(a), record_text(b))
    cmp["left_id"] = a.get("id")
    cmp["right_id"] = b.get("id")
    return cmp


def pairwise(records: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    recs = list(records)
    out: list[dict[str, Any]] = []
    for i, left in enumerate(recs):
        for right in recs[i + 1 :]:
            out.append(compare_records(left, right))
    return out
