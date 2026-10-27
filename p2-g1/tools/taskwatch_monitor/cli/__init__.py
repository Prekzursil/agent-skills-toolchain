"""CLI surface for taskwatch_monitor.

``cli.status`` folds a poll + probe reading into a flat :class:`~cli.status.TaskView`;
``cli.engine`` polls each registered task; ``cli.store`` persists the registry;
``cli.app`` is the stdlib-argparse entrypoint (``register`` / ``list`` / ``status``).
"""
