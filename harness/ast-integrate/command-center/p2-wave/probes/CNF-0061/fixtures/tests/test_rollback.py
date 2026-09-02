from rollback import rollback


def test_clean():
    state = {"dirty": False, "items": [1], "checkpoint": []}
    assert rollback(state) is False
    assert state["items"] == [1]


def test_dirty():
    state = {"dirty": True, "items": [1, 2], "checkpoint": [1]}
    assert rollback(state) is True
    assert state["items"] == [1]
