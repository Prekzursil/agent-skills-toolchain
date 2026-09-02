"""Enforcement surface for the chair role on wf-declared-split-roles.

Any non-chair attempting speak or vote is refused here.
Presence of this module is the mechanically independent B-signal:
the role is ENFORCED, not merely declared.
"""


def assert_speaking_allowed(role_id: str) -> None:
    if role_id != "chair":
        raise PermissionError("speaking_rights denied for non-chair")


def assert_vote_allowed(role_id: str) -> None:
    if role_id != "chair":
        raise PermissionError("vote_rights denied for non-chair")
