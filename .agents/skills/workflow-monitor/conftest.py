"""Pytest bootstrap for the workflow-monitor skill.

Puts the skill root on ``sys.path`` so tests under ``tests/`` can import the flat top-level
modules ``workflow_run`` and ``wfmon_export`` without an installed package.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
