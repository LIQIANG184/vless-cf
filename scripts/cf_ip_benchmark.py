#!/usr/bin/env python3
"""Benchmark Cloudflare edge IPs for a specific Worker hostname.

The test keeps the Worker hostname as TLS SNI and HTTP Host while connecting
TCP to each candidate IP. This is more useful than ping for selecting IPs for
VLESS + WebSocket + TLS configurations.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import ipaddress
import json
import socket
import ssl
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class Result:
    ip: str
    port: int
    ok: bool
    latency_ms: float | None = None
    status: str = ""
    error: str = ""


def parse_candidates(values: Iterable[str], max_hosts: int) -> list[str]:
    candidates: list[str] = []
    seen: set[str] = set()

    for raw in values:
        value = raw.strip()
        if not value or value.startswith("#"):
            continue
        try:
            network = ipaddress.ip_network(value, strict=False)
            hosts = network.hosts()
            for index, address in enumerate(hosts):
                if index >= max_hosts:
                    raise ValueError(
                        f"CIDR {value} contains more than {max_hosts} usable addresses; "
                        "split it or increase --max-hosts"
                    )
                text = str(address)
                if text not in seen:
                    seen.add(text)
                    candidates.append(text)
        except ValueError:
            try:
                address = str(ipaddress.ip_address(value))
            except ValueError as error:
                raise ValueError(f"invalid IP or CIDR: {value}") from error
            if address not in seen:
                seen.add(address)
                candidates.append(address)

    return candidates


def read_candidates(input_path: str | None, cidrs: list[str]) -> list[str]:
    values = list(cidrs)
    if input_path:
        if input_path == "-":
            values.extend(sys.stdin.read().splitlines())
        else:
            values.extend(Path(input_path).read_text(encoding="utf-8").splitlines())
    if not values:
        raise ValueError("provide --input, --cidr, or pipe candidates on stdin with --input -")
    return values


def open_connection(ip: str, port: int, host: str, timeout: float) -> socket.socket:
    family = socket.AF_INET6 if ":" in ip else socket.AF_INET
    sock = socket.socket(family, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    sock.connect((ip, port))

    if port in {443, 8443, 2053, 2083, 2087, 2096}:
        context = ssl.create_default_context()
        wrapped = context.wrap_socket(sock, server_hostname=host)
        wrapped.settimeout(timeout)
        return wrapped
    return sock


def request_worker(sock: socket.socket, host: str, path: str, websocket: bool) -> str:
    if websocket:
        request = (
            f"GET {path} HTTP/1.1\r\n"
            f"Host: {host}\r\n"
            "Connection: Upgrade\r\n"
            "Upgrade: websocket\r\n"
            "Sec-WebSocket-Version: 13\r\n"
            "Sec-WebSocket-Key: Y2YtaXAtYmVuY2htYXJrLWtleQ==\r\n"
            "User-Agent: cf-ip-benchmark/1.0\r\n\r\n"
        )
    else:
        request = (
            f"GET {path} HTTP/1.1\r\n"
            f"Host: {host}\r\n"
            "Connection: close\r\n"
            "User-Agent: cf-ip-benchmark/1.0\r\n\r\n"
        )

    sock.sendall(request.encode("ascii"))
    response = b""
    while b"\r\n\r\n" not in response and len(response) < 16384:
        chunk = sock.recv(4096)
        if not chunk:
            break
        response += chunk

    first_line = response.split(b"\r\n", 1)[0].decode("latin1", errors="replace")
    parts = first_line.split()
    if len(parts) < 2 or not parts[1].isdigit():
        raise OSError(f"invalid HTTP response: {first_line or 'empty response'}")
    return f"{parts[0]} {parts[1]}"


def benchmark(ip: str, port: int, host: str, path: str, timeout: float, websocket: bool) -> Result:
    started = time.perf_counter()
    sock: socket.socket | None = None
    try:
        sock = open_connection(ip, port, host, timeout)
        status = request_worker(sock, host, path, websocket)
        code = int(status.rsplit(" ", 1)[-1])
        expected = 101 if websocket else 200
        if code != expected:
            return Result(ip, port, False, elapsed_ms(started), status, f"expected HTTP {expected}")
        return Result(ip, port, True, elapsed_ms(started), status)
    except (OSError, ssl.SSLError, TimeoutError) as error:
        return Result(ip, port, False, elapsed_ms(started), error=short_error(error))
    finally:
        if sock is not None:
            try:
                sock.close()
            except OSError:
                pass


def elapsed_ms(started: float) -> float:
    return round((time.perf_counter() - started) * 1000, 1)


def short_error(error: BaseException) -> str:
    text = str(error).replace("\n", " ").strip()
    return text or error.__class__.__name__


def quote(value: object) -> str:
    return json.dumps(str(value), ensure_ascii=False)


def render_clash(results: list[Result], host: str, uuid: str, path: str) -> str:
    lines = [
        "proxies:",
    ]
    names: list[str] = []
    for index, result in enumerate(results, start=1):
        name = f"CF-{index:02d}-{result.ip}:{result.port}"
        names.append(name)
        tls = result.port in {443, 8443, 2053, 2083, 2087, 2096}
        lines.extend(
            [
                f"  - name: {quote(name)}",
                "    type: vless",
                f"    server: {quote(result.ip)}",
                f"    port: {result.port}",
                f"    uuid: {quote(uuid)}",
                "    udp: true",
                f"    tls: {str(tls).lower()}",
            ]
        )
        if tls:
            lines.append(f"    servername: {quote(host)}")
        lines.extend(
            [
                "    network: ws",
                "    ws-opts:",
                f"      path: {quote(path)}",
                "      headers:",
                f"        Host: {quote(host)}",
            ]
        )

    lines.extend(
        [
            "proxy-groups:",
            '  - name: "CF-BEST"',
            "    type: url-test",
            '    url: http://connectivitycheck.gstatic.com/generate_204',
            "    interval: 300",
            "    proxies:",
        ]
    )
    lines.extend(f"      - {quote(name)}" for name in names)
    lines.extend(["rules:", "  - MATCH,CF-BEST", ""])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", required=True, help="Worker hostname used for SNI and Host")
    parser.add_argument("--input", help="candidate file, or - for stdin")
    parser.add_argument("--cidr", action="append", default=[], help="IP or CIDR; repeatable")
    parser.add_argument("--port", action="append", type=int, help="port; repeatable (default: 443)")
    parser.add_argument(
        "--path",
        help="WebSocket or HTTP path (default: /?ed=2048, or /cf with --http)",
    )
    parser.add_argument("--timeout", type=float, default=3.0, help="per-IP timeout in seconds")
    parser.add_argument("--workers", type=int, default=32, help="parallel connections")
    parser.add_argument("--max-hosts", type=int, default=65536, help="maximum addresses expanded per CIDR")
    parser.add_argument("--http", action="store_true", help="test HTTP 200 instead of WebSocket HTTP 101")
    parser.add_argument("--limit", type=int, default=20, help="number of successful results to print")
    parser.add_argument("--uuid", help="UUID; generate Clash YAML when supplied")
    parser.add_argument("--clash-output", help="write successful results as Clash YAML")
    args = parser.parse_args()

    try:
        raw_values = read_candidates(args.input, args.cidr)
        candidates = parse_candidates(raw_values, args.max_hosts)
    except (OSError, ValueError) as error:
        parser.error(str(error))

    if not candidates:
        parser.error("no candidate IPs found")
    ports = args.port or [443]
    if args.clash_output and not args.uuid:
        parser.error("--clash-output requires --uuid")

    websocket = not args.http
    path = args.path or ("/?ed=2048" if websocket else "/cf")
    jobs = [(ip, port) for ip in candidates for port in ports]
    print(f"Testing {len(jobs)} endpoint(s) against {args.host} ...", file=sys.stderr)

    results: list[Result] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
        futures = [
            executor.submit(benchmark, ip, port, args.host, path, args.timeout, websocket)
            for ip, port in jobs
        ]
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            results.append(result)
            if result.ok:
                print(f"OK   {result.ip}:{result.port:<5} {result.latency_ms:>7.1f} ms {result.status}")

    successful = sorted(
        (result for result in results if result.ok),
        key=lambda result: result.latency_ms or float("inf"),
    )[: max(0, args.limit)]
    failed = len(results) - len([result for result in results if result.ok])
    print(f"\n{len(successful)} usable, {failed} failed", file=sys.stderr)

    if not successful:
        print("Failed endpoints:", file=sys.stderr)
        for result in sorted(results, key=lambda item: (item.ip, item.port)):
            detail = result.error or f"{result.status} ({'expected HTTP 101' if websocket else 'expected HTTP 200'})"
            print(f"  {result.ip}:{result.port} - {detail}", file=sys.stderr)
        print("No usable IP found. Try --http to separate Worker reachability from WS checks.", file=sys.stderr)
        return 2

    if args.clash_output:
        output = render_clash(successful, args.host, args.uuid, path)
        Path(args.clash_output).write_text(output, encoding="utf-8")
        print(f"Clash config written to {args.clash_output}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
