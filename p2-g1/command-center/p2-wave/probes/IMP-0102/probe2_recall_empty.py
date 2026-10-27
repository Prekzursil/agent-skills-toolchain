#!/usr/bin/env python3
"""IMP-0102 probe2: recall + typed outcomes. canonical-hello findable by name
and by skill token hello-operator; obscure-bundle findable ONLY via skills[]
(token absent from name and description); council-pack findable via the nested
skills path. No-match -> kind=empty (ok=true); missing registry file ->
kind=index_error (ok=false); the two are distinct. Skill-only findability is
the both-states signal (a name/description-only index would miss it)."""
from __future__ import annotations

import glob
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CORPUS = REPO / "tools" / "marketplace" / "fixtures" / "registry_corpus.json"


def load_search():
    hits = sorted(glob.glob(str(REPO / "tools" / "marketplace" / "search.py")))
    spec = importlib.util.spec_from_file_location("imp0102_search2", hits[0])
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def ids(res: dict) -> list[str]:
    return [h["id"] for h in res.get("hits") or []]


def main() -> int:
    S = load_search()
    by_name = S.search_path(CORPUS, "canonical-hello")
    by_skill = S.search_path(CORPUS, "hello-operator")
    skill_only = S.search_path(CORPUS, "binary-diff-oracle")
    council = S.search_path(CORPUS, "council")
    empty = S.search_path(CORPUS, "zzz-no-such-token-zzz")
    missing = S.search_path(REPO / "tools" / "marketplace" / "fixtures"
                            / "no-such-marketplace.json", "anything")

    name_hit = "canonical-hello" in ids(by_name)
    skill_hit = "canonical-hello" in ids(by_skill)
    only_via_skills = ids(skill_only) == ["obscure-bundle"]
    # the skill-only signal is both-states: prove the token is genuinely
    # ABSENT from name+description of the found package.
    corpus = json.loads(CORPUS.read_text(encoding="utf-8"))
    obs = next(p for p in corpus["plugins"] if p["id"] == "obscure-bundle")
    token_absent = ("binary-diff-oracle" not in obs["name"]
                    and "binary-diff-oracle" not in obs["description"])

    council_hit = "council-pack" in ids(council)
    empty_ok = empty.get("kind") == "empty" and empty.get("ok") is True and empty.get("hit_count") == 0
    missing_ok = missing.get("kind") == "index_error" and missing.get("ok") is False
    distinct = empty_ok and missing_ok and empty.get("kind") != missing.get("kind")

    result = {
        "unit_id": "IMP-0102",
        "probe": "probe2-recall-empty",
        "by_name_hit": name_hit,
        "by_skill_hit": skill_hit,
        "skill_only_hit": only_via_skills,
        "token_absent_from_name_desc": token_absent,
        "council_hit": council_hit,
        "empty_kind": empty.get("kind"),
        "missing_kind": missing.get("kind"),
        "empty_vs_error_distinct": distinct,
        "pass": all([name_hit, skill_hit, only_via_skills, token_absent,
                     council_hit, empty_ok, missing_ok, distinct]),
    }
    print("RESULT:" + json.dumps(result))
    tail = ("SUCCESS:IMP-0102-probe2 recall by name and skill; skill-only findability proven; "
            "empty vs index_error distinct (both-states)"
            if result["pass"] else
            "FAILED:IMP-0102-probe2 recall/typed-outcome contract broken")
    print(tail)
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
