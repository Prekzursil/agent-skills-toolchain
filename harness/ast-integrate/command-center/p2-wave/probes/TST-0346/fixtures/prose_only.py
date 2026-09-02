"""Prose-only mapping control. Comments are not declared links.

# covers REQ-FROM-COMMENT
# Mapping: REQ-FROM-COMMENT -> test_from_comment
# This test falsifies REQ-FROM-COMMENT.
"""


def test_from_comment() -> None:
    # REQ-FROM-COMMENT is asserted here, says the comment. That is not a link.
    assert True
