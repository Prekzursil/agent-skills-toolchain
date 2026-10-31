@dataclass
class Launched:
    returncode: int
    stdout: str
    stderr: str
    argv: list[str]
    uname_inside: str | None = None
    shell_interposed: bool = False


def child_uname_raw() -> str:
    """Raw sysname string from a genuinely launched child process.

    Uses uname where present (MSYS builds report MINGW64_NT-...); falls back
    to a Python child with platform.system() so the signal stays a genuinely
    launched child on every host.
    """
    exe = shutil.which("uname")
    if exe:
        proc = subprocess.run([exe, "-s"], capture_output=True, text=True)
        if proc.returncode == 0 and proc.stdout.strip():
            return proc.stdout.strip()
    proc = subprocess.run(
        [sys.executable, "-c", "import platform; print(platform.system())"],
        capture_output=True,
        text=True,
    )
    return proc.stdout.strip()
