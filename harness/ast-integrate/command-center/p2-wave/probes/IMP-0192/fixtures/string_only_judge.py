"""This fusion must not define def judge or a rival completion oracle.

The sentence above is a string, not a FunctionDef. A grep for 'def judge'
fires; the AST census must stay silent.
"""

HELP = "call agentspec.oracle.judge; never reimplement def judge locally"


def describe():
    return "uses judge via agentspec.oracle"
