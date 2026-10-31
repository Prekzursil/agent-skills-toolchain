"""w4s0 resume 2026-10-26: close the S4 suspend-drop race in engine.py.

Observed live: scenario_s4 passed wait_state_t (state T) but the classify
read ~0.2s later returned proc_state "R" with cpu_delta 0 - psutil's
suspended-enumeration flapped under fleet load while the worker never ran.
Result: S4 misclassified as S2, probe2 exit 1 ("reproc did not separate
S2 from S4"). Fix: re-verify T immediately before the classify read and
re-arm (re-suspend + re-wait) if the state was lost. Bounded; honest
RuntimeError if the primitive cannot hold. Verdict semantics unchanged.
"""
import sys
from pathlib import Path

ENGINE = Path.home() / "p2-g1/command-center/p2-wave/probes/ADV-0124/engine.py"
ANCHOR = "        backdate(artifact)\n        bundle = _classify_bundle("
PATCH = (
    "        backdate(artifact)\n"
    "        # w4s0 resume 2026-10-26: the win32 suspend primitive has been\n"
    "        # observed to read \"R\" again at classify time despite passing\n"
    "        # wait_state_t moments earlier (cpu_delta stayed 0, so the\n"
    "        # worker never ran; psutil's suspended-enumeration flapped under\n"
    "        # fleet load). Re-verify T immediately before the classify read\n"
    "        # and re-arm (re-suspend + re-wait) if the state was lost.\n"
    "        # Bounded; an honest RuntimeError if the primitive cannot hold.\n"
    "        # Verdict semantics unchanged.\n"
    "        for _rearm in range(3):\n"
    "            info = M.read_proc(worker.pid)\n"
    "            if info and info.get(\"state\") == \"T\":\n"
    "                break\n"
    "            if not _stop_process(worker.pid):\n"
    "                raise RuntimeError(\"S4 suspend primitive failed on re-arm\")\n"
    "            if not wait_state_t(worker.pid):\n"
    "                raise RuntimeError(\n"
    "                    \"S4 worker did not re-enter stopped state T\"\n"
    "                )\n"
    "        bundle = _classify_bundle("
)

text = ENGINE.read_text(encoding="utf-8")
if "w4s0 resume 2026-10-26" in text:
    print("ALREADY-PATCHED")
    sys.exit(0)
if ANCHOR not in text:
    print("FAILED:anchor-absent")
    sys.exit(1)
patched = text.replace(ANCHOR, PATCH, 1)
if patched == text:
    print("FAILED:replace-noop")
    sys.exit(1)
ENGINE.write_text(patched, encoding="utf-8", newline="\n")
import py_compile
py_compile.compile(str(ENGINE), doraise=True)
print("SUCCESS:engine.py patched + compiles")
