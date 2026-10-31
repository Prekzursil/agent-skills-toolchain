"""IMP-0264 negative-control fixture: a topology that bypasses the kernel.

Deliberately NOT under tools/council/topology/ so the live audit of the real
topology modules stays silent; the probe points the source audit at this file
and requires the direct-write findings to fire.
"""


def run(plan, participants, events):
    for participant in participants:
        # direct attribute store on the participant output object
        participant.output = "TURN canned"
        # direct append to the kernel event log, skipping the recorded turn path
        events.append({"kind": "TURN", "participant_id": participant.id})
    outputs = {}
    outputs["alice"] = participant.output
    return outputs
