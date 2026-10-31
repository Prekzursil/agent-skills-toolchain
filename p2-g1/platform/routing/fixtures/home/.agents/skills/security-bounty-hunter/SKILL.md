---
name: security-bounty-hunter
description: Hunt for exploitable, bounty-worthy security issues in repositories. Focuses on remotely reachable vulnerabilities that qualify for real reports instead of noisy local-only findings.
origin: ECC direct-port adaptation
version: "1.0.0"
---

# Security Bounty Hunter

Use this when the goal is practical vulnerability discovery for responsible disclosure or bounty submission, not a broad best-practices review.

## When to Use

- Scanning a repository for exploitable vulnerabilities
- Preparing a Huntr, HackerOne, or similar bounty submission
- Triage where the question is "does this actually pay?" rather than "is this theoretically unsafe?"

## How It Works

Bias toward remotely reachable, user-controlled attack paths and throw away patterns that platforms routinely reject as informative or out of scope.

## In-Scope Patterns

These are the kinds of issues that consistently matter:

| Pattern | CWE | Typical impact |
| --- | --- | --- |
| SSRF through user-controlled URLs | CWE-918 | internal network access, cloud metadata theft |
| Auth bypass in middleware or API guards | CWE-287 | unauthorized account or data access |
| Remote deserialization or upload-to-RCE paths | CWE-502 | code execution |
| SQL injection in reachable endpoints | CWE-89 | data exfiltration, auth bypass, data destruction |
| Command injection in request handlers | CWE-78 | code execution |
| Path traversal in file-serving paths | CWE-22 | arbitrary file read or write |
| Auto-triggered XSS | CWE-79 | session theft, admin compromise |

## Skip These

These are usually low-signal or out of bounty scope unless the program says otherwise:

- Local-only `pickle.loads`, `torch.load`, or equivalent with no remote path
- `eval()` or `exec()` in CLI-only tooling

### Workflow
### Example Triage Loop
### Report Structure
### Description
### Vulnerable Code
### Proof of Concept
### Impact
### Affected Version
### Quality Gate
