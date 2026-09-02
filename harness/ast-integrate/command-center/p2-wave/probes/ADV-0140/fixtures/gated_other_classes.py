"""Gated scratch sinks for the four non-publish classes.

These exist so each action class has an enumerated path the effect classifier
can name. They are not production code. TRANSPORT / DESTROY / WRITE / GH are
fake-sink substitution points. Credential rotation is deliberately absent.
"""
from __future__ import annotations

import shutil
import urllib.request
from pathlib import Path

TRANSPORT = urllib.request.urlopen


def human_checkpoint(question: str) -> str:
    return "approved"


def charge_inference_api(prompt: str = "ping") -> object:
    human_checkpoint("approve unbounded paid external spend?")
    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=prompt.encode("utf-8"),
        method="POST",
    )
    return TRANSPORT(req)


def purge_user_data(user_data_root: str = "/var/user_data/home") -> None:
    human_checkpoint("approve deleting user data?")
    shutil.rmtree(user_data_root)


def widen_egress_allowlist(path: str = "net-allowlist.json", body: str = "{}") -> None:
    human_checkpoint("approve changing security posture?")
    Path("net-allowlist.json").write_text(body, encoding="utf-8")


def create_public_repository(name: str = "public-example") -> object:
    human_checkpoint("approve creating a public repository?")
    req = urllib.request.Request(
        "https://api.github.com/user/repos",
        data=b'{"name":"%s","private":false}' % name.encode("ascii"),
        method="POST",
    )
    return TRANSPORT(req)
