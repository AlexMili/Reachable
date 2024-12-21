from reachable.client import BaseClient


def test_default_headers():
    """
    Test that the BaseClient initializes with the correct default headers.
    """
    base = BaseClient()

    assert "User-Agent" in base.headers
    assert "Accept" in base.headers
    assert "Accept-Language" in base.headers

    assert base.headers["Connection"] == "keep-alive"
    assert base.include_host is False
    assert base.ssl_fallback_to_http is False
    assert base.ensure_protocol_url is False
    assert base.timeout == 10


def test_custom_headers():
    """
    Test that passing custom headers to the BaseClient overrides defaults.
    """
    custom_headers = {"X-Custom-Header": "test"}
    base = BaseClient(headers=custom_headers, include_host=True)
    assert "User-Agent" in base.headers
    assert "Accept" in base.headers
    assert "Accept-Language" in base.headers
    assert base.include_host is True


def test_prepare_request_no_host():
    """
    Test that _prepare_request does not add "Host" if include_host is false.
    """
    base = BaseClient()
    _, headers, ssl_fallback = base._prepare_request("http://example.com")
    assert headers is None
    assert ssl_fallback is False


def test_prepare_request_include_host():
    """
    Test that _prepare_request sets the "Host" header if include_host is true.
    """
    base = BaseClient(include_host=True)
    _, headers, _ = base._prepare_request("http://example.com")
    assert headers is not None
    assert "Host" in headers
    assert headers["Host"] == "example.com"


def test_prepare_request_protocol_fix():
    """
    Test that if ensure_protocol_url is true and the scheme isn't http or https,
    it replaces it with https.
    """
    base = BaseClient(ensure_protocol_url=True)
    # Force a weird scheme
    url, _, _ = base._prepare_request("ftp://example.com")
    # The scheme should have been replaced by https
    assert url.startswith("https://example.com")


def test_prepare_request_keep_https():
    """
    Test that if ensure_protocol_url is true and the scheme is already https,
    the url remains https.
    """
    base = BaseClient(ensure_protocol_url=True)
    url, _, _ = base._prepare_request("https://example.com")
    assert url.startswith("https://example.com")
