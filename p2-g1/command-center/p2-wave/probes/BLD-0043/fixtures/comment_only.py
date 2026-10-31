# Recreated 2026-10-25 (wave-2 shard 7) after the original probe tree was
# lost with the prior builder session; content follows the recorded role in
# the unit receipt (anchors re-resolve live). Prior reviewer closure kept.
"""BLD-0043 fixture: a comment-only 'mapping'. The REQ id appears ONLY in a
code comment, never in the test id, a marker, or a registry entry -- so the
detector must report it UNMAPPED (comment_only_counts=false)."""


def test_comment_only_does_not_map():
    # REQ-FX-COMMENT is claimed here, in a comment, and nowhere else.
    assert True
