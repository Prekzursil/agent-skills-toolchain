#!/usr/bin/env python3
"""msgrpc TEST DOUBLE (rpc-dispatch lane verification, 2026-09-30).

Protocol-accurate stand-in for msfrpcd's msgpack-RPC wire: request frames
[0, msgid, method, params] -> response frames [1, msgid, result, error].
Implements auth.login / core.version / core.stats. This exists ONLY to prove
the gateway's kind=msgrpc client transport (framing, auth, method routing)
round-trips for real; the real msfrpcd is not installed on this box. Binds
127.0.0.1 ONLY. Kill after use.
"""
import socket
import socketserver
import threading

import msgpack

HOST, PORT = "127.0.0.1", 55553
TOKEN = "deadbeefcafe1234507"  # test double token; no real secret


class Handler(socketserver.BaseRequestHandler):
    def handle(self):
        unpacker = msgpack.Unpacker(raw=False)
        while True:
            try:
                chunk = self.request.recv(65536)
            except OSError:
                return
            if not chunk:
                return
            unpacker.feed(chunk)
            for msg in unpacker:
                if not (isinstance(msg, (list, tuple)) and len(msg) == 4):
                    continue
                typ, msgid, method, params = msg
                if typ != 0:
                    continue
                result, error = self.dispatch(method, params)
                self.request.sendall(
                    msgpack.packb([1, msgid, result, error], use_bin_type=True))

    @staticmethod
    def dispatch(method, params):
        if method == "auth.login":
            if len(params) >= 2 and params[0] == "msf" and params[1] == "msf-test-pass":
                return TOKEN, None
            return None, {"error_class": "MsfError",
                          "error_message": "Invalid User Credentials"}
        if not (params and params[0] == TOKEN):
            return None, {"error_class": "MsfError",
                          "error_message": "Invalid Authentication Token"}
        if method == "core.version":
            return {"version": "6.3.42-testdouble", "ruby": "3.3.5 x64-mswin64",
                    "api": "1.0"}, None
        if method == "core.stats":
            return {"active": 0, "sessions": 0, "jobs": 0,
                    "note": "msgrpc test double"}, None
        return None, {"error_class": "NoMethodError",
                      "error_message": "undefined method '%s'" % method}


class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


if __name__ == "__main__":
    with Server((HOST, PORT), Handler) as srv:
        print("msgrpc test double on %s:%d" % (HOST, PORT), flush=True)
        srv.serve_forever()
