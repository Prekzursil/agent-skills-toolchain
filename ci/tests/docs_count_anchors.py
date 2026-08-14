"""The commits the round-5 surface counts were measured at.

WHY THIS IS A SEPARATE MODULE
-----------------------------
It is the expectation for ``test_round5_counts_keep_their_commit_anchors`` in
``test_command_doc_promises.py``. The first version of that gate kept these SHAs
in a constant inside ``test_command_doc_promises.py`` itself -- which is one of
the two files the gate checks. ``docs/_lane_docs_r7_bothstates.py`` mutated the
real file and proved that version **inert**: stripping ``67137879`` from the
carrier also stripped it from the constant, so the expectation moved with the
thing it was expecting and the gate stayed GREEN on a genuinely broken file.

The general rule that cost: **a gate whose expected value lives inside the
artifact under test cannot detect that value's removal.** So this module must
never become one of ``COUNT_CARRIERS``; a control asserts exactly that.

WHAT THE VALUES ARE
-------------------
``67137879`` is the parent of the round-5 fix, where the command-doc surface
measured 20 bare ``scripts/...`` references / 16 unresolved. ``5d573583`` is the
fix itself, from which the same probe returns 19 / 15. Re-derive both with::

    py -3.11 docs/_lane_docs_r6_pinned_counts.py

That probe needs full history and cannot run in the fetch-depth-1 checkout that
hosts the test suite, which is why the suite gates the ANCHOR and not the count.
"""

from __future__ import annotations

#: (pre-fix parent, the fix). Order is not significant; presence is.
ROUND5_COUNT_ANCHORS: tuple[str, ...] = ("67137879", "5d573583")
