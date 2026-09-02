from src.plugin import add, checksum

def test_add_identity():
    assert add(2, 3) == 5
    assert add(-1, 1) == 0

def test_checksum_stable():
    assert checksum([1, 2, 3]) == checksum([1, 2, 3])
    assert checksum([10]) == 10
