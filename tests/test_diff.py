from src.diff import compute_diff, extract_mac, SyncPlan


def _adguard_client(name, mac, ip=None, tag="managed-by-unifi-sync"):
    ids = [mac]
    if ip:
        ids.append(ip)
    return {"name": name, "ids": ids, "tags": [tag] if tag else []}


# --- extract_mac ---

def test_extract_mac_finds_mac_in_ids():
    assert extract_mac({"ids": ["aa:bb:cc:dd:ee:ff", "10.0.0.5"]}) == "aa:bb:cc:dd:ee:ff"


def test_extract_mac_returns_none_if_no_mac():
    assert extract_mac({"ids": ["10.0.0.5"]}) is None


# --- compute_diff ---

def test_empty_both_sides_is_noop():
    plan = compute_diff(desired=[], adguard_clients=[], ownership_tag="t", deletable_macs=set())
    assert plan == SyncPlan(to_add=[], to_update=[], to_delete=[])


def test_new_client_in_unifi_only_is_added():
    desired = [{"name": "NAS", "ids": ["aa:01"], "tags": ["t"]}]
    plan = compute_diff(desired=desired, adguard_clients=[], ownership_tag="t", deletable_macs=set())
    assert len(plan.to_add) == 1
    assert plan.to_add[0]["name"] == "NAS"


def test_same_client_on_both_sides_is_noop():
    desired = [{"name": "NAS", "ids": ["aa:01"], "tags": ["t"], "use_global_settings": True, "upstreams": []}]
    current = [_adguard_client("NAS", "aa:01", tag="t")]
    plan = compute_diff(desired=desired, adguard_clients=current, ownership_tag="t", deletable_macs=set())
    assert plan == SyncPlan(to_add=[], to_update=[], to_delete=[])


def test_renamed_client_is_updated():
    desired = [{"name": "NewName", "ids": ["aa:01"], "tags": ["t"], "use_global_settings": True, "upstreams": []}]
    current = [_adguard_client("OldName", "aa:01", tag="t")]
    plan = compute_diff(desired=desired, adguard_clients=current, ownership_tag="t", deletable_macs=set())
    assert len(plan.to_update) == 1
    assert plan.to_update[0]["old_name"] == "OldName"
    assert plan.to_update[0]["new_payload"]["name"] == "NewName"


def test_client_removed_from_unifi_is_deleted_if_past_grace():
    desired = []
    current = [_adguard_client("NAS", "aa:01", tag="t")]
    plan = compute_diff(
        desired=desired, adguard_clients=current, ownership_tag="t",
        deletable_macs={"aa:01"},
    )
    assert plan.to_delete == ["NAS"]


def test_client_removed_from_unifi_kept_during_grace_period():
    desired = []
    current = [_adguard_client("NAS", "aa:01", tag="t")]
    plan = compute_diff(
        desired=desired, adguard_clients=current, ownership_tag="t",
        deletable_macs=set(),
    )
    assert plan.to_delete == []


def test_untagged_adguard_client_is_ignored():
    """The sacred-manual rule: clients without our tag are invisible to the diff."""
    desired = []
    current = [_adguard_client("AdGuard Home", "aa:99", tag=None)]
    plan = compute_diff(
        desired=desired, adguard_clients=current, ownership_tag="t",
        deletable_macs={"aa:99"},
    )
    assert plan.to_delete == []
    assert plan.to_add == []


def test_ip_change_triggers_update():
    desired = [{"name": "NAS", "ids": ["aa:01", "10.0.0.99"], "tags": ["t"], "use_global_settings": True, "upstreams": []}]
    current = [_adguard_client("NAS", "aa:01", ip="10.0.0.5", tag="t")]
    plan = compute_diff(desired=desired, adguard_clients=current, ownership_tag="t", deletable_macs=set())
    assert len(plan.to_update) == 1
