"""Refuse URLs that are not public http/https hosts."""

from __future__ import annotations

import ipaddress
import socket
from collections.abc import Callable
from urllib.parse import urlsplit

Resolver = Callable[[str], list[str]]


class UnsafeUrlError(ValueError):
    """Raised when a URL is not a public http/https address."""


def system_resolver(host: str) -> list[str]:
    """Resolve a hostname to IP strings using the system resolver.

    Args:
        host: Hostname to resolve.

    Returns:
        All resolved IP addresses.

    Raises:
        UnsafeUrlError: If the host cannot be resolved.
    """
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as exc:
        raise UnsafeUrlError(f"cannot resolve {host}") from exc
    return [str(info[4][0]) for info in infos]


def check_public_url(url: str, resolver: Resolver = system_resolver) -> str:
    """Validate that a URL is http/https and resolves only to public addresses.

    Args:
        url: URL to check.
        resolver: Function mapping a hostname to IP strings (injectable for tests).

    Returns:
        The same URL, if safe.

    Raises:
        UnsafeUrlError: If the scheme, host or any resolved address is not allowed.
    """
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https"):
        raise UnsafeUrlError(f"scheme not allowed: {parts.scheme!r}")
    host = parts.hostname
    if not host:
        raise UnsafeUrlError("missing host")
    try:
        addrs = [host] if ipaddress.ip_address(host) else []
    except ValueError:
        addrs = resolver(host)
    if not addrs:
        raise UnsafeUrlError(f"no addresses for {host}")
    for addr in addrs:
        ip = ipaddress.ip_address(addr)
        if not ip.is_global:
            raise UnsafeUrlError(f"non-public address for {host}: {addr}")
    return url
