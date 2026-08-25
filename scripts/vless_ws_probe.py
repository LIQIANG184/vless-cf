#!/usr/bin/env python3
"""Probe a VLESS-over-WebSocket Worker end to end with an HTTP target."""

from __future__ import annotations

import argparse
import base64
import hashlib
import ipaddress
import socket
import ssl
import struct
import time
import uuid


def read_until(sock: socket.socket, marker: bytes, limit: int = 65536) -> bytes:
    data = b""
    while marker not in data and len(data) < limit:
        chunk = sock.recv(4096)
        if not chunk:
            break
        data += chunk
    return data


def ws_connect(ip: str, host: str, port: int, timeout: float) -> socket.socket:
    sock = socket.socket(socket.AF_INET6 if ":" in ip else socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    sock.connect((ip, port))
    key = base64.b64encode(b"vless-ws-probe-key").decode()
    request = (
        f"GET /?ed=2048 HTTP/1.1\r\n"
        f"Host: {host}\r\n"
        "Connection: Upgrade\r\n"
        "Upgrade: websocket\r\n"
        "Sec-WebSocket-Version: 13\r\n"
        f"Sec-WebSocket-Key: {key}\r\n\r\n"
    )
    sock.sendall(request.encode("ascii"))
    response = read_until(sock, b"\r\n\r\n")
    first = response.split(b"\r\n", 1)[0]
    if b" 101 " not in first:
        raise OSError(f"WebSocket handshake failed: {first.decode('latin1', 'replace')}")
    return sock


def ws_send(sock: socket.socket, payload: bytes) -> None:
    mask = b"zedprobe"
    masked = bytes(value ^ mask[index % 4] for index, value in enumerate(payload))
    length = len(payload)
    if length < 126:
        header = bytes([0x81, 0x80 | length])
    elif length < 65536:
        header = bytes([0x81, 0x80 | 126]) + struct.pack("!H", length)
    else:
        header = bytes([0x81, 0x80 | 127]) + struct.pack("!Q", length)
    sock.sendall(header + mask + masked)


def ws_recv(sock: socket.socket) -> tuple[int, bytes]:
    header = sock.recv(2)
    if len(header) != 2:
        raise OSError("WebSocket closed before response")
    opcode = header[0] & 0x0F
    length = header[1] & 0x7F
    if length == 126:
        length = struct.unpack("!H", sock.recv(2))[0]
    elif length == 127:
        length = struct.unpack("!Q", sock.recv(8))[0]
    masked = header[1] & 0x80
    mask = sock.recv(4) if masked else b""
    data = b""
    while len(data) < length:
        chunk = sock.recv(length - len(data))
        if not chunk:
            raise OSError("WebSocket closed during response")
        data += chunk
    if masked:
        data = bytes(value ^ mask[index % 4] for index, value in enumerate(data))
    return opcode, data


def vless_header(user_uuid: str, target_host: str, target_port: int) -> bytes:
    target = target_host.encode("idna")
    if len(target) > 255:
        raise ValueError("target hostname is too long")
    return (
        b"\x00"
        + uuid.UUID(user_uuid).bytes
        + b"\x00\x01"
        + struct.pack("!H", target_port)
        + b"\x02"
        + bytes([len(target)])
        + target
    )


def probe(ip: str, args: argparse.Namespace) -> None:
    started = time.perf_counter()
    sock = ws_connect(ip, args.host, args.port, args.timeout)
    try:
        request = (
            f"GET /generate_204 HTTP/1.1\r\n"
            f"Host: {args.target}\r\n"
            "Connection: close\r\n"
            "User-Agent: vless-ws-probe/1.0\r\n\r\n"
        ).encode("ascii")
        ws_send(sock, vless_header(args.uuid, args.target, args.target_port) + request)
        opcode, data = ws_recv(sock)
        elapsed = (time.perf_counter() - started) * 1000
        if opcode == 0x8:
            raise OSError("Worker closed WebSocket")
        if len(data) >= 2 and data[0] == 0:
            data = data[2:]
        first_line = data.split(b"\r\n", 1)[0].decode("latin1", "replace")
        print(f"OK   {ip}:{args.port} {elapsed:.1f} ms {first_line}")
    finally:
        sock.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", required=True)
    parser.add_argument("--ip", action="append", required=True)
    parser.add_argument("--port", type=int, default=80)
    parser.add_argument("--uuid", required=True)
    parser.add_argument("--target", default="example.com")
    parser.add_argument("--target-port", type=int, default=80)
    parser.add_argument("--timeout", type=float, default=10)
    args = parser.parse_args()
    for ip in args.ip:
        try:
            probe(str(ipaddress.ip_address(ip)), args)
        except (OSError, TimeoutError, ValueError) as error:
            print(f"FAIL {ip}:{args.port} {error}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
