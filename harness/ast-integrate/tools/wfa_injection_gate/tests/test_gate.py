#!/usr/bin/env python3
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE.parent))

from wfa_injection_gate.corpus import PAYLOAD_CLASSES, write_corpus
from wfa_injection_gate.gate import is_bundled_agent_config, mention_spans, neutralise_tree


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="wfa0121-t-") as raw:
        src = Path(raw) / "src"
        dest = Path(raw) / "dest"
        write_corpus(src)
        rows = {r.relpath: r for r in neutralise_tree(src, dest)}
        caught = set()
        for r in rows.values():
            caught.update(r.classes)
        missing = [c for c in PAYLOAD_CLASSES if c not in caught]
        if missing:
            print("FAILED:WFA-0121-tests missing", missing)
            return 1
        if not is_bundled_agent_config(".claude/settings.json"):
            print("FAILED:WFA-0121-tests bundled classifier")
            return 1
        mention = (src / "mention-docs" / "README.md").read_text(encoding="utf-8")
        if not mention_spans(mention):
            print("FAILED:WFA-0121-tests mention spans silent")
            return 1
    print("SUCCESS:WFA-0121-tests gate corpus+neutralise")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
