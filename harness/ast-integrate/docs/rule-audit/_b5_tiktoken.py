"""BUILD-R1: is tiktoken importable here, and what does Counter actually report?"""

import importlib.util
import platform
import sys

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
import rule_audit  # noqa: E402

print(f"platform      : {platform.system()} python {sys.version.split()[0]}")
print(f"tiktoken spec : {importlib.util.find_spec('tiktoken') is not None}")
print(f"Counter.name  : {rule_audit.Counter().name}")
