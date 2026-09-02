# TST-0017 use-vs-mention discriminator kit

This file is the kit's own documentation. A detector that greps for defect
tokens will flag documentation. The helper must classify those hits as
MENTION, not USE.

## The question this kit answers

Target: a reusable helper that answers 'is this token USED (a semantic role in a typed field) or MENTIONED (text inside a payload, a fenced block, a doc body)?' and a labelled fixture kit of adversarial cases. A file documenting a defect necessarily contains that defect's text — measured ~8 hits in one session, mostly inside the verification probes themselves.

## Planted defect text (documentation only)

The string FAILED appears here as an example in prose: operators used to
search for FAILED and treat every hit as a live status. That is the
use-vs-mention failure this kit exists to stop.

Inline example of a status field (not a live record): `{"status": "FAILED"}`

Fenced example of a live-looking record:

```json
{
  "status": "FAILED",
  "job_id": "docs-only"
}
```

None of the FAILED tokens in this file are a typed live status. They are
MENTIONED.
