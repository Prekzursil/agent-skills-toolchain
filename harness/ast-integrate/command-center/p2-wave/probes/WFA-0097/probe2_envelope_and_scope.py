#!/usr/bin/env python3
"""Named probe 2: measured envelope, named settling experiments, live scope lint."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import envelope as E  # noqa: E402
import lint as L  # noqa: E402
import paths as P  # noqa: E402
import settle as S  # noqa: E402

DETECTABLE = {
    "exact-rename",
    "one-parameter-fork",
    "reworded-paraphrase",
    "full-rewrite",
    "structural-clone",
}
UNDETECTABLE = {
    "behavioral-isomorph-divergent-ir",
    "cross-language-divergent-ir",
    "ciphertext-opaque-payload",
}
DECOYS = {"decoy-distinct", "decoy-vs-decoy"}


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0097-probe2 {msg}")
    return 1


def main() -> int:
    env = E.measure()
    by_shape = {r["shape"]: r for r in env["rows"]}
    missing = (DETECTABLE | UNDETECTABLE | DECOYS) - set(by_shape)
    if missing:
        return fail(f"missing shapes {sorted(missing)}")

    rewrite = by_shape["full-rewrite"]
    if rewrite["lexical_hit"]:
        return fail("lexical caught full-rewrite; envelope no longer separates methods")
    if not rewrite["embedding_hit"]:
        return fail("embedding stand-in missed full-rewrite")
    if not by_shape["exact-rename"]["lexical_hit"]:
        return fail("lexical missed exact-rename")
    if not by_shape["one-parameter-fork"]["lexical_hit"]:
        return fail("lexical missed one-parameter-fork")
    if not by_shape["reworded-paraphrase"]["lexical_hit"]:
        return fail("lexical missed reworded-paraphrase")
    if not by_shape["structural-clone"]["structural_hit"]:
        return fail("structural missed structural-clone")
    if by_shape["structural-clone"]["lexical_hit"]:
        return fail("lexical false-hit on structural-clone")
    if by_shape["one-parameter-fork"]["structural_hit"]:
        return fail("structural false-hit on one-parameter-fork (tools differ)")

    for shape in DETECTABLE:
        if not by_shape[shape]["combined_hit"]:
            return fail(f"combined missed detectable shape {shape}")
    for shape in UNDETECTABLE:
        row = by_shape[shape]
        if row["combined_hit"]:
            return fail(f"combined false-hit on undetectable {shape}")
        exp = (row.get("settling_experiment") or "").strip()
        if len(exp) < 24:
            return fail(f"undetectable {shape} lacks a named settling experiment")
    for shape in DECOYS:
        if by_shape[shape]["combined_hit"]:
            return fail(f"combined false-hit on decoy {shape}")
        if by_shape[shape]["semantic_duplicate"]:
            return fail(f"decoy {shape} labelled semantic_duplicate")

    if env["decoy_false_positives"]:
        return fail(f"decoy false positives {env['decoy_false_positives']}")
    ids = {u["id"] for u in env["undetectable_classes"]}
    if ids != UNDETECTABLE:
        return fail(f"undetectable set {sorted(ids)} != {sorted(UNDETECTABLE)}")
    for u in env["undetectable_classes"]:
        if not (u.get("settling_experiment") or "").strip():
            return fail(f"{u['id']} settling_experiment empty")

    cipher = S.settle_ciphertext()
    if not cipher.get("settled"):
        return fail(f"ciphertext settling experiment did not flip {cipher}")

    art = P.REPO / P.OUT_REL
    artifact_lint = None
    if art.is_file() and art.stat().st_size > 0:
        artifact_lint = L.lint_path(art)
        if not artifact_lint.get("ok"):
            return fail(f"live artifact lint {artifact_lint}")
        doc = json.loads(art.read_text(encoding="utf-8"))
        text = json.dumps(doc)
        if P.CATALOG_SENTINEL not in text:
            return fail("live artifact missing SUCCESS:WFA-0097")
        state = str(doc.get("state") or "").upper()
        if state in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
            return fail(f"live artifact self-declared {state}")
        live_und = doc.get("undetectable_classes") or []
        if len(live_und) < 3:
            return fail("live artifact undetectable_classes < 3")
        for item in live_und:
            if not str(item.get("settling_experiment") or "").strip():
                return fail(f"live artifact {item.get('id')} missing settling_experiment")
            if not str(item.get("id") or "").strip():
                return fail("live artifact undetectable class missing id")

    print(
        json.dumps(
            {
                "detectable_combined": sorted(DETECTABLE),
                "undetectable": sorted(ids),
                "lexical_misses_full_rewrite": not rewrite["lexical_hit"],
                "embedding_hits_full_rewrite": rewrite["embedding_hit"],
                "structural_hits_clone": by_shape["structural-clone"]["structural_hit"],
                "decoys_silent": env["decoys_silent"],
                "ciphertext_settled": True,
                "artifact_lint_ok": None if artifact_lint is None else True,
                "undetectable_named_experiments": True,
            },
            sort_keys=True,
        )
    )
    print(
        "SUCCESS:WFA-0097-probe2 envelope tabulated; undetectable classes name "
        "settling experiments; ciphertext decode settles; live scope lint ok "
        "when artifact present"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
