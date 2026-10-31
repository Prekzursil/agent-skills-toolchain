"""Pre-fix subject: delivered := path.exists(). Empty files count as green."""


def is_delivered(path) -> bool:
    return path.exists()
