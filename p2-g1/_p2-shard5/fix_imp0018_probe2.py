#!/usr/bin/env python3
"""Fix cycle 1 for IMP-0018 probe2 (measured 2026-10-24, shard-5 resume).

Defect: the temp-permission gate demanded stat.S_IMODE == 0o600/0o700 exactly.
On Windows/NTFS, Python's stat mode bits are synthesized (0o666/0o777) and
os.chmod can only toggle the read-only flag — the POSIX bits are
unrepresentable, so the gate could never pass on this host. The prior green
came from a Linux run (SUBAGENT-RETURN raw outputs show uname=Linux,
/usr/bin/python3), i.e. evidence generated on a substrate the measure gate
cannot re-execute here.

Repair (platform-split, control-preserving):
* POSIX: keep the exact 0o600/0o700 stat gate, unchanged.
* Windows (os.name == 'nt'): prove the marshaller REQUESTS 0o600/0o700 in its
  real executed code path by intercepting os.chmod/os.open during a live
  marshaller.prepare(), and prove the payload lands under the user-private
  temp root (NTFS privacy is ACL-inherited from %TEMP%, not mode bits).
No branch weakens the other; the restrictive-permissions property stays
load-bearing on both platforms.
"""
from pathlib import Path

P = Path(__file__).resolve().parents[1] / (
    "command-center/p2-wave/probes/IMP-0018/probe2_inline_fail_and_cleanup.py"
)
src = P.read_text(encoding="utf-8")

OLD = '''    marshaller = am.ArgMarshaller()
    prepared = marshaller.prepare(am.default_prefix(), payload)
    path = prepared.payload_path
    directory = prepared.payload_dir
    if not path or not os.path.isfile(path) or not directory:
        print("FAILED:IMP-0018-probe2 expected a live payload file before spawn")
        prepared.close()
        return 1
    file_mode = stat.S_IMODE(os.stat(path).st_mode)
    dir_mode = stat.S_IMODE(os.stat(directory).st_mode)
    world_bits = file_mode & 0o077
    if file_mode != 0o600 or world_bits != 0 or dir_mode != 0o700:
        prepared.close()
        print(
            f"FAILED:IMP-0018-probe2 modes file={oct(file_mode)} dir={oct(dir_mode)}"
        )
        return 1'''

NEW = '''    marshaller = am.ArgMarshaller()
    # Restrictive-permissions control, platform-split (shard-5 resume
    # 2026-10-24): on POSIX the on-disk bits must read 0600/0700 exactly; on
    # Windows those bits are unrepresentable (stat synthesizes 0o666/0o777
    # and chmod only toggles read-only), so the control proves the marshaller
    # REQUESTS 0o600/0o700 in its executed code path (live interception of
    # os.chmod/os.open) AND that the payload lives under the user-private
    # temp root, whose NTFS ACL is what actually restricts access there.
    import tempfile as _tempfile

    chmod_calls: list = []
    open_modes: list = []
    real_chmod = os.chmod
    real_open = os.open

    def spy_chmod(path, mode, *a, **k):
        chmod_calls.append((str(path), mode))
        return real_chmod(path, mode, *a, **k)

    def spy_open(path, flags, mode=0o777, *a, **k):
        open_modes.append(mode)
        return real_open(path, flags, mode, *a, **k)

    if os.name == "nt":
        os.chmod = spy_chmod  # type: ignore[assignment]
        os.open = spy_open  # type: ignore[assignment]
    try:
        prepared = marshaller.prepare(am.default_prefix(), payload)
    finally:
        if os.name == "nt":
            os.chmod = real_chmod  # type: ignore[assignment]
            os.open = real_open  # type: ignore[assignment]
    path = prepared.payload_path
    directory = prepared.payload_dir
    if not path or not os.path.isfile(path) or not directory:
        print("FAILED:IMP-0018-probe2 expected a live payload file before spawn")
        prepared.close()
        return 1
    file_mode = stat.S_IMODE(os.stat(path).st_mode)
    dir_mode = stat.S_IMODE(os.stat(directory).st_mode)
    if os.name == "posix":
        if file_mode != 0o600 or dir_mode != 0o700:
            prepared.close()
            print(
                f"FAILED:IMP-0018-probe2 modes file={oct(file_mode)} dir={oct(dir_mode)}"
            )
            return 1
    else:
        requested = {m for _, m in chmod_calls} | set(open_modes)
        if not {0o600, 0o700} <= requested:
            prepared.close()
            print(
                "FAILED:IMP-0018-probe2 marshaller did not request restrictive "
                f"0o600/0o700 (observed: {sorted(oct(m) for m in requested)})"
            )
            return 1
        priv_root = os.path.realpath(_tempfile.gettempdir())
        if not os.path.realpath(directory).startswith(priv_root):
            prepared.close()
            print(
                f"FAILED:IMP-0018-probe2 payload dir {directory!r} not under "
                f"user-private temp root {priv_root!r}"
            )
            return 1'''
assert OLD in src, "mode-gate block not found verbatim"
P.write_text(src.replace(OLD, NEW), encoding="utf-8", newline="\n")
print("patched", P)
