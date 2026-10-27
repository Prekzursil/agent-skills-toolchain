"""Runner-control only: import a helper the CI console layout does not ship."""


def test_packaging_in_tree_helper() -> None:
    import only_in_tree

    assert only_in_tree.MARKER == "in-tree"
