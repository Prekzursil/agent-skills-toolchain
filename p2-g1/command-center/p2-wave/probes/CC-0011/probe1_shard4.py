"""Shard-4 wave-1 generated probe (uid=CC-0011, probe1)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "_shard4_w1"))

from lib_shard4 import run_probe

raise SystemExit(run_probe('CC-0011', 1))
