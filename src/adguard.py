import requests
from requests.auth import HTTPBasicAuth


class AdGuardError(RuntimeError):
    pass


class AdGuardClient:
    def __init__(self, host: str, user: str, password: str):
        self._host = host.rstrip("/")
        self._auth = HTTPBasicAuth(user, password)

    def _url(self, path: str) -> str:
        return f"{self._host}{path}"

    def _request(self, method: str, path: str, json: dict | None = None) -> requests.Response:
        try:
            resp = requests.request(
                method, self._url(path), auth=self._auth, json=json, timeout=10
            )
        except requests.RequestException as e:
            raise AdGuardError(f"AdGuard request failed: {e}") from e
        if resp.status_code >= 400:
            raise AdGuardError(
                f"AdGuard {method} {path} returned {resp.status_code}: {resp.text[:200]}"
            )
        return resp

    def list_clients(self) -> list[dict]:
        resp = self._request("GET", "/control/clients")
        body = resp.json()
        return body.get("clients", [])

    def add_client(self, payload: dict) -> None:
        self._request("POST", "/control/clients/add", json=payload)

    def update_client(self, name: str, payload: dict) -> None:
        self._request("POST", "/control/clients/update", json={"name": name, "data": payload})

    def delete_client(self, name: str) -> None:
        self._request("POST", "/control/clients/delete", json={"name": name})
