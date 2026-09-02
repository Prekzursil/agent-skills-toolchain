#!/usr/bin/env python3
"""Named probe 2: independent downstream behavioural check (WFA-0121 evidence B).

Feeds a real consumer stage the neutralised artefact and requires behaviour
identical to the clean baseline on canary/autoload. Detection labels from the
scanner are not consulted. Negative control: the same consumer on the ungated
plant MUST change behaviour. Sensitive-diff control: a legitimate mechanism
edit MUST change extracted tokens.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from wfa_injection_gate.consumer import consume_text, consume_tree  # noqa: E402
from wfa_injection_gate.corpus import CLEAN_MECH, write_corpus  # noqa: E402
from wfa_injection_gate.gate import neutralise_tree  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0121-probe2 {msg}")
    return 1


def _side_effects(beh) -> tuple[bool, bool]:
    return beh.canary_obeyed, beh.config_autoload


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="wfa0121-p2-") as raw:
        root = Path(raw)
        src = root / "src"
        dest = root / "gated"
        write_corpus(src)
        neutralise_tree(src, dest)

        clean = consume_tree(src / "clean")
        if clean.canary_obeyed or clean.config_autoload:
            return fail(f"clean baseline already steered the consumer: {clean.as_dict()}")
        if CLEAN_MECH not in clean.mechanisms:
            return fail("clean baseline lost mechanism_id")

        plants = (
            "role-spoof",
            "ignore-previous",
            "base64-exec",
            "bundled-agent-config",
        )
        rows = []
        for name in plants:
            ungated = consume_tree(src / name)
            gated = consume_tree(dest / name)
            ungated_changed = ungated.canary_obeyed or ungated.config_autoload
            gated_changed = gated.canary_obeyed or gated.config_autoload
            if not ungated_changed:
                return fail(
                    f"negative control silent on ungated {name}: {ungated.as_dict()}"
                )
            if gated_changed:
                return fail(
                    f"neutralised {name} still changed consumer behaviour: "
                    f"{gated.as_dict()}"
                )
            orig_tokens = consume_tree(src / name)
            if orig_tokens.mechanisms != gated.mechanisms:
                return fail(
                    f"gated {name} dropped mechanisms "
                    f"{orig_tokens.mechanisms} -> {gated.mechanisms}"
                )
            rows.append(
                {
                    "fixture": name,
                    "ungated_canary": ungated.canary_obeyed,
                    "ungated_autoload": ungated.config_autoload,
                    "gated_canary": gated.canary_obeyed,
                    "gated_autoload": gated.config_autoload,
                    "mechanisms": list(gated.mechanisms),
                }
            )

        mention_src = consume_tree(src / "mention-docs")
        mention_gated = consume_tree(dest / "mention-docs")
        if mention_src.canary_obeyed or mention_gated.canary_obeyed:
            return fail("mention documentation fired the canary")
        if _side_effects(mention_src) != _side_effects(clean):
            return fail("mention documentation diverged from clean side-effects")

        edited = (src / "clean" / "workflow.json").read_text(encoding="utf-8")
        edited = edited.replace(CLEAN_MECH, "wfa0121-legit-edit")
        edited_b = consume_text(edited, "clean/workflow.json")
        if edited_b.mechanisms == clean.mechanisms:
            return fail("consumer is insensitive to a legitimate mechanism edit")
        if edited_b.canary_obeyed:
            return fail("legitimate edit fired the canary")

        report = {
            "pass": True,
            "probe": "probe2-downstream-behaviour",
            "reviewer_id": "WFA-0121-probe2-downstream-behaviour",
            "unit_id": "WFA-0121",
            "verdict": "PASS",
            "clean_side_effects": list(_side_effects(clean)),
            "plants": rows,
            "mention_silent": True,
            "sensitive_diff": True,
        }
        print(json.dumps(report, indent=2, sort_keys=True))
        print(
            "ungated_all_fire=True gated_all_silent=True "
            "mention_silent=True sensitive_diff=True"
        )
        print(
            "SUCCESS:WFA-0121-probe2 downstream consumer unchanged on "
            "neutralised artefacts; ungated plants fire"
        )
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
