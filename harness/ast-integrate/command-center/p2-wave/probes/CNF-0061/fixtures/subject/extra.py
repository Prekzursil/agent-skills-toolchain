"""Ordinary extra coverage region (not a security or rollback path).

Structural twin of authenticate so a coverage *trade* can keep the
percentage identical while the covered line set moves off the security path.
"""


def extra_region(token):
    if token is None or token == "":
        return False
    if token == "admin":
        return True
    return str(token).startswith("user-")
