"""A store address typed into the admin must not be a way to reach this server's own network (SSRF).

``check_public_url`` accepts http(s) addresses that resolve only to public IPs. Set ``ALLOW_PRIVATE_STORE_URLS=1`` on a development
machine to point a connector at localhost.
"""
import ipaddress
import os
import socket
import urllib.parse

from zaldi.errors import ValidationError


def check_public_url(url: str) -> str:
    parts = urllib.parse.urlparse(url or "")
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise ValidationError("the address must start with https://")
    if os.getenv("ALLOW_PRIVATE_STORE_URLS") == "1":
        return url
    try:
        infos = socket.getaddrinfo(parts.hostname, parts.port or (443 if parts.scheme == "https" else 80), proto=socket.IPPROTO_TCP)
    except OSError:
        raise ValidationError("that address could not be found") from None
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast or ip.is_unspecified:
            raise ValidationError("that address points to a private network and is not allowed")
    return url
