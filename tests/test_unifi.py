import responses
from responses import matchers
import pytest
from src.unifi import UnifiClient, UnifiError


@responses.activate
def test_fetch_clients_returns_list():
    responses.get(
        "https://10.0.0.1/proxy/network/integration/v1/sites/default/clients",
        json={
            "data": [
                {
                    "id": "abc",
                    "name": "MacBook",
                    "macAddress": "aa:bb:cc:11:22:33",
                    "ipAddress": "10.0.0.5",
                    "fixedIp": True,
                }
            ]
        },
        status=200,
    )
    client = UnifiClient(
        host="https://10.0.0.1",
        api_key="key",
        site_id="default",
        verify_ssl=True,
    )
    clients = client.fetch_clients()
    assert len(clients) == 1
    assert clients[0]["macAddress"] == "aa:bb:cc:11:22:33"


@responses.activate
def test_fetch_clients_sends_api_key_header():
    responses.get(
        "https://10.0.0.1/proxy/network/integration/v1/sites/default/clients",
        json={"data": []},
        status=200,
    )
    client = UnifiClient("https://10.0.0.1", "secret-key", "default", True)
    client.fetch_clients()
    assert responses.calls[0].request.headers.get("X-API-KEY") == "secret-key"


@responses.activate
def test_fetch_clients_raises_on_401():
    responses.get(
        "https://10.0.0.1/proxy/network/integration/v1/sites/default/clients",
        json={"error": "unauthorized"},
        status=401,
    )
    client = UnifiClient("https://10.0.0.1", "bad-key", "default", True)
    with pytest.raises(UnifiError, match="401"):
        client.fetch_clients()


@responses.activate
def test_fetch_clients_raises_on_network_error():
    client = UnifiClient("https://10.0.0.1", "key", "default", True)
    with pytest.raises(UnifiError):
        client.fetch_clients()


_CLIENTS_URL = "https://10.0.0.1/proxy/network/integration/v1/sites/default/clients"


def _page(macs: list[str], offset: int, limit: int, total: int) -> dict:
    return {
        "offset": offset, "limit": limit, "count": len(macs), "totalCount": total,
        "data": [{"name": m, "macAddress": m} for m in macs],
    }


@responses.activate
def test_fetch_clients_requests_max_page_size_by_default():
    responses.get(
        _CLIENTS_URL,
        match=[matchers.query_param_matcher({"offset": "0", "limit": "200"})],
        json=_page(["aa:00:00:00:00:01"], 0, 200, 1),
    )
    client = UnifiClient("https://10.0.0.1", "key", "default", True)
    assert [c["macAddress"] for c in client.fetch_clients()] == ["aa:00:00:00:00:01"]


@responses.activate
def test_fetch_clients_follows_pages_until_total_count():
    for offset, macs in ((0, ["m1", "m2"]), (2, ["m3", "m4"]), (4, ["m5"])):
        responses.get(
            _CLIENTS_URL,
            match=[matchers.query_param_matcher({"offset": str(offset), "limit": "2"})],
            json=_page(macs, offset, 2, 5),
        )
    client = UnifiClient("https://10.0.0.1", "key", "default", True, page_size=2)
    assert [c["macAddress"] for c in client.fetch_clients()] == ["m1", "m2", "m3", "m4", "m5"]
    assert len(responses.calls) == 3


@responses.activate
def test_fetch_clients_raises_if_later_page_fails():
    # A partial list would make the missing devices look absent and start
    # their deletion grace clock, so a failed page must abort the whole fetch.
    responses.get(
        _CLIENTS_URL,
        match=[matchers.query_param_matcher({"offset": "0", "limit": "2"})],
        json=_page(["m1", "m2"], 0, 2, 4),
    )
    responses.get(
        _CLIENTS_URL,
        match=[matchers.query_param_matcher({"offset": "2", "limit": "2"})],
        status=500,
    )
    client = UnifiClient("https://10.0.0.1", "key", "default", True, page_size=2)
    with pytest.raises(UnifiError, match="500"):
        client.fetch_clients()


@responses.activate
def test_fetch_clients_stops_on_empty_page():
    # Clients can disconnect while paging; an empty page must not loop forever.
    responses.get(
        _CLIENTS_URL,
        match=[matchers.query_param_matcher({"offset": "0", "limit": "2"})],
        json=_page(["m1", "m2"], 0, 2, 5),
    )
    responses.get(
        _CLIENTS_URL,
        match=[matchers.query_param_matcher({"offset": "2", "limit": "2"})],
        json=_page([], 2, 2, 2),
    )
    client = UnifiClient("https://10.0.0.1", "key", "default", True, page_size=2)
    assert [c["macAddress"] for c in client.fetch_clients()] == ["m1", "m2"]


@responses.activate
def test_fetch_clients_without_total_count_pages_until_short_page():
    responses.get(
        _CLIENTS_URL,
        match=[matchers.query_param_matcher({"offset": "0", "limit": "2"})],
        json={"data": [{"macAddress": "m1"}, {"macAddress": "m2"}]},
    )
    responses.get(
        _CLIENTS_URL,
        match=[matchers.query_param_matcher({"offset": "2", "limit": "2"})],
        json={"data": [{"macAddress": "m3"}]},
    )
    client = UnifiClient("https://10.0.0.1", "key", "default", True, page_size=2)
    assert [c["macAddress"] for c in client.fetch_clients()] == ["m1", "m2", "m3"]


_KNOWN_URL = "https://10.0.0.1/proxy/network/api/s/default/rest/user"


@responses.activate
def test_fetch_fixed_ip_clients_returns_reserved_devices_with_reserved_ip():
    responses.get(_KNOWN_URL, json={"meta": {"rc": "ok"}, "data": [
        {"mac": "aa:00:00:00:00:01", "name": "NAS", "hostname": "nas01",
         "use_fixedip": True, "fixed_ip": "192.168.10.2", "last_ip": "192.168.10.99"},
        {"mac": "aa:00:00:00:00:02", "hostname": "printer",
         "use_fixedip": True, "fixed_ip": "192.168.40.11"},
        {"mac": "aa:00:00:00:00:03", "name": "Phone", "use_fixedip": False,
         "last_ip": "192.168.2.50"},
        {"mac": "aa:00:00:00:00:04", "name": "Half-set", "use_fixedip": True},
    ]})
    client = UnifiClient("https://10.0.0.1", "key", "default", True)
    assert client.fetch_fixed_ip_clients() == [
        {"macAddress": "aa:00:00:00:00:01", "name": "NAS", "hostname": "nas01",
         "ipAddress": "192.168.10.2", "fixedIp": True},
        {"macAddress": "aa:00:00:00:00:02", "name": None, "hostname": "printer",
         "ipAddress": "192.168.40.11", "fixedIp": True},
    ]
    assert responses.calls[0].request.headers.get("X-API-KEY") == "key"


@responses.activate
def test_fetch_fixed_ip_clients_raises_on_error_meta():
    responses.get(_KNOWN_URL, json={"meta": {"rc": "error", "msg": "api.err.LoginRequired"}, "data": []})
    client = UnifiClient("https://10.0.0.1", "key", "default", True)
    with pytest.raises(UnifiError, match="LoginRequired"):
        client.fetch_fixed_ip_clients()


@responses.activate
def test_fetch_fixed_ip_clients_raises_on_401():
    responses.get(_KNOWN_URL, json={"meta": {"rc": "error"}}, status=401)
    client = UnifiClient("https://10.0.0.1", "key", "default", True)
    with pytest.raises(UnifiError, match="401"):
        client.fetch_fixed_ip_clients()
