#!/usr/bin/env python3
"""GROUNDING round 2: has the fleet drifted since the audit was measured?

Two INDEPENDENT instruments, deliberately not the same measurement re-run:

  A. The committed artifact `disposition.json` (produced 2026-08-12/13 by a stdio
     handshake sweep + config read).
  B. THIS auditing session's own mounted tool namespace, read off the deferred-tool
     listing the harness injected into the prompt. That listing is produced by the
     Claude Code client from the live config at session start -- a different producer,
     a different code path, a different day.

If A and B disagree, the fleet drifted (or one instrument is broken). If they agree,
the disposition table is still describing the fleet that is actually mounted.

CONTROL (rule 3 / both-states): the comparison must be able to SEE a difference.
A sentinel name absent from the session is injected into the artifact side, and a
real name is withheld from the session side; both must show up as diffs. If the
differ reports "identical" for the mangled pair, the differ is broken and this
script exits non-zero WITHOUT publishing a drift verdict.

Read-only. Spawns nothing. Reads no credential.
"""

from __future__ import annotations

import json
import pathlib

HERE = pathlib.Path(__file__).resolve().parent

# Instrument B: this session's mounted MCP namespace, transcribed from the harness's
# own deferred-tool listing (the `mcp__<server>__<tool>` prefixes it enumerated).
SESSION_NAMESPACE = {
    "agent-mail",
    "angr",
    "basic-memory",
    "brightdata",
    "chrome-devtools",
    "claude-code-mcp",
    "cloud-hub",
    "codex",
    "context7",
    "deepwiki",
    "figma",
    "frida-mcp",
    "github",
    "huggingface",
    "paper-search",
    "playwright",
    "playwright-cdp",
    "playwright-extension",
    "qlty",
    "repomix",
    "scholarly-access",
    "search-hub",
    "searxng",
}


def load_disposition() -> dict[str, dict]:
    path = HERE / "disposition.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = data["rows"] if isinstance(data, dict) and "rows" in data else data
    if isinstance(rows, dict):
        rows = list(rows.values())
    out: dict[str, dict] = {}
    for row in rows:
        name = row.get("name") or row.get("server")
        if name:
            out[name] = row
    return out


def diff(artifact: set[str], session: set[str]) -> tuple[set[str], set[str]]:
    """Return (in artifact only, in session only). BOTH directions -- a one-directional
    read is exactly how a divergence gets scored as agreement."""
    return artifact - session, session - artifact


def main() -> int:
    rows = load_disposition()
    artifact = set(rows)

    # ---- CONTROL FIRST: prove the differ can see a difference in BOTH directions ----
    sentinel = "zzz-sentinel-not-a-real-server"
    c_only_a, c_only_b = diff(
        artifact | {sentinel}, session=SESSION_NAMESPACE - {"qlty"}
    )
    control_ok = sentinel in c_only_a and "qlty" in c_only_a and not c_only_b
    # withholding qlty from the session side must surface it as artifact-only;
    # the injected sentinel must surface too. If either is invisible, stop.
    if not control_ok:
        print("FAILED:g2-drift differ control did NOT fire -- verdict withheld")
        print(
            f"  control artifact-only={sorted(c_only_a)} session-only={sorted(c_only_b)}"
        )
        return 1
    print("  ok  differ control fired (sees both an injected name and a withheld one)")

    only_artifact, only_session = diff(artifact, SESSION_NAMESPACE)

    print(f"  artifact rows (disposition.json) : {len(artifact)}")
    print(f"  session namespace (this session) : {len(SESSION_NAMESPACE)}")
    print(f"  in artifact but NOT mounted here : {sorted(only_artifact) or '(none)'}")
    print(f"  mounted here but NOT in artifact : {sorted(only_session) or '(none)'}")

    dispositions: dict[str, int] = {}
    for row in rows.values():
        d = row.get("disposition", "?")
        dispositions[d] = dispositions.get(d, 0) + 1
    print(f"  dispositions                     : {dispositions}")

    if only_artifact or only_session:
        print(
            f"FAILED:g2-drift fleet DRIFTED "
            f"({len(only_artifact)} gone, {len(only_session)} new) -- re-run the sweep"
        )
        return 1
    print(
        f"SUCCESS:g2-drift {len(artifact)}/{len(artifact)} names agree across two "
        f"independent instruments; disposition table still describes the mounted fleet"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
