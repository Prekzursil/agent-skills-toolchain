---
name: patent-fto-search
description: Search patent-extracted chemical structures by SMILES in SureChEMBL,
  continue asynchronous searches, and inspect patent metadata or claims for prior-art
  and FTO triage.
permalink: dqverify-repo-20261013/skills/patent-fto-search/skill
---

# Patent FTO search

Use this skill when a question asks whether a molecule or scaffold appears in patent literature,
requests chemical prior-art leads, or needs an initial freedom-to-operate screen. Use the patent
structure tools instead of treating a PubChem CID lookup as a novelty search.

## Workflow

1. Confirm the query is a valid SMILES and identify whether the whole molecule or a smaller
   commercially meaningful scaffold should be searched.
2. Call `patent_substructure_search`. Keep `structure_limit` and `patent_limit` modest on the
   first pass.
3. When the result is `pending`, call `patent_structure_search_results` with the returned
   `search_id`. Reuse the same ID until it reaches `complete`; do not resubmit the query.
4. Preserve the matched-structure evidence when ranking patent hits. Do not report a patent as a
   match solely because its title sounds relevant.
5. Fetch short-listed records with `patent_metadata`. Set `include_claims=true` for claim review;
   if `claims_truncated` is true, raise `text_char_limit` up to 20000 or inspect the source record.
6. Report publication identifiers, dates, applicants, earliest priority date, family ID, relevant
   claims, and the exact query structure. Separate direct evidence from inference.

## Interpretation rules

- A hit means SureChEMBL associated an extracted structure containing the query subgraph with a
  patent document. It does not establish that a live claim covers the contemplated activity.
- Check claims, family members, jurisdictions, prosecution history, ownership, expiry, and
  current status before making an FTO decision.
- Automated text and image extraction can miss structures or create false positives.
- Markush claims and functional language can cover compounds that were never enumerated as an
  extracted exact structure.
- Provider legal events are leads only. Verify them in the relevant official register.

Stop and state the coverage limit when the structure search is capped, repeatedly fails at the
provider, or the decision depends on legal claim construction. Never label this screen as legal
clearance or a complete novelty opinion.