"""Fixture payload for hello-skill 1.0.0.

Deliberately trivial. The package exists to be published, installed, verified and revoked; if
this file ever needs to be interesting, the test it supports has stopped being a control.
"""


def greet(name: str = "world") -> str:
    return f"hello, {name} -- from hello-skill 1.0.0"
