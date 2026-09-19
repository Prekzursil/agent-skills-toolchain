"""Feature #2 -- ``biomni_fetch_artifact``: real result-file download.

The online claude.ai Biomni Lab returns result files as *names + sizes* with
blocked/expiring S3 links, so bytes cannot be pulled programmatically -- for
that backend we surface the ``biomni_url`` deep link + a ``display_instruction``
telling the user to download in the Lab UI, and record a best-effort attempt.
For self-host backends (databricks Unity Catalog Volume, or the OSS agent's
local workdir) we pull the actual bytes, persist them under the hub data dir,
hash them, and register the artifact in the store. FAILS CLOSED.
"""

from __future__ import annotations

import base64
import hashlib
import os
from typing import TYPE_CHECKING, Any

from .backend import CAP_BIOMNI_URL, CAP_FETCH_BYTES

if TYPE_CHECKING:
    from fastmcp import FastMCP

    from .context import HubContext


def register(mcp: FastMCP, ctx: HubContext) -> None:
    @mcp.tool()
    async def biomni_fetch_artifact(
        name: str,
        run_id: str | None = None,
        session_id: str | None = None,
        backend: str | None = None,
        dest_dir: str | None = None,
        max_inline_bytes: int = 262_144,
    ) -> dict[str, Any]:
        """Download a named result file for a run, backend-aware.

        Args:
            name: result-file name (from ``list_result_files``).
            run_id: hub run id; used to resolve backend/session and to attach
                the stored artifact record.
            session_id: Biomni session id (needed if ``run_id`` is unknown).
            backend: override the backend; default resolves from the run/env.
            dest_dir: where to write bytes (default ``<data_dir>/artifacts/<run>``).
            max_inline_bytes: also return base64 bytes inline if <= this size.

        Returns a status of ``downloaded`` | ``url_only`` | ``not_found``.
        """
        await ctx.store.ensure_schema()
        run = await ctx.store.get_run(run_id) if run_id else None
        chosen = backend or (run.get("backend") if run else None)
        sess = session_id or (run.get("session_id") if run else None)
        client = ctx.backends.resolve(chosen)
        caps = client.capabilities()

        # Self-host path: pull real bytes.
        if CAP_FETCH_BYTES in caps and sess:
            data = await client.fetch_result_bytes(sess, name)
            if data is None:
                return {"status": "not_found", "name": name, "backend": client.name}
            out_dir = dest_dir or os.path.join(
                ctx.data_dir, "artifacts", run_id or sess or "adhoc"
            )
            os.makedirs(out_dir, exist_ok=True)
            path = os.path.join(out_dir, os.path.basename(name))
            with open(path, "wb") as fh:
                fh.write(data)
            digest = hashlib.sha256(data).hexdigest()
            aid = await ctx.store.add_artifact(
                run_id=run_id, name=name, size=len(data), local_path=path,
                sha256=digest, source="download",
            )
            result: dict[str, Any] = {
                "status": "downloaded",
                "artifact_id": aid,
                "name": name,
                "backend": client.name,
                "size": len(data),
                "sha256": digest,
                "local_path": path,
            }
            if len(data) <= max_inline_bytes:
                result["bytes_base64"] = base64.b64encode(data).decode("ascii")
            return result

        # Online path: bytes are blocked -> surface the deep link.
        url = None
        if CAP_BIOMNI_URL in caps and sess:
            url = await client.biomni_url(sess)
        await ctx.store.add_artifact(
            run_id=run_id, name=name, url=url, source="url_only",
        )
        return {
            "status": "url_only",
            "name": name,
            "backend": client.name,
            "biomni_url": url,
            "display_instruction": (
                "This backend does not expose downloadable result bytes. Open the "
                "run in the Biomni Lab UI via biomni_url and download the file "
                "there, or re-run on a self-hosted backend (databricks/oss) to "
                "fetch bytes directly."
            ),
        }
