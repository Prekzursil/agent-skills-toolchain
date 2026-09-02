"""Council presets: named, inheritable council configurations.

Submodules: ``store`` (``PresetStore`` with canonical hashing, key reordering and fidelity
checks), ``catalog`` (the on-disk preset catalog and ``ensure_catalog``) and ``inherit``
(parent/child resolution, including the rule that a child may not weaken its parent's
evidence requirement).  Import the submodule you need; nothing is re-exported here.
"""
