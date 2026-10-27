"""Review-transport shim: route bare 'bash' resolution to Git Bash.

WHY: On this box C:\\Windows\\System32\\bash.exe (WSL launcher) precedes PATH in
CreateProcess search order, and the WSL distro is wedged, so any probe child
spawned as ["bash", ...] hangs until its internal timeout and exits 1. The
builder's probe scripts (unmodified) were written for a Git-Bash-first box.
This shim patches subprocess.Popen ONLY to rewrite argv[0]=='bash' to the
Git Bash absolute path. It changes review transport, not any repo artifact.
"""
import subprocess

_GIT_BASH = r"C:\Program Files\Git\usr\bin\bash.exe"

_orig_init = subprocess.Popen.__init__


def _patched_init(self, args, *a, **kw):
    try:
        if isinstance(args, (list, tuple)) and args and args[0] == "bash":
            args = [_GIT_BASH] + list(args[1:])
    except Exception:
        pass
    return _orig_init(self, args, *a, **kw)


subprocess.Popen.__init__ = _patched_init
