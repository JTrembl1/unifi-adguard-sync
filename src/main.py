import logging
import os
import signal
import sys
import time
from pathlib import Path

from src.config import Config, ConfigError
from src.unifi import UnifiClient, UnifiError
from src.adguard import AdGuardClient, AdGuardError
from src.grace import GraceTracker
from src.sync import run_sync_cycle


HEALTH_FILE = Path("/data/last_sync_ok")
STATE_FILE = Path("/data/last_seen.json")


def _setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


def _connectivity_check(cfg: Config) -> int:
    logger = logging.getLogger("connectivity")
    unifi = UnifiClient(cfg.unifi_host, cfg.unifi_api_key, cfg.unifi_site_id, cfg.unifi_verify_ssl)
    adguard = AdGuardClient(cfg.adguard_host, cfg.adguard_user, cfg.adguard_password)

    ok = True
    try:
        clients = unifi.fetch_clients()
        logger.info("UniFi OK — %d client records visible", len(clients))
    except UnifiError as e:
        logger.error("UniFi check FAILED: %s", e)
        ok = False
    try:
        clients = adguard.list_clients()
        logger.info("AdGuard OK — %d client records visible", len(clients))
    except AdGuardError as e:
        logger.error("AdGuard check FAILED: %s", e)
        ok = False
    return 0 if ok else 1


def _touch_health_file() -> None:
    HEALTH_FILE.parent.mkdir(parents=True, exist_ok=True)
    HEALTH_FILE.touch()


_should_stop = False


def _handle_signal(signum, frame):
    global _should_stop
    _should_stop = True


def _loop(cfg: Config) -> int:
    logger = logging.getLogger("loop")
    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    unifi = UnifiClient(cfg.unifi_host, cfg.unifi_api_key, cfg.unifi_site_id, cfg.unifi_verify_ssl)
    adguard = AdGuardClient(cfg.adguard_host, cfg.adguard_user, cfg.adguard_password)
    grace = GraceTracker(state_file=STATE_FILE, grace_hours=cfg.delete_grace_hours)

    logger.info(
        "starting loop  scope=%s interval=%ds dry_run=%s grace_hours=%d",
        cfg.sync_scope, cfg.sync_interval_seconds, cfg.dry_run, cfg.delete_grace_hours,
    )

    while not _should_stop:
        try:
            result = run_sync_cycle(
                unifi=unifi, adguard=adguard, grace=grace,
                scope=cfg.sync_scope, ownership_tag=cfg.ownership_tag,
                dry_run=cfg.dry_run,
            )
            logger.info(
                "sync ok  added=%d updated=%d deleted=%d untouched=%d failed=%d took=%dms",
                result.added, result.updated, result.deleted,
                result.untouched, result.failed, result.took_ms,
            )
            if result.failed == 0:
                _touch_health_file()
        except UnifiError as e:
            logger.error("sync failed  stage=unifi_fetch error=%s", e)
        except AdGuardError as e:
            logger.error("sync failed  stage=adguard error=%s", e)
        except Exception as e:
            logger.exception("sync failed  stage=unknown error=%s", e)

        for _ in range(cfg.sync_interval_seconds):
            if _should_stop:
                break
            time.sleep(1)

    logger.info("shutting down")
    return 0


def main() -> int:
    try:
        cfg = Config.from_env()
    except ConfigError as e:
        print(f"FATAL: {e}", file=sys.stderr)
        return 2

    _setup_logging(cfg.log_level)

    if cfg.mode == "connectivity-check":
        return _connectivity_check(cfg)
    return _loop(cfg)


if __name__ == "__main__":
    sys.exit(main())
