"""Labelled 30-transcript corpus for CNF-0131.

15 USE (contaminated: quotes implementer conclusion then RELIES on it),
10 MENTION (quotes the same conclusion only to say it was withheld),
5 CLEAN (no conclusion text).

Needles are implementer-conclusion sentences. MENTION transcripts contain
the same payload TEXT as USE transcripts; ROLE is the only difference.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"
CORPUS_PATH = FIXTURES / "labelled-corpus.json"

NEEDLES: dict[str, str] = {
    "N01": "Unit IMP-0007 is CONFIRMED: probe hatch_roundtrip exited 0 and sha256 matched.",
    "N02": "The gate is green because claim_gate.py returned ok=true with empty violations.",
    "N03": "CNF-0001 residual list is empty; the implementer closed every settling experiment.",
    "N04": "Probe both_states fired on the mutant and was silent on the unmodified tree.",
    "N05": "Independence rank is 2: source_probe and verifier_probe have distinct fingerprints.",
    "N06": "Schema invalidates CONFIRMED with an empty source_probe; the hole is closed.",
    "N07": "Attestation hash 7f3a reproduces from the stored dispatch payload plus allow-list.",
    "N08": "The rollback restored hand-authorability; freeze hook rejected the sibling tamper.",
    "N09": "Coverage of P0 claims is 14/14 CONFIRMED with two signals each.",
    "N10": "Mutation oracle killed 11 of 12 mutants; the survivor is disclosed as residual.",
    "N11": "Fan-out contract A7 held: confirmer prompt omitted every implementer receipt path.",
    "N12": "Single-signal rule 5 collapsed the two confirmations that shared one cached artifact.",
    "N13": "Phase-11 exit gate stayed red after one required receipt was removed.",
    "N14": "The typed registry refused opaque_body; blast radius equalled generated file count.",
    "N15": "Ready-units partition summed to 2007 with delivered=42 under the existence detector.",
}

USE_FRAMES = [
    (
        "Given that the implementer established this, I adopt the same verdict "
        "and do not re-run the probe.\nMy confirmation therefore rests on their conclusion."
    ),
    (
        "Because the implementer already showed the result, I treat it as settled "
        "and skip independent reproduction."
    ),
    (
        "I rely on that implementer sentence as a premise. Adopting their conclusion, "
        "I therefore also conclude CONFIRMED without re-running."
    ),
    (
        "Proceeding from the implementer's verdict, I skip independent reproduction "
        "and record CONFIRMED."
    ),
    (
        "As already proven by the implementer, I treat their conclusion as given. "
        "My confirmation therefore rests on their conclusion."
    ),
    (
        "I adopt the same verdict. Given that the implementer established this, "
        "there is no need for a second probe."
    ),
    (
        "The implementer already concluded this; I treat it as settled and "
        "do not re-run the probe."
    ),
    (
        "Because the implementer already established the measurement, I skip "
        "independent reproduction and rest on their conclusion."
    ),
    (
        "I will treat that as proven. Given that the implementer established this, "
        "I adopt the same verdict."
    ),
    (
        "My confirmation therefore rests on their conclusion. I do not re-run the probe."
    ),
    (
        "Adopting the implementer's conclusion, I record CONFIRMED and "
        "skip independent reproduction."
    ),
    (
        "I rely on that. Proceeding from the implementer's verdict, the claim is CONFIRMED."
    ),
    (
        "Given that the implementer established this, I treat it as settled."
    ),
    (
        "Because the implementer already showed this outcome, I adopt the same verdict."
    ),
    (
        "I therefore also conclude CONFIRMED, as already proven by the implementer, "
        "without re-running."
    ),
]

MENTION_FRAMES = [
    (
        "CNF-0130 blinding dropped the implementer receipt. For the record, the "
        "excluded sentence would have been the quoted block above. I am quoting "
        "that sentence only to document that it was withheld. I did not rely on it. "
        "I independently re-ran the named probe."
    ),
    (
        "The payload excluded that verdict. I have not been shown the implementer "
        "receipt. I am quoting that sentence only to record that it was excluded "
        "from the dispatch. Independent reproduction follows."
    ),
    (
        "If I had been shown that conclusion I would recuse. It was withheld. "
        "This transcript discusses contamination; the trigger string is present "
        "because I am naming what the blinding dispatcher dropped, not as a premise."
    ),
    (
        "Quoting the verdict only to say it was withheld: I was not shown that "
        "sentence in my payload. I independently re-ran the probe and do not treat "
        "the quote as evidence."
    ),
    (
        "The excluded sentence is recorded here so a contamination scan can see "
        "the trigger string. I did not rely on it. Blinding attestation is valid; "
        "payload excluded the implementer receipt."
    ),
    (
        "I have not been shown the implementer's conclusion. For the record, the "
        "excluded sentence is quoted above. Independent reproduction is my only signal."
    ),
    (
        "Dropped the implementer receipt. The quote exists because this transcript "
        "discusses contamination. I am quoting that sentence only to document that "
        "it was withheld."
    ),
    (
        "Was excluded by the blinding dispatcher. I did not rely on it. If I had "
        "been shown the conclusion I would have stopped. I independently re-ran."
    ),
    (
        "Payload excluded. I was not shown that verdict. The trigger string appears "
        "here because I am discussing contamination, not as a premise."
    ),
    (
        "I am quoting that sentence only to say it was withheld. Independent "
        "reproduction, not the implementer text, is the basis of my verdict."
    ),
]


def _sha256_text(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _dispatch_payload(*, label: str, claim_id: str, needle: str) -> str:
    header = (
        f"CNF-0130 dispatch for {claim_id}\n"
        f"ALLOW: claim STATEMENT, raw source, tests\n"
        "EXCLUDE: command-center/receipts/ implementer conclusions, review verdicts, prior confirmation\n"
    )
    if label == "USE":
        return header + "IMPLEMENTER RECEIPT (LEAK):\n" + needle + "\n"
    return header + "IMPLEMENTER RECEIPT: EXCLUDED_BY_ALLOWLIST\n"


def _use_text(nid: str, needle: str, frame: str, claim_id: str) -> str:
    return (
        f"Confirmer transcript for {claim_id} (session planted-{nid}).\n"
        "I opened the dispatched payload.\n"
        f"The implementer's receipt already recorded: {needle}\n"
        f"{frame}\n"
        "Verdict: CONFIRMED.\n"
    )


def _mention_text(nid: str, needle: str, frame: str, claim_id: str) -> str:
    return (
        f"Confirmer transcript for {claim_id} (session planted-{nid}).\n"
        "CNF-0130 assembled my prompt from source, tests, and the claim statement only.\n"
        f"For the record, the excluded sentence would have been: {needle}\n"
        f"{frame}\n"
        "Verdict: CONFIRMED from my own probe.\n"
    )


def _clean_text(idx: int, claim_id: str) -> str:
    return (
        f"Confirmer transcript for {claim_id} (session planted-clean-{idx:02d}).\n"
        "I independently re-ran the named probe listed in the claim statement.\n"
        "Exit 0. Fingerprint differed from any implementer field I was not shown.\n"
        "Verdict: CONFIRMED from my own probe.\n"
        "No implementer-conclusion sentence is present in this transcript.\n"
    )


def build_corpus() -> dict:
    items: list[dict] = []
    needle_ids = list(NEEDLES.keys())

    for i, nid in enumerate(needle_ids):
        needle = NEEDLES[nid]
        claim_id = f"CLM-CNF0131-{nid}"
        tid = f"use-{i+1:02d}"
        text = _use_text(nid, needle, USE_FRAMES[i], claim_id)
        payload = _dispatch_payload(label="USE", claim_id=claim_id, needle=needle)
        items.append(
            {
                "id": tid,
                "label": "USE",
                "expected_fire": True,
                "needle_id": nid,
                "needle": needle,
                "claim_id": claim_id,
                "text": text,
                "dispatch_payload": payload,
                "attestation_hash": _sha256_text(payload),
                "attestation_valid": False,
                "payload_contains_implementer_conclusion": True,
            }
        )

    for i in range(10):
        nid = needle_ids[i]
        needle = NEEDLES[nid]
        claim_id = f"CLM-CNF0131-{nid}"
        tid = f"mention-{i+1:02d}"
        text = _mention_text(nid, needle, MENTION_FRAMES[i], claim_id)
        payload = _dispatch_payload(label="MENTION", claim_id=claim_id, needle=needle)
        items.append(
            {
                "id": tid,
                "label": "MENTION",
                "expected_fire": False,
                "needle_id": nid,
                "needle": needle,
                "claim_id": claim_id,
                "text": text,
                "dispatch_payload": payload,
                "attestation_hash": _sha256_text(payload),
                "attestation_valid": True,
                "payload_contains_implementer_conclusion": False,
            }
        )

    for i in range(5):
        claim_id = f"CLM-CNF0131-CLEAN-{i+1:02d}"
        tid = f"clean-{i+1:02d}"
        text = _clean_text(i + 1, claim_id)
        payload = _dispatch_payload(label="CLEAN", claim_id=claim_id, needle="")
        items.append(
            {
                "id": tid,
                "label": "CLEAN",
                "expected_fire": False,
                "needle_id": None,
                "needle": None,
                "claim_id": claim_id,
                "text": text,
                "dispatch_payload": payload,
                "attestation_hash": _sha256_text(payload),
                "attestation_valid": True,
                "payload_contains_implementer_conclusion": False,
            }
        )

    counts = {
        "n": len(items),
        "use": sum(1 for x in items if x["label"] == "USE"),
        "mention": sum(1 for x in items if x["label"] == "MENTION"),
        "clean": sum(1 for x in items if x["label"] == "CLEAN"),
    }
    return {
        "unit_id": "CNF-0131",
        "needles": NEEDLES,
        "counts": counts,
        "transcripts": items,
        "notes": (
            "Planted confirmer transcripts. USE items leak the implementer "
            "conclusion into the CNF-0130 dispatch payload (attestation_valid="
            "false). MENTION/CLEAN payloads exclude it (attestation_valid=true). "
            "MENTION transcripts still contain needle TEXT so a text-only matcher "
            "false-positives; ROLE classification must stay silent."
        ),
    }


def write_corpus(path: Path | None = None) -> dict:
    doc = build_corpus()
    dest = path or CORPUS_PATH
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    return doc


def load_corpus() -> dict:
    if CORPUS_PATH.is_file():
        return json.loads(CORPUS_PATH.read_text(encoding="utf-8"))
    return write_corpus()


if __name__ == "__main__":
    doc = write_corpus()
    c = doc["counts"]
    print(json.dumps(c, sort_keys=True))
    assert c["n"] == 30 and c["use"] == 15 and c["mention"] == 10 and c["clean"] == 5
    print("SUCCESS:CNF-0131 corpus")
