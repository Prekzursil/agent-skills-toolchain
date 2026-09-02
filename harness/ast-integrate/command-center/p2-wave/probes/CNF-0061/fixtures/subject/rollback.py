"""Rollback path: restore checkpointed state.

Lines here sit on a rollback path. The delete-one-test control drops the
rollback tests so this region must appear in the newly-uncovered set.
"""


def rollback(state):
    if not state.get("dirty"):
        return False
    state["items"] = list(state.get("checkpoint") or [])
    return True
