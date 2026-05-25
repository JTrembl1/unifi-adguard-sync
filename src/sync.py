import logging
import time
from dataclasses import dataclass

from src.mapping import filter_by_scope, to_adguard_payload
from src.diff import compute_diff, extract_mac

logger = logging.getLogger(__name__)


@dataclass
class SyncResult:
    added: int = 0
    updated: int = 0
    deleted: int = 0
    untouched: int = 0
    failed: int = 0
    took_ms: int = 0


def run_sync_cycle(
    *,
    unifi,
    adguard,
    grace,
    scope: str,
    ownership_tag: str,
    dry_run: bool,
) -> SyncResult:
    start = time.monotonic()
    result = SyncResult()

    unifi_records = unifi.fetch_clients()
    in_scope = filter_by_scope(unifi_records, scope=scope)
    adguard_clients = adguard.list_clients()

    desired = [
        to_adguard_payload(r, ownership_tag=ownership_tag)
        for r in in_scope
        if r.get("macAddress")
    ]

    currently_seen = {r["macAddress"].lower() for r in in_scope if r.get("macAddress")}
    deletable_macs = grace.update_and_get_deletable(currently_seen=currently_seen)

    plan = compute_diff(
        desired=desired,
        adguard_clients=adguard_clients,
        ownership_tag=ownership_tag,
        deletable_macs=deletable_macs,
    )

    if dry_run:
        logger.info(
            "DRY_RUN plan  would_add=%d would_update=%d would_delete=%d",
            len(plan.to_add), len(plan.to_update), len(plan.to_delete),
        )
        for p in plan.to_add:
            logger.info("DRY_RUN add    name=%r mac=%s", p["name"], extract_mac(p))
        for u in plan.to_update:
            logger.info(
                "DRY_RUN update old_name=%r new_name=%r mac=%s",
                u["old_name"], u["new_payload"]["name"], extract_mac(u["new_payload"]),
            )
        for d in plan.to_delete:
            logger.info("DRY_RUN delete name=%r", d)
        result.added = len(plan.to_add)
        result.updated = len(plan.to_update)
        result.deleted = len(plan.to_delete)
    else:
        for payload in plan.to_add:
            try:
                adguard.add_client(payload)
                result.added += 1
            except Exception as e:
                logger.warning("add failed for %r: %s", payload["name"], e)
                result.failed += 1
        for upd in plan.to_update:
            try:
                adguard.update_client(upd["old_name"], upd["new_payload"])
                result.updated += 1
            except Exception as e:
                logger.warning("update failed for %r: %s", upd["old_name"], e)
                result.failed += 1
        for name in plan.to_delete:
            try:
                adguard.delete_client(name)
                result.deleted += 1
            except Exception as e:
                logger.warning("delete failed for %r: %s", name, e)
                result.failed += 1

    managed_count = sum(
        1 for c in adguard_clients if ownership_tag in c.get("tags", [])
    )
    result.untouched = max(0, managed_count - result.updated - result.deleted)
    result.took_ms = int((time.monotonic() - start) * 1000)
    return result
