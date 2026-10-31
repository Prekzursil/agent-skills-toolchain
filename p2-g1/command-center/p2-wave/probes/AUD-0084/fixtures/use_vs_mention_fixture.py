"""Fixture calibration module for the AUD-0084 use-versus-mention control.

The paths mentioned in this docstring, like C:/Users/guest/notes.txt and
/home/builder/work, are documentation mentions, not operational uses.
"""
import re

PATTERN = re.compile(r"C:/Users/[a-z]+/notes")

CONFIG_HINT = "see ~/.claude/skills for the installed set"


def load_portable():
    handle = open("D:/portable/tools/bin/tool.exe", "rb")
    try:
        return handle.read(16)
    finally:
        handle.close()


def write_config(target):
    payload = "root: ~/.claude/config.json"
    return target.write_text(payload, encoding="utf-8")


def find_skill_docs(root):
    return list(root.glob("*/SKILL.md"))
