import pytest
import requests

import provider


class FakeResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        if self._payload is None:
            raise ValueError("not json")
        return self._payload


def fake_get(responses):
    calls = []

    def _get(url, params=None, timeout=None):
        calls.append((url, params))
        item = responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    return _get, calls


def no_sleep(_seconds):
    pass


def test_fetch_channels_returns_names_and_epg_ids(monkeypatch):
    get, calls = fake_get([FakeResponse(200, [
        {"name": " US| CNN HD ", "epg_channel_id": "CNN.us"},
        {"name": "UK| BBC ONE", "epg_channel_id": ""},
        {"name": "", "epg_channel_id": "x"},
        "not a dict",
    ])])
    monkeypatch.setattr(provider.requests, "get", get)
    channels = provider.fetch_channels("http://host.example/", "user1", "pass1", sleep=no_sleep)
    assert channels == [{"name": "US| CNN HD", "epg_id": "CNN.us"}, {"name": "UK| BBC ONE", "epg_id": None}]
    assert calls[0][0] == "http://host.example/player_api.php"
    assert calls[0][1] == {"username": "user1", "password": "pass1", "action": "get_live_streams"}


def test_http_513_means_login_rejected(monkeypatch):
    get, _ = fake_get([FakeResponse(513)])
    monkeypatch.setattr(provider.requests, "get", get)
    with pytest.raises(provider.LoginRejected, match="513"):
        provider.fetch_channels("http://host.example", "u", "p", sleep=no_sleep)


def test_auth_zero_means_login_rejected(monkeypatch):
    get, _ = fake_get([FakeResponse(200, {"user_info": {"auth": 0}})])
    monkeypatch.setattr(provider.requests, "get", get)
    with pytest.raises(provider.LoginRejected):
        provider.fetch_channels("http://host.example", "u", "p", sleep=no_sleep)


def test_network_errors_retry_then_raise_unavailable_without_secrets(monkeypatch):
    message = ("HTTPConnectionPool(host='host.example', port=80): Max retries exceeded with url: "
               "/player_api.php?username=user1&password=secretpw&action=get_live_streams")
    get, calls = fake_get([requests.ConnectionError(message) for _ in range(3)])
    monkeypatch.setattr(provider.requests, "get", get)
    with pytest.raises(provider.ProviderUnavailable) as caught:
        provider.fetch_channels("http://host.example", "user1", "secretpw", sleep=no_sleep)
    text = str(caught.value)
    assert "secretpw" not in text and "user1" not in text and "host.example" not in text
    assert len(calls) == 3


def test_retry_recovers_after_a_failure(monkeypatch):
    get, calls = fake_get([FakeResponse(502), FakeResponse(200, [{"name": "US| CNN", "epg_channel_id": None}])])
    monkeypatch.setattr(provider.requests, "get", get)
    assert provider.fetch_channels("http://h", "u", "p", sleep=no_sleep) == [{"name": "US| CNN", "epg_id": None}]
    assert len(calls) == 2


def test_server_errors_become_unavailable(monkeypatch):
    get, _ = fake_get([FakeResponse(502), FakeResponse(502), FakeResponse(502)])
    monkeypatch.setattr(provider.requests, "get", get)
    with pytest.raises(provider.ProviderUnavailable, match="HTTP 502"):
        provider.fetch_channels("http://h", "u", "p", sleep=no_sleep)


def test_redact_replaces_longest_secrets_first():
    assert provider.redact("http://host.example host.example u1 pw", ["u1", "pw", "http://host.example", "host.example", ""]) == "*** *** *** ***"
