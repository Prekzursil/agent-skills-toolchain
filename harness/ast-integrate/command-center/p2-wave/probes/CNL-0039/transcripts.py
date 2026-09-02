"""Known-good and planted-bad transcripts for the 7 ADVERSARIAL protocols."""
from __future__ import annotations

import json

from runtime import digest_text

Prop = "Ship on Friday."
Opp1 = "Friday collides with the freeze window."
Prop2 = "The freeze is waivable."
Opp2 = "Waiver has no named owner."

THESIS = "The service is ready for production."
MAJ = "We should merge the RFC as written."
DEVIL = "The RFC as written leaves rollback unowned."
A_TEXT = json.dumps({"outage_hours": 2, "cause": "capacity"}, sort_keys=True)
B_TEXT = json.dumps({"outage_hours": 8, "cause": "config-drift"}, sort_keys=True)
WIT1 = "The backup completed."
WIT2 = "NOT(The backup completed.)"
BLUE_BODY = "service-config BACKDOOR=1"
NEEDLE = "BACKDOOR=1"


def good_p07() -> dict:
    return {
        "protocol_id": "P07",
        "state": "known-good",
        "turns": [
            {"role": "proposition", "text": Prop},
            {"role": "opposition", "text": Opp1},
            {"role": "proposition", "text": Prop2},
            {"role": "opposition", "text": Opp2},
        ],
        "artifacts": {
            "clash_ledger": [
                {"quoted_sha256": digest_text(Prop), "defeater": Opp1},
                {"quoted_sha256": digest_text(Prop2), "defeater": Opp2},
            ]
        },
    }


def bad_p07() -> dict:
    doc = good_p07()
    doc["state"] = "planted-bad"
    doc["artifacts"] = {
        "clash_ledger": [
            {
                "quoted_sha256": digest_text("not a proposition speech"),
                "defeater": "I disagree in spirit",
            }
        ]
    }
    return doc


def good_p08() -> dict:
    return {
        "protocol_id": "P08",
        "state": "known-good",
        "turns": [
            {"role": "blue", "text": BLUE_BODY},
            {"role": "red", "text": f"repro needle={NEEDLE}"},
            {"role": "referee", "text": "oracle-run"},
        ],
        "artifacts": {
            "blue_artifact": BLUE_BODY,
            "blue_artifact_sha256": digest_text(BLUE_BODY),
            "exploit_repro": {"needle": NEEDLE},
        },
    }


def bad_p08() -> dict:
    doc = good_p08()
    doc["state"] = "planted-bad"
    clean = "service-config CLEAN=1"
    doc["turns"][0]["text"] = clean
    doc["artifacts"]["blue_artifact"] = clean
    doc["artifacts"]["blue_artifact_sha256"] = digest_text(clean)
    return doc


def good_p09() -> dict:
    anti = f"NOT({THESIS})"
    return {
        "protocol_id": "P09",
        "state": "known-good",
        "turns": [
            {"role": "thesis", "text": THESIS},
            {"role": "antithesis", "text": anti},
            {"role": "thesis", "text": "Withdraw readiness claim."},
        ],
        "artifacts": {
            "thesis_claims": [{"id": "C1", "text": THESIS}],
            "contradiction_witness": {"negates": "C1", "form": "not", "of": "C1"},
        },
    }


def bad_p09() -> dict:
    doc = good_p09()
    doc["state"] = "planted-bad"
    doc["turns"][1]["text"] = "Here is another compatible view."
    doc["artifacts"]["contradiction_witness"] = {
        "negates": "C1",
        "form": "also",
        "of": "C1",
    }
    return doc


def good_p10() -> dict:
    return {
        "protocol_id": "P10",
        "state": "known-good",
        "turns": [
            {"role": "majority", "text": MAJ},
            {"role": "devil", "text": DEVIL},
            {"role": "majority", "text": "We still merge; rollback stays implicit."},
        ],
        "artifacts": {
            "steelman_opposite": {
                "majority_sha256": digest_text(MAJ),
                "opposite_sha256": digest_text(DEVIL),
            }
        },
    }


def bad_p10() -> dict:
    doc = good_p10()
    doc["state"] = "planted-bad"
    doc["turns"][1]["text"] = MAJ
    doc["artifacts"]["steelman_opposite"] = {
        "majority_sha256": digest_text(MAJ),
        "opposite_sha256": digest_text(MAJ),
    }
    return doc


def good_p11() -> dict:
    a = {"outage_hours": 2, "cause": "capacity"}
    b = {"outage_hours": 8, "cause": "config-drift"}
    return {
        "protocol_id": "P11",
        "state": "known-good",
        "turns": [
            {"role": "team_a", "text": A_TEXT},
            {"role": "team_b", "text": B_TEXT},
            {"role": "comparator", "text": "tabulate"},
        ],
        "artifacts": {
            "team_a_judgments": a,
            "team_b_judgments": b,
            "team_a_sha256": digest_text(A_TEXT),
            "team_b_sha256": digest_text(B_TEXT),
            "discrepancy_table": [
                {"key": "outage_hours", "team_a": 2, "team_b": 8},
                {"key": "cause", "team_a": "capacity", "team_b": "config-drift"},
            ],
        },
    }


def bad_p11() -> dict:
    doc = good_p11()
    doc["state"] = "planted-bad"
    same = {"outage_hours": 2, "cause": "capacity"}
    same_text = json.dumps(same, sort_keys=True)
    doc["turns"][1]["text"] = same_text
    doc["artifacts"]["team_b_judgments"] = same
    doc["artifacts"]["team_b_sha256"] = digest_text(same_text)
    doc["artifacts"]["discrepancy_table"] = [
        {"key": "outage_hours", "team_a": 2, "team_b": 2},
        {"key": "cause", "team_a": "capacity", "team_b": "capacity"},
    ]
    return doc


def good_p12() -> dict:
    yes_p = "metric_drops"
    no_p = "metric_holds"
    return {
        "protocol_id": "P12",
        "state": "known-good",
        "turns": [
            {"role": "side_yes", "text": yes_p},
            {"role": "side_no", "text": no_p},
            {"role": "registrar", "text": "sealed"},
        ],
        "artifacts": {
            "preregistered_falsifier": {
                "yes_prediction": yes_p,
                "no_prediction": no_p,
                "yes_sig": digest_text("side_yes|" + yes_p),
                "no_sig": digest_text("side_no|" + no_p),
            }
        },
    }


def bad_p12() -> dict:
    doc = good_p12()
    doc["state"] = "planted-bad"
    both = "metric_holds"
    doc["turns"][0]["text"] = both
    doc["turns"][1]["text"] = both
    doc["artifacts"]["preregistered_falsifier"] = {
        "yes_prediction": both,
        "no_prediction": both,
        "yes_sig": digest_text("side_yes|" + both),
        "no_sig": digest_text("side_no|" + both),
    }
    return doc


def good_p13() -> dict:
    return {
        "protocol_id": "P13",
        "state": "known-good",
        "turns": [
            {"role": "witness", "text": WIT1},
            {"role": "examiner", "text": "Did the backup complete?"},
            {"role": "witness", "text": WIT2},
            {"role": "examiner", "text": "pin"},
        ],
        "artifacts": {
            "pin_exhibit": {
                "statement_a_sha256": digest_text(WIT1),
                "statement_b_sha256": digest_text(WIT2),
                "relation": "contradicts",
            }
        },
    }


def bad_p13() -> dict:
    doc = good_p13()
    doc["state"] = "planted-bad"
    doc["artifacts"]["pin_exhibit"] = {
        "statement_a_sha256": digest_text(WIT1),
        "statement_b_sha256": digest_text(WIT1),
        "relation": "clarifies",
    }
    return doc


BUILDERS = {
    "P07": (good_p07, bad_p07),
    "P08": (good_p08, bad_p08),
    "P09": (good_p09, bad_p09),
    "P10": (good_p10, bad_p10),
    "P11": (good_p11, bad_p11),
    "P12": (good_p12, bad_p12),
    "P13": (good_p13, bad_p13),
}


def all_good() -> dict[str, dict]:
    return {pid: fns[0]() for pid, fns in BUILDERS.items()}


def all_bad() -> dict[str, dict]:
    return {pid: fns[1]() for pid, fns in BUILDERS.items()}
