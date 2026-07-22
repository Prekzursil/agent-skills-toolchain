"""ChatGPT Desktop cookie inventory and explicit local export helpers.

Inventory APIs in this module never return cookie values.  Decryption and
secret-bearing export are separate, opt-in operations intended to run as the
same Windows user that owns the ChatGPT Desktop profile.
"""

from __future__ import annotations

import base64
import ctypes
import hashlib
import json
import os
import sqlite3
import subprocess
import tempfile
from ctypes import wintypes
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping


RESULT_DIR = Path("/dbfs/tmp/crcp-auth-session/results")
NEXTAUTH_COOKIE = "__Secure-next-auth.session-token"
_CHROME_EPOCH_OFFSET_SECONDS = 11_644_473_600


def default_user_data_dir() -> Path:
    """Return the measured ChatGPT Desktop Chromium user-data directory."""
    appdata = os.environ.get("APPDATA")
    if appdata:
        return Path(appdata) / "Codex" / "web" / "Codex"
    if os.name == "nt":
        return Path.home() / "AppData" / "Roaming" / "Codex" / "web" / "Codex"
    raise RuntimeError("APPDATA_REQUIRED: run on Windows or set APPDATA explicitly")


def cookie_db_paths(user_data: Path) -> list[Path]:
    """Return the two measured Desktop Cookies SQLite locations."""
    profile = Path(user_data) / "Default"
    return [
        profile / "Network" / "Cookies",
        profile / "Partitions" / "codex-browser-app" / "Network" / "Cookies",
    ]


def _chrome_time_to_unix(value: Any) -> float | None:
    try:
        micros = int(value)
    except (TypeError, ValueError, OverflowError):
        return None
    if micros <= 0:
        return None
    return micros / 1_000_000 - _CHROME_EPOCH_OFFSET_SECONDS


def _sqlite_uri(path: Path, *, immutable: bool = False) -> str:
    mode = "mode=ro"
    if immutable:
        mode += "&immutable=1"
    return f"file:{path.resolve().as_posix()}?{mode}"


def _is_lock_error(exc: BaseException) -> bool:
    text = str(exc).lower()
    winerror = getattr(exc, "winerror", None)
    return winerror in (32, 33) or any(
        marker in text
        for marker in (
            "sharing violation",
            "used by another process",
            "database is locked",
            "unable to open database file",
            "disk i/o error",
            "permission denied",
        )
    )


def _shared_read_bytes(path: Path) -> bytes:
    """Best-effort shared read of a locked file (Windows CreateFile share flags)."""
    if os.name != "nt":
        return Path(path).read_bytes()
    import ctypes
    from ctypes import wintypes

    generic_read = 0x80000000
    share_all = 0x00000001 | 0x00000002 | 0x00000004
    open_existing = 3
    file_attribute_normal = 0x80
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    create = k32.CreateFileW
    create.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    ]
    create.restype = wintypes.HANDLE
    handle = create(
        str(path),
        generic_read,
        share_all,
        None,
        open_existing,
        file_attribute_normal,
        None,
    )
    invalid = wintypes.HANDLE(-1).value
    if handle in (invalid, 0, 0xFFFFFFFF):
        raise OSError(ctypes.get_last_error(), f"CreateFile failed for {path}")
    try:
        size = wintypes.LARGE_INTEGER()
        if not k32.GetFileSizeEx(handle, ctypes.byref(size)):
            raise OSError(ctypes.get_last_error(), "GetFileSizeEx failed")
        n = int(size.QuadPart)
        buf = (ctypes.c_char * n)()
        read = wintypes.DWORD()
        if not k32.ReadFile(handle, buf, n, ctypes.byref(read), None):
            raise OSError(ctypes.get_last_error(), "ReadFile failed")
        return bytes(buf[: read.value])
    finally:
        k32.CloseHandle(handle)


def _inventory_open(db_path: Path) -> list[dict[str, Any]]:
    path = Path(db_path)
    last_error: BaseException | None = None
    for immutable in (False, True):
        try:
            connection = sqlite3.connect(
                _sqlite_uri(path, immutable=immutable), uri=True
            )
            try:
                connection.execute("PRAGMA query_only=ON")
                columns = {
                    str(row[1])
                    for row in connection.execute("PRAGMA table_info(cookies)")
                }
                required = {"host_key", "name", "path", "encrypted_value"}
                missing = sorted(required - columns)
                if missing:
                    raise ValueError(
                        f"cookies table missing columns: {', '.join(missing)}"
                    )

                def column(name: str, fallback: str = "0") -> str:
                    return name if name in columns else fallback

                query = f"""
                    SELECT host_key, name, path,
                           {column("is_secure")} AS is_secure,
                           {column("is_httponly")} AS is_httponly,
                           {column("samesite", "-1")} AS samesite,
                           {column("is_persistent")} AS is_persistent,
                           {column("expires_utc")} AS expires_utc,
                           length(encrypted_value) AS encrypted_value_len
                      FROM cookies
                     ORDER BY host_key, name, path
                """
                rows = list(connection.execute(query))
            finally:
                connection.close()
            return [
                {
                    "host_key": str(row[0]),
                    "name": str(row[1]),
                    "path": str(row[2]),
                    "secure": bool(row[3]),
                    "httpOnly": bool(row[4]),
                    "samesite": int(row[5]) if row[5] is not None else -1,
                    "persistent": bool(row[6]),
                    "expires_unix": _chrome_time_to_unix(row[7]),
                    "encrypted_value_len": int(row[8] or 0),
                }
                for row in rows
            ]
        except (OSError, sqlite3.Error) as exc:
            last_error = exc
            continue
    assert last_error is not None
    raise last_error


def inventory_cookies(db_path: Path) -> list[dict[str, Any]]:
    """Read cookie metadata, using shared-read or VSS on Windows if locked.

    No plaintext or encrypted cookie bytes are included in the result.
    """
    source = Path(db_path)
    try:
        return _inventory_open(source)
    except (OSError, sqlite3.Error) as exc:
        if os.name != "nt" or not _is_lock_error(exc):
            raise
        work = Path(tempfile.mkdtemp(prefix="crcp-cookie-ro-"))
        try:
            candidate = work / "Cookies.db"
            try:
                candidate.write_bytes(_shared_read_bytes(source))
            except OSError:
                vss_raw = work / "Cookies.vss"
                copy_via_vss(source, vss_raw)
                # Second copy into a plain path so SQLite never opens the VSS dest.
                candidate.write_bytes(vss_raw.read_bytes())
            return _inventory_open(candidate)
        finally:
            # Best-effort cleanup; ignore lingering Windows locks.
            for child in sorted(work.rglob("*"), reverse=True):
                try:
                    if child.is_file():
                        child.unlink()
                    else:
                        child.rmdir()
                except OSError:
                    pass
            try:
                work.rmdir()
            except OSError:
                pass


def copy_via_vss(src: Path, dest: Path) -> Path:
    """Copy a locked Windows file through a temporary Volume Shadow Copy.

    Creating snapshots normally requires an elevated Windows process.  The
    temporary shadow is deleted after the copy.  Failures use stable error
    prefixes so an operator can distinguish a lock from unavailable VSS.
    """
    if os.name != "nt":
        raise RuntimeError("VSS_REQUIRED: Volume Shadow Copy is Windows-only")
    source = Path(src).resolve()
    destination = Path(dest)
    if not source.drive:
        raise RuntimeError("VSS_REQUIRED: source must be on a local Windows volume")
    destination.parent.mkdir(parents=True, exist_ok=True)

    def _ps_single_quote(value: str) -> str:
        return "'" + value.replace("'", "''") + "'"

    # Embed paths — `-Command` does not forward trailing argv into $args.
    # GLOBALROOT device paths need cmd copy, not Copy-Item.
    script = f"""
$ErrorActionPreference = 'Stop'
$source = [System.IO.Path]::GetFullPath({_ps_single_quote(str(source))})
$destination = [System.IO.Path]::GetFullPath({_ps_single_quote(str(destination))})
$root = [System.IO.Path]::GetPathRoot($source)
if (-not $root) {{ throw 'VSS_REQUIRED: empty volume root' }}
$relative = $source.Substring($root.Length)
$created = Invoke-CimMethod -ClassName Win32_ShadowCopy -MethodName Create -Arguments @{{Volume=$root; Context='ClientAccessible'}}
if ($created.ReturnValue -ne 0) {{ throw "Win32_ShadowCopy Create returned $($created.ReturnValue)" }}
$shadow = Get-CimInstance -ClassName Win32_ShadowCopy | Where-Object {{ $_.ID -eq $created.ShadowID }}
if (-not $shadow) {{ throw 'VSS_REQUIRED: shadow instance missing' }}
try {{
    $snapshotPath = $shadow.DeviceObject.TrimEnd('\\') + '\\' + $relative
    $null = New-Item -ItemType Directory -Force -Path (Split-Path -Parent $destination)
    cmd /c copy /y `"$snapshotPath`" `"$destination`"
    if (-not (Test-Path -LiteralPath $destination)) {{ throw 'FILE_LOCKED: snapshot copy produced no file' }}
}} finally {{
    if ($null -ne $shadow) {{ Remove-CimInstance -InputObject $shadow | Out-Null }}
}}
"""
    try:
        completed = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                script,
            ],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError(f"VSS_REQUIRED: {type(exc).__name__}") from exc
    if completed.returncode != 0 or not destination.is_file():
        # PowerShell output can contain sensitive filesystem context; do not echo it.
        detail = (completed.stderr or completed.stdout or "").strip().splitlines()
        hint = detail[-1][:160] if detail else "snapshot copy failed"
        raise RuntimeError(f"FILE_LOCKED: VSS_REQUIRED ({hint})")
    return destination


class _DataBlob(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_ubyte))]


def _dpapi_unprotect(payload: bytes) -> bytes | None:
    if os.name != "nt" or not payload:
        return None
    buffer = ctypes.create_string_buffer(payload)
    incoming = _DataBlob(
        len(payload), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte))
    )
    outgoing = _DataBlob()
    crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    crypt32.CryptUnprotectData.argtypes = [
        ctypes.POINTER(_DataBlob),
        ctypes.c_void_p,
        ctypes.POINTER(_DataBlob),
        ctypes.c_void_p,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(_DataBlob),
    ]
    crypt32.CryptUnprotectData.restype = wintypes.BOOL
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    kernel32.LocalFree.restype = ctypes.c_void_p
    if not crypt32.CryptUnprotectData(
        ctypes.byref(incoming), None, None, None, None, 0, ctypes.byref(outgoing)
    ):
        return None
    try:
        return ctypes.string_at(outgoing.pbData, outgoing.cbData)
    finally:
        kernel32.LocalFree(outgoing.pbData)


def _read_oscrypt_key(local_state: Path) -> bytes | None:
    try:
        state = json.loads(Path(local_state).read_text(encoding="utf-8"))
        encoded = state["os_crypt"]["encrypted_key"]
        wrapped = base64.b64decode(encoded, validate=True)
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None
    if wrapped.startswith(b"DPAPI"):
        wrapped = wrapped[5:]
    return _dpapi_unprotect(wrapped)


def _aes_gcm_decrypt(
    key: bytes, nonce: bytes, ciphertext: bytes, tag: bytes
) -> bytes | None:
    """Decrypt AES-GCM with the Windows CNG API, without third-party packages."""
    if os.name != "nt":
        return None
    bcrypt = ctypes.WinDLL("bcrypt", use_last_error=True)
    byte_pointer = ctypes.POINTER(ctypes.c_ubyte)
    bcrypt.BCryptOpenAlgorithmProvider.argtypes = [
        ctypes.POINTER(ctypes.c_void_p),
        wintypes.LPCWSTR,
        wintypes.LPCWSTR,
        wintypes.ULONG,
    ]
    bcrypt.BCryptOpenAlgorithmProvider.restype = ctypes.c_long
    bcrypt.BCryptSetProperty.argtypes = [
        ctypes.c_void_p,
        wintypes.LPCWSTR,
        byte_pointer,
        wintypes.ULONG,
        wintypes.ULONG,
    ]
    bcrypt.BCryptSetProperty.restype = ctypes.c_long
    bcrypt.BCryptGetProperty.argtypes = [
        ctypes.c_void_p,
        wintypes.LPCWSTR,
        byte_pointer,
        wintypes.ULONG,
        ctypes.POINTER(wintypes.ULONG),
        wintypes.ULONG,
    ]
    bcrypt.BCryptGetProperty.restype = ctypes.c_long
    bcrypt.BCryptGenerateSymmetricKey.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_void_p),
        byte_pointer,
        wintypes.ULONG,
        byte_pointer,
        wintypes.ULONG,
        wintypes.ULONG,
    ]
    bcrypt.BCryptGenerateSymmetricKey.restype = ctypes.c_long
    bcrypt.BCryptDecrypt.argtypes = [
        ctypes.c_void_p,
        byte_pointer,
        wintypes.ULONG,
        ctypes.c_void_p,
        byte_pointer,
        wintypes.ULONG,
        byte_pointer,
        wintypes.ULONG,
        ctypes.POINTER(wintypes.ULONG),
        wintypes.ULONG,
    ]
    bcrypt.BCryptDecrypt.restype = ctypes.c_long
    bcrypt.BCryptDestroyKey.argtypes = [ctypes.c_void_p]
    bcrypt.BCryptDestroyKey.restype = ctypes.c_long
    bcrypt.BCryptCloseAlgorithmProvider.argtypes = [ctypes.c_void_p, wintypes.ULONG]
    bcrypt.BCryptCloseAlgorithmProvider.restype = ctypes.c_long
    handle = ctypes.c_void_p()
    if bcrypt.BCryptOpenAlgorithmProvider(ctypes.byref(handle), "AES", None, 0) != 0:
        return None
    key_handle = ctypes.c_void_p()
    key_object = None
    try:
        mode = ctypes.create_unicode_buffer("ChainingModeGCM")
        if (
            bcrypt.BCryptSetProperty(
                handle,
                "ChainingMode",
                ctypes.cast(mode, byte_pointer),
                ctypes.sizeof(mode),
                0,
            )
            != 0
        ):
            return None
        size = wintypes.DWORD()
        used = wintypes.DWORD()
        if (
            bcrypt.BCryptGetProperty(
                handle,
                "ObjectLength",
                ctypes.cast(ctypes.byref(size), byte_pointer),
                ctypes.sizeof(size),
                ctypes.byref(used),
                0,
            )
            != 0
        ):
            return None
        key_object = ctypes.create_string_buffer(size.value)
        key_buffer = ctypes.create_string_buffer(key)
        if (
            bcrypt.BCryptGenerateSymmetricKey(
                handle,
                ctypes.byref(key_handle),
                ctypes.cast(key_object, byte_pointer),
                size.value,
                ctypes.cast(key_buffer, byte_pointer),
                len(key),
                0,
            )
            != 0
        ):
            return None

        class AuthInfo(ctypes.Structure):
            _fields_ = [
                ("cbSize", wintypes.ULONG),
                ("dwInfoVersion", wintypes.ULONG),
                ("pbNonce", ctypes.POINTER(ctypes.c_ubyte)),
                ("cbNonce", wintypes.ULONG),
                ("pbAuthData", ctypes.POINTER(ctypes.c_ubyte)),
                ("cbAuthData", wintypes.ULONG),
                ("pbTag", ctypes.POINTER(ctypes.c_ubyte)),
                ("cbTag", wintypes.ULONG),
                ("pbMacContext", ctypes.POINTER(ctypes.c_ubyte)),
                ("cbMacContext", wintypes.ULONG),
                ("cbAAD", wintypes.ULONG),
                ("cbData", ctypes.c_ulonglong),
                ("dwFlags", wintypes.ULONG),
            ]

        nonce_buffer = ctypes.create_string_buffer(nonce)
        tag_buffer = ctypes.create_string_buffer(tag)
        auth = AuthInfo()
        auth.cbSize = ctypes.sizeof(AuthInfo)
        auth.dwInfoVersion = 1
        auth.pbNonce = ctypes.cast(nonce_buffer, ctypes.POINTER(ctypes.c_ubyte))
        auth.cbNonce = len(nonce)
        auth.pbTag = ctypes.cast(tag_buffer, ctypes.POINTER(ctypes.c_ubyte))
        auth.cbTag = len(tag)
        encrypted = ctypes.create_string_buffer(ciphertext)
        output = ctypes.create_string_buffer(len(ciphertext))
        output_size = wintypes.ULONG()
        status = bcrypt.BCryptDecrypt(
            key_handle,
            ctypes.cast(encrypted, byte_pointer),
            len(ciphertext),
            ctypes.byref(auth),
            None,
            0,
            ctypes.cast(output, byte_pointer),
            len(output),
            ctypes.byref(output_size),
            0,
        )
        return output.raw[: output_size.value] if status == 0 else None
    except (OSError, ValueError, TypeError):
        return None
    finally:
        if key_handle:
            bcrypt.BCryptDestroyKey(key_handle)
        bcrypt.BCryptCloseAlgorithmProvider(handle, 0)


def decrypt_cookie_value(
    encrypted_value: bytes, local_state: Path, *, allow_decrypt: bool = False
) -> bytes | None:
    """Best-effort Windows OSCrypt decrypt; explicit opt-in is mandatory."""
    if not allow_decrypt:
        raise PermissionError("allow_decrypt=True is required")
    if os.name != "nt":
        return None
    blob = bytes(encrypted_value)
    if blob.startswith((b"v10", b"v11")):
        if len(blob) < 3 + 12 + 16:
            return None
        key = _read_oscrypt_key(Path(local_state))
        if not key:
            return None
        body = blob[3:]
        return _aes_gcm_decrypt(key, body[:12], body[12:-16], body[-16:])
    return _dpapi_unprotect(blob)


def _secret_output_allowed(out_path: Path) -> Path:
    destination = Path(out_path).resolve()
    result_root = RESULT_DIR.resolve()
    if destination == result_root or result_root in destination.parents:
        raise PermissionError(
            "secret material may not be written under CRCP result directory"
        )
    destination.parent.mkdir(parents=True, exist_ok=True)
    return destination


def export_cookies_json(
    cookies_decrypted: Iterable[Mapping[str, Any]],
    out_path: Path,
    *,
    allow_decrypt: bool = False,
) -> Path:
    """Write decrypted cookies for import, only with explicit authorization."""
    if not allow_decrypt:
        raise PermissionError("allow_decrypt=True is required")
    destination = _secret_output_allowed(Path(out_path))
    records = [dict(cookie) for cookie in cookies_decrypted]
    destination.write_text(json.dumps(records, indent=2) + "\n", encoding="utf-8")
    return destination


def export_cookies_netscape(
    cookies_decrypted: Iterable[Mapping[str, Any]],
    out_path: Path,
    *,
    allow_decrypt: bool = False,
) -> Path:
    """Write a Netscape cookie file, only with explicit authorization."""
    if not allow_decrypt:
        raise PermissionError("allow_decrypt=True is required")
    destination = _secret_output_allowed(Path(out_path))
    lines = [
        "# Netscape HTTP Cookie File",
        "# Generated locally by CRCP; contains secrets.",
    ]
    for cookie in cookies_decrypted:
        host = str(cookie["host_key"])
        include_subdomains = "TRUE" if host.startswith(".") else "FALSE"
        secure = "TRUE" if cookie.get("secure") else "FALSE"
        expires = int(cookie.get("expires_unix") or 0)
        value = cookie.get("value", "")
        if isinstance(value, bytes):
            value = value.decode("utf-8", "surrogateescape")
        fields = [
            host,
            include_subdomains,
            str(cookie.get("path", "/")),
            secure,
            str(expires),
            str(cookie["name"]),
            str(value),
        ]
        if any("\t" in field or "\n" in field or "\r" in field for field in fields):
            raise ValueError("cookie fields cannot contain tabs or newlines")
        lines.append("\t".join(fields))
    destination.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return destination


def format_cdp_cookie(cookie_dict: Mapping[str, Any]) -> dict[str, Any]:
    """Convert a decrypted cookie mapping to Network.setCookie parameters."""
    if "name" not in cookie_dict or "value" not in cookie_dict:
        raise ValueError("CDP cookie requires name and value")
    value = cookie_dict["value"]
    if isinstance(value, bytes):
        value = value.decode("utf-8", "surrogateescape")
    domain = str(cookie_dict.get("domain") or cookie_dict.get("host_key") or "")
    secure = bool(cookie_dict.get("secure", cookie_dict.get("is_secure", True)))
    result: dict[str, Any] = {
        "name": str(cookie_dict["name"]),
        "value": str(value),
        "path": str(cookie_dict.get("path") or "/"),
        "secure": secure,
        "httpOnly": bool(
            cookie_dict.get("httpOnly", cookie_dict.get("is_httponly", False))
        ),
    }
    # Prefer url; domain is optional when url is set (works better for CDP).
    host = domain.lstrip(".") if domain else "chatgpt.com"
    result["url"] = f"{'https' if secure else 'http'}://{host}/"
    if domain:
        result["domain"] = domain
    same_site = cookie_dict.get("sameSite", cookie_dict.get("samesite"))
    same_site_map = {-1: None, 0: "None", 1: "Lax", 2: "Strict"}
    mapped = (
        same_site_map.get(same_site, same_site)
        if isinstance(same_site, int)
        else same_site
    )
    if mapped in ("Strict", "Lax", "None"):
        result["sameSite"] = mapped
    expires = cookie_dict.get("expires", cookie_dict.get("expires_unix"))
    if expires is not None and float(expires) > 0:
        result["expires"] = float(expires)
    if not result.get("domain") and not result.get("url"):
        raise ValueError("CDP cookie requires domain/host_key or url")
    return result


def format_edge_import_instructions() -> str:
    """Return operator guidance without embedding any cookie values."""
    return (
        "Close ChatGPT Desktop before reading its profile when possible. Export on the "
        "same Windows user account because DPAPI is user-bound. Start a separate Edge "
        "profile with remote debugging enabled, connect a trusted local CDP client, and "
        "send each format_cdp_cookie() result to Network.setCookie. Do not paste cookies "
        "into logs, shells, tickets, or the CRCP results directory. Cookie mirroring is "
        "partial when the NextAuth session cookie is absent; complete normal web SSO in "
        "that Edge profile if chatgpt.com still requests login."
    )


def _summarize(inventories: list[tuple[Path, list[dict[str, Any]]]]) -> dict[str, Any]:
    cookies = [cookie for _, rows in inventories for cookie in rows]
    names = sorted({str(cookie["name"]) for cookie in cookies})
    return {
        "status": "ok" if NEXTAUTH_COOKIE in names else "partial_without_nextauth",
        "cookie_count": len(cookies),
        "hosts": sorted({str(cookie["host_key"]) for cookie in cookies}),
        "names": names,
        "paths": [str(path) for path, _ in inventories],
    }


def run_mirror_inventory() -> dict[str, Any]:
    """Inventory existing Desktop cookie databases and return metadata only."""
    user_data = default_user_data_dir()
    inventories: list[tuple[Path, list[dict[str, Any]]]] = []
    missing: list[str] = []
    errors: list[dict[str, str]] = []
    for path in cookie_db_paths(user_data):
        if not path.is_file():
            missing.append(str(path))
            continue
        try:
            inventories.append((path, inventory_cookies(path)))
        except Exception as exc:  # soft-fail per DB so CLI still returns JSON
            errors.append(
                {
                    "path": str(path),
                    "error": f"{type(exc).__name__}: {exc}"[:240],
                }
            )
    report = _summarize(inventories)
    report["user_data"] = str(user_data)
    report["missing_paths"] = missing
    report["errors"] = errors
    report["ok"] = not errors or bool(inventories)
    if not inventories and not errors:
        report["status"] = "not_found"
    elif not inventories and errors:
        report["status"] = "error"
        report["ok"] = False
    return report


def _decrypted_records(
    db_path: Path, local_state: Path
) -> tuple[list[dict[str, Any]], int]:
    metadata = inventory_cookies(db_path)

    def read_encrypted(path: Path) -> list[tuple[Any, ...]]:
        with sqlite3.connect(_sqlite_uri(path), uri=True) as connection:
            columns = {
                str(row[1]) for row in connection.execute("PRAGMA table_info(cookies)")
            }
            plaintext = "value" if "value" in columns else "''"
            return list(
                connection.execute(
                    f"SELECT host_key, name, path, encrypted_value, {plaintext} FROM cookies "
                    "ORDER BY host_key, name, path"
                )
            )

    try:
        encrypted = read_encrypted(db_path)
    except (OSError, sqlite3.Error) as exc:
        if os.name != "nt" or not _is_lock_error(exc):
            raise
        with tempfile.TemporaryDirectory(prefix="crcp-cookie-vss-") as temporary:
            snapshot = copy_via_vss(db_path, Path(temporary) / "Cookies")
            encrypted = read_encrypted(snapshot)
    lookup = {(row["host_key"], row["name"], row["path"]): row for row in metadata}
    records: list[dict[str, Any]] = []
    failures = 0
    for host, name, path, blob, plaintext in encrypted:
        if blob:
            value = decrypt_cookie_value(bytes(blob), local_state, allow_decrypt=True)
        elif isinstance(plaintext, str) and plaintext:
            value = plaintext.encode("utf-8")
        else:
            value = None
        if value is None:
            failures += 1
            continue
        host_digest = hashlib.sha256(str(host).encode("utf-8")).digest()
        if value.startswith(host_digest):
            value = value[len(host_digest) :]
        record = dict(lookup[(str(host), str(name), str(path))])
        record["value"] = value.decode("utf-8", "surrogateescape")
        records.append(record)
    return records, failures


def run_mirror_export(out_dir: Path, *, decrypt: bool = False) -> dict[str, Any]:
    """Write metadata inventory, or an explicitly requested local secret export.

    The returned mapping contains counts and paths only, never cookie values.
    """
    output = Path(out_dir)
    output.mkdir(parents=True, exist_ok=True)
    user_data = default_user_data_dir()
    existing = [path for path in cookie_db_paths(user_data) if path.is_file()]
    inventories = [(path, inventory_cookies(path)) for path in existing]
    summary = _summarize(inventories)
    summary["decrypt_requested"] = decrypt
    if not decrypt:
        metadata_path = output / "cookie_inventory.json"
        payload = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "summary": summary,
            "cookies": [
                dict(cookie, source=str(path))
                for path, rows in inventories
                for cookie in rows
            ],
        }
        metadata_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        summary["export_path"] = str(metadata_path)
        summary["export_kind"] = "metadata_only"
        return summary

    # Validate the secret destination before decryption happens.
    secret_path = _secret_output_allowed(output / "cookies.json")
    records: list[dict[str, Any]] = []
    failures = 0
    for path in existing:
        decrypted, failed = _decrypted_records(path, user_data / "Local State")
        records.extend(decrypted)
        failures += failed
    export_cookies_json(records, secret_path, allow_decrypt=True)
    summary.update(
        {
            "export_path": str(secret_path),
            "export_kind": "decrypted_json",
            "decrypted_count": len(records),
            "decrypt_failed_count": failures,
        }
    )
    return summary
