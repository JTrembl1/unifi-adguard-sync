from pathlib import Path
from unittest.mock import MagicMock
from src.sync import run_sync_cycle, SyncResult


def _fake_unifi(records: list[dict]) -> MagicMock:
    m = MagicMock()
    m.fetch_clients.return_value = records
    return m


def _fake_adguard(clients: list[dict]) -> MagicMock:
    m = MagicMock()
    m.list_clients.return_value = clients
    return m


def _fake_grace(deletable: set[str]) -> MagicMock:
    m = MagicMock()
    m.update_and_get_deletable.return_value = deletable
    return m


def test_adds_new_unifi_client_to_adguard():
    unifi = _fake_unifi([
        {"name": "NAS", "macAddress": "aa:bb:cc:11:22:33", "ipAddress": "10.0.0.5", "fixedIp": True}
    ])
    adguard = _fake_adguard([])
    grace = _fake_grace(set())

    result = run_sync_cycle(
        unifi=unifi, adguard=adguard, grace=grace,
        scope="fixed", ownership_tag="t", dry_run=False,
    )
    adguard.add_client.assert_called_once()
    assert result.added == 1
    assert result.updated == 0
    assert result.deleted == 0


def test_dry_run_does_not_write():
    unifi = _fake_unifi([
        {"name": "NAS", "macAddress": "aa:bb:cc:11:22:33", "ipAddress": "10.0.0.5", "fixedIp": True}
    ])
    adguard = _fake_adguard([])
    grace = _fake_grace(set())

    result = run_sync_cycle(
        unifi=unifi, adguard=adguard, grace=grace,
        scope="fixed", ownership_tag="t", dry_run=True,
    )
    adguard.add_client.assert_not_called()
    adguard.update_client.assert_not_called()
    adguard.delete_client.assert_not_called()
    assert result.added == 1


def test_scope_fixed_excludes_non_fixed_clients():
    unifi = _fake_unifi([
        {"name": "NAS", "macAddress": "aa:01", "fixedIp": True},
        {"name": "Phone", "macAddress": "aa:02", "fixedIp": False},
    ])
    adguard = _fake_adguard([])
    grace = _fake_grace(set())

    result = run_sync_cycle(
        unifi=unifi, adguard=adguard, grace=grace,
        scope="fixed", ownership_tag="t", dry_run=False,
    )
    assert result.added == 1
    call_payload = adguard.add_client.call_args[0][0]
    assert call_payload["name"] == "NAS"


def test_failed_single_write_does_not_stop_cycle():
    unifi = _fake_unifi([
        {"name": "A", "macAddress": "aa:01", "fixedIp": True},
        {"name": "B", "macAddress": "aa:02", "fixedIp": True},
    ])
    adguard = _fake_adguard([])
    grace = _fake_grace(set())

    adguard.add_client.side_effect = [Exception("boom"), None]

    result = run_sync_cycle(
        unifi=unifi, adguard=adguard, grace=grace,
        scope="fixed", ownership_tag="t", dry_run=False,
    )
    assert adguard.add_client.call_count == 2
    assert result.added == 1
    assert result.failed == 1


def test_grace_tracker_called_with_current_unifi_macs():
    unifi = _fake_unifi([
        {"name": "A", "macAddress": "AA:01", "fixedIp": True},
    ])
    adguard = _fake_adguard([])
    grace = _fake_grace(set())

    run_sync_cycle(
        unifi=unifi, adguard=adguard, grace=grace,
        scope="fixed", ownership_tag="t", dry_run=False,
    )
    grace.update_and_get_deletable.assert_called_once()
    seen_arg = grace.update_and_get_deletable.call_args[1]["currently_seen"]
    assert "aa:01" in {m.lower() for m in seen_arg}
