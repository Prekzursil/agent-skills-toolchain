<!-- verbatim final report of background subagent abd8e8d8b019fffe7, saved 2026-09-19 -->

## Boundary decisions
All URLs and Hub facts were checked on 2026-09-19.

### 1. No credentials in a container that runs model-authored code
- What is at stake: `HF_TOKEN` and `NF4_UPLOAD_TOKEN` sit in the environment of the app process. The `python_eval` child inherits that environment and has raw sockets, so one injected web page plus a compliant model can post the tokens out. An account-wide write token reaches public Space `Prekzursil/GLM-5.3`, public model `Prekzursil/reframe-asd-weights`, two other private Spaces, and credits via Jobs.
- Evidence:
  - `web_tools.py:440-445` passes no `env=`; I reproduced the inheritance locally with a dummy variable. `app.py:208` reads the upload token.
  - The served models are public and ungated, so serving needs no token.
  - ToS indemnity covers "any other party's use of any Service with your credentials" (huggingface.co/terms-of-service, effective 2022-09-15).
  - Docs: "We recommend you create one access token per app or usage" (huggingface.co/docs/hub/security-tokens).
- Effort to address: S.
- Decision it forces: which credentials may live in the app?
  - (a) None. Run the export once elsewhere with a token scoped to the NF4 repo, delete that token, and mount the repo as a volume.
  - (b) One read-only token scoped to a single repo.
  - (c) Status quo.
  - I recommend (a). The trade-off is a manual export step.
  - Separately, and not a decision: revoke the token pasted into chat today.

### 2. Risky features are caller-selected, not operator-gated
- What is at stake: `python_eval` is a plain argument of `chat`, and `mcp_server=True` publishes `chat` as a tool. "OFF by default" is only a checkbox default, and `/v1/chat/completions` has no app-level auth. The visibility setting is the only protection, and PRO's "protected" level sounds private but is not. One visibility change makes this an open code-executing endpoint for a refusal-removed model.
- Evidence:
  - `app.py:654,693-694,1158`; `openai_api.py:18-45`; gradio `mcp.py:564-577`.
  - Docs: "Protected Spaces keep their source code private on the Hub … However, the running app is publicly accessible through its embed URL" (huggingface.co/docs/hub/spaces-overview).
  - Same page: secrets "won’t be added to Spaces duplicated from your repository".
  - ToS: "You are solely responsible for the Content you post, publish, display or otherwise make available".
- Effort to address: S-M.
- Decision it forces: hard-code a fail-closed guard?
  - (a) `python_eval`, MCP, `/v1` and HTTP POST each require a secret flag. Add a boot tripwire: an anonymous GET of the Space's own Hub API returned 401 while private (behaviour for "protected" is unverified).
  - (b) Flag only.
  - (c) Trust the visibility setting.
  - I recommend (a). Duplicates start safe because secrets are not copied. The trade-off is one more secret and one Hub call at boot.

### 3. Who may push to production, and with what
- What is at stake: a second agent pushes to the live Space every few minutes with a write token and no gate. HEAD cannot import, and a failing test shipped anyway. A weekly unattended task also bumps dependencies and deploys. Each path is code execution inside the owner's account.
- Evidence:
  - SCOUT A2/A3; `maintenance/update_deps_and_deploy.py:183-199`.
  - `deploy_space.py:21` and `maintenance/keepalive.py:20-21` read the same `HF_TOKEN` variable, so the deploy credential is also sent to the Space every 12 h (inferred).
  - `requirements.txt:4-7` is unpinned.
  - `trust_remote_code=True` at `app.py:109,122,127,143,155`, with no `revision=`. It is inert today (no `.py` or `auto_map` upstream) but is a standing opt-in to upstream code.
- Effort to address: M.
- Decision it forces: which deploy paths and tokens are allowed?
  - (a) One deploy path gated by pyflakes and tests, with:
    - a token scoped to this Space;
    - a separate read token for keepalive;
    - no `trust_remote_code`;
    - pinned revisions and versions.
  - (b) Agents push only to a staging duplicate.
  - (c) Status quo.
  - I recommend (a) plus (b). The trade-off is slower iteration.

### 4. Becoming the host of the derivative weights
- What is at stake: today the Space only mounts heretic-org's repo. The NF4 export makes the owner the uploader of refusal-removed weights, which changes who answers a report. Licence duties attach once the repo is shared.
- Evidence:
  - `app.py:197-216,238-254`; the export writes no LICENSE or model card.
  - Content policy (huggingface.co/content-policy, effective 2025-04-10):
    - It covers "any material posted, displayed, or accessed on our Website or Hub", with no private carve-out.
    - Enforcement includes "Account Suspension or Termination".
    - Under the Australian-compliance heading (wider scope unverified): "Before uploading any content to the Hub, particularly any ML Artifacts, you must take appropriate steps to minimise the risk …".
    - It does not name refusal-removed models.
  - Both repos are `apache-2.0` with no NOTICE. §4 requires "a copy of this License" and "prominent notices stating that You changed the files" (apache.org/licenses/LICENSE-2.0.txt).
- Effort to address: S.
- Decision it forces: host a copy of the weights?
  - (a) Host privately; add LICENSE and a card naming the base model and the changes.
  - (b) Do not host; accept 5-minute boots.
  - (c) Host, and perhaps publish later.
  - I recommend (a). The trade-off is that the account now carries the artifact.

### 5. Which persona set ships in the repo (owner's call)
- What is at stake: the swap changed vocabulary, not position.
  - README still advertises the originals, and git history holds them verbatim.
  - One test asserts keyword absence; another needs an archive that exists on one disk.
  - One clause in the neutral set keeps the original function: prompts for other AI systems worded so the intent reads as ordinary documentation. That exposure falls on the owner's accounts with those providers (their terms unverified).
- Evidence: `README.md:38-42`; `git show 17dce0c:system_prompt.py`; `tests/test_personas.py:51-66,68-74`; `system_prompt.py:3-8,36-39`.
- Effort to address: S.
- Decision it forces: which set lives in the repo?
  - (a) Neutral set, with README and tests made consistent. Keep the originals versioned privately, or they are not reproducible.
  - (b) Originals in the repo, stated openly. Most reproducible, but any visibility change discloses them.
  - (c) No built-in personas, Custom box only. Least to review.
  - My lean is (c). None of these changes how actual use is judged. Keeping that clause is the owner's explicit call.

## Killed concerns
- Private Space visible on the public model page: 0 anonymous mentions, and the Hub API returns 401.
- Visitors draining the owner's quota if public: ZeroGPU bills the visitor's `X-IP-Token` (`spaces/zero/client.py:29,322-324`). Attribution for `/v1` calls is unverified.
- Uploads and tool results at rest: never cleaned (`file_bench.py:282`), but there is no persistent storage (A7), so they vanish on restart. Residual risk: `.env` uploads are accepted (`app.py:1043`) while POST-capable web tools default on (`app.py:984-985`, `web_tools.py:395-403`).
- Browser history: encrypted with a per-process random secret (gradio `components/browser_state.py:51-53`).
- Logs: status lines only; the committed `runlog_tail.txt` is boot output.
- Licence forbidding refusal removal: Apache-2.0 has no use restrictions.

## Biggest unknown
The real scope of the Space's `HF_TOKEN`, and whether the pushing agent uses the pasted token. If it has account-wide write, item 1 is an emergency; if it is read-only on a single repo, item 2 comes first. Cheapest check: in Settings, Access Tokens, read the scopes and last-used dates.

Paths: code refs are under `/tmp/claude-1000/-workspaces-agent-skills-toolchain/ca9aa7a4-16ad-4e9d-bafe-00eed0171063/scratchpad/space-latest/`. Library refs are under the sibling `libsrc/`. Fetched policy text is under the sibling `work/lens-exposure/`.