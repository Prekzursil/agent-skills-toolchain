#!/usr/bin/env python3
"""IMP-0007 probe2: real client loader out-of-process accept/reject (signal 2).

Invokes ``platform/plugin/manifest.py`` via a fresh subprocess with
``PYTHONPATH=<repo>/platform`` so this is not the fixture parser in-process.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
PROBE = Path(__file__).resolve().parent

CLIENT_SCRIPT = r"""
import json
import sys
from plugin.errors import PluginError
from plugin import manifest as M

base = json.loads(sys.argv[1])
bare = dict(base)
bare["surprise_unknown_field"] = True
under_x = dict(base)
under_x["x-surprise_unknown_field"] = True

def try_parse(doc):
    try:
        m = M.parse(json.dumps(doc))
        return {"ok": True, "extensions": sorted(m.extensions.keys())}
    except PluginError as exc:
        return {"ok": False, "code": exc.code, "detail": exc.detail}

out = {
    "base": try_parse(base),
    "bare_unknown": try_parse(bare),
    "under_x": try_parse(under_x),
    "client_allowed_top": sorted(M.ALLOWED[""]),
    "extension_prefix": M.EXTENSION_PREFIX,
}
print(json.dumps(out, sort_keys=True))
"""


def main() -> int:
    sys.path.insert(0, str(REPO / "tools" / "plugin"))
    import strict_parser_policy as P  # noqa: E402

    base = P.fixture_base_manifest()
    env = dict(**{k: v for k, v in __import__("os").environ.items()})
    # Fresh process; do not inherit a polluted PYTHONPATH that could shadow plugin.
    platform_path = str(REPO / "platform")
    env["PYTHONPATH"] = platform_path

    proc = subprocess.run(
        [sys.executable, "-c", CLIENT_SCRIPT, json.dumps(base)],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )
    raw_out = (proc.stdout or "") + (proc.stderr or "")
    (PROBE / "probe2-client-loader.raw.txt").write_text(raw_out, encoding="utf-8")

    if proc.returncode != 0:
        meas = {
            "ok": False,
            "probe_2_confirmed": False,
            "subprocess_rc": proc.returncode,
            "raw_tail": raw_out[-2000:],
        }
        (PROBE / "probe2-measurement.json").write_text(
            json.dumps(meas, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        print(raw_out)
        return 1

    # Last JSON line from the client script.
    payload = None
    for line in reversed(raw_out.splitlines()):
        line = line.strip()
        if line.startswith("{"):
            payload = json.loads(line)
            break
    if payload is None:
        raise SystemExit(f"IMP-0007 probe2: no JSON payload in:\n{raw_out}")

    reject_bare = (
        payload["bare_unknown"]["ok"] is False
        and payload["bare_unknown"].get("code") == "E_MANIFEST"
        and "unknown field" in payload["bare_unknown"].get("detail", "")
    )
    accept_x = (
        payload["under_x"]["ok"] is True
        and "x-surprise_unknown_field" in payload["under_x"].get("extensions", [])
    )
    base_ok = payload["base"]["ok"] is True
    client_keys = frozenset(payload["client_allowed_top"])
    frozen_match = client_keys == P.FROZEN_TOP_LEVEL_KEYS
    confirmed = bool(base_ok and reject_bare and accept_x and frozen_match)

    meas = {
        "probe": "probe2-client-loader-oop",
        "ok": confirmed,
        "probe_2_confirmed": confirmed,
        "subprocess_rc": proc.returncode,
        "base_ok": base_ok,
        "reject_bare_unknown": reject_bare,
        "accept_under_x": accept_x,
        "frozen_matches_client_allowed": frozen_match,
        "client_allowed_top": sorted(client_keys),
        "policy_frozen_top": sorted(P.FROZEN_TOP_LEVEL_KEYS),
        "extension_prefix": payload.get("extension_prefix"),
        "client_payload": payload,
        "out_of_process": True,
        "pythonpath": platform_path,
    }
    (PROBE / "probe2-measurement.json").write_text(
        json.dumps(meas, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    lines = [
        "NAMED PROBE 2: REAL CLIENT LOADER OUT-OF-PROCESS",
        "PROBE-2-BEGIN:IMP-0007",
        f"subprocess_rc={proc.returncode}",
        f"base_ok={base_ok}",
        f"reject_bare_unknown={reject_bare}",
        f"accept_under_x={accept_x}",
        f"frozen_matches_client_allowed={frozen_match}",
        f"out_of_process=True",
        f"probe_2_confirmed={confirmed}",
        "PROBE-2-COMPLETE:IMP-0007",
        "SUCCESS:IMP-0007-probe2" if confirmed else "FAILED:IMP-0007-probe2",
    ]
    summary = "\n".join(lines) + "\n"
    # Append summary to raw evidence file.
    (PROBE / "probe2-client-loader.raw.txt").write_text(
        raw_out + "\n" + summary, encoding="utf-8"
    )
    print(summary, end="")
    return 0 if confirmed else 1


if __name__ == "__main__":
    raise SystemExit(main())
