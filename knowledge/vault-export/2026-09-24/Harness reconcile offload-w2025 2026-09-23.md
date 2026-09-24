---
title: Harness reconcile offload-w2025 2026-09-23
type: note
permalink: main/harness/harness-reconcile-offload-w2025-2026-09-23
---

- [fact] ROOT CAUSE FOUND: the Microsoft Visual C++ runtime (msvcp140.dll, vcruntime140.dll, vcruntime140_1.dll) was ENTIRELY ABSENT on offload-w2025. This silently broke every native-dependency Python package: onnxruntime failed to import, cascading to fastembed, which made basic-memory report "Semantic Dependencies Missing". The same gap broke PyMuPDF (found independently in the wave-2 audit). Fixed by installing vc_redist.x64 (exit 0). One missing system runtime, multiple unrelated failures.
- [fact] basic-memory RECOVERED on offload-w2025: v0.22.1 installed via uv tool (the prior install was an orphaned trampoline pointing at a deleted venv). Config auto-created pointing at a WRONG empty path C:\Users\prekzursil\basic-memory; surgically repointed to D:\basic-memory. HTTP daemon on 127.0.0.1:18765/mcp per contract (never stdio spawn). 713 notes intact, index 25.14 MB, semantic retrieval VERIFIED returning real hits.
- [decision] VM harness wired by porting HOME settings.json (758 B -> 27163 B): 20 hook events, 43 hook commands all verified resolvable BEFORE applying, 19 env vars, skillListingBudgetFraction, 6 denied MCP servers. No-regression check caught and restored 3 VM-specific blanket shell allow rules the port had dropped. Hooks confirmed live same session.
- [fact] git had NO author identity configured, so every commit failed with "Author identity unknown" and work sat staged forever. This is a mechanical root cause of the owner's recurring "committed work never gets pushed / gets abandoned" complaint. Set globally; commits now succeed.
- [decision] The vault must NOT go into Prekzursil/agent-skills-toolchain while that repo is PUBLIC (verified world-readable, HTTP 200 unauthenticated). A scan found 3 of 713 notes containing credential-shaped values and 258 mentioning credential words. Owner elected to make the repo PRIVATE instead, which unblocks committing the 2.2 MB of notes for versioned off-machine durability.
- [fact] MCP fleet root cause: the session cwd C:\Users\prekzursil (lowercase p) does not match the project key C:/Users/Prekzursil (capital P) holding the 120-entry disable list, so at the real cwd NOTHING is disabled and all 88 servers launch. Fix is additive (copy the list onto the lowercase key), never destructive.
- relates_to [[Harness health verdict 2026-07-04]]
- relates_to [[MCP restore and curation]]
See also [[Commit exhaustion root cause]].