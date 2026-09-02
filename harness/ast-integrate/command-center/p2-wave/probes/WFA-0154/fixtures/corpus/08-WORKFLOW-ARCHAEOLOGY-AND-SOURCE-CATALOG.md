# 08 Workflow archaeology and source catalog

H-executed-corpus candidates are reconstructed from recorded runs, not from saved workflow files.

DEFINE `replay.stage-sequence`
A reconstructed blueprint is replayed against its transcript by comparing stage sequence, gates, and stopping point. A mismatch cites the transcript record id and the stage index of first divergence.
