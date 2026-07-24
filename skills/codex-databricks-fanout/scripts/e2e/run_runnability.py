"""Program E Step 2: runnability + push preflight for <repo> on the node.
Validates clone + install + `pytest --cov` + push-token, and enumerates uncovered-file gaps.
Usage: python e2e/run_runnability.py <repo> <clone_url>  -> writes _<repo>_gaps.json. Real spend."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from harness.lanes import run_E

repo = sys.argv[1] if len(sys.argv) > 1 else "env-inspector"
url = (
    sys.argv[2] if len(sys.argv) > 2 else "https://github.com/Prekzursil/env-inspector"
)
TOKEN_REF = "{{secrets/codex-harness-prekzursil/github_token}}"

ok, gaps, text = run_E.runnability(repo, url, extra_env={"GITHUB_TOKEN": TOKEN_REF})
print(f"RUNNABILITY {repo} ok={ok} gaps={len(gaps)}")
Path(__file__).parent.joinpath(f"_{repo}_gaps.json").write_text(
    json.dumps(gaps, indent=2), encoding="utf-8"
)
print("=== artifact (first 3500 chars) ===")
print((text or "(empty)")[:3500])
