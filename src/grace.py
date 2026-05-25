import json
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)


class GraceTracker:
    """Tracks when each MAC was last seen, reports which absent MACs are past grace."""

    def __init__(self, state_file: Path, grace_hours: int):
        self._state_file = state_file
        self._grace = timedelta(hours=grace_hours)

    def _load(self) -> dict[str, str]:
        if not self._state_file.exists():
            return {}
        try:
            raw = json.loads(self._state_file.read_text())
            if not isinstance(raw, dict):
                raise ValueError("expected JSON object")
            return raw
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning("state file unreadable, treating as empty: %s", e)
            return {}

    def _save(self, state: dict[str, str]) -> None:
        self._state_file.parent.mkdir(parents=True, exist_ok=True)
        self._state_file.write_text(json.dumps(state, indent=2, sort_keys=True))

    def update_and_get_deletable(self, currently_seen: set[str]) -> set[str]:
        now = datetime.now(timezone.utc)
        state = self._load()

        for mac in currently_seen:
            state[mac.lower()] = now.isoformat()

        deletable: set[str] = set()
        for mac, last_seen_iso in list(state.items()):
            if mac in {m.lower() for m in currently_seen}:
                continue
            try:
                last_seen = datetime.fromisoformat(last_seen_iso)
            except ValueError:
                state[mac] = now.isoformat()
                continue
            if now - last_seen > self._grace:
                deletable.add(mac)

        self._save(state)
        return deletable
