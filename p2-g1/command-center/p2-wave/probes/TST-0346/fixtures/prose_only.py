"""A module whose COMMENTS name a requirement - comments are not links.

The mapping REQ-FROM-COMMENT -> TST-FROM-COMMENT below exists only in a
Python comment. The matrix must be computed from DECLARED links (the links
JSON), so this id must never appear in any matrix output list.
"""

# mapping: REQ-FROM-COMMENT is falsified by TST-FROM-COMMENT (prose only)


def unrelated():
    return None
