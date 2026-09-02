"""Planted deliberation loop. The AST probe must FIRE on this file."""


def vote(participant):
    return {"id": participant, "choice": "yes"}


def run_round(seats):
    ballots = []
    for participant in seats:
        ballots.append(vote(participant))
    return ballots


def deliberate(question):
    seats = ["a", "b", "c"]
    transcript = []
    for round_i in range(3):
        transcript.append(run_round(seats))
    return {"question": question, "transcript": transcript}
