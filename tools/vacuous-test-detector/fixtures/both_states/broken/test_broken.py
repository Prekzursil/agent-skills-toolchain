# both-states BROKEN side: detector MUST fire (vacuous tests present).


def test_broken_no_assert():
    x = "mentions assert in a string"
    y = len(x)
    _ = y
