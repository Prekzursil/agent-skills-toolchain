# 11 Council specification

Council-level seats. These are a cross-check, not a candidate-role source.
A role that appears only here belongs in the council bucket, not on a workflow candidate.

## Role `owner-veto`

mandate: estate owner may veto any council outcome
tool_access: none
speaking_rights: yes
vote_rights: yes
veto_rights: yes

The owner-veto seat belongs to the council runtime. No workflow candidate defines it.

## Role `juror`

mandate: cast equal-weight ballots on council motions
tool_access: none
speaking_rights: yes
vote_rights: yes
veto_rights: no

Juror is a council protocol seat. A candidate that never names it must not inherit it.
