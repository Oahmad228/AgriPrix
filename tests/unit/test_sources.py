"""Integrity-checked downloads: DQ-01 (WAF/HTTP) and DQ-02 (size + MD5), without network."""

from pathlib import Path

import httpx
import pytest
from src.etl.sources import (
    SourceIntegrityError,
    SourceSpec,
    fetch,
    md5_of,
    resolve_expected,
)

HDX_SPEC = SourceSpec("wfp_SEN", "hdx", "wfp-food-prices-for-senegal", "wfp_SEN.csv", "SEN")
FAO_SPEC = SourceSpec("faostat_cpi", "faostat", "CPI.zip", "CPI.zip", "MAR")
BODY = b"date,price\n2024-01-15,100\n"
DOWNLOAD_URL = "https://data.humdata.org/download/wfp_food_prices_sen.csv"


def hdx_metadata(size: int = len(BODY), md5: str = md5_of(BODY)) -> dict:
    return {
        "result": {
            "resources": [
                {"download_url": "https://x/wfp_markets_sen.csv", "format": "CSV", "size": 1},
                {
                    "download_url": DOWNLOAD_URL,
                    "format": "CSV",
                    "size": size,
                    "hash": md5,
                    "last_modified": "2026-11-04T01:37:17",
                },
            ]
        }
    }


def client_for(download_responses: list[httpx.Response], metadata: dict | None = None):
    calls = {"downloads": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if "package_show" in str(request.url):
            return httpx.Response(200, json=metadata or hdx_metadata())
        response = download_responses[min(calls["downloads"], len(download_responses) - 1)]
        calls["downloads"] += 1
        return response

    return httpx.Client(transport=httpx.MockTransport(handler)), calls


def test_valid_download_is_written_and_verified(tmp_path: Path) -> None:
    client, calls = client_for([httpx.Response(200, content=BODY)])
    result = fetch(client, HDX_SPEC, tmp_path, sleep=lambda _s: None)
    assert result.from_cache is False
    assert (tmp_path / "wfp_SEN.csv").read_bytes() == BODY
    assert result.md5 == md5_of(BODY)
    assert calls["downloads"] == 1


def test_matching_local_copy_skips_download(tmp_path: Path) -> None:
    (tmp_path / "wfp_SEN.csv").write_bytes(BODY)
    client, calls = client_for([httpx.Response(500)])
    result = fetch(client, HDX_SPEC, tmp_path, sleep=lambda _s: None)
    assert result.from_cache is True
    assert calls["downloads"] == 0


def test_waf_challenge_is_retried_with_backoff(tmp_path: Path) -> None:
    waits: list[float] = []
    client, calls = client_for(
        [httpx.Response(202, content=b""), httpx.Response(200, content=BODY)]
    )
    result = fetch(client, HDX_SPEC, tmp_path, sleep=waits.append, backoff_seconds=1)
    assert result.from_cache is False
    assert calls["downloads"] == 2
    assert waits == [1]


def test_truncated_file_fails_after_all_attempts(tmp_path: Path) -> None:
    waits: list[float] = []
    client, _ = client_for([httpx.Response(200, content=BODY[:-5])])
    with pytest.raises(SourceIntegrityError, match="DQ-02 size"):
        fetch(client, HDX_SPEC, tmp_path, max_attempts=3, backoff_seconds=1, sleep=waits.append)
    assert waits == [1, 2]  # exponential backoff
    assert not (tmp_path / "wfp_SEN.csv").exists()  # nothing half-written


def test_md5_mismatch_is_rejected(tmp_path: Path) -> None:
    tampered = BODY.replace(b"100", b"999")
    client, _ = client_for([httpx.Response(200, content=tampered)])
    with pytest.raises(SourceIntegrityError, match="MD5"):
        fetch(client, HDX_SPEC, tmp_path, max_attempts=1, sleep=lambda _s: None)


def test_hdx_metadata_without_md5_is_refused() -> None:
    client, _ = client_for([], metadata=hdx_metadata(md5=""))
    with pytest.raises(SourceIntegrityError, match="no usable size/MD5"):
        resolve_expected(client, HDX_SPEC)


def test_faostat_uses_s3_etag_as_md5() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "HEAD"
        return httpx.Response(
            200, headers={"ETag": f'"{md5_of(BODY)}"', "Content-Length": str(len(BODY))}
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    expected = resolve_expected(client, FAO_SPEC)
    assert expected.md5 == md5_of(BODY)
    assert expected.size_bytes == len(BODY)


def test_faostat_multipart_etag_is_refused() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"ETag": '"abc-3"', "Content-Length": "10"})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(SourceIntegrityError, match="ETag"):
        resolve_expected(client, FAO_SPEC)
