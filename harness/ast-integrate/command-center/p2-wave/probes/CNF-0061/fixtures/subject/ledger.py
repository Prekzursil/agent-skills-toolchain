"""Ordinary ledger mutations (not a security or rollback path)."""


def append_item(items, x):
    items.append(x)
    return items


def count_items(items):
    return len(items)
