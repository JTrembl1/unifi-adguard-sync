def resolve_name(record: dict) -> str:
    name = (record.get("name") or "").strip()
    if name:
        return name
    hostname = (record.get("hostname") or "").strip()
    if hostname:
        return hostname
    mac = record.get("macAddress", "")
    tail = mac.replace(":", "").lower()[-4:] if mac else "xxxx"
    return f"unknown-{tail}"


def to_adguard_payload(record: dict, ownership_tag: str) -> dict:
    ids = [record["macAddress"]]
    ip = record.get("ipAddress")
    if ip:
        ids.append(ip)
    return {
        "name": resolve_name(record),
        "ids": ids,
        "use_global_settings": True,
        "tags": [ownership_tag],
        "upstreams": [],
    }


def filter_by_scope(records: list[dict], scope: str) -> list[dict]:
    if scope == "all":
        return list(records)
    if scope == "fixed":
        return [r for r in records if r.get("fixedIp") is True]
    raise ValueError(f"Unknown scope: {scope}")


def filter_excluded_macs(records: list[dict], excluded: frozenset[str]) -> list[dict]:
    """Remove records whose MAC address is in the excluded set (case-insensitive)."""
    if not excluded:
        return list(records)
    return [
        r for r in records
        if (r.get("macAddress") or "").lower() not in excluded
    ]
