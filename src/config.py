import os
from dataclasses import dataclass


class ConfigError(ValueError):
    pass


_VALID_SCOPES = {"fixed", "all"}
_VALID_MODES = {"loop", "connectivity-check"}


def _required(name: str) -> str:
    val = os.environ.get(name)
    if not val:
        raise ConfigError(f"Required env var {name} is not set")
    return val


def _bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError as e:
        raise ConfigError(f"{name} must be an integer, got {raw!r}") from e


@dataclass(frozen=True)
class Config:
    unifi_host: str
    unifi_api_key: str
    unifi_site_id: str
    unifi_verify_ssl: bool
    adguard_host: str
    adguard_user: str
    adguard_password: str
    sync_scope: str
    sync_interval_seconds: int
    delete_grace_hours: int
    dry_run: bool
    mode: str
    ownership_tag: str
    log_level: str

    @classmethod
    def from_env(cls) -> "Config":
        scope = os.environ.get("SYNC_SCOPE", "fixed")
        if scope not in _VALID_SCOPES:
            raise ConfigError(
                f"SYNC_SCOPE must be one of {sorted(_VALID_SCOPES)}, got {scope!r}"
            )
        mode = os.environ.get("MODE", "loop")
        if mode not in _VALID_MODES:
            raise ConfigError(
                f"MODE must be one of {sorted(_VALID_MODES)}, got {mode!r}"
            )
        return cls(
            unifi_host=_required("UNIFI_HOST"),
            unifi_api_key=_required("UNIFI_API_KEY"),
            unifi_site_id=os.environ.get("UNIFI_SITE_ID", "default"),
            unifi_verify_ssl=_bool("UNIFI_VERIFY_SSL", True),
            adguard_host=_required("ADGUARD_HOST"),
            adguard_user=_required("ADGUARD_USER"),
            adguard_password=_required("ADGUARD_PASSWORD"),
            sync_scope=scope,
            sync_interval_seconds=_int("SYNC_INTERVAL_SECONDS", 300),
            delete_grace_hours=_int("DELETE_GRACE_HOURS", 24),
            dry_run=_bool("DRY_RUN", False),
            mode=mode,
            ownership_tag=os.environ.get("OWNERSHIP_TAG", "managed-by-unifi-sync"),
            log_level=os.environ.get("LOG_LEVEL", "info"),
        )
