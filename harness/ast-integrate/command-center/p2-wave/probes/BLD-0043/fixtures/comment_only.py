"""Comment-only mapping control: a REQ id in a comment must be reported unmapped."""


def test_comment_only_does_not_map():
    # covers REQ-FX-COMMENT
    assert 1 + 1 == 2
