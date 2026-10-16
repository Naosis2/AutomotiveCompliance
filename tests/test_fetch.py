import httpx
import pytest

from allincheck.config import Settings
from allincheck.fetch import BlockedError, FetchError, RobotsDisallowedError

from .conftest import make_fetcher


def test_fetch_ok_and_user_agent(settings: Settings) -> None:
    seen: list[str] = []

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append(req.headers["user-agent"])
        if req.url.path == "/robots.txt":
            return httpx.Response(404)
        return httpx.Response(200, text="<html>hi</html>")

    f = make_fetcher(settings, httpx.MockTransport(handler))
    assert "hi" in f.get("https://dealer.ca/a")
    assert all("t@example.com" in ua for ua in seen)


def test_robots_disallow(settings: Settings) -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nDisallow: /private")
        return httpx.Response(200, text="x")

    f = make_fetcher(settings, httpx.MockTransport(handler))
    with pytest.raises(RobotsDisallowedError):
        f.get("https://dealer.ca/private/car")
    assert f.get("https://dealer.ca/public") == "x"


def test_block_detection_stops(settings: Settings) -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path == "/robots.txt":
            return httpx.Response(404)
        return httpx.Response(200, text="<title>Just a moment...</title>")

    f = make_fetcher(settings, httpx.MockTransport(handler))
    with pytest.raises(BlockedError):
        f.get("https://dealer.ca/a")


def test_403_is_blocked_not_retried(settings: Settings) -> None:
    calls = {"n": 0}

    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path == "/robots.txt":
            return httpx.Response(404)
        calls["n"] += 1
        return httpx.Response(403)

    f = make_fetcher(settings, httpx.MockTransport(handler))
    with pytest.raises(BlockedError):
        f.get("https://dealer.ca/a")
    assert calls["n"] == 1


def test_retries_on_500_then_ok(settings: Settings) -> None:
    calls = {"n": 0}

    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path == "/robots.txt":
            return httpx.Response(404)
        calls["n"] += 1
        return httpx.Response(500) if calls["n"] < 3 else httpx.Response(200, text="ok")

    f = make_fetcher(settings, httpx.MockTransport(handler))
    assert f.get("https://dealer.ca/a") == "ok"


def test_redirect_to_private_ip_refused(settings: Settings) -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path == "/robots.txt":
            return httpx.Response(404)
        return httpx.Response(302, headers={"location": "http://169.254.169.254/latest"})

    f = make_fetcher(settings, httpx.MockTransport(handler))
    with pytest.raises(FetchError, match="unsafe"):
        f.get("https://dealer.ca/a")
