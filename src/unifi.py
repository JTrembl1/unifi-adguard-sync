import requests


class UnifiError(RuntimeError):
    pass


class UnifiClient:
    def __init__(
        self, host: str, api_key: str, site_id: str, verify_ssl: bool, page_size: int = 200
    ):
        self._host = host.rstrip("/")
        self._api_key = api_key
        self._site_id = site_id
        self._verify_ssl = verify_ssl
        self._page_size = page_size  # 200 is the API's maximum `limit`

    def _url(self, path: str) -> str:
        return f"{self._host}{path}"

    def _headers(self) -> dict:
        return {"X-API-KEY": self._api_key, "Accept": "application/json"}

    def fetch_clients(self) -> list[dict]:
        """Return every connected client, following the API's offset/limit paging.

        Any failed page raises, so callers never see a partial list.
        """
        clients: list[dict] = []
        while True:
            body = self._fetch_page(offset=len(clients))
            page = body["data"]
            clients.extend(page)
            total = body.get("totalCount")
            if not page:
                return clients
            if total is not None and len(clients) >= total:
                return clients
            if total is None and len(page) < self._page_size:
                return clients

    def fetch_fixed_ip_clients(self) -> list[dict]:
        """Return every known client with a fixed IP, connected or not.

        The Integration API has no fixed-IP field, so this reads the classic
        known-clients list (which accepts the same API key) and reshapes each
        record like an Integration record, using the reserved IP as the address.
        """
        body = self._get(f"/proxy/network/api/s/{self._site_id}/rest/user")
        meta = body.get("meta") or {}
        if meta.get("rc") != "ok":
            raise UnifiError(f"UniFi known-clients request failed: {meta.get('msg', meta)}")
        return [
            {
                "macAddress": r["mac"],
                "name": r.get("name"),
                "hostname": r.get("hostname"),
                "ipAddress": r["fixed_ip"],
                "fixedIp": True,
            }
            for r in body["data"]
            if r.get("use_fixedip") is True and r.get("fixed_ip") and r.get("mac")
        ]

    def _fetch_page(self, offset: int) -> dict:
        return self._get(
            f"/proxy/network/integration/v1/sites/{self._site_id}/clients",
            params={"offset": offset, "limit": self._page_size},
        )

    def _get(self, path: str, params: dict | None = None) -> dict:
        try:
            resp = requests.get(
                self._url(path),
                headers=self._headers(),
                params=params,
                verify=self._verify_ssl,
                timeout=10,
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
        return body
