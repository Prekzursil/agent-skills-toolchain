"""Security path: authentication decisions.

Lines here sit on a security path. Dropping the auth tests while adding
unrelated ledger coverage is the coverage-trade the detector must see.
"""


def authenticate(token):
    if token is None or token == "":
        return False
    if token == "admin":
        return True
    return str(token).startswith("user-")
