from extra import extra_region


def test_reject_empty():
    assert extra_region(None) is False
    assert extra_region("") is False


def test_admin():
    assert extra_region("admin") is True


def test_user():
    assert extra_region("user-1") is True
    assert extra_region("nope") is False
