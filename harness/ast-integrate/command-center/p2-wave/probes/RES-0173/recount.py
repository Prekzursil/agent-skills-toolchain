#!/usr/bin/env python3
"""Independent recount: no import of evaluate.py.

Recomputes:
  * token Jaccard with NO stoplist (alnum tokens, presence-only Counter keys)
  * mechanism identity via sha256(action|object) equality, not raw-string compare
  * clusters by union-find on key hashes (aggregation, not the pairwise table)
  * exact-string and always-merge taxonomy calibrators

Neural sentence embeddings are not invoked. A second local cosine
(char-3gram signed bags) is recorded as a diagnostic, not as a named method.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIXTURE = HERE / "fixtures" / "planted_claims.json"
ALNUM = re.compile(r"[a-z0-9]+")
JACCARD_THRESHOLD = 0.50
KEY_SALT = b"RES-0173-key-v1"


def load_fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def alnum_tokens(text: str) -> set[str]:
    return set(ALNUM.findall((text or "").lower()))


def jaccard_counter(a: str, b: str) -> float:
    ca = Counter(alnum_tokens(a))
    cb = Counter(alnum_tokens(b))
    A, B = set(ca), set(cb)
    if not A and not B:
        return 1.0
    if not A or not B:
        return 0.0
    return len(A & B) / len(A | B)


def slot(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(value or "").lower()).strip("-")


def key_digest(claim: dict) -> str | None:
    mech = claim.get("canonical_mechanism")
    if not isinstance(mech, dict):
        return None
    action, obj = slot(mech.get("action")), slot(mech.get("object"))
    if not action or not obj:
        return None
    payload = KEY_SALT + f"{action}|{obj}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def char3_cosine(a: str, b: str, dim: int = 128) -> float:
    def grams(text: str) -> list[str]:
        s = re.sub(r"\s+", " ", (text or "").lower()).strip()
        if len(s) < 3:
            return []
        return [s[i : i + 3] for i in range(len(s) - 2)]

    def bag(text: str) -> list[int]:
        vec = [0] * dim
        for g in grams(text):
            digest = hashlib.sha256(g.encode("utf-8")).digest()
            idx = int.from_bytes(digest[:2], "little") % dim
            sign = 1 if digest[2] & 1 else -1
            vec[idx] += sign
        return vec

    u, v = bag(a), bag(b)
    dot = nu = nv = 0
    for x, y in zip(u, v):
        dot += x * y
        nu += x * x
        nv += y * y
    if nu == 0 or nv == 0:
        return 1.0 if nu == 0 and nv == 0 else 0.0
    return dot / (math.sqrt(nu) * math.sqrt(nv))


class UnionFind:
    def __init__(self, ids: list[str]) -> None:
        self.parent = {i: i for i in ids}

    def find(self, x: str) -> str:
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: str, b: str) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[rb] = ra


def recount() -> dict:
    fixture = load_fixture()
    claims = {c["id"]: c for c in fixture["claims"]}
    uf = UnionFind(list(claims))
    by_hash: dict[str, list[str]] = {}
    for cid, claim in claims.items():
        digest = key_digest(claim)
        if digest is None:
            raise AssertionError(f"unkeyed claim {cid}")
        by_hash.setdefault(digest, []).append(cid)
    for group in by_hash.values():
        for other in group[1:]:
            uf.union(group[0], other)

    pair_rows = []
    para_ok = True
    dist_split = True
    rewrite_same_cluster = True
    for spec in fixture["labeled_pairs"]:
        left, right = claims[spec["left"]], claims[spec["right"]]
        jac = round(jaccard_counter(left["text"], right["text"]), 6)
        same_key = key_digest(left) == key_digest(right)
        same_cluster = uf.find(spec["left"]) == uf.find(spec["right"])
        if same_key != same_cluster:
            raise AssertionError(
                f"union-find disagrees with key hash on {spec['left']}/{spec['right']}"
            )
        row = {
            "left": spec["left"],
            "right": spec["right"],
            "class": spec["class"],
            "intended": spec["intended"],
            "jaccard_nostop": jac,
            "jaccard_merge": jac >= JACCARD_THRESHOLD,
            "key_hash_merge": same_key,
            "cluster_merge": same_cluster,
            "exact_string_merge": left["text"].strip() == right["text"].strip(),
            "always_merge": True,
            "char3_cosine": round(char3_cosine(left["text"], right["text"]), 6),
        }
        pair_rows.append(row)
        if spec["class"] == "paraphrase":
            if not (row["jaccard_merge"] and same_key and same_cluster):
                para_ok = False
        if spec["class"] == "true_distinction":
            if row["jaccard_merge"] or same_key or same_cluster:
                dist_split = False
        if spec["class"] == "full_rewrite":
            if row["jaccard_merge"] or not same_cluster:
                rewrite_same_cluster = False

    def taxonomy(merge_field: str) -> str:
        para = [r for r in pair_rows if r["class"] == "paraphrase"]
        dist = [r for r in pair_rows if r["class"] == "true_distinction"]
        all_para = bool(para) and all(r[merge_field] for r in para)
        any_dist = any(r[merge_field] for r in dist)
        if all_para and not any_dist:
            return "correct"
        if all_para and any_dist:
            return "collapser"
        if not all_para and not any_dist:
            return "string_comparator"
        return "inverted"

    unique_keys = len(by_hash)
    return {
        "n_claims": len(claims),
        "unique_mechanism_key_hashes": unique_keys,
        "pair_rows": pair_rows,
        "taxonomy": {
            "lexical_jaccard_nostop": taxonomy("jaccard_merge"),
            "mechanism_key_hash": taxonomy("key_hash_merge"),
            "union_find_cluster": taxonomy("cluster_merge"),
            "always_merge": taxonomy("always_merge"),
            "exact_string": taxonomy("exact_string_merge"),
        },
        "paraphrases_merged_by_jaccard_and_key": para_ok,
        "distinctions_split_by_jaccard_and_key": dist_split,
        "rewrite_same_cluster_not_jaccard": rewrite_same_cluster,
        "neural_sentence_embedding": "NOT-CHECKED",
        "independent": True,
        "imports_evaluate": False,
    }


def assert_invariants(bundle: dict) -> None:
    tax = bundle["taxonomy"]
    if tax["always_merge"] != "collapser":
        raise AssertionError("always-merge control is not a collapser")
    if tax["exact_string"] != "string_comparator":
        raise AssertionError("exact-string control is not a string comparator")
    if tax["mechanism_key_hash"] != "correct":
        raise AssertionError("key-hash taxonomy is not correct")
    if tax["union_find_cluster"] != "correct":
        raise AssertionError("union-find taxonomy is not correct")
    if tax["lexical_jaccard_nostop"] != "correct":
        raise AssertionError("no-stoplist Jaccard failed both-states")
    if not bundle["paraphrases_merged_by_jaccard_and_key"]:
        raise AssertionError("paraphrase recount failed")
    if not bundle["distinctions_split_by_jaccard_and_key"]:
        raise AssertionError("distinction recount failed")
    if not bundle["rewrite_same_cluster_not_jaccard"]:
        raise AssertionError("rewrite cluster recount failed")
    if bundle["unique_mechanism_key_hashes"] != 3:
        raise AssertionError(
            f"unique keys={bundle['unique_mechanism_key_hashes']} want 3 (A/B/C)"
        )
    rew = next(r for r in bundle["pair_rows"] if r["class"] == "full_rewrite")
    if rew["jaccard_merge"]:
        raise AssertionError("no-stoplist Jaccard merged the rewrite")
    if not rew["cluster_merge"]:
        raise AssertionError("rewrite not in parent cluster")


def main() -> int:
    bundle = recount()
    assert_invariants(bundle)
    print(json.dumps(
        {
            "taxonomy": bundle["taxonomy"],
            "unique_keys": bundle["unique_mechanism_key_hashes"],
            "rewrite": next(
                r for r in bundle["pair_rows"] if r["class"] == "full_rewrite"
            ),
            "neural": bundle["neural_sentence_embedding"],
        },
        indent=2,
        sort_keys=True,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
