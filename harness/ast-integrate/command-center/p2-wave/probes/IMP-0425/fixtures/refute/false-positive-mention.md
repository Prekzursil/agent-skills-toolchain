# Adversarial false-positive candidate (must be ACCEPTED)

This unit's subject is fire-and-forget dispatch. The measured failure mode is
that a fan-in barrier accepted a job receipt as if it were a result.

Quoted historical speech acts (mentions, not this document's role):

> I've started this in the background. Check /codex:status.

A second mention inside a fence:

```
Codex is running in the background. Check /codex:status for updates.
Job started in the background.
```

Findings:
1. A naive substring gate rejects this analysis because the phrases appear.
2. Role-aware classification must ACCEPT this payload: the speech act is an
   analysis of the failure mode, not a background-start receipt.
3. A gate that rejects both this document and a real receipt is a
   use-vs-mention defect.

Verdict: this is a genuine work result. The receipt strings above are quoted
examples of the thing being rejected, not a job ticket.
