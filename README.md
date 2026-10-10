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

Only AdGuard clients carrying the ownership tag (`os_other` by default) are ever touched. Manually-created AdGuard entries (e.g., entries you made by hand for services like `AdGuard Home` or `Traefik`) are left alone.

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
| `SYNC_SCOPE` | `fixed` | `fixed`: every UniFi client with a fixed IP, connected or not, synced at its reserved IP. `all`: every *currently connected* client at its current IP; clients that go offline are deleted after the grace period and re-added when they return |
| `SYNC_INTERVAL_SECONDS` | `300` | Poll interval |
| `DELETE_GRACE_HOURS` | `24` | Grace before deleting absent clients |
| `DRY_RUN` | `false` | Plan-only mode (no AdGuard writes; still updates `last_seen.json`) |
| `MODE` | `loop` | `loop` (normal) or `connectivity-check` (one-shot) |
| `OWNERSHIP_TAG` | `os_other` | Fence tag for managed clients. Must be an AdGuard built-in tag (AdGuard rejects custom ones), and one you never set by hand |
| `EXCLUDE_MACS` | (empty) | Comma-separated MACs to skip — useful for infra devices (the host VM, hypervisor) you don't want in AdGuard |
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

The Docker image ships only the runtime (no pytest, no `tests/`), so run the suite locally:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
python -m pytest -v
```

## Troubleshooting

| Symptom | Likely cause | Check |
|---|---|---|
| Container "unhealthy" | No successful sync in 15+ min | `docker compose logs` — look for sync failure errors |
| "UniFi returned 401" | API key wrong or revoked | Regenerate in UniFi → Settings → Integrations |
| "AdGuard returned 401" | Wrong user/password | Re-verify by logging into the AdGuard UI |
| Dry-run shows unexpected deletes | A managed client genuinely vanished from UniFi for 24h+ | Check UniFi's client list; if it should still be there, look for DHCP issues |
| Container restart loop | Almost certainly a config error | `docker compose logs` — the error will be on the first line |
| Every device on the network loses DNS at once | The AdGuard host is down, not misconfigured | Confirm the AdGuard guest is actually running **before** changing any config — see Future-Gerald note 6 |

## Future-Gerald notes

> If you're reading this six months from now and have forgotten everything:
>
> 1. **Secrets live in `/opt/homelab/services/unifi-adguard-sync/.env`** on the homelab VM. Not in this repo. Not in git.
> 2. **The state file** (`./data/last_seen.json`) tracks when each MAC was last seen, for the grace-period deletion. Blowing it away (or a corrupted file, which is treated as empty) never causes a wrong deletion, but it has a catch: any managed device that's *already* gone at that moment is never re-recorded, so the sync will never delete it. Remove those from AdGuard by hand. Devices still on the network just start a fresh clock.
> 3. **Don't manually edit AdGuard clients that have the `os_other` tag** — your changes get overwritten on the next cycle. To "release" a client to manual control, remove the tag in AdGuard's UI; the sync will then leave it alone. The flip side: never *add* `os_other` to a hand-made client, or the sync will adopt it. AdGuard only allows its built-in tags, which is why the fence reuses one instead of a custom `managed-by-unifi-sync` tag. Any `$ctag=os_other` filtering rule would apply to every synced device.
> 4. **The tool never touches AdGuard clients without the tag.** Your hand-crafted entries are safe.
> 5. **Updating the tool**: `git pull && docker compose up -d --build` from `/opt/homelab/services/unifi-adguard-sync/`.
> 6. **If the whole network loses DNS, check that the AdGuard host is running before you debug anything else.** Every client gets that host as its only resolver via DHCP, with no secondary — so if it fails to come back after a power event, name resolution dies network-wide and there is no fallback. The failure looks like a *misconfiguration* (the DNS server "doesn't exist") but it's just an unstarted guest. Two traps to avoid: make sure the hypervisor's **"start on boot"** is enabled for that guest, and don't be misled by any *other* AdGuard instance on the network that looks healthy — a spare with its listener bound to loopback will serve its own web UI happily while answering no queries at all. Confirm the host is up first; only then look at AdGuard or UniFi settings.

## License

[MIT](LICENSE)
