"""Use-versus-mention control.

This file documents the forbidden fork. A grep on the name
``reduce_completion`` would treat the docstring as a call site.
Import-graph / AST analysis must stay silent: there is no Import,
no ImportFrom, and no FunctionDef.

Example of a FORBIDDEN second implementation (prose only):

    def reduce_completion(receipt):
        return receipt.get("exit_code") == 0

    FANIN_ROLE = "rogue-documented-only"
"""

NOTE = (
    "from lib.completion_reducer import reduce_completion  # mention, not an import"
)
