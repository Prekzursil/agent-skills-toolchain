#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

DEFAULT_HOST = os.environ.get('HEXSTRIKE_HOST', '127.0.0.1')
DEFAULT_PORT = int(os.environ.get('HEXSTRIKE_PORT', '8888'))
DEFAULT_START_TIMEOUT = int(os.environ.get('HEXSTRIKE_START_TIMEOUT', '180'))
DEFAULT_POLL_INTERVAL = float(os.environ.get('HEXSTRIKE_POLL_INTERVAL', '1.0'))
DEFAULT_INSTALL_ROOT = Path(os.environ.get('HEXSTRIKE_INSTALL_ROOT', Path.home() / '.local' / 'opt' / 'hexstrike-ai'))


def install_root() -> Path:
    return DEFAULT_INSTALL_ROOT


def server_url(host: str, port: int) -> str:
    return f'http://{host}:{port}'


def health_url(host: str, port: int) -> str:
    return f'{server_url(host, port)}/health'


def port_open(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(1.0)
        return sock.connect_ex((host, port)) == 0


def healthy(host: str, port: int) -> bool:
    try:
        with urllib.request.urlopen(health_url(host, port), timeout=30) as response:
            body = response.read().decode('utf-8', errors='replace')
        payload = json.loads(body)
        return payload.get('status') == 'healthy'
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return False


def spawn_server(host: str, port: int) -> None:
    root = install_root()
    python_exe = root / '.venv' / 'Scripts' / 'python.exe'
    server_script = root / 'hexstrike_server.py'
    logs_dir = root / 'logs'
    logs_dir.mkdir(parents=True, exist_ok=True)
    stdout_handle = (logs_dir / 'server.stdout.log').open('ab')
    stderr_handle = (logs_dir / 'server.stderr.log').open('ab')
    env = os.environ.copy()
    env['HEXSTRIKE_HOST'] = host
    env['HEXSTRIKE_PORT'] = str(port)
    env['PYTHONIOENCODING'] = 'utf-8'
    env['PYTHONUTF8'] = '1'
    kwargs = {
        'cwd': str(root),
        'env': env,
        'stdin': subprocess.DEVNULL,
        'stdout': stdout_handle,
        'stderr': stderr_handle,
        'close_fds': True,
    }
    if os.name == 'nt':
        kwargs['creationflags'] = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
    subprocess.Popen([str(python_exe), str(server_script)], **kwargs)


def ensure_server(host: str, port: int) -> None:
    if not port_open(host, port):
        spawn_server(host, port)
    deadline = time.time() + DEFAULT_START_TIMEOUT
    while time.time() < deadline:
        if healthy(host, port) or port_open(host, port):
            return
        time.sleep(DEFAULT_POLL_INTERVAL)
    raise RuntimeError(f'HexStrike server did not start at {host}:{port} within {DEFAULT_START_TIMEOUT}s')


def read_framed_message() -> dict | None:
    header = b''
    while b'\r\n\r\n' not in header:
        chunk = sys.stdin.buffer.read(1)
        if not chunk:
            return None
        header += chunk
    raw_headers, _ = header.split(b'\r\n\r\n', 1)
    content_length = None
    for line in raw_headers.decode('ascii', errors='replace').split('\r\n'):
        if line.lower().startswith('content-length:'):
            content_length = int(line.split(':', 1)[1].strip())
            break
    if content_length is None:
        raise RuntimeError('missing Content-Length header')
    body = sys.stdin.buffer.read(content_length)
    return json.loads(body.decode('utf-8'))


def write_framed_message(payload: dict) -> None:
    data = json.dumps(payload, separators=(',', ':')).encode('utf-8')
    sys.stdout.buffer.write(f'Content-Length: {len(data)}\r\n\r\n'.encode('ascii'))
    sys.stdout.buffer.write(data)
    sys.stdout.buffer.flush()


def relay_child_stdout(child: subprocess.Popen[str]) -> None:
    assert child.stdout is not None
    for line in child.stdout:
        stripped = line.strip()
        if not stripped:
            continue
        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError:
            continue
        write_framed_message(payload)


def relay_child_stderr(child: subprocess.Popen[str]) -> None:
    assert child.stderr is not None
    for line in child.stderr:
        sys.stderr.write(line)
        sys.stderr.flush()


def main() -> int:
    root = install_root()
    if not root.exists():
        raise SystemExit(f'HexStrike install root not found: {root}')
    host = DEFAULT_HOST
    port = DEFAULT_PORT
    python_exe = root / '.venv' / 'Scripts' / 'python.exe'
    mcp_script = root / 'hexstrike_mcp.py'
    ensure_server(host, port)
    env = os.environ.copy()
    env['PYTHONIOENCODING'] = 'utf-8'
    env['PYTHONUTF8'] = '1'
    child = subprocess.Popen(
        [str(python_exe), str(mcp_script), '--server', server_url(host, port), *sys.argv[1:]],
        cwd=str(root),
        env=env,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )
    threading.Thread(target=relay_child_stdout, args=(child,), daemon=True).start()
    threading.Thread(target=relay_child_stderr, args=(child,), daemon=True).start()
    try:
        while True:
            message = read_framed_message()
            if message is None:
                break
            if child.stdin is None:
                raise RuntimeError('child stdin unavailable')
            child.stdin.write(json.dumps(message, separators=(',', ':')) + '\n')
            child.stdin.flush()
    finally:
        if child.poll() is None:
            child.terminate()
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                child.kill()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
