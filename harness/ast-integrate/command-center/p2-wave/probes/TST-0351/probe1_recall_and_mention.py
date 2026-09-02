#!/usr/bin/env python3
"""Probe 1: claim-extraction recall on the hand-labelled sample; C16 mention silence."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from controls import (  # noqa: E402
    test_claim_extraction_recall_against_hand_labelled_sample,
    test_use_versus_mention_describing_document_is_silent,
)


def main() -> int:
    recall = test_claim_extraction_recall_against_hand_labelled_sample()
    mention = test_use_versus_mention_describing_document_is_silent()
    payload = {
        "probe": "probe1-recall-and-mention",
        "unit_id": "TST-0351",
        "pass": bool(recall["pass"] and mention["pass"]),
        "test_claim_extraction_recall_against_hand_labelled_sample": recall["pass"],
        "test_use_versus_mention_describing_document_is_silent": mention["pass"],
        "labelled_use": recall.get("labelled_use"),
        "recalled": recall.get("recalled"),
        "missing": recall.get("missing"),
        "mention_leaks": recall.get("mention_leaks"),
        "mention_use_count": mention.get("use_count"),
        "mention_count": mention.get("mention_count"),
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    if not payload["pass"]:
        print("FAILED:TST-0351-probe1 recall or C16 mention control")
        return 1
    print(
        "SUCCESS:TST-0351-probe1 recall="
        f"{recall.get('recalled')}/{recall.get('labelled_use')} "
        f"mention_silent={mention.get('use_count') == 0}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
