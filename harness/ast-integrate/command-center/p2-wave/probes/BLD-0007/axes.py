"""OS x shell axes for BLD-0007.

The cartesian product is the unit's declared matrix. Empty cells ship a
runnable probe script, never a prose gap.
"""
from __future__ import annotations

OS_AXIS = ("Windows", "macOS", "Linux")
SHELL_AXIS = (
    "PowerShell 7",
    "cmd.exe",
    "Git Bash/MSYS",
    "WSL bash",
    "macOS zsh",
    "POSIX sh",
)

SHELL_SLUG = {
    "PowerShell 7": "powershell-7",
    "cmd.exe": "cmd.exe",
    "Git Bash/MSYS": "git-bash-msys",
    "WSL bash": "wsl-bash",
    "macOS zsh": "macos-zsh",
    "POSIX sh": "posix-sh",
}

OS_SLUG = {"Windows": "windows", "macOS": "macos", "Linux": "linux"}


def cell_id(os_name: str, shell: str) -> str:
    return f"{OS_SLUG[os_name]}__{SHELL_SLUG[shell]}"


def all_cells() -> list[tuple[str, str, str]]:
    rows = []
    for os_name in OS_AXIS:
        for shell in SHELL_AXIS:
            rows.append((cell_id(os_name, shell), os_name, shell))
    if len(rows) != 18:
        raise RuntimeError(f"expected 18 cells, got {len(rows)}")
    return rows
