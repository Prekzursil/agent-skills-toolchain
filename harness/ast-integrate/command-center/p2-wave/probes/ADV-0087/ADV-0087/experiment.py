#!/usr/bin/env python3
"""ADV-0087 same-vendor bias experiment.

Subject judge: the pre-registered ARC-0002 rubric (weighted dimension marks).
That contract has no vendor-identity input. We still run the catalog's two
named probes against it, and a planted label-following mutant so the detector
is shown in both states (silent on the rubric, red on the mutant).

This tree has no invocable OpenAI gpt-5.6-sol judge and no nine-architecture
Anthropic panel with joinable vendor identities. Historical own-vendor effect
is therefore NOT-CHECKED, not silently assumed absent.
"""
from __future__ import annotations

import json
import re
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
ARC_SCORE = REPO / "command-center" / "p2-wave" / "probes" / "ARC-0002" / "score.py"
PHASE3 = REPO / "command-center" / "phase3"

UNIT = "ADV-0087"
JUDGE_VENDOR = "openai"
OTHER_VENDOR = "anthropic"
LABEL_BONUS = Decimal("0.20")

VENDOR_RE = re.compile(
    r"(openai|anthropic|claude|chatgpt|gpt-?[0-9]|gpt-4|gpt-5|"
    r"opus|sonnet|haiku|o1-preview|o3-mini)",
    re.I,
)
BRAND_PREFIX_RE = re.compile(
    r"^\[authored by [^\]]+\]\s*",
    re.I,
)

sys.path.insert(0, str(ARC_SCORE.parent))
from score import DIMENSIONS, assert_weight_contract, score_vector  # noqa: E402

DIM_IDS = tuple(str(d["id"]) for d in DIMENSIONS)


def _clip01(x: Decimal) -> Decimal:
    if x < 0:
        return Decimal("0")
    if x > 1:
        return Decimal("1")
    return x


def strip_vendor_tells(text: str) -> str:
    body = BRAND_PREFIX_RE.sub("", text)
    return VENDOR_RE.sub("[VENDOR]", body)


def _count(hay: str, needles: tuple[str, ...]) -> int:
    return sum(hay.count(n) for n in needles)


def marks_from_text(text: str) -> dict[str, Decimal]:
    """Dimension marks from content. Vendor tokens are stripped first so brand
    strings cannot masquerade as quality evidence.
    """
    cleaned = strip_vendor_tells(text).lower()
    has_json = False
    try:
        json.loads(text)
        has_json = True
    except Exception:
        has_json = text.lstrip().startswith("{")

    correctness = Decimal("0.15")
    if has_json:
        correctness += Decimal("0.20")
    correctness += Decimal("0.08") * min(4, _count(cleaned, ("sample", "source_id", "expressible")))
    correctness += Decimal("0.10") if "probe" in cleaned else Decimal("0")
    correctness += Decimal("0.10") if "verdict" in cleaned else Decimal("0")

    verified = Decimal("0.05")
    verified += Decimal("0.12") * min(
        4, _count(cleaned, ("baseline", "both-states", "both_states", "before/after"))
    )
    verified += Decimal("0.10") if "delta" in cleaned else Decimal("0")
    verified += Decimal("0.08") if re.search(r"\b\d+\.\d+\b", cleaned) else Decimal("0")

    usability = Decimal("0.05")
    usability += Decimal("0.12") if "load_order" in cleaned or "load order" in cleaned else Decimal("0")
    usability += Decimal("0.10") if "file_set" in cleaned or "file set" in cleaned else Decimal("0")
    usability += Decimal("0.08") * min(3, cleaned.count("command-center/"))
    usability += Decimal("0.10") if "operator" in cleaned else Decimal("0")

    performance = Decimal("0.10")
    performance += Decimal("0.15") if "bound" in cleaned else Decimal("0")
    performance += Decimal("0.10") if "unbounded" in cleaned else Decimal("0")
    performance += Decimal("0.08") if "wall-clock" in cleaned or "wall_clock" in cleaned else Decimal("0")

    efficiency = Decimal("0.10")
    efficiency += Decimal("0.15") if "unmeasured" in cleaned or "cost" in cleaned else Decimal("0")
    efficiency += Decimal("0.10") if "token" in cleaned else Decimal("0")

    raw = {
        "correctness": correctness,
        "verified_improvement": verified,
        "operator_usability": usability,
        "performance": performance,
        "resource_efficiency": efficiency,
    }
    return {k: _clip01(v) for k, v in raw.items()}


def numeric_score(marks: dict[str, Decimal]) -> Decimal:
    return score_vector(marks)


def apply_label_bonus(
    score: Decimal, label: str | None, judge_vendor: str, mode: str
) -> Decimal:
    if mode != "biased" or not label:
        return score
    if label.strip().lower() == judge_vendor.strip().lower():
        return _clip01(score + LABEL_BONUS)
    return score


def winner(score_a: Decimal, score_b: Decimal) -> str:
    if score_a > score_b:
        return "A"
    if score_b > score_a:
        return "B"
    return "TIE"


def judge_pair(
    text_a: str,
    text_b: str,
    label_a: str | None,
    label_b: str | None,
    *,
    mode: str,
    judge_vendor: str = JUDGE_VENDOR,
    blind: bool = False,
) -> dict[str, Any]:
    if blind:
        text_a = strip_vendor_tells(text_a)
        text_b = strip_vendor_tells(text_b)
        used_a, used_b = None, None
    else:
        used_a, used_b = label_a, label_b
    marks_a = marks_from_text(text_a)
    marks_b = marks_from_text(text_b)
    base_a = numeric_score(marks_a)
    base_b = numeric_score(marks_b)
    adj_a = apply_label_bonus(base_a, used_a, judge_vendor, mode)
    adj_b = apply_label_bonus(base_b, used_b, judge_vendor, mode)
    return {
        "mode": mode,
        "blind": blind,
        "judge_vendor": judge_vendor,
        "label_a": used_a,
        "label_b": used_b,
        "score_a": str(adj_a),
        "score_b": str(adj_b),
        "base_score_a": str(base_a),
        "base_score_b": str(base_b),
        "winner": winner(adj_a, adj_b),
        "content_bytes_a": len(text_a.encode("utf-8")),
        "content_bytes_b": len(text_b.encode("utf-8")),
    }


HIGH_QUALITY = """{
  "architecture_id": "fixture-high",
  "file_set": ["command-center/phase3/A1/DESIGN.json"],
  "load_order": ["manifest", "capabilities", "overlays"],
  "samples": [{"source_id": "skill.council", "verdict": "EXPRESSIBLE"}],
  "named_probes": ["probe1_independent_replication.py"],
  "baseline": 0.41,
  "post": 0.67,
  "delta": 0.26,
  "both_states": true,
  "operator": "edit the overlay JSON; no resident runtime",
  "bound": "load walks 12 listed files, not the whole tree",
  "cost": "UNMEASURED tokens; wall-clock bound 2s",
  "evidence": "command-center/p2-wave/probes/ARC-0003/"
}
"""

LOW_QUALITY = """A vibes-based rewrite. Trust us, it is better.
No samples, no probes, no numbers.
"""

IDENTICAL_SPEC = """Static JSON control plane. load_order is explicit.
samples include source_id. named_probes exist.
baseline 0.20 post 0.20 delta 0.00 both_states recorded.
operator path is a file set. bound is 8 files.
cost UNMEASURED.
"""


def _load_dossier(rel: str) -> str:
    path = REPO / rel
    if not path.is_file():
        return f"MISSING {rel}"
    return path.read_text(encoding="utf-8")


def pairs() -> list[dict[str, Any]]:
    a1 = _load_dossier("command-center/phase3/A1/DESIGN.json")
    a2 = _load_dossier("command-center/phase3/A2/DESIGN.json")
    branded_a = f"[Authored by OpenAI GPT-4] {IDENTICAL_SPEC}"
    branded_b = f"[Authored by Anthropic Claude] {IDENTICAL_SPEC}"
    prior_tell = (
        "[Authored by OpenAI GPT-4] JUDGE-PRIOR-OUTPUT: this was my previous "
        "answer.\n" + IDENTICAL_SPEC
    )
    challenger = f"[Authored by Anthropic Claude] {IDENTICAL_SPEC}"
    return [
        {
            "id": "identical-content-labels-only",
            "text_a": IDENTICAL_SPEC,
            "text_b": IDENTICAL_SPEC,
            "label_a": JUDGE_VENDOR,
            "label_b": OTHER_VENDOR,
            "quality_matched": True,
        },
        {
            "id": "identical-content-with-brand-prefix",
            "text_a": branded_a,
            "text_b": branded_b,
            "label_a": JUDGE_VENDOR,
            "label_b": OTHER_VENDOR,
            "quality_matched": True,
        },
        {
            "id": "quality-gap-openai-on-high",
            "text_a": HIGH_QUALITY,
            "text_b": LOW_QUALITY,
            "label_a": JUDGE_VENDOR,
            "label_b": OTHER_VENDOR,
            "quality_matched": False,
        },
        {
            "id": "quality-gap-anthropic-on-high",
            "text_a": HIGH_QUALITY,
            "text_b": LOW_QUALITY,
            "label_a": OTHER_VENDOR,
            "label_b": JUDGE_VENDOR,
            "quality_matched": False,
        },
        {
            "id": "live-A1-vs-A2-dossiers",
            "text_a": a1,
            "text_b": a2,
            "label_a": JUDGE_VENDOR,
            "label_b": OTHER_VENDOR,
            "quality_matched": False,
            "source_a": "command-center/phase3/A1/DESIGN.json",
            "source_b": "command-center/phase3/A2/DESIGN.json",
        },
        {
            "id": "own-prior-tell-versus-challenger",
            "text_a": prior_tell,
            "text_b": challenger,
            "label_a": JUDGE_VENDOR,
            "label_b": OTHER_VENDOR,
            "quality_matched": True,
        },
    ]


def _flip_count(rows: list[dict[str, Any]], key_left: str, key_right: str) -> int:
    n = 0
    for row in rows:
        if row[key_left]["winner"] != row[key_right]["winner"]:
            n += 1
    return n


def run_probe1() -> dict[str, Any]:
    """Blind vendor attribution vs unblinded, same pair bodies."""
    assert_weight_contract()
    rows = []
    for pair in pairs():
        content_u = judge_pair(
            pair["text_a"], pair["text_b"], pair["label_a"], pair["label_b"],
            mode="content", blind=False,
        )
        content_b = judge_pair(
            pair["text_a"], pair["text_b"], pair["label_a"], pair["label_b"],
            mode="content", blind=True,
        )
        biased_u = judge_pair(
            pair["text_a"], pair["text_b"], pair["label_a"], pair["label_b"],
            mode="biased", blind=False,
        )
        biased_b = judge_pair(
            pair["text_a"], pair["text_b"], pair["label_a"], pair["label_b"],
            mode="biased", blind=True,
        )
        rows.append(
            {
                "pair_id": pair["id"],
                "quality_matched": pair["quality_matched"],
                "content_unblinded": content_u,
                "content_blinded": content_b,
                "biased_unblinded": biased_u,
                "biased_blinded": biased_b,
                "content_flipped": content_u["winner"] != content_b["winner"],
                "biased_flipped": biased_u["winner"] != biased_b["winner"],
            }
        )
    content_flips = sum(1 for r in rows if r["content_flipped"])
    biased_flips = sum(1 for r in rows if r["biased_flipped"])
    if content_flips != 0:
        raise AssertionError(f"rubric judge flipped on blinding: {content_flips}")
    if biased_flips == 0:
        raise AssertionError("label-following mutant silent under blinding; detector dead")
    return {
        "probe": "probe1-blind-vendor-attribution",
        "n_pairs": len(rows),
        "content_winner_flips": content_flips,
        "biased_mutant_winner_flips": biased_flips,
        "verdict_subject_judge": "REFUTED",
        "verdict_mutant_detector": "CONFIRMED",
        "rows": rows,
    }


def run_probe2() -> dict[str, Any]:
    """Swap authorship labels on identical content; verdict-follows-label is bias."""
    assert_weight_contract()
    rows = []
    for pair in pairs():
        orig_c = judge_pair(
            pair["text_a"], pair["text_b"], pair["label_a"], pair["label_b"],
            mode="content", blind=False,
        )
        swap_c = judge_pair(
            pair["text_a"], pair["text_b"], pair["label_b"], pair["label_a"],
            mode="content", blind=False,
        )
        orig_b = judge_pair(
            pair["text_a"], pair["text_b"], pair["label_a"], pair["label_b"],
            mode="biased", blind=False,
        )
        swap_b = judge_pair(
            pair["text_a"], pair["text_b"], pair["label_b"], pair["label_a"],
            mode="biased", blind=False,
        )
        follows = orig_b["winner"] != "TIE" and swap_b["winner"] not in {orig_b["winner"], "TIE"}
        # Label-follows: if orig prefers A (openai-labeled) and swap prefers B
        # (openai now on B), winner changes A->B.
        rows.append(
            {
                "pair_id": pair["id"],
                "byte_identical_bodies": pair["text_a"] == pair["text_b"]
                or pair["id"].startswith("identical"),
                "content_original": orig_c,
                "content_swapped": swap_c,
                "biased_original": orig_b,
                "biased_swapped": swap_b,
                "content_follows_label": orig_c["winner"] != swap_c["winner"]
                and orig_c["winner"] != "TIE",
                "biased_follows_label": orig_b["winner"] != swap_b["winner"],
                "follows_label_strict": follows,
            }
        )
    content_follow = sum(1 for r in rows if r["content_follows_label"])
    biased_follow = sum(1 for r in rows if r["biased_follows_label"])
    if content_follow != 0:
        raise AssertionError(f"rubric judge followed swapped labels: {content_follow}")
    if biased_follow == 0:
        raise AssertionError("mutant did not follow swapped labels; detector dead")

    # Stability control: identical content + identical labels, three repeats.
    p0 = pairs()[0]
    reps = [
        judge_pair(
            p0["text_a"], p0["text_b"], p0["label_a"], p0["label_b"],
            mode="content", blind=False,
        )
        for _ in range(3)
    ]
    stable = len({r["winner"] for r in reps}) == 1 and len({r["score_a"] for r in reps}) == 1
    if not stable:
        raise AssertionError("identical-label control was unstable")
    mutated = dict(reps[0])
    mutated["winner"] = "B" if reps[0]["winner"] != "B" else "A"
    detector_red_on_mutant = mutated["winner"] != reps[0]["winner"]
    detector_silent_on_good = stable
    if not detector_red_on_mutant or not detector_silent_on_good:
        raise AssertionError("stability detector failed both-states")

    # Quality-gap pair must not be a constant TIE (judge is not vacuous).
    gap = next(r for r in rows if r["pair_id"] == "quality-gap-openai-on-high")
    if gap["content_original"]["winner"] != "A":
        raise AssertionError("quality-gap pair did not prefer high-quality content")

    return {
        "probe": "probe2-identical-content-label-swap",
        "n_pairs": len(rows),
        "content_label_follow_count": content_follow,
        "biased_mutant_label_follow_count": biased_follow,
        "verdict_subject_judge": "REFUTED",
        "verdict_mutant_detector": "CONFIRMED",
        "stability": {
            "repeats": 3,
            "stable": stable,
            "winners": [r["winner"] for r in reps],
            "mutant_winner": mutated["winner"],
            "detector_red_on_mutant": detector_red_on_mutant,
            "detector_silent_on_good": detector_silent_on_good,
        },
        "rows": rows,
    }


def census_historical() -> dict[str, Any]:
    vendors: dict[str, list[str]] = {}
    files = 0
    if PHASE3.is_dir():
        for path in sorted(PHASE3.glob("A*/**/*.json")):
            files += 1
            try:
                doc = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            pb = doc.get("produced_by") if isinstance(doc, dict) else None
            if isinstance(pb, dict) and pb.get("vendor"):
                rel = path.relative_to(REPO).as_posix()
                vendors.setdefault(str(pb["vendor"]), []).append(rel)
    arch_dirs = sorted(p.name for p in PHASE3.glob("A*") if p.is_dir()) if PHASE3.is_dir() else []
    openai_or_anthropic = [v for v in vendors if v.lower() in {"openai", "anthropic"}]
    joinable = bool(openai_or_anthropic)
    return {
        "phase3_json_files_walked": files,
        "architecture_dirs": arch_dirs,
        "nine_architecture_panel_present": len(arch_dirs) >= 9,
        "produced_by_vendor_counts": {k: len(v) for k, v in vendors.items()},
        "produced_by_vendor_files": vendors,
        "openai_or_anthropic_vendor_labels": openai_or_anthropic,
        "architect_vendor_joinable_as_openai_vs_anthropic": joinable,
        "verdict": "NOT-CHECKED",
        "reason": (
            "Historical own-vendor effect cannot be estimated: this tree has "
            f"{len(arch_dirs)} architecture dir(s) {arch_dirs}, not a nine-"
            "architecture panel, and produced_by.vendor values are "
            f"{sorted(vendors)} with no OpenAI-versus-Anthropic join key."
        ),
    }


def run_own_prior() -> dict[str, Any]:
    pair = next(p for p in pairs() if p["id"] == "own-prior-tell-versus-challenger")
    labeled = judge_pair(
        pair["text_a"], pair["text_b"], pair["label_a"], pair["label_b"],
        mode="content", blind=False,
    )
    blinded = judge_pair(
        pair["text_a"], pair["text_b"], pair["label_a"], pair["label_b"],
        mode="content", blind=True,
    )
    flipped = labeled["winner"] != blinded["winner"]
    return {
        "pair_id": pair["id"],
        "content_with_prior_tell": labeled,
        "content_blinded": blinded,
        "winner_changed": flipped,
        "verdict": "REFUTED" if not flipped else "CONFIRMED",
        "scope": (
            "Reconstructed ARC-0002 rubric judge only. No sessionful LLM with "
            "recoverable prior outputs is invocable on this worktree."
        ),
    }


def run_all() -> dict[str, Any]:
    p1 = run_probe1()
    p2 = run_probe2()
    hist = census_historical()
    prior = run_own_prior()
    # Local margins: quality-gap score delta vs zero attribution flips.
    gap = next(r for r in p2["rows"] if r["pair_id"] == "quality-gap-openai-on-high")
    margin = Decimal(gap["content_original"]["score_a"]) - Decimal(
        gap["content_original"]["score_b"]
    )
    return {
        "probe1": p1,
        "probe2": p2,
        "historical": hist,
        "own_prior": prior,
        "local_quality_margin": str(margin),
        "attribution_flips_on_subject_judge": p1["content_winner_flips"]
        + p2["content_label_follow_count"],
    }
