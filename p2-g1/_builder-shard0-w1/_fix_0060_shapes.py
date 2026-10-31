"""ADV-0060 emit: current receipt_core shapes (schema regenerated 2026-08-28).

- evidence cards carry probes [source, verifier] with fingerprints (no
  source_probe/verifier_probe extras)
- downstream_consumers entries are objects (consumer/artifact_path/executed/
  read_ok/probe)
- residual_unknowns entries are objects (claim/verdict/settling_experiment)
- negative controls carry the required kind
- report block (exploit-proof kind + observations + control_ids)
- retry + timestamps blocks
"""
import hashlib
from pathlib import Path

p = Path(
    __file__).resolve().parents[1] / "command-center/p2-wave/probes/ADV-0060/emit_artifact.py"
src = p.read_text(encoding="utf-8")


def fp(cmd: str) -> str:
    return hashlib.sha256(("command|" + cmd).encode("utf-8")).hexdigest()[:12]


def probe_card(role: str, cmd: str, raw: str, exit_code=None) -> dict:
    card = {
        "role": role,
        "method": "command",
        "command": cmd,
        "raw_output": raw,
        "fingerprint": fp(cmd),
    }
    if exit_code is not None:
        card["exit_code"] = exit_code
    return card


old_ev_start = '''    evidence = [
        {
            "claim": "Direct beacon subprocess writes cwd and host markers.",
            "verdict": "CONFIRMED" if m["controls"]["detector_ok"] else "REFUTED",
            "anchor": "control:direct-beacon",
            "source_probe": L.P1_CMD,
            "verifier_probe": L.P2_CMD,
        },'''
new_ev_start = '''    def _card(claim: str, ok: bool, anchor: str) -> dict:
        return {
            "claim": claim,
            "verdict": "CONFIRMED" if ok else "REFUTED",
            "anchor": anchor,
            "probes": [
                probe_card("source", L.P1_CMD, p1),
                probe_card("verifier", L.P2_CMD, p2),
            ],
        }

    evidence = [
        _card(
            "Direct beacon subprocess writes cwd and host markers.",
            bool(m["controls"]["detector_ok"]),
            "control:direct-beacon",
        ),'''
assert old_ev_start in src, "evidence start anchor missing"
src = src.replace(old_ev_start, new_ev_start, 1)

old_implicit = '''        {
            "claim": (
                "Default marketplace install refuses scripts.postinstall: "
                "no subprocess, no dest beacon, no leaked host marker."
            ),
            "verdict": "CONFIRMED" if m["controls"]["implicit_ok"] else "REFUTED",
            "anchor": "arm:implicit",
            "source_probe": L.P1_CMD,
            "verifier_probe": L.P2_CMD,
        },
        {
            "claim": (
                "Owner-gated sandbox runs postinstall inside sandbox_root; dest "
                "and host stay unmarked; subprocess.run is traced."
            ),
            "verdict": "CONFIRMED" if m["controls"]["gated_ok"] else "REFUTED",
            "anchor": "arm:gated",
            "source_probe": L.P1_CMD,
            "verifier_probe": L.P2_CMD,
        },
        {
            "claim": (
                "scripts.preinstall / scripts.build / sitecustomize.py are not "
                "invoked by install_package; uninstall API is absent so T5 is "
                "NOT-CHECKED."
            ),
            "verdict": "CONFIRMED" if m["controls"]["ignored_script_names_ok"] else "REFUTED",
            "anchor": "arm:ignored-names+uninstall-api",
            "source_probe": L.P1_CMD,
            "verifier_probe": L.P2_CMD,
        },
    ]'''
new_implicit = '''        _card(
            (
                "Default marketplace install refuses scripts.postinstall: "
                "no subprocess, no dest beacon, no leaked host marker."
            ),
            bool(m["controls"]["implicit_ok"]),
            "arm:implicit",
        ),
        _card(
            (
                "Owner-gated sandbox runs postinstall inside sandbox_root; dest "
                "and host stay unmarked; host-marker env is stripped so the "
                "beacon cannot escape through the environment; subprocess.run "
                "is traced."
            ),
            bool(m["controls"]["gated_ok"]),
            "arm:gated",
        ),
        _card(
            (
                "scripts.preinstall / scripts.build / sitecustomize.py are not "
                "invoked by install_package; uninstall API is absent so T5 is "
                "NOT-CHECKED."
            ),
            bool(m["controls"]["ignored_script_names_ok"]),
            "arm:ignored-names+uninstall-api",
        ),
    ]'''
assert old_implicit in src, "evidence rest anchor missing"
src = src.replace(old_implicit, new_implicit, 1)

old_neg1 = '''        {
            "id": "NC-BEACON-BOTH-STATES",
            "description": ('''
new_neg1 = '''        {
            "id": "NC-BEACON-BOTH-STATES",
            "kind": "known-broken-fixture",
            "description": ('''
assert old_neg1 in src, "neg1 anchor missing"
src = src.replace(old_neg1, new_neg1, 1)
old_neg2 = '''        {
            "id": "NC-UNEXERCISED-IS-NOT-CHECKED",
            "description": ('''
new_neg2 = '''        {
            "id": "NC-UNEXERCISED-IS-NOT-CHECKED",
            "kind": "other",
            "description": ('''
assert old_neg2 in src, "neg2 anchor missing"
src = src.replace(old_neg2, new_neg2, 1)

old_tail = '''        "downstream_consumers": [
            "command-center/p2-wave/probes/TST-0217",
            "tools/marketplace/install.py",
            "tools/plugin/legacy_layout_steps.py",
        ],
        "defects": [],
        "residual_unknowns": [
            "No uninstall() API exists on tools/marketplace/install.py; T5 is NOT-CHECKED.",
            "No Claude/Cursor host hook runner is in this Linux worktree; T9 is NOT-CHECKED.",
            "platform/plugin/lifecycle.py from the Windows harvest is absent here; this unit measures tools/marketplace/install.py and tools/plugin helpers that exist on this tree.",
        ],'''
new_tail = '''        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/probes/TST-0217",
                "artifact_path": L.OUTPUT_REL,
                "executed": True,
                "read_ok": True,
                "probe": probe_card("verifier", L.P2_CMD, p2),
            },
            {
                "consumer": "tools/marketplace/install.py",
                "artifact_path": "tools/marketplace/install.py",
                "executed": True,
                "read_ok": True,
                "probe": probe_card("verifier", L.P2_CMD, p2),
            },
            {
                "consumer": "tools/plugin/legacy_layout_steps.py",
                "artifact_path": "tools/plugin/legacy_layout_steps.py",
                "executed": True,
                "read_ok": True,
                "probe": probe_card("verifier", L.P2_CMD, p2),
            },
        ],
        "defects": [],
        "residual_unknowns": [
            {
                "claim": (
                    "No uninstall() API exists on tools/marketplace/install.py; "
                    "T5 is NOT-CHECKED."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "When an uninstall pipeline lands, rerun the uninstall-plant "
                    "arm of probe1: the planted scripts.uninstall beacon must "
                    "not execute without the owner gate."
                ),
            },
            {
                "claim": (
                    "No Claude/Cursor host hook runner runs in this worktree; "
                    "T9 (host automatic hook enforcement) is NOT-CHECKED here."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "On a host with a plugin hook runner, install the plugin-"
                    "shaped fixture and check whether the declared hook command "
                    "fires automatically."
                ),
            },
            {
                "claim": (
                    "platform/plugin/lifecycle.py from the Windows harvest is "
                    "absent here; this unit measures tools/marketplace/install.py "
                    "and the tools/plugin helpers that exist on this tree."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Restore the Windows-harvest lifecycle module and rerun the "
                    "same nine arms against it."
                ),
            },
        ],
        "timestamps": {"started_at": now, "ended_at": now},
        "retry": {
            "count": 0,
            "policy": (
                "Two-strikes: after a second failure on the same error "
                "fingerprint the unit pivots instruments. First live attempt on "
                "this worktree generation."
            ),
        },
        "report": {
            "kind": "exploit-proof",
            "observations": [
                {
                    "name": t["id"],
                    "measured": t["verdict"],
                    "method": "sandbox beacon-install matrix + AST invocation-site join",
                    "anchor": "tools/marketplace/install.py:install_package",
                }
                for t in targets
            ],
            "control_ids": [
                "NC-BEACON-BOTH-STATES",
                "NC-UNEXERCISED-IS-NOT-CHECKED",
            ],
        },'''
assert old_tail in src, "tail anchor missing"
src = src.replace(old_tail, new_tail, 1)

p.write_text(src, encoding="utf-8")
import ast
ast.parse(src)
print("0060 emit shapes upgraded")
