import requests


class UnifiError(RuntimeError):
    pass


class UnifiClient:
    def __init__(self, host: str, api_key: str, site_id: str, verify_ssl: bool):
        self._host = host.rstrip("/")
        self._api_key = api_key
        self._site_id = site_id
        self._verify_ssl = verify_ssl

    def _url(self, path: str) -> str:
        return f"{self._host}{path}"

    def _headers(self) -> dict:
        return {"X-API-KEY": self._api_key, "Accept": "application/json"}

    def fetch_clients(self) -> list[dict]:
        url = self._url(
            f"/proxy/network/integration/v1/sites/{self._site_id}/clients"
        )
        try:
            resp = requests.get(
                url, headers=self._headers(), verify=self._verify_ssl, timeout=10
            )
        except requests.RequestException as e:
            raise UnifiError(f"UniFi request failed: {e}") from e
        if resp.status_code != 200:
            raise UnifiError(
                f"UniFi returned {resp.status_code}: {resp.text[:200]}"
            )
        body = resp.json()
        if not isinstance(body, dict) or "data" not in body:
            raise UnifiError(f"Unexpected UniFi response shape: {body!r}")
        return body["data"]
