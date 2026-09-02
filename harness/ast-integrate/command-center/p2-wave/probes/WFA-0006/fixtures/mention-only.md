# WFA-0006 use-vs-mention control

This file merely documents the discovery_only flag. It must not be counted
as a consumer of the three discovery records.

The 08-WORKFLOW-PROVENANCE-AND-LICENSE-GRAPH.json honesty block records discovery_only:true.
The 09-WORKFLOW-BLUEPRINT-LIBRARY.json file self-declares discovery_only:true; it is the input queue, not progress.
The 10-WORKFLOW-MERGE-AND-COMPOSITION-MAPS.json map states no_merge_has_been_performed.
