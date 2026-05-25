# unifi-adguard-sync

One-way sync of device names from UniFi Network → AdGuard Home. Edit your device names in UniFi; they appear in AdGuard's client list automatically within a few minutes.

## Why this exists

Device names live in two places: UniFi (where you set them once) and AdGuard Home (where they show up in query logs and per-client filtering rules). Renaming a device in UniFi doesn't propagate to AdGuard, so the two lists drift apart. This tool keeps AdGuard in sync with UniFi, treating UniFi as the source of truth for device names.

It does NOT touch service hostnames (those are managed by Traefik + AdGuard's wildcard rewrite).

## How it works

```
        ┌────────────────────────────────────────────────────────┐
        │            Homelab VM                                  │
        │                                                         │
        │   ┌─────────────────────────────────┐                  │
        │   │  unifi-adguard-sync (container) │                  │
        │   │  every 5 min:                   │                  │
        │   │   1. fetch UniFi clients        │──► UCG Max       │
        │   │   2. fetch AdGuard clients      │──► AdGuard       │
        │   │   3. diff (ownership-tag fence) │                  │
        │   │   4. add/update/delete          │──► AdGuard       │
        │   │   5. log result                 │                  │
        │   └─────────────────────────────────┘                  │
        └────────────────────────────────────────────────────────┘
```

Only clients tagged `managed-by-unifi-sync` in AdGuard are ever touched. Manually-created AdGuard entries (e.g., entries you made by hand for services like `AdGuard Home` or `Traefik`) are left alone.

## Prerequisites

- A UniFi controller (UniFi OS 4+ / modern Network API). Tested against UCG Max running Network 10.x.
- AdGuard Home with admin credentials.
- Docker + Docker Compose on the host where this will run.
- A Docker network named `proxy_net` (matches the existing homelab pattern). Adjust `docker-compose.yml` if your network is named differently.

## Setup

### 1. Get a UniFi API key

UniFi UI → Settings → System → Cloud Identifiers → Integrations → "Create API Key". Give it a memorable name like "adguard-sync". Copy the key — you only see it once.

### 2. Clone this repo to the host

```bash
git clone <repo-url> /opt/homelab/services/unifi-adguard-sync
cd /opt/homelab/services/unifi-adguard-sync
```

### 3. Configure secrets

```bash
cp .env.example .env
$EDITOR .env
```

Fill in the required fields (see Configuration below).

### 4. Validate connectivity

```bash
docker compose run --rm -e MODE=connectivity-check unifi-adguard-sync
```

Expected output (something like):

```
INFO connectivity UniFi OK — 47 client records visible
INFO connectivity AdGuard OK — 12 client records visible
```

If either fails, fix credentials/network reachability before continuing.

### 5. Dry-run first

Set `DRY_RUN=true` in `.env`, then:

```bash
docker compose up
```

Watch the logs. You'll see lines like:

```
INFO DRY_RUN plan  would_add=3 would_update=1 would_delete=0
INFO DRY_RUN add    name='Living Room AppleTV' mac=aa:bb:cc:11:22:33
INFO DRY_RUN add    name='Office Printer'     mac=aa:bb:cc:dd:ee:ff
INFO DRY_RUN update old_name='Old NAS Name' new_name='Synology NAS' mac=...
```

Cross-check against what you'd expect. If anything looks wrong (e.g., a manually-created AdGuard entry showing up in the delete plan — it shouldn't, but verify), STOP and investigate.

### 6. Go live

Set `DRY_RUN=false` in `.env`, then:

```bash
docker compose down
docker compose up -d
docker compose logs -f
```

The first real cycle runs immediately. After that, sync runs every `SYNC_INTERVAL_SECONDS` (default 300).

## Configuration

All settings live in `.env` (which is gitignored — secrets never leave this host).

| Variable | Default | Purpose |
|---|---|---|
| `UNIFI_HOST` | — | UniFi controller URL (e.g., `https://192.168.1.1`) |
| `UNIFI_API_KEY` | — | API key from UniFi Settings → Integrations |
| `UNIFI_SITE_ID` | `default` | Site identifier (almost always `default`) |
| `UNIFI_VERIFY_SSL` | `true` | Set `false` to skip cert verification (self-signed) |
| `ADGUARD_HOST` | — | AdGuard URL (e.g., `http://192.168.10.11:3000`) |
| `ADGUARD_USER` | — | Admin username |
| `ADGUARD_PASSWORD` | — | Admin password |
| `SYNC_SCOPE` | `fixed` | `fixed` (only fixed-IP clients) or `all` |
| `SYNC_INTERVAL_SECONDS` | `300` | Poll interval |
| `DELETE_GRACE_HOURS` | `24` | Grace before deleting absent clients |
| `DRY_RUN` | `false` | Plan-only mode (no writes) |
| `MODE` | `loop` | `loop` (normal) or `connectivity-check` (one-shot) |
| `OWNERSHIP_TAG` | `managed-by-unifi-sync` | Fence tag for managed clients |
| `LOG_LEVEL` | `info` | `debug` / `info` / `warning` / `error` |
| `TZ` | `America/Toronto` | Log timestamps |

## Operations

### Check status

```bash
docker compose ps         # is the container healthy?
docker compose logs -f    # tail logs
```

### Force a sync now

```bash
docker compose restart    # restart triggers an immediate cycle
```

### Switch back to dry-run

```bash
$EDITOR .env              # set DRY_RUN=true
docker compose up -d      # recreates the container with new env
```

### Rotate credentials

```bash
$EDITOR .env              # update UNIFI_API_KEY or ADGUARD_PASSWORD
docker compose up -d      # recreates with new env, no rebuild needed
```

### Run the test suite

```bash
docker compose run --rm unifi-adguard-sync python -m pytest -v
```

## Troubleshooting

| Symptom | Likely cause | Check |
|---|---|---|
| Container "unhealthy" | No successful sync in 15+ min | `docker compose logs` — look for sync failure errors |
| "UniFi returned 401" | API key wrong or revoked | Regenerate in UniFi → Settings → Integrations |
| "AdGuard returned 401" | Wrong user/password | Re-verify by logging into the AdGuard UI |
| Dry-run shows unexpected deletes | A managed client genuinely vanished from UniFi for 24h+ | Check UniFi's client list; if it should still be there, look for DHCP issues |
| Container restart loop | Almost certainly a config error | `docker compose logs` — the error will be on the first line |

## Future-Gerald notes

> If you're reading this six months from now and have forgotten everything:
>
> 1. **Secrets live in `/opt/homelab/services/unifi-adguard-sync/.env`** on the homelab VM. Not in this repo. Not in git.
> 2. **The state file** (`./data/last_seen.json`) tracks when each MAC was last seen, for the grace-period deletion. If you blow it away, every absent device gets its clock reset to "just now" — no harm done, just delays deletions for 24 hours.
> 3. **Don't manually edit AdGuard clients that have the `managed-by-unifi-sync` tag** — your changes get overwritten on the next cycle. To "release" a client to manual control, remove the tag in AdGuard's UI; the sync will then leave it alone.
> 4. **The tool never touches AdGuard clients without the tag.** Your hand-crafted entries are safe.
> 5. **Updating the tool**: `git pull && docker compose up -d --build` from `/opt/homelab/services/unifi-adguard-sync/`.

## License

TBD (this is internal homelab tooling for now).
