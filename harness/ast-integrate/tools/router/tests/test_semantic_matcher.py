"""Unit tests for the IMP-0390 semantic matcher, its pinned model and the control set.

Run from the repo root: ``PYTHONPATH=tools python3 -m unittest router.tests.test_semantic_matcher``.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from router import build_pinned_model as bpm
from router import embed_model as em
from router import semantic_matcher as sm
from router.lexical import jaccard_int, lexical_rank, shared_tokens, tokenize

PLANTED = sm.load_planted()
CAPS = PLANTED["capabilities"]
K = int(PLANTED["k"])
SEED = int(PLANTED["seed"])
BY_ID = {c["capability_id"]: c["description"] for c in CAPS}


def _tmp_path(name: str) -> Path:
    return Path(tempfile.mkdtemp(prefix="imp0390-")) / name


def _mutated_model(mutate) -> Path:
    doc = json.loads(sm.MODEL_PATH.read_text(encoding="utf-8"))
    mutate(doc)
    p = _tmp_path("mutated-model.json")
    p.write_text(json.dumps(doc, sort_keys=True), encoding="utf-8")
    return p


class ControlSetTests(unittest.TestCase):
    def test_paraphrases_share_no_content_token_with_target(self) -> None:
        self.assertGreaterEqual(len(PLANTED["paraphrase_queries"]), 12)
        for q in PLANTED["paraphrase_queries"]:
            target = BY_ID[q["capability_id"]]
            self.assertEqual(shared_tokens(q["query"], target), [], q["query_id"])
            self.assertEqual(jaccard_int(tokenize(q["query"]), tokenize(target)), 0)
            top = [r["capability_id"] for r in lexical_rank(q["query"], CAPS, k=K, seed=SEED)]
            self.assertNotIn(q["capability_id"], top, q["query_id"])

    def test_verbatim_queries_are_exact_descriptions(self) -> None:
        self.assertEqual(len(PLANTED["verbatim_queries"]), 5)
        for q in PLANTED["verbatim_queries"]:
            self.assertEqual(q["query"], BY_ID[q["capability_id"]])
            rows = lexical_rank(q["query"], CAPS, k=K, seed=SEED)
            self.assertEqual(rows[0]["capability_id"], q["capability_id"])
            self.assertEqual(rows[0]["jaccard_e9"], em.E9)

    def test_catalogue_is_the_imp0388_index_plus_the_mutant(self) -> None:
        caps, mutant, _ = bpm.load_imp0388()
        ids = [c["capability_id"] for c in CAPS]
        self.assertEqual(ids[: len(caps)], [c["capability_id"] for c in caps])
        self.assertEqual(ids[-1], mutant["new_id"])
        pair = PLANTED["imp0388_planted_pair"]
        self.assertEqual(pair["left_id"], mutant["sibling_id"])
        self.assertEqual(pair["right_id"], mutant["new_id"])
        self.assertEqual(shared_tokens(BY_ID[pair["left_id"]], BY_ID[pair["right_id"]]), [])

    def test_validate_planted_rejects_leaky_paraphrase(self) -> None:
        doc = json.loads(json.dumps(PLANTED))
        leaky = doc["paraphrase_queries"][0]
        leaky["query"] = BY_ID[leaky["capability_id"]].split(".")[0]
        with self.assertRaises(sm.PlantedSetError):
            sm.validate_planted(doc)

    def test_validate_planted_rejects_inexact_verbatim(self) -> None:
        doc = json.loads(json.dumps(PLANTED))
        doc["verbatim_queries"][0]["query"] += " extra"
        with self.assertRaises(sm.PlantedSetError):
            sm.validate_planted(doc)

    def test_build_is_byte_reproducible(self) -> None:
        files, rows = bpm.build_all()
        self.assertEqual(bpm.check_drift(files), [])
        self.assertTrue(all(r["semantic_rank"] == 1 for r in rows if r["class"] == "verbatim"))
        self.assertTrue(all(r["semantic_rank"] <= K for r in rows if r["class"] == "paraphrase"))


class EmbedModelTests(unittest.TestCase):
    def setUp(self) -> None:
        self.load = em.load_model(sm.MODEL_PATH)
        self.assertTrue(self.load.ok, self.load.detail)
        self.model = self.load.model

    def test_embedding_is_unit_norm_and_identity_scores_full(self) -> None:
        text = BY_ID["skill.git-push"]
        vec = self.model.embed(text)
        self.assertEqual(len(vec), self.model.dim)
        self.assertAlmostEqual(sum(v * v for v in vec), 1.0, places=9)
        self.assertEqual(em.cosine_e9(vec, self.model.embed(text)), em.E9)
        self.assertEqual(self.model.embed(""), [0.0] * self.model.dim)
        self.assertEqual(em.cosine_e9(self.model.embed(""), vec), 0)

    def test_concepts_bridge_disjoint_surface_forms(self) -> None:
        left = "Verify an access credential"
        right = "Validates API keys"
        self.assertEqual(shared_tokens(left, right), [])
        shared = set(self.model.concepts_of(left)) & set(self.model.concepts_of(right))
        self.assertIn("validate", shared)
        self.assertIn("credential", shared)
        self.assertGreater(self.model.similarity_e9(left, right), 0)

    def test_document_digest_and_validation(self) -> None:
        doc = json.loads(sm.MODEL_PATH.read_text(encoding="utf-8"))
        self.assertEqual(doc["digest"], em.model_digest(doc))
        bad = dict(doc)
        bad["dim"] = 4
        with self.assertRaises(em.EmbedModelError):
            em.validate_document(bad)
        with self.assertRaises(em.EmbedModelError):
            em.validate_document({"schema": "other"})

    def test_load_model_typed_codes(self) -> None:
        absent = em.load_model(_tmp_path("absent.json"))
        self.assertEqual((absent.status, absent.code), (em.STATUS_DEGRADED, em.CODE_ABSENT))
        garbage = _tmp_path("garbage.json")
        garbage.write_text("{not json", encoding="utf-8")
        self.assertEqual(em.load_model(garbage).code, em.CODE_SCHEMA)
        wrong_id = _mutated_model(lambda d: d.update(model_id="someone-else-v9"))
        self.assertEqual(em.load_model(wrong_id).code, em.CODE_ID)
        stale_digest = _mutated_model(lambda d: d.update(seed=d["seed"] + 1))
        self.assertEqual(em.load_model(stale_digest).code, em.CODE_DIGEST)


class MatchTests(unittest.TestCase):
    def test_match_is_deterministic_and_tagged(self) -> None:
        query = PLANTED["paraphrase_queries"][0]["query"]
        a = sm.match(query, CAPS, k=K, seed=SEED)
        b = sm.match(query, CAPS, k=K, seed=SEED)
        self.assertEqual(a.status, em.STATUS_OK)
        self.assertEqual(a.code, em.CODE_OK)
        self.assertFalse(a.lexical_results_suppressed)
        self.assertEqual(a.ranking_bytes(), b.ranking_bytes())
        self.assertEqual(len(a.ranking), K)
        self.assertEqual([r["rank"] for r in a.ranking], list(range(1, K + 1)))
        scores = [r["cosine_e9"] for r in a.ranking]
        self.assertEqual(scores, sorted(scores, reverse=True))
        self.assertTrue(all(r["method"] == sm.METHOD for r in a.ranking))
        self.assertTrue(all(r["model_id"] == em.MODEL_ID for r in a.ranking))
        self.assertEqual(a.model_digest, sm.pin_identity()["pinned_sha256"])

    def test_match_rejects_bad_arguments(self) -> None:
        with self.assertRaises(ValueError):
            sm.match("x", CAPS, k=0)
        with self.assertRaises(ValueError):
            sm.match("x", CAPS + [dict(CAPS[0])])
        with self.assertRaises(TypeError):
            sm.match("x", CAPS, seed="390")  # type: ignore[arg-type]

    def test_absent_model_is_typed_degraded_without_lexical_fallback(self) -> None:
        verbatim = PLANTED["verbatim_queries"][0]["query"]
        res = sm.match(verbatim, CAPS, k=K, seed=SEED, model_path=_tmp_path("absent.json"))
        self.assertEqual(res.status, em.STATUS_DEGRADED)
        self.assertEqual(res.stage, sm.STAGE)
        self.assertEqual(res.code, em.CODE_ABSENT)
        self.assertEqual(res.ranking, [])
        self.assertTrue(res.lexical_results_suppressed)
        self.assertTrue(lexical_rank(verbatim, CAPS, k=K, seed=SEED))

    def test_mutated_or_relabelled_model_is_typed_degraded(self) -> None:
        query = PLANTED["paraphrase_queries"][0]["query"]
        dim = _mutated_model(lambda d: d.update(dim=d["dim"] + 1))
        self.assertEqual(sm.match(query, CAPS, k=K, seed=SEED, model_path=dim).code, em.CODE_DIGEST)
        ident = _mutated_model(lambda d: d.update(model_id="imp0390-local-concept-embed-v9.9.9"))
        self.assertEqual(sm.match(query, CAPS, k=K, seed=SEED, model_path=ident).code, em.CODE_ID)
        # Same canonical content, different bytes: the pin is over the file, so this degrades too.
        reformatted = _tmp_path("reformatted.json")
        reformatted.write_text(
            json.dumps(json.loads(sm.MODEL_PATH.read_text(encoding="utf-8")), sort_keys=True),
            encoding="utf-8",
        )
        res = sm.match(query, CAPS, k=K, seed=SEED, model_path=reformatted)
        self.assertEqual((res.status, res.code, res.ranking), (em.STATUS_DEGRADED, em.CODE_DIGEST, []))

    def test_pin_identity(self) -> None:
        ident = sm.pin_identity()
        self.assertTrue(ident["digest_matches_pin"], ident)
        self.assertEqual(ident["model_id"], em.MODEL_ID)
        self.assertEqual(ident["version"], em.MODEL_VERSION)
        self.assertEqual(ident["path"], sm.MODEL_REL)
        self.assertEqual(ident["live_sha256"], em.file_digest(sm.MODEL_PATH))
        self.assertEqual(ident["pinned_sha256"], ident["live_sha256"])
        missing = sm.pin_identity(pin_path=_tmp_path("no-pin.json"))
        self.assertFalse(missing["digest_matches_pin"])
        self.assertIn("FileNotFoundError", missing["detail"])


class RecallTests(unittest.TestCase):
    def test_verbatim_is_two_sided(self) -> None:
        res = sm.measure_recall(PLANTED["verbatim_queries"], CAPS, k=K, seed=SEED)
        self.assertEqual(res["n"], 5)
        self.assertEqual(res["lexical_recall_at_k"], 1.0)
        self.assertEqual(res["semantic_recall_at_k"], 1.0)
        self.assertTrue(all(r["semantic_rank"] == 1 for r in res["rows"]))
        self.assertTrue(all(r["class"] == "verbatim" for r in res["rows"]))

    def test_paraphrases_miss_lexical_and_hit_semantic(self) -> None:
        res = sm.measure_recall(PLANTED["paraphrase_queries"], CAPS, k=K, seed=SEED)
        self.assertEqual(res["lexical_hits"], 0)
        self.assertEqual(res["semantic_hits"], res["n"])
        self.assertEqual(res["lexical_recall_at_k"], 0.0)
        self.assertEqual(res["semantic_recall_at_k"], 1.0)
        for row in res["rows"]:
            self.assertEqual(row["lexical_jaccard_e9"], 0)
            self.assertEqual(row["semantic_status"], em.STATUS_OK)
            self.assertGreater(row["semantic_cosine_e9"], 0)

    def test_degraded_semantic_stage_scores_zero_not_lexical(self) -> None:
        res = sm.measure_recall(
            PLANTED["verbatim_queries"], CAPS, k=K, seed=SEED, model_path=_tmp_path("absent.json")
        )
        self.assertEqual(res["lexical_recall_at_k"], 1.0)
        self.assertEqual(res["semantic_recall_at_k"], 0.0)
        self.assertEqual(res["semantic_status"], em.STATUS_DEGRADED)
        self.assertEqual(res["semantic_code"], em.CODE_ABSENT)
        self.assertTrue(all(r["semantic_top"] == [] for r in res["rows"]))

    def test_planted_pair_is_invisible_lexically_and_recovered_semantically(self) -> None:
        pair = PLANTED["imp0388_planted_pair"]
        scores = sm.pair_scores(BY_ID[pair["left_id"]], BY_ID[pair["right_id"]], seed=SEED)
        self.assertEqual(scores["lexical_jaccard_e9"], 0)
        self.assertEqual(scores["lexical_shared_tokens"], [])
        self.assertGreater(scores["semantic_cosine_e9"], 0)
        self.assertTrue(scores["semantic_shared_concepts"])
        degraded = sm.pair_scores("a b", "c d", model_path=_tmp_path("absent.json"))
        self.assertIsNone(degraded["semantic_cosine_e9"])
        self.assertEqual(degraded["semantic_code"], em.CODE_ABSENT)


if __name__ == "__main__":
    unittest.main()
