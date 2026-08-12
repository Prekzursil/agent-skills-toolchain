# CNL-0002 -- resolve the measured v1 schema-catalogue non-intersection

This fixture stands in for a genuine council design note. It exists so the text-artifact
gate has a KNOWN-GOOD state to stay silent on; without one, a gate that rejects everything
would score identically to a gate that works. The prose is deliberately varied so the
distinct-character and longest-run checks are not what admits it.

Decision: two schemas plus a typed reference edge, on the falsifiable criterion that a
discriminated union cannot express the 0-of-12 key intersection without a synthetic tag.

SUCCESS:CNL-0002
