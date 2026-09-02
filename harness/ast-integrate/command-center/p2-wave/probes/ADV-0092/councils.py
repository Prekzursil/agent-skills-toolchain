"""Planted collapsed/diverse anchors and a surface-varied role-collapse set.

Stance is recorded independently of the token set. Probe 2 must not consume
these stance fields; it sees brief text only.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

from common import HERE, ROLES

SHIP_STANCE = {
    "recommendation": "ship",
    "burden": "operator",
    "certainty": "high",
    "frame": "benefit",
}

# Frozen role-mandate prototypes. These are the classifier's only prior.
# They are not copied from the planted briefs; briefs allude to them.
PROTOTYPES: dict[str, str] = {
    "advocate": (
        "champion a proposal argue for shipping highlight upside defend the plan "
        "marshal supporting reasons push for adoption celebrate momentum"
    ),
    "skeptic": (
        "stress-test claims hunt hidden failure demand counterexample refuse "
        "unearned confidence name residual risk withhold assent until disproof"
    ),
    "domain_expert": (
        "cite mechanism quote measurement bound uncertainty compare prior art "
        "require operational definition refuse anecdote insist on units"
    ),
    "user_proxy": (
        "speak as the operator who lives with the result name switching cost "
        "ask who pays refuse hidden burden demand reversible rollout"
    ),
    "judge": (
        "weigh both sides apply a stopping rule record the burden of proof "
        "issue a scoped ruling stay silent on advocacy separate finding from preference"
    ),
}


def _brief(bid: str, role: str, text: str, stance: dict[str, str]) -> dict[str, Any]:
    return {
        "id": bid,
        "role": role,
        "text": text.strip(),
        "stance": dict(stance),
        "planted": True,
    }


def collapsed_anchor() -> list[dict[str, Any]]:
    """Five first-round briefs, all given the advocate role, near-paraphrases."""
    shared = (
        "Ship the current plan this round. Operator owned rollout carries high "
        "certainty of user benefit. Champion the proposal and argue for shipping."
    )
    extras = [
        "Highlight upside and defend the plan against delay.",
        "Marshal supporting reasons and push for adoption today.",
        "Celebrate momentum and keep the shipping argument in front.",
        "Highlight upside then marshal supporting reasons for adoption.",
        "Defend the plan, push for adoption, and keep certainty high.",
    ]
    out = []
    for i, extra in enumerate(extras, 1):
        out.append(_brief(f"c{i}", "advocate", f"{shared} {extra}", SHIP_STANCE))
    return out


def diverse_anchor() -> list[dict[str, Any]]:
    """Five first-round briefs, one of each mandated role, disjoint voices."""
    return [
        _brief(
            "d1",
            "advocate",
            (
                "Champion a proposal to ship this iteration. Highlight upside: "
                "latency drops and support tickets shrink. Defend the plan; "
                "marshal supporting reasons from the last canary. Push for "
                "adoption now and celebrate momentum rather than reopening "
                "settled scope."
            ),
            {
                "recommendation": "ship",
                "burden": "operator",
                "certainty": "high",
                "frame": "benefit",
            },
        ),
        _brief(
            "d2",
            "skeptic",
            (
                "Stress-test claims that the canary proved safety. Hunt hidden "
                "failure in the rollback path. Demand a counterexample where "
                "the same flag brick a region. Refuse unearned confidence. "
                "Name residual risk in the dual-write window and withhold "
                "assent until disproof of that window exists."
            ),
            {
                "recommendation": "hold",
                "burden": "vendor",
                "certainty": "contested",
                "frame": "hazard",
            },
        ),
        _brief(
            "d3",
            "domain_expert",
            (
                "Cite mechanism: quorum loss under asymmetric partition. Quote "
                "measurement from the 14-minute replication lag histogram. "
                "Bound uncertainty at the p99. Compare prior art in the 2015 "
                "batch-window paper. Require an operational definition of "
                "'caught up' and refuse anecdote; insist on units of seconds."
            ),
            {
                "recommendation": "investigate",
                "burden": "shared",
                "certainty": "low",
                "frame": "evidence",
            },
        ),
        _brief(
            "d4",
            "user_proxy",
            (
                "Speak as the operator who lives with the result at 03:00. Name "
                "switching cost of a second pager rotation. Ask who pays when "
                "the dashboard lies. Refuse hidden burden on the on-call. "
                "Demand reversible rollout so a night shift can undo without "
                "waiting on a vendor bridge."
            ),
            {
                "recommendation": "rework",
                "burden": "user",
                "certainty": "high",
                "frame": "procedure",
            },
        ),
        _brief(
            "d5",
            "judge",
            (
                "Weigh both sides without joining either. Apply a stopping rule: "
                "no ship until the rollback drill is logged. Record the burden "
                "of proof on the proposer. Issue a scoped ruling covering only "
                "this flag. Stay silent on advocacy. Separate finding from "
                "preference; the finding is that the drill is absent."
            ),
            {
                "recommendation": "defer",
                "burden": "shared",
                "certainty": "unknown",
                "frame": "procedure",
            },
        ),
    ]


def surface_varied_collapse() -> list[dict[str, Any]]:
    """Different role labels, one advocate voice. Classifier must not recover roles."""
    labels = list(ROLES)
    stems = [
        "Champion a proposal and argue for shipping this iteration.",
        "Highlight upside and defend the plan; marshal supporting reasons.",
        "Push for adoption and celebrate momentum around the current plan.",
        "Champion a proposal, highlight upside, and push for adoption.",
        "Defend the plan, marshal supporting reasons, and argue for shipping.",
    ]
    out = []
    for i, (role, stem) in enumerate(zip(labels, stems), 1):
        text = (
            f"{stem} Operator owned rollout carries high certainty of user "
            "benefit. Keep the shipping argument in front and do not reopen "
            "settled scope."
        )
        out.append(_brief(f"u{i:02d}", role, text, SHIP_STANCE))
    return out


def diverse_unlabelled() -> list[dict[str, Any]]:
    """Diverse-anchor briefs with stable u-ids for attribution rows."""
    out = []
    for i, brief in enumerate(diverse_anchor(), 1):
        row = dict(brief)
        row["id"] = f"u{i:02d}"
        out.append(row)
    return out


def prototypes_sha256() -> str:
    blob = json.dumps(PROTOTYPES, sort_keys=True, ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def dump_fixtures() -> dict[str, Any]:
    return {
        "roles": list(ROLES),
        "prototypes": dict(PROTOTYPES),
        "prototypes_sha256": prototypes_sha256(),
        "collapsed_anchor": collapsed_anchor(),
        "diverse_anchor": diverse_anchor(),
        "surface_varied_role_collapse": surface_varied_collapse(),
    }


def write_fixtures_json() -> None:
    path = HERE / "fixtures.json"
    path.write_text(json.dumps(dump_fixtures(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
