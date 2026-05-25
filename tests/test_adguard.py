import responses
import pytest
from src.adguard import AdGuardClient, AdGuardError


def _client():
    return AdGuardClient(
        host="http://10.0.0.2:3000", user="admin", password="pw"
    )


@responses.activate
def test_list_clients_returns_clients():
    responses.get(
        "http://10.0.0.2:3000/control/clients",
        json={"clients": [{"name": "NAS", "ids": ["aa:bb:cc:dd:ee:ff"]}]},
        status=200,
    )
    clients = _client().list_clients()
    assert clients == [{"name": "NAS", "ids": ["aa:bb:cc:dd:ee:ff"]}]


@responses.activate
def test_list_clients_uses_basic_auth():
    responses.get(
        "http://10.0.0.2:3000/control/clients",
        json={"clients": []},
        status=200,
    )
    _client().list_clients()
    auth = responses.calls[0].request.headers.get("Authorization", "")
    assert auth.startswith("Basic ")


@responses.activate
def test_add_client_posts_correct_payload():
    responses.post("http://10.0.0.2:3000/control/clients/add", status=200)
    payload = {"name": "MBP", "ids": ["aa:bb:cc:11:22:33"], "tags": ["managed-by-unifi-sync"]}
    _client().add_client(payload)
    assert responses.calls[0].request.body is not None


@responses.activate
def test_update_client_posts_with_name_and_data():
    responses.post("http://10.0.0.2:3000/control/clients/update", status=200)
    _client().update_client("MBP", {"name": "MBP", "ids": ["aa:bb:cc:11:22:33"]})
    body = responses.calls[0].request.body
    assert body is not None
    import json
    decoded = json.loads(body)
    assert decoded["name"] == "MBP"
    assert "data" in decoded


@responses.activate
def test_delete_client_posts_name():
    responses.post("http://10.0.0.2:3000/control/clients/delete", status=200)
    _client().delete_client("MBP")
    import json
    decoded = json.loads(responses.calls[0].request.body)
    assert decoded == {"name": "MBP"}


@responses.activate
def test_list_clients_raises_on_401():
    responses.get(
        "http://10.0.0.2:3000/control/clients",
        json={"error": "unauthorized"},
        status=401,
    )
    with pytest.raises(AdGuardError, match="401"):
        _client().list_clients()
