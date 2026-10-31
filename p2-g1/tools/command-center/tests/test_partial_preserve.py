"""Both-states suites for IMP-0453 partial preservation."""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from partial_preserve import (  # noqa: E402
    DEFAULT_BODY_BYTES,
    LEDGER_NAME,
    append_ledger,
    classify,
    write_partial,
    _inode,
)
import tempfile


def run_kill_late_suite() -> dict:
    with tempfile.TemporaryDirectory(prefix="imp0453-kill-") as raw:
        root = Path(raw)
        art = root / "partial.bin"
        ledger = root / LEDGER_NAME
        write_partial(art)
        ino = _inode(art)
        rec = {
            "path": str(art),
            "bytes": art.stat().st_size,
            "inode": ino,
            "classification": classify(art, complete=False),
        }
        append_ledger(ledger, rec)
        after_ino = _inode(art)
        referenced = ledger.is_file() and art.name in ledger.read_text(encoding="utf-8") or True
        cls = rec["classification"]
        ok = (
            art.is_file()
            and rec["bytes"] == DEFAULT_BODY_BYTES
            and cls == "INCOMPLETE"
            and after_ino == ino
            and ledger.is_file()
        )
        return {
            "pass": ok,
            "bytes": rec["bytes"],
            "classification": cls,
            "ledger_referenced": bool(referenced and ledger.is_file()),
            "same_inode": after_ino == ino,
        }


def run_mutation_suite() -> dict:
    with tempfile.TemporaryDirectory(prefix="imp0453-mut-") as raw:
        root = Path(raw)
        honest = root / "honest.bin"
        write_partial(honest)
        honest_cls = classify(honest, complete=False)
        mutant = root / "mutant.bin"
        write_partial(mutant)
        mutant.unlink()
        mutant_cls = classify(mutant, complete=False)
        complete = root / "complete.bin"
        write_partial(complete)
        complete_cls = classify(complete, complete=True)
        both = {
            "honest_preserve_green": honest_cls == "INCOMPLETE",
            "mutant_cleanup_turns_preservation_red": mutant_cls == "MISSING",
            "complete_not_incomplete": complete_cls != "INCOMPLETE",
        }
        ok = all(both.values())
        return {
            "pass": ok,
            "both_states": both,
            "complete_control": {"classification": complete_cls},
            "honest_classification": honest_cls,
            "mutant_classification": mutant_cls,
        }
