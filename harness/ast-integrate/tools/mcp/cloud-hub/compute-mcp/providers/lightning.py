#!/usr/bin/env python3
"""Lightning AI adapter -- Studios via the in-process ``lightning_sdk``.

Unlike RunPod/OVH (HTTP), Lightning is driven through its Python SDK in-process,
imported LAZILY (like the cloud-hub ``lightning-mcp`` wrapper) so the module
enumerates even when ``lightning-sdk`` is absent; a call then returns a clear
install/auth hint. The resolved account credentials
(``LIGHTNING_USER_ID``/``LIGHTNING_API_KEY``) are pushed into the environment
for the duration of each SDK call and restored afterwards, so a named-account
call cannot leak creds into the next one.

Studios bill by the second while a machine is attached -- ``compute_teardown``
stops (or, with ``terminate=True``, deletes) them.
"""

from __future__ import annotations

import contextlib
import os

import envelope
import handles

_KNOWN_MACHINES = [
    "CPU",
    "T4",
    "L4",
    "A10G",
    "L40S",
    "A100_X_8",
    "H100_X_8",
]


def _sdk():
    """Import ``lightning_sdk`` lazily -> (module, error_message)."""
    try:
        import lightning_sdk  # noqa: PLC0415  (lazy on purpose)

        return lightning_sdk, ""
    except Exception as exc:  # noqa: BLE001
        return None, (
            "lightning_sdk not available; `pip install lightning-sdk` and set "
            f"LIGHTNING_USER_ID + LIGHTNING_API_KEY ({exc})"
        )


@contextlib.contextmanager
def _auth(env: dict):
    """Temporarily export the resolved Lightning creds, then restore."""
    keys = ("LIGHTNING_USER_ID", "LIGHTNING_API_KEY")
    saved = {k: os.environ.get(k) for k in keys}
    try:
        for k in keys:
            if env.get(k):
                os.environ[k] = env[k]
        yield
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def _ref(handle: handles.Handle) -> tuple[str, str]:
    """Split a lightning handle ident into (name, teamspace)."""
    parts = handle.parts
    if len(parts) >= 2:
        return parts[-1], parts[0]
    return (parts[0] if parts else ""), ""


def _studio(sdk, name: str, teamspace: str, *, create_ok: bool = False):
    """Look up a Studio. LOOKUP-ONLY by default - only ``provision`` may create.

    ``lightning_sdk.Studio.__init__`` defaults to ``create_ok=True``, so an
    unqualified construction CREATES a Studio whenever the name does not resolve.
    Inherited by the read/lookup verbs that is a silent mutation: a typo in a
    ``status``/``exec``/``push``/``teardown`` handle conjures a persistent Studio and
    ``status`` then reports ``ok=True, state=...`` for a resource the caller never
    had. Defaulting to ``create_ok=False`` turns that into the ``ValueError`` the SDK
    raises for a missing Studio, which each caller already maps to an error envelope.

    RESIDUAL, deliberately NOT handled here: for an EXISTING RUNNING Studio the SDK
    calls ``self._setup()`` - which starts a 30s keepalive daemon - from the
    ``existing_studio is not None`` branch, BEFORE it ever consults ``create_ok``
    (lightning_sdk v2026.07.22 ``studio.py``). So ``create_ok=False`` does NOT stop a
    read from defeating autosleep on a running paid Studio. The only suppression the
    SDK offers is the private ``Studio._skip_setup`` thread-local; using it needs a
    decision this adapter cannot make alone (this repo does not pin lightning-sdk, so
    a private thread-local could vanish on any bump). Track it separately.
    """
    return sdk.Studio(name, teamspace=teamspace or None, create_ok=create_ok)


def provision(env: dict, spec: dict, dry_run: bool) -> dict:
    """Start a Studio on a machine (bills by the second)."""
    name = spec.get("name", "")
    machine = spec.get("gpu") or "CPU"
    teamspace = spec.get("teamspace", "")
    if not name:
        return envelope.err("lightning", "provision needs name=<studio>")
    ident = f"{teamspace}/{name}" if teamspace else name
    handle = handles.make("lightning", ident, "studio")
    if dry_run:
        return envelope.dry_run(
            "lightning",
            "provision",
            {"studio": name, "machine": machine, "teamspace": teamspace},
            handle=handle.format(),
        )
    sdk, err = _sdk()
    if err:
        return envelope.err("lightning", err)
    try:
        with _auth(env):
            # provision is the ONE verb whose intent is to bring a Studio into
            # existence, so it is the only caller allowed to create.
            studio = _studio(sdk, name, teamspace, create_ok=True)
            studio.start(machine=getattr(sdk.Machine, machine, machine))
            state = str(getattr(studio, "status", "started"))
    except Exception as exc:  # noqa: BLE001
        return envelope.err("lightning", f"studio start failed: {exc}")
    return envelope.ok(
        "lightning", handle=handle.format(), kind="studio", id=name, state=state
    )


def exec_(env: dict, handle: handles.Handle, command: str) -> dict:
    """Run a command inside a started Studio (``Studio.run``)."""
    sdk, err = _sdk()
    if err:
        return envelope.err("lightning", err)
    name, teamspace = _ref(handle)
    try:
        with _auth(env):
            out = _studio(sdk, name, teamspace).run(command)
    except Exception as exc:  # noqa: BLE001
        return envelope.err(
            "lightning", f"studio run failed: {exc}", handle=handle.format()
        )
    return envelope.ok(
        "lightning",
        handle=handle.format(),
        stdout=str(out)[:8000],
        stderr="",
        exit_code=0,
    )


def push(env: dict, handle: handles.Handle, local_path: str, remote_path: str) -> dict:
    """Upload a local file into a started Studio (``Studio.upload_file``)."""
    sdk, err = _sdk()
    if err:
        return envelope.err("lightning", err)
    name, teamspace = _ref(handle)
    try:
        with _auth(env):
            _studio(sdk, name, teamspace).upload_file(
                local_path, remote_path or None, progress_bar=False
            )
    except Exception as exc:  # noqa: BLE001
        return envelope.err(
            "lightning", f"upload failed: {exc}", handle=handle.format()
        )
    return envelope.ok(
        "lightning",
        handle=handle.format(),
        mechanism="upload_file",
        direction="push",
        remote_path=remote_path or None,
    )


def pull(env: dict, handle: handles.Handle, remote_path: str, local_path: str) -> dict:
    """Honest gap: the SDK has no file download (use an rclone remote/UI)."""
    return envelope.ok(
        "lightning",
        handle=handle.format(),
        mechanism="none",
        direction="pull",
        downloaded=False,
        note="Lightning SDK has no file download; use an rclone remote "
        "(via=rclone) or the Studio UI to pull files.",
    )


def status(env: dict, handle: handles.Handle) -> dict:
    """Report a Studio's status."""
    sdk, err = _sdk()
    if err:
        return envelope.err("lightning", err)
    name, teamspace = _ref(handle)
    try:
        with _auth(env):
            state = str(getattr(_studio(sdk, name, teamspace), "status", "unknown"))
    except Exception as exc:  # noqa: BLE001
        return envelope.err(
            "lightning", f"studio status failed: {exc}", handle=handle.format()
        )
    return envelope.ok(
        "lightning", handle=handle.format(), kind="studio", id=name, state=state
    )


def ls(env: dict, opts: dict) -> dict:
    """Best-effort: list a teamspace's studios (needs teamspace=)."""
    teamspace = opts.get("teamspace", "")
    if not teamspace:
        return envelope.ok(
            "lightning",
            kind="studio",
            items=[],
            note="pass teamspace=<name> to list studios, or use the dashboard.",
        )
    sdk, err = _sdk()
    if err:
        return envelope.err("lightning", err)
    try:
        with _auth(env):
            studios = getattr(sdk.Teamspace(name=teamspace), "studios", []) or []
            names = [str(getattr(s, "name", s)) for s in studios]
    except Exception as exc:  # noqa: BLE001
        return envelope.err("lightning", f"list studios failed: {exc}")
    return envelope.ok("lightning", kind="studio", count=len(names), items=names)


def catalog(env: dict, opts: dict) -> dict:
    """List Studio machine (GPU) types from the SDK (or a known fallback)."""
    sdk, err = _sdk()
    if err:
        return envelope.ok("lightning", kind="machine", items=_KNOWN_MACHINES, note=err)
    machines = sorted(m for m in dir(sdk.Machine) if m.isupper())
    return envelope.ok("lightning", kind="machine", items=machines or _KNOWN_MACHINES)


def cost(env: dict, opts: dict) -> dict:
    """Lightning exposes cost only on its dashboard -- honest note."""
    return envelope.ok(
        "lightning",
        balance=None,
        currency=None,
        spend_per_hr=None,
        note="Lightning AI reports credits/usage on its dashboard; there is no "
        "public balance API. Studios bill by the second while running.",
    )


def teardown(
    env: dict, handle: handles.Handle, terminate: bool, confirm: bool, dry_run: bool
) -> dict:
    """Stop (``Studio.stop``) or delete (``Studio.delete``) a Studio."""
    name, teamspace = _ref(handle)
    action = "terminate" if terminate else "stop"
    if dry_run:
        return envelope.dry_run(
            "lightning", action, {"studio": name, "teamspace": teamspace}
        )
    if terminate and not confirm:
        return envelope.needs_confirm(
            "lightning", "terminate", {"studio": name, "teamspace": teamspace}
        )
    sdk, err = _sdk()
    if err:
        return envelope.err("lightning", err)
    try:
        with _auth(env):
            studio = _studio(sdk, name, teamspace)
            if terminate:
                studio.delete()
            else:
                studio.stop()
    except Exception as exc:  # noqa: BLE001
        return envelope.err(
            "lightning", f"{action} failed: {exc}", handle=handle.format()
        )
    return envelope.ok(
        "lightning",
        handle=handle.format(),
        state="terminated" if terminate else "stopped",
    )
