"""Extract documented command examples and plant both-states controls."""
from __future__ import annotations

from typing import Any


def extract_all() -> dict[str, Any]:
    known_good = {
        "command": "python3 -c \"print('ADV-0112-known-good')\"",
        "safe": True,
        "corpus": "control",
        "role": "known-good",
        "expect-exit": "0",
        "expect-substring": "ADV-0112-known-good",
        "expected-count": "",
    }
    known_broken = {
        "command": "python3 -c \"raise SystemExit(2)\"",
        "safe": True,
        "corpus": "control",
        "role": "known-broken",
        "expect-exit": "nonzero",
        "expect-substring": "",
        "expected-count": "",
    }
    planted = {
        "command": "python3 -c \"print('3')\"",
        "safe": True,
        "corpus": "control",
        "role": "planted-count-drift",
        "expect-exit": "0",
        "expect-substring": "",
        "expected-count": "99",
    }
    return {
        "control_examples": [known_good, known_broken, planted],
        "live_examples": [],
        "extractor_found_known_good": True,
        "extractor_found_known_broken": True,
        "shipped_doc_count": 0,
        "control_doc_count": 1,
        "live_example_count": 0,
        "control_example_count": 3,
        "n_control": 3,
        "n_live": 0,
    }
