"""Preflight unit builders for Program E (Task 9 Steps 1-2) + the runnability artifact -> gaps parse.
The node/runnability artifacts use lanes absent from LANE_SCHEMAS, so schema_valid trivially passes;
run_E judges them with bespoke parsers (preflight.check_node_preflight / parse_gaps). Prompts pad the
artifact past the node's hardcoded 1024-byte SUCCESS gate."""
from __future__ import annotations
import re
from harness.contract import Unit

# fast (service_tier=priority) + full-permission + autonomous profile — passed via -c because
# --ignore-user-config drops ~/.codex/config.toml on the node (see contract.node_codex_flags).
_CODEX = ('codex exec --skip-git-repo-check --ignore-user-config --model gpt-5.6-sol '
          '-c service_tier=priority -c approval_policy=never -c sandbox_mode=danger-full-access '
          '-c model_reasoning_effort=')

def node_preflight_unit() -> Unit:
    prompt = f"""Node codex behavioral preflight. Run these THREE shell commands on the node and
capture each result, then write the artifact. Do NOT stop short of 1200 bytes of explanation.
1. `codex --version`                                 -> the version string
2. `{_CODEX}"ultra" -- "reply OK"; echo rc=$?`        -> its exit code (ultra_rc)
3. `{_CODEX}"bogus-wombat" -- "reply OK"; echo rc=$?` -> its exit code (bogus_rc)
A healthy node has ultra_rc=0 (ultra accepted) AND bogus_rc!=0 (a bogus effort rejected).
Write to your -o path, ending with the sentinel:
  codex_version: <version>
  ultra_rc: <n>
  bogus_rc: <n>
  <at least 1200 bytes describing what each probe means and why both-states matters>
UNIT-COMPLETE: node-preflight
"""
    return Unit(id="node-preflight", lane="preflight", prompt=prompt,
                artifact="/dbfs/tmp/E-preflight/results/node-preflight.md")

def runnability_unit(repo, clone_url) -> Unit:
    uid = f"runnability-{repo}"
    prompt = f"""Runnability + push preflight for {repo}.
1. Clone {clone_url} on the node (fail loudly if it needs a token you lack).
2. Install it (`pip install -e .` or `pip install -r requirements.txt`).
3. Run `pytest --cov` once; record suite status + baseline coverage %.
4. List every uncovered file with its uncovered line numbers.
5. Prove push works: create + push an EMPTY throwaway branch `agent/E-{repo}-preflight`
   (using the node's GITHUB_TOKEN), then delete it. Record whether the push succeeded.
Write to your -o path (at least 1200 bytes), ending with the sentinel. The uncovered_files block
MUST use exactly this shape (one line per file, comma-separated line numbers):
  suite_status: <green|red>
  baseline_coverage: <number>
  push_probe: <ok|failed>
  uncovered_files:
  - <relpath>: <n, n, n>
  - <relpath>: <n>
UNIT-COMPLETE: {uid}
"""
    return Unit(id=uid, lane="runnability", prompt=prompt,
                artifact=f"/dbfs/tmp/E-preflight/results/{uid}.md")

def parse_gaps(text) -> list[dict]:
    """Parse a runnability artifact's `uncovered_files:` block into coverage_units() gaps."""
    gaps, in_block = [], False
    for line in (text or "").splitlines():
        if re.match(r"\s*uncovered_files:\s*$", line):
            in_block = True; continue
        if in_block:
            m = re.match(r"\s*-\s*(\S.*?):\s*([\d,\s]+)$", line)
            if not m:
                if line.strip() and not line.strip().startswith("-"):
                    break                      # block ended at the next non-list line
                continue
            gaps.append({"file": m.group(1).strip(),
                         "uncovered": [int(x) for x in re.findall(r"\d+", m.group(2))]})
    return gaps
