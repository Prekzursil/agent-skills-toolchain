"""TST-0205 shared contract constants."""

UNIT = "TST-0205"
OUT_REL = "command-center/receipts/TST-0205.json"
SCHEMA_REL = "command-center/schema/receipt.schema.json"
SCHEMA_POINTER = "command-center/schema/receipt.schema.json#/$defs/portability_report"
SENTINEL = "SUCCESS:TST-0205"
COMPLETION_SENTINEL = (
    "SUCCESS:TST-0205 long-path visibility across pwsh7, Git Bash and WSL: "
    "POSIX parity on this host, Git Bash MSYS extended-prefix and MAX_PATH "
    "leaks planted and enumerated"
)
QUESTION = (
    "Is a long path created in one shell visible and writable from the other "
    "two, or is the difference documented as an abstraction leak? PASS requires "
    "either parity or an explicit documented leak with the affected operations "
    "enumerated."
)
SHELLS = ("pwsh7", "git-bash", "wsl")
OPERATIONS = ("create", "stat", "read", "write", "delete")
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})
MAX_PATH = 260
LONG_MIN = 261
P1_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0205/probe1_short_path_control.py"
)
P2_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0205/probe2_leak_table.py"
)
SPEC_ANCHOR = (
    "command-center/WORK-UNIT-CATALOG.json:TST-0205 "
    "(_USER-PROMPTS.md:11017 Phase 10 layer 29; rules/common/windows-shell.md)"
)
RETRY_POLICY = (
    "two strikes then pivot (AGENTS.md 4b): after the second failure on the "
    "same hypothesis, enumerate >=2 alternative approaches before a third attempt"
)
