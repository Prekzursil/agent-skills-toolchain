"""Mention trap: test_aud0038_ghost_does_not_exist appears only in this prose.

A resolver that greps the tree (or this file) would count the ghost as
present. Probe 1 must match pytest --collect-only node IDs, not file text.
"""


def test_aud0038_mention_trap_is_collectible():
    assert True
