---
wf_id: wf_export00-fixture
name: wfmon-export-fixture
session: d219bc39-7d7f-4290-befd-f1c079161057
scope: run
redaction_mode: 'off'
generated_at: '2026-07-12T00:00:00+00:00'
schema_version: 2.1.207
permalink: dqverify-repo-20261013/tools/monitorcore/tests/golden/wf-export00.noredact
---

# wfmon-export-fixture (`wf_export00-fixture`)

> **redaction: off** - secrets NOT masked (`--no-redact`)

> ⚠ run still active - snapshot only (data may be incomplete)

**Agents:** 3 total - 1 done - 1 error - 1 running - 0 idle - 1,750 tokens

## Contents

- [Investigate](#phase-1)
  - [kitchensink](#agent-kitchensink)
  - [secretcheck](#agent-secretcheck)
- [Synthesize](#phase-2)
  - [taskorder](#agent-taskorder)

## Fan-out

```mermaid
flowchart TD; P1["Investigate"]
    P2["Synthesize"]
    P1 --> P2
    P1 --> A0["kitchensink"]
    P1 --> A1["secretcheck"]
    P2 --> A2["taskorder"]
```

_Text fallback:_
```
Investigate
├─ kitchensink [done]
└─ secretcheck [error]
Synthesize
└─ taskorder [running]
```

## <a id="phase-1"></a>Investigate

### <a id="agent-kitchensink"></a>kitchensink - done
`claude-opus-4-8[1m]` - 1,000 tokens - 4 tool calls
_Kitchensink Report_

**Task:**
> Do the kitchen-sink task.

**Transcript:**

```
Do the kitchen-sink task.
```

*thinking:*

```
Let me reason about the kitchen sink carefully.
```

```
Here is my plan.
```

<details>
<summary>🔧 Bash</summary>

Input:
```
{
  "command": "ls -la"
}
```

Output:
```
total 0
drwxr-xr-x  2 user user
```
</details>

<details>
<summary>🔧 web_search</summary>

Input:
```
{
  "query": "kitchen sink"
}
```

Output:
```
search result A
search result B
```
</details>

<details>
<summary>🔧 Read</summary>

Input:
```
{
  "file_path": "missing.txt"
}
```

_(no result)_
</details>

<details>
<summary>🔧 Grep - error</summary>

Input:
```
{
  "pattern": "boom"
}
```

Output:
```
{"error": "boom", "code": 2}
```
</details>

```
after the image
```

**Output:**
```
# Kitchensink Report
All transcript block kinds are covered by this fixture.
```

### <a id="agent-secretcheck"></a>secretcheck - error
`claude-opus-4-8[1m]` - 500 tokens - 1 tool calls - attempt 2
_FAKE credentials for redaction tests (all synthetic, non-functional):_

**Task:**
> Audit this text for secrets and home paths.

**Transcript:**

```
Audit this text for secrets and home paths.
```

```
FAKE credentials for redaction tests (all synthetic, non-functional):
api-key: sk-FAKE0000000000000000000000
gh-pat: ghp_FAKE00000000000000000000000000000000
gh-fine: github_pat_FAKE00000000000000000000000000
aws: AKIAFAKE0000000000AB
slack: xoxb-FAKE000000000000
gh-oauth: gho_FAKE00000000000000000000000000000000
jwt: Bearer eyJFAKEheaderaaa.eyJFAKEpayloadbbb.FAKEsigccc000
pem: -----BEGIN PRIVATE KEY-----
MIIFAKEKEYMATERIALLINEONE
MIIFAKEKEYMATERIALLINETWO
-----END PRIVATE KEY-----
benign-jwt-lookalike: abcdef...not.a.jwt.value
gitcrypt: C:\Users\Prekzursil\agent-skills-toolchain.gitcrypt.key
home-win: C:\Users\Prekzursil\Documents\notes.txt
home-fwd: C:/Users/Prekzursil/Documents/notes.txt
home-gitbash: /c/Users/Prekzursil/work/file
home-wsl: /mnt/c/Users/Prekzursil/work/file
home-83: C:\Users\PREKZU~1\Local\cache
```

**Output:**
```
FAKE credentials for redaction tests (all synthetic, non-functional):
api-key: sk-FAKE0000000000000000000000
gh-pat: ghp_FAKE00000000000000000000000000000000
gh-fine: github_pat_FAKE00000000000000000000000000
aws: AKIAFAKE0000000000AB
slack: xoxb-FAKE000000000000
gh-oauth: gho_FAKE00000000000000000000000000000000
jwt: Bearer eyJFAKEheaderaaa.eyJFAKEpayloadbbb.FAKEsigccc000
pem: -----BEGIN PRIVATE KEY-----
MIIFAKEKEYMATERIALLINEONE
MIIFAKEKEYMATERIALLINETWO
-----END PRIVATE KEY-----
benign-jwt-lookalike: abcdef...not.a.jwt.value
gitcrypt: C:\Users\Prekzursil\agent-skills-toolchain.gitcrypt.key
home-win: C:\Users\Prekzursil\Documents\notes.txt
home-fwd: C:/Users/Prekzursil/Documents/notes.txt
home-gitbash: /c/Users/Prekzursil/work/file
home-wsl: /mnt/c/Users/Prekzursil/work/file
home-83: C:\Users\PREKZU~1\Local\cache
```

## <a id="phase-2"></a>Synthesize

### <a id="agent-taskorder"></a>taskorder - running
`claude-opus-4-8[1m]` - 250 tokens - 0 tool calls
_working on the ordered task_

**Task:**
> short task

**Transcript:**

```
short task
```

```
working on the ordered task
```

```
This is a much larger later user message that must NOT be selected by agent_task, because agent_task returns the FIRST user message that carries text (the spawn prompt), not the largest one the way agent_prompt does. It is padded well past the length of the short first message so that a max-by-length selector would wrongly prefer it, which is exactly the regression this taskorder fixture pins against.
```

**Output:**
```
working on the ordered task
```