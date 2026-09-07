"""Shipped module that illicitly imports a declared-dev-only package.

Probe 2 MUST flag this: pytest is declared only under optional-dependencies.dev,
yet this module is part of the packaged surface (tool.setuptools.packages).
"""

import pytest  # noqa: F401  # intentional packaging defect for AUD-0026 control


def ping() -> str:
    return "shipped"
