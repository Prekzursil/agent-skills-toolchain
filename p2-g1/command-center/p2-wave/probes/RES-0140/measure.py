#!/usr/bin/env python3
"""Live yield measurement for RES-0140 (20-item, three source classes)."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import corpus as C  # noqa: E402
import extract as E  # noqa: E402
import tokenizer as T  # noqa: E402
from restatement import restatement_talk  # noqa: E402
from textutil import bytes_to_text  # noqa: E402

REPO = C.REPO


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def load_index() -> dict:
    path = C.CAPTURES / "index.json"
    if not path.is_file():
        raise RuntimeError("captures/index.json missing; run fetch_corpus.py")
    return json.loads(path.read_text(encoding="utf-8"))


def lineage_from_row(row: dict) -> dict:
    return {
        "item_id": row["id"],
        "resolved_url": row.get("permalink") or row.get("final_url") or row.get("requested_url"),
        "requested_url": row.get("requested_url"),
        "fetch_timestamp": row.get("fetched_at"),
        "sha256": row.get("sha256"),
        "bytes": row.get("bytes"),
        "http_status": row.get("http_status"),
        "via": row.get("via"),
        "capture_path": row.get("capture_path"),
        "kind": row.get("kind"),
        "independent_verification_path": (
            "Re-hash capture bytes; compare to index sha256; re-run extract+tokenizer."
        ),
    }


def load_item(spec: dict, row: dict) -> dict:
    path = C.capture_path(spec["id"])
    if not path.is_file():
        raise RuntimeError(f"capture missing {spec['id']}")
    raw = path.read_bytes()
    digest = sha256_bytes(raw)
    if row.get("sha256") and row["sha256"] != digest:
        raise RuntimeError(f"sha-mismatch {spec['id']}")
    text = bytes_to_text(raw, row.get("content_type") or "")
    tokens = T.count_text(text)
    nbytes = len(raw.replace(b"\r\n", b"\n"))
    mechs = E.extract_mechanisms(text)
    return {
        "id": spec["id"],
        "source_class": spec["source_class"],
        "subject": spec["subject"],
        "role": spec.get("role") or spec["source_class"],
        "companion_blog_id": spec.get("companion_blog_id"),
        "tokens": tokens,
        "bytes": nbytes,
        "chars": len(text),
        "chars_div_4": len(text) // 4,
        "tokenizer_ne_chars_div_4": tokens != (len(text) // 4),
        "mechanism_count_raw": len(mechs),
        "mechanisms": mechs,
        "lineage": lineage_from_row(row),
        "note": spec.get("note"),
    }


def class_rollup(items: list[dict], other_mechs: list[dict] | None = None) -> dict:
    intra = E.cluster([m["text"] for it in items for m in it["mechanisms"]])
    tokens = sum(it["tokens"] for it in items)
    nbytes = sum(it["bytes"] for it in items)
    per_10k = (len(intra) / tokens * 10000.0) if tokens else 0.0
    unique = intra
    if other_mechs is not None:
        unique = E.unique_against(intra, other_mechs)
    unique_per_10k = (len(unique) / tokens * 10000.0) if tokens else 0.0
    return {
        "item_count": len(items),
        "item_ids": [it["id"] for it in items],
        "tokens_consumed": tokens,
        "bytes": nbytes,
        "distinct_mechanisms_intra": len(intra),
        "yield_intra_per_10k": round(per_10k, 4),
        "incremental_unique_count": len(unique),
        "incremental_unique_per_10k": round(unique_per_10k, 4),
        "tokenizer_ne_chars_div_4": all(it["tokenizer_ne_chars_div_4"] for it in items),
        "representatives": [
            {"text": m["text"][:240], "cluster_size": m["cluster_size"]} for m in unique[:40]
        ],
    }


def restatement_control(items: list[dict]) -> dict:
    by_id = {it["id"]: it for it in items}
    rows = []
    for it in items:
        if it["role"] != "restatement-control":
            continue
        blog = by_id[it["companion_blog_id"]]
        uniq = E.unique_against(it["mechanisms"], blog["mechanisms"])
        inflated = it["mechanism_count_raw"]
        collapsed = len(uniq)
        rows.append(
            {
                "transcript_id": it["id"],
                "companion_blog_id": blog["id"],
                "subject": it["subject"],
                "transcript_mechanisms": it["mechanism_count_raw"],
                "blog_mechanisms": blog["mechanism_count_raw"],
                "unique_after_collapse": collapsed,
                "inflated_if_undeduped": inflated,
                "collapses": collapsed == 0,
            }
        )
    if len(rows) != 2:
        raise RuntimeError(f"restatement rows {len(rows)}")
    return {
        "n": 2,
        "both_collapse": all(r["collapses"] for r in rows),
        "rows": rows,
    }


def threshold_verdict(tr_inc: float, od_inc: float) -> dict:
    t = C.THRESHOLD
    clears_abs = tr_inc >= t["min_incremental_unique_per_10k"]
    clears_rel = od_inc <= 0 or (tr_inc >= t["min_fraction_of_official_docs"] * od_inc)
    stay = bool(clears_abs and clears_rel)
    return {
        **t,
        "transcript_incremental_per_10k": tr_inc,
        "official_docs_incremental_per_10k": od_inc,
        "clears_absolute": clears_abs,
        "clears_relative": clears_rel,
        "stay_in_default_source_class_set": stay,
    }


def measure() -> dict:
    C.assert_inventory()
    index = load_index()
    rows = {r["id"]: r for r in index["items"]}
    missing = [it["id"] for it in C.ITEMS if not rows.get(it["id"], {}).get("ok")]
    if missing:
        raise RuntimeError(f"captures not ok: {missing}")
    items = [load_item(it, rows[it["id"]]) for it in C.ITEMS]
    if len(items) != 20:
        raise RuntimeError("sample != 20")

    by_class: dict[str, list[dict]] = {c: [] for c in C.CLASSES}
    for it in items:
        by_class[it["source_class"]].append(it)

    od_mechs = [m for it in by_class["official-docs"] for m in it["mechanisms"]]
    blog_mechs = [m for it in by_class["blog-post"] for m in it["mechanisms"]]
    tr_all = by_class["transcript"]
    tr_honest = [it for it in tr_all if it["role"] != "restatement-control"]
    tr_rest = [it for it in tr_all if it["role"] == "restatement-control"]

    od = class_rollup(
        by_class["official-docs"],
        blog_mechs + [m for it in tr_honest for m in it["mechanisms"]],
    )
    blog = class_rollup(
        by_class["blog-post"],
        od_mechs + [m for it in tr_honest for m in it["mechanisms"]],
    )
    tr_inflated = class_rollup(tr_all, od_mechs + blog_mechs)
    tr_honest_roll = class_rollup(tr_honest, od_mechs + blog_mechs)

    ctrl = restatement_control(items)
    verdict = threshold_verdict(
        tr_honest_roll["incremental_unique_per_10k"],
        od["incremental_unique_per_10k"],
    )

    def byte_rate(roll: dict) -> float:
        return (roll["incremental_unique_count"] / roll["bytes"] * 10000.0) if roll["bytes"] else 0.0

    token_ranked = sorted(
        [
            ("official-docs", od["incremental_unique_per_10k"]),
            ("blog-post", blog["incremental_unique_per_10k"]),
            ("transcript", tr_honest_roll["incremental_unique_per_10k"]),
        ],
        key=lambda kv: kv[1],
        reverse=True,
    )
    byte_ranked = sorted(
        [
            ("official-docs", byte_rate(od)),
            ("blog-post", byte_rate(blog)),
            ("transcript", byte_rate(tr_honest_roll)),
        ],
        key=lambda kv: kv[1],
        reverse=True,
    )
    two_signal = {
        "signal_a": "tokenizer unigram token count of extracted plaintext per item (not chars/4)",
        "signal_b": "UTF-8 byte length of capture bytes (CRLF-normalised) plus Jaccard-clustered mechanism fingerprints",
        "every_item_tokenizer_ne_chars_div_4": all(it["tokenizer_ne_chars_div_4"] for it in items),
        "tokens_ne_bytes": sum(it["tokens"] for it in items) != sum(it["bytes"] for it in items),
        "token_rank_leader": token_ranked[0][0],
        "byte_rank_leader": byte_ranked[0][0],
        "leaders": {"tokens": token_ranked, "bytes_per_10k_unique": byte_ranked},
    }

    per_item = []
    for it in items:
        per_item.append(
            {
                "id": it["id"],
                "source_class": it["source_class"],
                "subject": it["subject"],
                "role": it["role"],
                "tokens_consumed": it["tokens"],
                "bytes": it["bytes"],
                "chars_div_4": it["chars_div_4"],
                "tokenizer_ne_chars_div_4": it["tokenizer_ne_chars_div_4"],
                "mechanism_count_raw": it["mechanism_count_raw"],
                "lineage": it["lineage"],
            }
        )

    return {
        "sample_size": 20,
        "subjects": list(C.SUBJECTS),
        "tokenizer": T.pin_record(),
        "per_item": per_item,
        "classes": {
            "official-docs": od,
            "blog-post": blog,
            "transcript_inflated_including_restatements": tr_inflated,
            "transcript_after_restatement_collapse": tr_honest_roll,
            "transcript_restatement_items_only": class_rollup(tr_rest, blog_mechs),
        },
        "restatement_control": ctrl,
        "threshold": verdict,
        "two_signal": two_signal,
        "comparison": {
            "official_docs_intra_per_10k": od["yield_intra_per_10k"],
            "blog_intra_per_10k": blog["yield_intra_per_10k"],
            "transcript_intra_inflated_per_10k": tr_inflated["yield_intra_per_10k"],
            "transcript_incremental_honest_per_10k": tr_honest_roll["incremental_unique_per_10k"],
            "official_docs_incremental_per_10k": od["incremental_unique_per_10k"],
            "blog_incremental_per_10k": blog["incremental_unique_per_10k"],
        },
    }


def rebuild_restatement_from_blog(blog_id: str, rest_id: str) -> str:
    spec = C.item_by_id(rest_id)
    raw = C.capture_path(blog_id).read_bytes()
    index = load_index()
    row = next(r for r in index["items"] if r["id"] == blog_id)
    text = bytes_to_text(raw, row.get("content_type") or "")
    return restatement_talk(text, spec["id"])


if __name__ == "__main__":
    doc = measure()
    print(
        json.dumps(
            {k: doc[k] for k in ("sample_size", "comparison", "threshold", "restatement_control")},
            indent=2,
        )
    )
    print("SUCCESS:RES-0140-measure")
