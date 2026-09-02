"""Named scope and preservation cases. Outcomes are computed by the model."""
from __future__ import annotations

from copy import deepcopy

from model import empty_enable

SERVER = "alpha"

SCOPE_CASES = [
    {
        "id": "project-enable-user-disable",
        "family": "inert-wrong-scope",
        "notes": (
            "User/root disable is inert while project has an entry. This is the "
            "measured trap: a disable that looks correct at the wrong scope."
        ),
        "enable": {
            "local": {},
            "project": {SERVER: True},
            "user": {SERVER: False},
        },
        "expect_enabled": True,
        "expect_effective_scope": "project",
        "expect_inert_user_disable": True,
    },
    {
        "id": "project-disable",
        "family": "effective-scope",
        "notes": "Project disable is the effective scope; process must not spawn.",
        "enable": {
            "local": {},
            "project": {SERVER: False},
            "user": {SERVER: True},
        },
        "expect_enabled": False,
        "expect_effective_scope": "project",
        "expect_inert_user_disable": False,
    },
    {
        "id": "user-disable-only",
        "family": "user-effective-when-no-inner",
        "notes": "With no local/project entry, user disable is effective.",
        "enable": {
            "local": {},
            "project": {},
            "user": {SERVER: False},
        },
        "expect_enabled": False,
        "expect_effective_scope": "user",
        "expect_inert_user_disable": False,
    },
    {
        "id": "local-enable-over-project-disable",
        "family": "local-wins",
        "notes": "Local overlay is most specific.",
        "enable": {
            "local": {SERVER: True},
            "project": {SERVER: False},
            "user": {},
        },
        "expect_enabled": True,
        "expect_effective_scope": "local",
        "expect_inert_user_disable": False,
    },
    {
        "id": "empty-default-enabled",
        "family": "default",
        "notes": "Unmentioned servers default to enabled.",
        "enable": empty_enable(),
        "expect_enabled": True,
        "expect_effective_scope": None,
        "expect_inert_user_disable": False,
    },
    {
        "id": "local-disable",
        "family": "local-wins",
        "notes": "Local disable wins over project enable.",
        "enable": {
            "local": {SERVER: False},
            "project": {SERVER: True},
            "user": {SERVER: True},
        },
        "expect_enabled": False,
        "expect_effective_scope": "local",
        "expect_inert_user_disable": False,
    },
]


PRESERVATION_MAP = {
    "local": {"scratch": True},
    "project": {"alpha": False, "beta": True},
    "user": {"legacy": False},
}


def clone_enable(enable: dict) -> dict:
    return deepcopy(enable)
