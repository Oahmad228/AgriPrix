"""Rate-limit keys on managed platforms (Render): visitor address and the dashboard's secret."""

import pytest
from src.api import limits
from src.config import get_settings
from starlette.requests import Request


def _request(headers: dict[str, str], client: str = "203.0.113.7") -> Request:
    raw = [(k.lower().encode(), v.encode()) for k, v in headers.items()]
    return Request({"type": "http", "headers": raw, "client": (client, 1234), "path": "/"})


@pytest.fixture
def settings(monkeypatch):
    cfg = get_settings()
    monkeypatch.setattr(cfg, "api_internal_key", "")
    monkeypatch.setattr(cfg, "forwarded_for_position", "first")
    return cfg


def test_visitor_is_the_first_hop_behind_our_own_proxy(settings) -> None:
    assert (
        limits.client_key(_request({"X-Forwarded-For": "198.51.100.1, 10.0.0.2"})) == "198.51.100.1"
    )


def test_visitor_is_the_last_hop_when_the_platform_appends_it(settings) -> None:
    settings.forwarded_for_position = "last"
    # A visitor forging the header cannot choose its key: the platform appends the real address.
    forged = _request({"X-Forwarded-For": "1.2.3.4, 198.51.100.1"})
    assert limits.client_key(forged) == "198.51.100.1"


def test_internal_key_exempts_only_the_exact_secret(settings) -> None:
    settings.api_internal_key = "s3cret-value"
    good = _request({"X-Forwarded-For": "198.51.100.1", "X-Internal-Key": "s3cret-value"})
    bad = _request({"X-Forwarded-For": "198.51.100.1", "X-Internal-Key": "guess"})
    assert limits.has_internal_key(good) and not limits.has_internal_key(bad)
    token = limits.current_request.set(good)
    try:
        assert limits.is_internal_call()
    finally:
        limits.current_request.reset(token)


def test_no_secret_configured_means_no_exemption(settings) -> None:
    assert not limits.has_internal_key(_request({"X-Internal-Key": ""}))
