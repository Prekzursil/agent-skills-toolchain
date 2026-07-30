"""R1: the build/test node gets NO long-lived write token. Push is a SEPARATE, per-unit step using a
short-lived, single-repo installation token. Wiring this into the adoption step is DEFERRED (Roadmap);
the primitives are built + fully tested here."""

from __future__ import annotations

from dataclasses import dataclass

from backends.base import MintedToken


@dataclass(frozen=True)
class AppAuth:
    app_id: str
    installation_id: str
    private_key: str


def mint_push_token(repo: str, auth: AppAuth, _mint_fn=None) -> MintedToken:
    """Mint a ~1h contents:write token scoped to a SINGLE repo. The real path calls the GitHub App
    installation-token API with repositories=[repo.split('/')[1]], permissions={'contents':'write'};
    `_mint_fn` is injected in tests."""
    if _mint_fn is None:
        raise RuntimeError("real mint path requires an injected GitHub App client")
    token, expires_at = _mint_fn(repo, auth)
    return MintedToken(token=token, repo=repo, expires_at=expires_at)


def push_branch(repo: str, branch: str, token: MintedToken, run_cmd) -> bool:
    if token.repo != repo:
        raise ValueError(f"token scoped to {token.repo}, not {repo}")
    url = f"https://x-access-token:{token.token}@github.com/{repo}.git"
    rc, _, _ = run_cmd(["git", "push", url, f"HEAD:{branch}"])
    return rc == 0
