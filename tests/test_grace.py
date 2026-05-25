from pathlib import Path
from freezegun import freeze_time
from src.grace import GraceTracker


def test_currently_seen_macs_have_no_deletable_status(tmp_path):
    state_file = tmp_path / "last_seen.json"
    tracker = GraceTracker(state_file=state_file, grace_hours=24)
    deletable = tracker.update_and_get_deletable(currently_seen={"aa:01", "aa:02"})
    assert deletable == set()


def test_mac_absent_for_less_than_grace_not_deletable(tmp_path):
    state_file = tmp_path / "last_seen.json"
    tracker = GraceTracker(state_file=state_file, grace_hours=24)

    with freeze_time("2026-05-25 10:00:00"):
        tracker.update_and_get_deletable(currently_seen={"aa:01"})

    with freeze_time("2026-05-25 20:00:00"):
        deletable = tracker.update_and_get_deletable(currently_seen=set())
        assert "aa:01" not in deletable


def test_mac_absent_past_grace_is_deletable(tmp_path):
    state_file = tmp_path / "last_seen.json"
    tracker = GraceTracker(state_file=state_file, grace_hours=24)

    with freeze_time("2026-05-25 10:00:00"):
        tracker.update_and_get_deletable(currently_seen={"aa:01"})

    with freeze_time("2026-05-26 11:00:00"):
        deletable = tracker.update_and_get_deletable(currently_seen=set())
        assert "aa:01" in deletable


def test_mac_reappearing_resets_clock(tmp_path):
    state_file = tmp_path / "last_seen.json"
    tracker = GraceTracker(state_file=state_file, grace_hours=24)

    with freeze_time("2026-05-25 10:00:00"):
        tracker.update_and_get_deletable(currently_seen={"aa:01"})

    with freeze_time("2026-05-25 20:00:00"):
        tracker.update_and_get_deletable(currently_seen=set())

    with freeze_time("2026-05-25 21:00:00"):
        tracker.update_and_get_deletable(currently_seen={"aa:01"})

    with freeze_time("2026-05-26 21:00:00"):
        deletable = tracker.update_and_get_deletable(currently_seen=set())
        assert "aa:01" not in deletable


def test_state_persists_across_tracker_instances(tmp_path):
    state_file = tmp_path / "last_seen.json"

    with freeze_time("2026-05-25 10:00:00"):
        t1 = GraceTracker(state_file=state_file, grace_hours=24)
        t1.update_and_get_deletable(currently_seen={"aa:01"})

    with freeze_time("2026-05-26 11:00:00"):
        t2 = GraceTracker(state_file=state_file, grace_hours=24)
        deletable = t2.update_and_get_deletable(currently_seen=set())
        assert "aa:01" in deletable


def test_corrupted_state_file_treated_as_empty(tmp_path):
    state_file = tmp_path / "last_seen.json"
    state_file.write_text("not json at all {{{")
    tracker = GraceTracker(state_file=state_file, grace_hours=24)
    deletable = tracker.update_and_get_deletable(currently_seen={"aa:01"})
    assert deletable == set()
