import re
from dataclasses import dataclass, field


_MAC_RE = re.compile(r"^([0-9a-f]{2}:){5}[0-9a-f]{2}$", re.IGNORECASE)


@dataclass
class SyncPlan:
    to_add: list[dict] = field(default_factory=list)
    to_update: list[dict] = field(default_factory=list)
    to_delete: list[str] = field(default_factory=list)


def extract_mac(client: dict) -> str | None:
    for ident in client.get("ids", []):
        if isinstance(ident, str) and _MAC_RE.match(ident):
            return ident.lower()
    return None


def _is_managed(client: dict, ownership_tag: str) -> bool:
    return ownership_tag in client.get("tags", [])


def _payloads_differ(desired: dict, current: dict) -> bool:
    if desired["name"] != current.get("name"):
        return True
    if set(desired.get("ids", [])) != set(current.get("ids", [])):
        return True
    if set(desired.get("tags", [])) != set(current.get("tags", [])):
        return True
    return False


def compute_diff(
    desired: list[dict],
    adguard_clients: list[dict],
    ownership_tag: str,
    deletable_macs: set[str],
) -> SyncPlan:
    plan = SyncPlan()

    desired_by_mac: dict[str, dict] = {}
    for d in desired:
        mac = extract_mac(d)
        if mac:
            desired_by_mac[mac.lower()] = d

    managed_by_mac: dict[str, dict] = {}
    for c in adguard_clients:
        if not _is_managed(c, ownership_tag):
            continue
        mac = extract_mac(c)
        if mac:
            managed_by_mac[mac.lower()] = c

    for mac, d in desired_by_mac.items():
        current = managed_by_mac.get(mac)
        if current is None:
            plan.to_add.append(d)
        elif _payloads_differ(d, current):
            plan.to_update.append({"old_name": current["name"], "new_payload": d})

    for mac, c in managed_by_mac.items():
        if mac in desired_by_mac:
            continue
        if mac in deletable_macs:
            plan.to_delete.append(c["name"])

    return plan
