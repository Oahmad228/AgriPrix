"""Per-visitor rate limiting (ENF-05): protects the public demo against abuse.

Who is limited: the real visitor. Behind the HTTPS reverse proxy (the only public entry
point; the API port is bound to 127.0.0.1 or the internal Docker network), the client
address comes from the X-Forwarded-For header the proxy sets. Calls made by the dashboard
inside the Docker network carry no such header and come from a private address: they are
internal service traffic, already bounded by the dashboard's cache, and are not limited;
otherwise every dashboard visitor would share one quota.

Every business route is decorated with ``@limited``. The SlowAPI *middleware* is not used:
with the FastAPI/Starlette versions pinned in requirements.lock it cannot resolve the route
of a request and silently exempts everything (found by tests/integration/test_api.py).
"""

from __future__ import annotations

import ipaddress
from contextvars import ContextVar

from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request

from src.config import get_settings

current_request: ContextVar[Request | None] = ContextVar("current_request", default=None)


def client_key(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return get_remote_address(request)


def is_internal_call() -> bool:
    """True for service-to-service calls (no proxy header, private source address)."""
    request = current_request.get()
    if request is None or request.headers.get("x-forwarded-for") or request.client is None:
        return False
    try:
        address = ipaddress.ip_address(request.client.host)
    except ValueError:
        return False
    return address.is_private or address.is_loopback


limiter = Limiter(key_func=client_key)
limited = limiter.limit(get_settings().api_rate_limit, exempt_when=is_internal_call)
