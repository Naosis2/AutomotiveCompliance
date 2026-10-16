import pytest

from allincheck.urlguard import UnsafeUrlError, check_public_url


def pub(host: str) -> list[str]:
    return ["93.184.216.34"]


def priv(host: str) -> list[str]:
    return ["10.0.0.5"]


def test_public_ok() -> None:
    assert check_public_url("https://dealer.ca/x", pub)


@pytest.mark.parametrize("url", ["ftp://a.ca", "file:///etc/passwd", "javascript:1", "http:///x"])
def test_bad_scheme_or_host(url: str) -> None:
    with pytest.raises(UnsafeUrlError):
        check_public_url(url, pub)


@pytest.mark.parametrize("url", ["http://127.0.0.1/", "http://169.254.169.254/", "http://[::1]/"])
def test_literal_private_ips(url: str) -> None:
    with pytest.raises(UnsafeUrlError):
        check_public_url(url, pub)


def test_hostname_resolving_private() -> None:
    with pytest.raises(UnsafeUrlError):
        check_public_url("https://evil.example/", priv)
