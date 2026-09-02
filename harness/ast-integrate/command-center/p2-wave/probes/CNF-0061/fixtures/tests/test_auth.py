from auth import authenticate


def test_reject_empty():
    assert authenticate(None) is False
    assert authenticate("") is False


def test_admin():
    assert authenticate("admin") is True


def test_user():
    assert authenticate("user-1") is True
    assert authenticate("nope") is False
