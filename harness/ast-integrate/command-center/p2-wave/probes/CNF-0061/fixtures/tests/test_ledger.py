from ledger import append_item, count_items


def test_append_and_count():
    items = []
    append_item(items, "a")
    assert count_items(items) == 1
