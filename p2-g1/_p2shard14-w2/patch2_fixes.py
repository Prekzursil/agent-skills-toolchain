#!/usr/bin/env python3
"""Shard14 wave2 resume completion, part 2: fix-round-2 patches.

  IMP-0409  work_claim.py  - guard the renameat2 argtypes block on Windows
  IMP-0321  participation.py - filler detector uses the agreement/discourse
            stopword lexicon (planted filler volume must not count as substance)
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def patch(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    if new in text:
        print(f"SKIP  {label} (already applied)")
        return
    if old not in text:
        print(f"FAILED:shard14-p2 anchor missing for {label}")
        sys.exit(1)
    path.write_text(text.replace(old, new, 1), encoding="utf-8", newline="\n")
    print(f"OK    {label}")


wc = REPO / "tools" / "command-center" / "work_claim.py"
patch(
    wc,
    """_LIBC.renameat2.argtypes = [
    ctypes.c_int,
    ctypes.c_char_p,
    ctypes.c_int,
    ctypes.c_char_p,
    ctypes.c_uint,
]
_LIBC.renameat2.restype = ctypes.c_int
""",
    """if _LIBC is not None:
    _LIBC.renameat2.argtypes = [
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_uint,
    ]
    _LIBC.renameat2.restype = ctypes.c_int
""",
    "IMP-0409 argtypes guarded on Windows",
)

part = REPO / "tools" / "council" / "antifail" / "participation.py"
OLD = '''def is_filler_sentence(text: str) -> bool:
    t = text.strip().lower()
    if not t:
        return True
    fillers = ("um", "uh", "yeah", "ok", "okay", "right", "sure", "hmm")
    words = [w.strip(".,!?") for w in t.split()]
    if not words:
        return True
    return all(w in fillers for w in words) or len(words) <= 1
'''
NEW = '''_FILLER_STOPWORDS = frozenset(
    """
    i you we they he she it this that these those a an the and or but
    is are was were be been being am do does did done have has had
    noted agree agreed with sounds good to me no objection at all likewise
    happy proceed please continue yes okay ok acknowledged seconded keep going
    as previously said concur add nothing have not it
    um uh yeah sure right hmm well thanks thank there here
    """.split()
)


def is_filler_sentence(text: str) -> bool:
    """A sentence is filler when no content word survives the stopword lexicon.

    Planted agreement volume ("Noted. I agree with that. No objection.") is
    filler; substantive contributions carry content words (claim/evidence/
    quota/kernel/...) that survive.
    """
    t = text.strip().lower()
    if not t:
        return True
    words = [w.strip(".,!?;:()") for w in t.split()]
    content = [w for w in words if w and w not in _FILLER_STOPWORDS]
    return not content
'''
patch(part, OLD, NEW, "IMP-0321 filler stopword lexicon")

print("SUCCESS:shard14-p2")
