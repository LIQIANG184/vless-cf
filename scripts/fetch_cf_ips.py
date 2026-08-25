#!/usr/bin/env python3
"""Fetch IPv4 Cloudflare candidates from cf.vvhan.com's public API."""

from __future__ import annotations

import argparse
import ipaddress
import json
from pathlib import Path
from urllib.request import Request, urlopen

DEFAULT_URL = "https://api.4ce.cn/api/bestCFIP"


def fetch_candidates(url: str, timeout: float) -> list[str]:
    request = Request(
        url,
        headers={"Accept": "application/json", "User-Agent": "vless-cf/1.0"},
    )
    with urlopen(request, timeout=timeout) as response:
        payload = json.load(response)

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
