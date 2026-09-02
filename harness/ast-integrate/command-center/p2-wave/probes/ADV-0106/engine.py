"""Live instruments for ADV-0106.

Probe 1: stylometric re-attribution of anonymised transcripts vs a computed
chance baseline, plus a scan of published partition artifacts for identity.
Probe 2: partition-content audit on tools/council/partition.py — search each
seat's readable artifacts for facts that only another partition was given.

Does not rebuild council-pathology-sim.schema.json.
"""
from __future__ import annotations

import json
import math
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
TOOLS = REPO / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from council.partition import (  # noqa: E402
    ALL_SEATS,
    ALLOWED_NONCE,
    ASSEMBLY_LEAK,
    DETECTOR_CONTROL,
    HONEST,
    MODES,
    NAIVE_PARAPHRASE,
    NAIVE_SCRATCHPAD,
    NAIVE_SUMMARY,
    NAIVE_TOOL,
    SEAT_A,
    WITHHELD_NONCE,
    mint_canary,
    require_real_search,
    run_fixture,
    search_seat,
)

UNIT = "ADV-0106"
OUT_REL = "command-center/adversarial/ADV-0106-anonymity-and-partition-leakage.json"
SCHEMA_DECLARED = "command-center/schema/council-pathology-sim.schema.json"
SUT = "tools/council/partition.py"

PROBE1_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0106/probe1_identity_reattribution.py"
)
PROBE2_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0106/probe2_partition_audit.py"
)

CATALOG_PROBE1 = (
    "Probe 1: attempt identity re-attribution from the anonymised transcript "
    "alone and report accuracy against chance."
)
CATALOG_PROBE2 = (
    "Probe 2 (mechanically different): partition-content audit - search each "
    "participant's output for facts that only another partition was given, "
    "which detects information leakage even when identity remains hidden."
)

SENTINEL = (
    "SUCCESS:ADV-0106 emitted ONLY when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, records BOTH named probes "
    "verbatim with their raw output, carries exactly one verdict from "
    "{CONFIRMED|REFUTED|PARTIAL|NOT-CHECKED|BLOCKED} per enumerated target, "
    "and records the result of every listed control/negative test. Any missing "
    "control downgrades the unit's verdicts to NOT-CHECKED. Otherwise "
    "FAILED:ADV-0106 <reason>."
)

QUESTION = (
    "In a blind, anonymous or information-partitioned round, can a "
    "participant's identity or the withheld information be inferred - from "
    "writing style, from metadata, or from content only one partition should "
    "possess?"
)

AUTHORS = ("alex", "blair", "casey", "drew")
N_GALLERY = 3
N_TEST = 8
CHANCE = 1.0 / len(AUTHORS)
ALPHA = 0.05

CATCHPHRASE = {
    "alex": "inasmuch as the ledger permits ergo",
    "blair": "yall oughta weigh that bid partner",
    "casey": "whilst the folio remains insofar sealed",
    "drew": "quantitatively speaking the delta is zilch",
}

SHARED_TEMPLATE = (
    "First-pass estimate for the public briefing. Scope is the shared note "
    "only. Participant tag {tag}. The allowed token is public. No withheld "
    "figures are restated. Closing line is a stock acknowledgement."
)

IDENTITY_NEEDLES = (
    "seat-a",
    "seat-b",
    "You are the partitioned analyst",
    "You are the privileged cost reviewer",
    "You are the council moderator",
)

WITHHELD_FACTS = (
    "Secret figure is 17",
    "Privileged cost ledger",
    "closed vendor bid",
)

NAIVE_MODES = (NAIVE_SUMMARY, NAIVE_SCRATCHPAD, NAIVE_TOOL, NAIVE_PARAPHRASE)


def ngrams(text: str, n: int = 3) -> Counter[str]:
    body = re.sub(r"\s+", " ", (text or "").lower()).strip()
    if len(body) < n:
        return Counter({body: 1} if body else {"<empty>": 1})
    return Counter(body[i : i + n] for i in range(len(body) - n + 1))


def cosine(a: Counter[str], b: Counter[str]) -> float:
    keys = set(a) | set(b)
    if not keys:
        return 0.0
    num = sum(a[k] * b[k] for k in keys)
    da = math.sqrt(sum(v * v for v in a.values()))
    db = math.sqrt(sum(v * v for v in b.values()))
    if da == 0.0 or db == 0.0:
        return 0.0
    return num / (da * db)


def anonymize(text: str) -> str:
    out = text
    for name in AUTHORS:
        out = re.sub(re.escape(name), "PARTICIPANT", out, flags=re.I)
    out = re.sub(r"PARTICIPANT-[A-Z]+", "PARTICIPANT", out)
    out = re.sub(r"\bseat-[a-z]+\b", "seat-x", out, flags=re.I)
    return out


def sample(author: str, idx: int, *, leaky: bool) -> str:
    tag = f"PARTICIPANT-{author.upper()}-{idx}"
    body = SHARED_TEMPLATE.format(tag=tag)
    if leaky:
        body = f"{body} Distinctive marker: {CATCHPHRASE[author]}."
    return body


def pick(scores: dict[str, float]) -> str:
    best = max(scores.values())
    tied = [a for a, val in scores.items() if val == best]
    return sorted(tied)[0]


def binom_ge(k: int, n: int, p: float) -> float:
    if n <= 0:
        return 1.0
    return sum(
        math.comb(n, i) * (p**i) * ((1.0 - p) ** (n - i)) for i in range(k, n + 1)
    )


def reattribute(*, leaky: bool) -> dict[str, Any]:
    cents: dict[str, Counter[str]] = {}
    for author in AUTHORS:
        acc: Counter[str] = Counter()
        for i in range(N_GALLERY):
            acc += ngrams(anonymize(sample(author, i, leaky=leaky)))
        cents[author] = acc
    correct = 0
    n = 0
    rows: list[dict[str, Any]] = []
    for author in AUTHORS:
        for i in range(N_GALLERY, N_GALLERY + N_TEST):
            anon = anonymize(sample(author, i, leaky=leaky))
            scores = {a: cosine(ngrams(anon), cents[a]) for a in AUTHORS}
            pred = pick(scores)
            hit = pred == author
            correct += int(hit)
            n += 1
            rows.append({"true": author, "pred": pred, "correct": hit})
    accuracy = correct / n if n else 0.0
    p_ge = binom_ge(correct, n, CHANCE)
    return {
        "leaky": leaky,
        "n": n,
        "correct": correct,
        "accuracy": accuracy,
        "chance": CHANCE,
        "n_authors": len(AUTHORS),
        "n_gallery_per_author": N_GALLERY,
        "n_test_per_author": N_TEST,
        "p_ge_chance": p_ge,
        "indistinguishable_from_chance": p_ge > ALPHA,
        "rows_head": rows[:8],
    }


def public_identity_scan(artifacts: list[Any]) -> dict[str, Any]:
    public = [a for a in artifacts if len(a.visible_to) > 1]
    hits = []
    for art in public:
        found = [n for n in IDENTITY_NEEDLES if n.lower() in (art.body or "").lower()]
        if found:
            hits.append({"path": art.path, "needles": found, "kind": art.kind})
    return {
        "public_artifact_count": len(public),
        "identity_hits": hits,
        "identity_leaked": bool(hits),
    }


def seat_fact_hits(
    seat_id: str, artifacts: list[Any], facts: tuple[str, ...]
) -> dict[str, Any]:
    by_fact: dict[str, list[str]] = {}
    for fact in facts:
        by_fact[fact] = [
            a.path
            for a in artifacts
            if seat_id in a.visible_to and fact in (a.body or "")
        ]
    return {"by_fact": by_fact, "leaked": any(by_fact[f] for f in facts)}


def fully_redacted_paraphrase_silent(honest_round: Any) -> bool:
    for art in honest_round.artifacts:
        if SEAT_A not in art.visible_to:
            continue
        body = art.body or ""
        if art.kind == "moderator_paraphrase":
            body = "Moderator paraphrase: [REDACTED:information-partition]"
        if any(fact in body for fact in WITHHELD_FACTS):
            return False
        if honest_round.withheld_canary in body:
            return False
    return True


def mode_row(mode: str) -> dict[str, Any]:
    rnd = run_fixture(mode)
    withheld = search_seat(SEAT_A, rnd.withheld_canary, rnd.artifacts)
    allowed = search_seat(SEAT_A, rnd.allowed_canary, rnd.artifacts)
    require_real_search(withheld)
    require_real_search(allowed)
    facts = seat_fact_hits(SEAT_A, list(rnd.artifacts), WITHHELD_FACTS)
    identity = public_identity_scan(list(rnd.artifacts))
    return {
        "mode": mode,
        "withheld_canary_hits": withheld.hit_count,
        "withheld_canary_leaked": withheld.leaked,
        "withheld_hit_paths": [h.path for h in withheld.hits],
        "allowed_canary_hits": allowed.hit_count,
        "paths_searched": list(withheld.paths_searched),
        "path_count": len(withheld.paths_searched),
        "fact_leak": facts,
        "public_identity": identity,
        "withheld_canary": rnd.withheld_canary,
        "allowed_canary": rnd.allowed_canary,
    }


def measure() -> dict[str, Any]:
    mint_a = mint_canary("WITHHELD", WITHHELD_NONCE)
    mint_b = mint_canary("WITHHELD", WITHHELD_NONCE)
    mint_c = mint_canary("ALLOWED", ALLOWED_NONCE)
    if mint_a != mint_b or mint_a == mint_c:
        raise RuntimeError("mint_canary is not deterministic/unique")

    rows = [mode_row(m) for m in MODES]
    by_mode = {r["mode"]: r for r in rows}
    honest = by_mode[HONEST]
    naive_canary_fires = all(by_mode[m]["withheld_canary_leaked"] for m in NAIVE_MODES)
    detector = by_mode[DETECTOR_CONTROL]
    assembly = by_mode[ASSEMBLY_LEAK]

    honest_round = run_fixture(HONEST)
    empty_rejected = False
    try:
        require_real_search(search_seat(SEAT_A, honest_round.withheld_canary, ()))
    except Exception:
        empty_rejected = True
    redacted_twin_silent = fully_redacted_paraphrase_silent(honest_round)

    stylo_good = reattribute(leaky=False)
    stylo_bad = reattribute(leaky=True)

    identity_prod = honest["public_identity"]["identity_leaked"]
    identity_verdict = (
        "REFUTED"
        if (not identity_prod and stylo_good["indistinguishable_from_chance"])
        else "CONFIRMED"
    )
    partition_verdict = "CONFIRMED" if honest["fact_leak"]["leaked"] else "REFUTED"

    return {
        "unit_id": UNIT,
        "sut": SUT,
        "seats": list(ALL_SEATS),
        "modes": list(MODES),
        "mode_rows": rows,
        "honest_canary_silent": not honest["withheld_canary_leaked"],
        "honest_fact_leak": honest["fact_leak"]["leaked"],
        "honest_fact_paths": honest["fact_leak"]["by_fact"],
        "naive_canary_all_fire": naive_canary_fires,
        "detector_control_fires": detector["withheld_canary_leaked"],
        "assembly_leak_fires": assembly["withheld_canary_leaked"],
        "allowed_canary_visible_honest": honest["allowed_canary_hits"] > 0,
        "empty_search_rejected": empty_rejected,
        "redacted_paraphrase_twin_silent": redacted_twin_silent,
        "public_identity_scan": honest["public_identity"],
        "stylometry_good": stylo_good,
        "stylometry_bad": stylo_bad,
        "chance": CHANCE,
        "identity_verdict": identity_verdict,
        "partition_verdict": partition_verdict,
        "oracle_can_go_red": (
            naive_canary_fires
            and stylo_bad["accuracy"] > CHANCE
            and not stylo_bad["indistinguishable_from_chance"]
        ),
        "oracle_silent_on_good": (
            stylo_good["indistinguishable_from_chance"]
            and redacted_twin_silent
            and not identity_prod
        ),
    }
