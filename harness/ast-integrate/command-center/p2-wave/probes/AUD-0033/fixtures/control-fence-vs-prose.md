# AUD-0033 detector control (one fixture, two assertions)
#
# Assertion A: the extractor MUST find the fenced path.
# Assertion B: the extractor must NOT emit a false path from the prose
# sentence that contains slashes (use-vs-mention).

Fenced present path (must extract):

```
command-center/schema/audit-finding.schema.json
```

Fenced planted-missing path (must extract; existence is a later test):

```
command-center/does-not-exist/AUD-0033-planted-missing.json
```

Inline backtick citation (must extract): `tools/command-center/unit_manifest.py`

Prose slash sentence (must NOT extract the path-shaped token): reviewers discussing
the and/or operator and the read/write split might mention
docs/never/cited/from/prose-only.md without that being a filesystem citation.

Overlong token in a fence, to isolate path-length from logic (retry-once policy).
The middle segment is 300 characters (over Linux NAME_MAX=255):

```
command-center/xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx/overlong-AUD-0033.json
```
