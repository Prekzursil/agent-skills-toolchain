#!/usr/bin/env python3
"""probe2 for TST-0058: lenient-versus-strict agreement matrix, live.

Corpus: >=50 real JSON documents from the tree + 10 adversarial json5-ism
fixtures. Asserts, over the LIVE tools/json_ingest.py:
  1. no document is accepted by one production path and rejected by the other;
  2. every adversarial fixture is rejected by BOTH (and tolerated by the
     jsonc detector-control, proving each fixture is a real json5-ism).
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
UID = "TST-0058"
HERE = Path(__file__).resolve().parent


def load_ji():
    spec = importlib.util.spec_from_file_location("t58_ji", REPO / "tools" / "json_ingest.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["t58_ji"] = mod
    spec.loader.exec_module(mod)
    return mod


ADVERSARIAL = [
    ("01-trailing-comma-object.jsonc", '{"a": 1,}'),
    ("02-trailing-comma-array.jsonc", '{"a": [1, 2,]}'),
    ("03-line-comment.jsonc", '// leading note\n{"a": 1}'),
    ("04-block-comment.jsonc", '{"a": /* inline */ 1}'),
    ("05-single-quoted-string.jsonc", '{"a": \'single\'}'),
    ("06-single-quoted-key.jsonc", "{a: 1}"),
    ("07-comment-and-trailing-comma.jsonc", '// note\n{"a": 1, /* tail */}'),
    ("08-block-comment-in-array.jsonc", '{"a": [1 /* x */, 2]}'),
    ("09-nested-trailing-comma.jsonc", '{"a": {"b": [1,],},}'),
    ("10-mixed-json5.jsonc", "// header\n{'a': [1, 2,], /* e */}"),
]


def main() -> int:
    ji = load_ji()
    checks: dict[str, object] = {}

    # write the adversarial fixtures
    adv_dir = HERE / "fixtures" / "adversarial"
    adv_dir.mkdir(parents=True, exist_ok=True)
    for name, body in ADVERSARIAL:
        (adv_dir / name).write_text(body + chr(10), encoding="utf-8", newline=chr(10))
    written = sorted(p.name for p in adv_dir.glob("*.jsonc"))
    checks["ten_adversarial_fixtures_written"] = len(written) == 10

    # corpus: real JSON documents from the tree (>=50)
    corpus: list[Path] = []
    for root in [REPO / "tools" / "plugin" / "schema", REPO / "command-center" / "schema"]:
        if root.is_dir():
            corpus.extend(sorted(root.glob("*.json")))
    corpus = corpus[:120]
    checks["corpus_at_least_50"] = len(corpus) >= 50

    agreements = 0
    disagreements: list[str] = []
    for p in corpus:
        try:
            text = p.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        lenient = ji.lenient_loads(text)
        strict = ji.strict_loads(text)
        if ji.decisions_agree(lenient, strict):
            agreements += 1
        else:
            disagreements.append(p.as_posix())
    checks["no_document_accepted_by_one_rejected_by_other"] = not disagreements
    checks["corpus_agreements_recorded"] = agreements >= 50

    # adversarial fixtures: rejected by BOTH production paths, tolerated by the control
    both_rejected = 0
    control_tolerated = 0
    for name, _ in ADVERSARIAL:
        text = (adv_dir / name).read_text(encoding="utf-8")
        ln = ji.lenient_loads(text)
        st = ji.strict_loads(text)
        jc = ji.jsonc_loads(text)
        if (not ln.ok) and (not st.ok):
            both_rejected += 1
        if jc.ok:
            control_tolerated += 1
    checks["adversarial_rejected_by_both"] = both_rejected == 10
    checks["detector_control_tolerates_all_ten"] = control_tolerated == 10

    matrix = {
        "corpus_documents": len(corpus),
        "agreements": agreements,
        "disagreements": disagreements,
        "adversarial": len(ADVERSARIAL),
        "adversarial_rejected_by_both": both_rejected,
        "control_tolerated": control_tolerated,
    }
    ok = all(bool(v) for v in checks.values())
    print(json.dumps({"unit_id": UID, "probe": "probe2-agreement-matrix-live",
                      "pass": ok, "matrix": matrix, "checks": checks}))
    if ok:
        print(f"SUCCESS:{UID}-probe2 live: {agreements}/{len(corpus)} real documents agree accept/reject across lenient+strict; all 10 adversarial json5-isms rejected by both and tolerated by the jsonc control")
        return 0
    print(f"FAILED:{UID}-probe2 " + ",".join(k for k, v in checks.items() if not v))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
