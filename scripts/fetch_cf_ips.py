#!/usr/bin/env python3
"""Fetch IPv4 Cloudflare candidates from cf.vvhan.com's public API."""

from __future__ import annotations

import argparse
import ipaddress
import json
import subprocess
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

DEFAULT_URL = "https://api.4ce.cn/api/bestCFIP"


def fetch_payload(url: str, timeout: float) -> object:
    request = Request(
        url,
        headers={"Accept": "application/json", "User-Agent": "vless-cf/1.0"},
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            return json.load(response)
    except (OSError, URLError) as python_error:
        try:
            completed = subprocess.run(
                [
                    "curl",
                    "--fail",
                    "--silent",
                    "--show-error",
                    "--location",
                    "--http1.1",
                    "--ipv4",
                    "--retry",
                    "2",
                    "--retry-delay",
                    "1",
                    "--connect-timeout",
                    str(timeout),
                    "--max-time",
                    str(timeout),
                    "-A",
                    "vless-cf/1.0",
                    url,
                ],
                check=True,
                capture_output=True,
                text=True,
                timeout=timeout * 4 + 5,
            )
            return json.loads(completed.stdout)
        except FileNotFoundError as curl_error:
            raise RuntimeError(
                f"Python HTTPS request failed ({python_error}); curl is not installed"
            ) from curl_error
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, json.JSONDecodeError) as curl_error:
            detail = getattr(curl_error, "stderr", "") or str(curl_error)
            raise RuntimeError(
                f"Unable to fetch {url} with Python or curl: {detail.strip()}"
            ) from curl_error


def fetch_candidates(url: str, timeout: float) -> list[str]:
    payload = fetch_payload(url, timeout)
    if not isinstance(payload, dict):
        raise ValueError("API response is not a JSON object")

    groups = payload.get("data", {}).get("v4", {})
    if not isinstance(groups, dict):
        raise ValueError("API response does not contain data.v4 groups")

    candidates: list[str] = []
    seen: set[str] = set()
    for entries in groups.values():
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            value = entry.get("ip")
            try:
                address = str(ipaddress.IPv4Address(value))
            except (TypeError, ValueError):
                continue
            if address not in seen:
                seen.add(address)
                candidates.append(address)

    if not candidates:
        raise ValueError("API response contains no valid IPv4 candidates")
    return candidates


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="cf-ips.txt", help="output candidate file")
    parser.add_argument("--url", default=DEFAULT_URL, help="candidate API URL")
    parser.add_argument("--timeout", type=float, default=20.0, help="HTTP timeout in seconds")
    args = parser.parse_args()

    candidates = fetch_candidates(args.url, args.timeout)
    output = Path(args.output)
    output.write_text("\n".join(candidates) + "\n", encoding="utf-8")
    print(f"Wrote {len(candidates)} unique IPv4 candidate(s) to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
