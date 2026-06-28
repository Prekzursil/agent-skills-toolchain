"""Make ``research_harness`` importable when running pytest from any CWD."""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
