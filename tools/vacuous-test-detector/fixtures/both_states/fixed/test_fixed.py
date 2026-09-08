# both-states FIXED side: detector MUST stay silent.


def _subject(n: int) -> int:
    return n * 2


def test_fixed_real_assertion():
    assert _subject(3) == 6
