"""Three collapse pairs, one per deciding signal.

Each pair carries unique capability fields so the preserved union is not a
no-op: the survivor lacks a mechanism, provenance anchor, licence, or stop
rule that the absorbed record holds.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

# Frozen so trail hashes are deterministic across emit and live probes.
TS = "2026-08-24T19:00:00Z"

LEX_KEEP = "wf-lex-keep"
LEX_DROP = "wf-lex-drop"
EMB_KEEP = "wf-emb-keep"
EMB_DROP = "wf-emb-drop"
STR_KEEP = "wf-str-keep"
STR_DROP = "wf-str-drop"


def _rec(**kwargs: Any) -> dict[str, Any]:
    rec = {
        "id": "",
        "text": "",
        "mechanisms": [],
        "provenance_anchors": [],
        "licence_obligations": [],
        "stop_rules": [],
        "stages": [],
        "roles": [],
        "gates": [],
        "tools": [],
        "duplicate_of": [],
    }
    rec.update(kwargs)
    rec["mechanisms"] = list(rec["mechanisms"])
    rec["provenance_anchors"] = list(rec["provenance_anchors"])
    rec["licence_obligations"] = list(rec["licence_obligations"])
    rec["stop_rules"] = list(rec["stop_rules"])
    rec["stages"] = list(rec["stages"])
    rec["roles"] = list(rec["roles"])
    rec["gates"] = list(rec["gates"])
    rec["tools"] = list(rec["tools"])
    rec["duplicate_of"] = list(rec["duplicate_of"])
    return rec


def lexical_pair() -> tuple[dict, dict]:
    """Near-identical surface form (rename of an identifier in metadata only)."""
    text = (
        "verify the workflow manifest sha256 digest before merge commit "
        "and refuse unsigned payloads"
    )
    keep = _rec(
        id=LEX_KEEP,
        text=text,
        mechanisms=["manifest-sha-verify", "unsigned-payload-refuse"],
        provenance_anchors=["anchor://lex/keep/manifest-gate"],
        licence_obligations=["MIT"],
        stop_rules=["halt-on-unsigned-payload"],
        stages=["intake", "hash", "merge"],
        roles=["verifier"],
        gates=["unsigned-refuse"],
        tools=["sha256sum"],
    )
    drop = _rec(
        id=LEX_DROP,
        text=text,
        mechanisms=["manifest-sha-verify", "byte-size-floor"],
        provenance_anchors=["anchor://lex/drop/size-floor"],
        licence_obligations=["Apache-2.0"],
        stop_rules=["halt-below-byte-floor"],
        stages=["intake", "measure", "emit"],
        roles=["sizer"],
        gates=["min-bytes"],
        tools=["stat"],
    )
    return keep, drop


def embedding_pair() -> tuple[dict, dict]:
    """Paraphrase: low token Jaccard, high synonym-folded embedding cosine."""
    keep = _rec(
        id=EMB_KEEP,
        text=(
            "verify writing of the completion document covers the digest "
            "of listed files"
        ),
        mechanisms=["completion-document-digest-cover"],
        provenance_anchors=["anchor://emb/keep/digest-cover"],
        licence_obligations=["MIT"],
        stop_rules=["halt-if-digest-uncovered"],
        stages=["draft", "cover", "seal"],
        roles=["author"],
        gates=["digest-cover"],
        tools=["digest-cli"],
    )
    drop = _rec(
        id=EMB_DROP,
        text=(
            "confirm emitting of the wrap report includes the hash of "
            "listed artifacts"
        ),
        mechanisms=["wrap-report-hash-include"],
        provenance_anchors=["anchor://emb/drop/hash-include"],
        licence_obligations=["GPL-3.0-only"],
        stop_rules=["halt-if-hash-missing"],
        stages=["render", "include", "publish"],
        roles=["emitter"],
        gates=["hash-include"],
        tools=["hash-cli"],
    )
    return keep, drop


def structural_pair() -> tuple[dict, dict]:
    """Same stage/role/gate/tool graph; unrelated prose (lexical+embedding miss)."""
    graph = dict(
        stages=["intake", "diff", "gate", "emit"],
        roles=["differ", "gatekeeper"],
        gates=["fail-closed-diff"],
        tools=["diffoscope"],
    )
    keep = _rec(
        id=STR_KEEP,
        text=(
            "orange tabby cats nap on sunlit windowsills after breakfast "
            "sardines"
        ),
        mechanisms=["fail-closed-diff-graph"],
        provenance_anchors=["anchor://str/keep/diff-graph"],
        licence_obligations=["BSD-3-Clause"],
        stop_rules=["halt-on-diff-fail-closed"],
        **graph,
    )
    drop = _rec(
        id=STR_DROP,
        text=(
            "cargo barges haul timber crates upriver past the lock gates "
            "at dusk"
        ),
        mechanisms=["barge-lock-side-channel-unused"],
        provenance_anchors=["anchor://str/drop/barge-lock"],
        licence_obligations=["LGPL-2.1-only"],
        stop_rules=["halt-on-lock-mismatch"],
        **graph,
    )
    return keep, drop


def all_records() -> dict[str, dict]:
    recs: dict[str, dict] = {}
    for pair in (lexical_pair, embedding_pair, structural_pair):
        a, b = pair()
        recs[a["id"]] = a
        recs[b["id"]] = b
    return recs


def collapse_plans() -> list[dict[str, Any]]:
    """Three collapses, disjoint ids, one required primary signal each."""
    return [
        {
            "primary_signal": "LEXICAL",
            "surviving_id": LEX_KEEP,
            "absorbed_ids": [LEX_DROP],
        },
        {
            "primary_signal": "EMBEDDING",
            "surviving_id": EMB_KEEP,
            "absorbed_ids": [EMB_DROP],
        },
        {
            "primary_signal": "STRUCTURAL",
            "surviving_id": STR_KEEP,
            "absorbed_ids": [STR_DROP],
        },
    ]


def clone_records() -> dict[str, dict]:
    return deepcopy(all_records())
