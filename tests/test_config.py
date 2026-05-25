import os
import pytest
from src.config import Config, ConfigError


def _base_env() -> dict:
    return {
        "UNIFI_HOST": "https://10.0.0.1",
        "UNIFI_API_KEY": "key",
        "ADGUARD_HOST": "http://10.0.0.2:3000",
        "ADGUARD_USER": "admin",
        "ADGUARD_PASSWORD": "secret",
    }


def test_loads_required_fields(monkeypatch):
    for k, v in _base_env().items():
        monkeypatch.setenv(k, v)
    cfg = Config.from_env()
    assert cfg.unifi_host == "https://10.0.0.1"
    assert cfg.unifi_api_key == "key"
    assert cfg.adguard_host == "http://10.0.0.2:3000"
    assert cfg.adguard_user == "admin"
    assert cfg.adguard_password == "secret"


def test_defaults_applied(monkeypatch):
    for k, v in _base_env().items():
        monkeypatch.setenv(k, v)
    cfg = Config.from_env()
    assert cfg.unifi_site_id == "default"
    assert cfg.unifi_verify_ssl is True
    assert cfg.sync_scope == "fixed"
    assert cfg.sync_interval_seconds == 300
    assert cfg.delete_grace_hours == 24
    assert cfg.dry_run is False
    assert cfg.mode == "loop"
    assert cfg.ownership_tag == "managed-by-unifi-sync"
    assert cfg.log_level == "info"


def test_missing_required_raises(monkeypatch):
    monkeypatch.delenv("UNIFI_HOST", raising=False)
    with pytest.raises(ConfigError, match="UNIFI_HOST"):
        Config.from_env()


def test_bool_parsing(monkeypatch):
    for k, v in _base_env().items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("DRY_RUN", "true")
    monkeypatch.setenv("UNIFI_VERIFY_SSL", "false")
    cfg = Config.from_env()
    assert cfg.dry_run is True
    assert cfg.unifi_verify_ssl is False


def test_invalid_sync_scope_raises(monkeypatch):
    for k, v in _base_env().items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("SYNC_SCOPE", "everything")
    with pytest.raises(ConfigError, match="SYNC_SCOPE"):
        Config.from_env()


def test_invalid_mode_raises(monkeypatch):
    for k, v in _base_env().items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("MODE", "rocket")
    with pytest.raises(ConfigError, match="MODE"):
        Config.from_env()
