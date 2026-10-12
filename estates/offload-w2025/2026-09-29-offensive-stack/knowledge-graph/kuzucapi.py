"""kuzucapi.py - ctypes binding for the official prebuilt Kuzu C API on Windows.

Why this exists (2026-09-29): `pip install kuzu` into C:\\Python314 cannot produce
a working module on this box - PyPI publishes no cp314 win_amd64 wheel for any
kuzu release (checked 0.11.0..0.11.3 individually), the sdist fails at extract
time on Windows MAX_PATH, there is no C/C++ toolchain on the VM to build it,
and upstream (kuzudb/kuzu) is archived, so no wheel is coming. The official
v0.11.3 GitHub release ships `libkuzu-windows-x86_64.zip` containing
kuzu_shared.dll + kuzu.h; this module binds that stable C API directly, which
keeps the embedded Kuzu engine (same version, same on-disk format) available
in-process under C:\\Python314. If a future Python gains an official wheel,
swap this module out - kgcore.py only uses the small surface below.

Surface used: open (create/open db), query (returns columns + rows as
strings), close. All cells are rendered with kuzu_value_to_string, so this
binding never needs per-type value extraction.
"""
from __future__ import annotations

import ctypes
import os
import threading
from ctypes import POINTER, Structure, byref, c_bool, c_char_p, c_int, c_uint64, c_void_p

# Official release: https://github.com/kuzudb/kuzu/releases/tag/v0.11.3
# libkuzu-windows-x86_64.zip (sha256 recorded in README.md)
DLL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_dist", "libkuzu", "kuzu_shared.dll")

KUZU_SUCCESS = 0

# --- opaque struct mirrors from kuzu.h (Windows build: no __APPLE__ branch) ---


class SystemConfig(Structure):
    _fields_ = [
        ("buffer_pool_size", c_uint64),
        ("max_num_threads", c_uint64),
        ("enable_compression", c_bool),
        ("read_only", c_bool),
        ("max_db_size", c_uint64),
        ("auto_checkpoint", c_bool),
        ("checkpoint_threshold", c_uint64),
    ]


class CDatabase(Structure):
    _fields_ = [("_database", c_void_p)]


class CConnection(Structure):
    _fields_ = [("_connection", c_void_p)]


class CQueryResult(Structure):
    _fields_ = [("_query_result", c_void_p), ("_is_owned_by_cpp", c_bool)]


class CFlatTuple(Structure):
    _fields_ = [("_flat_tuple", c_void_p), ("_is_owned_by_cpp", c_bool)]


class CValue(Structure):
    _fields_ = [("_value", c_void_p), ("_is_owned_by_cpp", c_bool)]


_LIB = None
_LIB_LOCK = threading.Lock()


def _load_lib(dll_path: str | None = None):
    """Load kuzu_shared.dll once and declare argtypes/restypes."""
    global _LIB
    with _LIB_LOCK:
        if _LIB is not None:
            return _LIB
        path = dll_path or DLL_PATH
        if not os.path.isfile(path):
            raise FileNotFoundError(f"kuzu_shared.dll not found at {path}")
        lib = ctypes.CDLL(path)

        lib.kuzu_default_system_config.restype = SystemConfig
        lib.kuzu_default_system_config.argtypes = []

        lib.kuzu_database_init.restype = c_int
        lib.kuzu_database_init.argtypes = [c_char_p, SystemConfig, POINTER(CDatabase)]
        lib.kuzu_database_destroy.restype = None
        lib.kuzu_database_destroy.argtypes = [POINTER(CDatabase)]

        lib.kuzu_connection_init.restype = c_int
        lib.kuzu_connection_init.argtypes = [POINTER(CDatabase), POINTER(CConnection)]
        lib.kuzu_connection_destroy.restype = None
        lib.kuzu_connection_destroy.argtypes = [POINTER(CConnection)]

        lib.kuzu_connection_query.restype = c_int
        lib.kuzu_connection_query.argtypes = [POINTER(CConnection), c_char_p, POINTER(CQueryResult)]

        lib.kuzu_query_result_is_success.restype = c_bool
        lib.kuzu_query_result_is_success.argtypes = [POINTER(CQueryResult)]
        # OWNED char* returns MUST be c_void_p: with restype=c_char_p ctypes
        # copies into a Python bytes object and the original allocation
        # pointer is lost, making kuzu_destroy_string a heap-corruption bug.
        lib.kuzu_query_result_get_error_message.restype = c_void_p
        lib.kuzu_query_result_get_error_message.argtypes = [POINTER(CQueryResult)]
        lib.kuzu_query_result_get_num_columns.restype = c_uint64
        lib.kuzu_query_result_get_num_columns.argtypes = [POINTER(CQueryResult)]
        lib.kuzu_query_result_get_num_tuples.restype = c_uint64
        lib.kuzu_query_result_get_num_tuples.argtypes = [POINTER(CQueryResult)]
        lib.kuzu_query_result_get_column_name.restype = c_int
        lib.kuzu_query_result_get_column_name.argtypes = [POINTER(CQueryResult), c_uint64, POINTER(c_void_p)]
        lib.kuzu_query_result_has_next.restype = c_bool
        lib.kuzu_query_result_has_next.argtypes = [POINTER(CQueryResult)]
        lib.kuzu_query_result_get_next.restype = c_int
        lib.kuzu_query_result_get_next.argtypes = [POINTER(CQueryResult), POINTER(CFlatTuple)]
        lib.kuzu_query_result_destroy.restype = None
        lib.kuzu_query_result_destroy.argtypes = [POINTER(CQueryResult)]

        lib.kuzu_flat_tuple_get_value.restype = c_int
        lib.kuzu_flat_tuple_get_value.argtypes = [POINTER(CFlatTuple), c_uint64, POINTER(CValue)]
        lib.kuzu_flat_tuple_destroy.restype = None
        lib.kuzu_flat_tuple_destroy.argtypes = [POINTER(CFlatTuple)]

        lib.kuzu_value_to_string.restype = c_void_p  # owned char* - see note above
        lib.kuzu_value_to_string.argtypes = [POINTER(CValue)]
        lib.kuzu_value_destroy.restype = None
        lib.kuzu_value_destroy.argtypes = [POINTER(CValue)]

        lib.kuzu_destroy_string.restype = None
        lib.kuzu_destroy_string.argtypes = [c_void_p]

        _LIB = lib
        return lib


def _take_str(lib, ptr) -> str:
    """Decode a C-API-returned owned char* (c_void_p) and free it with
    kuzu_destroy_string. ctypes.string_at reads the bytes at the original
    allocation - the pointer itself stays valid until we free it."""
    if not ptr:
        return ""
    try:
        return ctypes.string_at(ptr).decode("utf-8", errors="replace")
    finally:
        lib.kuzu_destroy_string(ptr)


class KuzuError(RuntimeError):
    pass


class Database:
    """Embedded Kuzu database (one process-owned handle). Thread-safe queries.

    A single internal Connection is guarded by a lock; Kuzu connections are
    thread-safe, but serializing keeps transaction/scheming races impossible.
    """

    def __init__(self, path: str, read_only: bool = False, buffer_pool_size: int = 0,
                 dll_path: str | None = None):
        self._lib = _load_lib(dll_path)
        lib = self._lib
        self._db = CDatabase()
        cfg = lib.kuzu_default_system_config()
        if buffer_pool_size:
            cfg.buffer_pool_size = buffer_pool_size
        cfg.read_only = bool(read_only)
        st = lib.kuzu_database_init(str(path).encode("utf-8"), cfg, byref(self._db))
        if st != KUZU_SUCCESS:
            raise KuzuError(f"kuzu_database_init failed (state={st}) for {path}")
        self._conn = CConnection()
        st = lib.kuzu_connection_init(byref(self._db), byref(self._conn))
        if st != KUZU_SUCCESS:
            lib.kuzu_database_destroy(byref(self._db))
            raise KuzuError(f"kuzu_connection_init failed (state={st})")
        self._lock = threading.Lock()
        self._closed = False

    def query(self, cypher: str) -> dict:
        """Run one Cypher statement. Returns {ok, columns, rows, num_tuples}
        where rows are lists of string-rendered cells, or {ok, error}.

        Note: the engine returns state=1 for ordinary Cypher errors (binder
        exceptions etc.) but the out-result is still valid and carries the
        error message - so the result is processed regardless of state, and
        KuzuError is raised only when even the message is unavailable."""
        lib = self._lib
        res = CQueryResult()
        with self._lock:
            if self._closed:
                raise KuzuError("database is closed")
            st = lib.kuzu_connection_query(byref(self._conn), cypher.encode("utf-8"), byref(res))
        hard_fail = st != KUZU_SUCCESS
        try:
            if hard_fail and not lib.kuzu_query_result_get_error_message(byref(res)):
                raise KuzuError(f"kuzu_connection_query failed (state={st}) with no error message")
            if not lib.kuzu_query_result_is_success(byref(res)):
                err = _take_str(lib, lib.kuzu_query_result_get_error_message(byref(res)))
                return {"ok": False, "error": err}
            ncol = int(lib.kuzu_query_result_get_num_columns(byref(res)))
            names = []
            for i in range(ncol):
                out = c_void_p()
                if lib.kuzu_query_result_get_column_name(byref(res), i, byref(out)) == KUZU_SUCCESS:
                    names.append(_take_str(lib, out))
                else:
                    names.append(f"col{i}")
            rows = []
            while lib.kuzu_query_result_has_next(byref(res)):
                tup = CFlatTuple()
                if lib.kuzu_query_result_get_next(byref(res), byref(tup)) != KUZU_SUCCESS:
                    break
                try:
                    row = []
                    for i in range(ncol):
                        val = CValue()
                        if lib.kuzu_flat_tuple_get_value(byref(tup), i, byref(val)) != KUZU_SUCCESS:
                            row.append(None)
                            continue
                        try:
                            row.append(_take_str(lib, lib.kuzu_value_to_string(byref(val))))
                        finally:
                            lib.kuzu_value_destroy(byref(val))
                    rows.append(row)
                finally:
                    lib.kuzu_flat_tuple_destroy(byref(tup))
            return {"ok": True, "columns": names, "rows": rows,
                    "num_tuples": int(lib.kuzu_query_result_get_num_tuples(byref(res)))}
        finally:
            lib.kuzu_query_result_destroy(byref(res))

    def close(self):
        with self._lock:
            if self._closed:
                return
            self._closed = True
        self._lib.kuzu_connection_destroy(byref(self._conn))
        self._lib.kuzu_database_destroy(byref(self._db))
