import responses
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
