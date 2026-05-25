import pytest
from src.mapping import resolve_name, to_adguard_payload, filter_by_scope


# --- resolve_name ---

def test_name_uses_alias_when_present():
    record = {"name": "Living Room AppleTV", "hostname": "atv", "macAddress": "aa:bb:cc:dd:ee:ff"}
    assert resolve_name(record) == "Living Room AppleTV"


def test_name_falls_back_to_hostname():
    record = {"name": "", "hostname": "kitchen-pi", "macAddress": "aa:bb:cc:dd:ee:ff"}
    assert resolve_name(record) == "kitchen-pi"


def test_name_falls_back_to_unknown_with_mac_tail():
    record = {"name": "", "hostname": "", "macAddress": "aa:bb:cc:dd:ee:ff"}
    assert resolve_name(record) == "unknown-eeff"


def test_name_handles_missing_fields_entirely():
    record = {"macAddress": "aa:bb:cc:dd:ee:ff"}
    assert resolve_name(record) == "unknown-eeff"


# --- to_adguard_payload ---

def test_payload_contains_name_ids_and_ownership_tag():
    record = {
        "name": "MBP",
        "macAddress": "aa:bb:cc:11:22:33",
        "ipAddress": "192.168.10.42",
    }
    p = to_adguard_payload(record, ownership_tag="managed-by-unifi-sync")
    assert p["name"] == "MBP"
    assert "aa:bb:cc:11:22:33" in p["ids"]
    assert "192.168.10.42" in p["ids"]
    assert p["tags"] == ["managed-by-unifi-sync"]
    assert p["use_global_settings"] is True


def test_payload_omits_ip_when_missing():
    record = {"name": "MBP", "macAddress": "aa:bb:cc:11:22:33"}
    p = to_adguard_payload(record, ownership_tag="t")
    assert p["ids"] == ["aa:bb:cc:11:22:33"]


# --- filter_by_scope ---

def test_filter_fixed_keeps_only_fixed_ip():
    records = [
        {"macAddress": "aa:01", "fixedIp": True},
        {"macAddress": "aa:02", "fixedIp": False},
        {"macAddress": "aa:03"},  # missing fixedIp → not fixed
    ]
    result = filter_by_scope(records, scope="fixed")
    assert [r["macAddress"] for r in result] == ["aa:01"]


def test_filter_all_keeps_everything():
    records = [
        {"macAddress": "aa:01", "fixedIp": True},
        {"macAddress": "aa:02", "fixedIp": False},
    ]
    result = filter_by_scope(records, scope="all")
    assert len(result) == 2
