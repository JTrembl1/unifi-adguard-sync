# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A small homelab service that does a **one-way** sync of device names from UniFi Network (source of truth) into AdGuard Home's persistent client list. It runs as a Docker container on a polling loop. Scope is deliberately narrow: two-way sync, DNS rewrites, and service hostnames are out of scope (see `.github/CONTRIBUTING.md`).

## Commands

```bash
# Dev setup (Python 3.12+); a .venv already exists in the repo root
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Tests (pytest, responses for HTTP mocking, freezegun for time)
python -m pytest -v
python -m pytest tests/test_diff.py -v                       # one file
python -m pytest tests/test_sync.py::test_dry_run_does_not_write -v   # one test

# Run against real hardware (needs a filled-in .env) — always dry-run first
docker compose run --rm -e MODE=connectivity-check unifi-adguard-sync
docker compose up            # with DRY_RUN=true in .env
```

There is no linter or formatter configured.

`docker-compose.yml` attaches to an external network `proxy_net`, so the compose commands fail on a machine where that network doesn't exist. The `./data:/data` bind mount replaces the Dockerfile's `chown`, so the host's `./data` must be writable by the container's `appuser`, or the health file never gets written.

Tests can't run in the container: the Dockerfile installs only `requests` and copies only `src/`, so the image has neither pytest nor `tests/`. Run them locally.

## Architecture

Entry point is `python -m src.main` (the package is literally named `src`, and imports are `from src.x import ...`). `main.py` loads `Config.from_env()` and dispatches on `MODE`: `connectivity-check` (one-shot read of both APIs) or `loop`.

Each loop iteration calls `sync.run_sync_cycle()`, which is the pipeline:

1. Fetch from UniFi with `X-API-KEY`, with the source chosen by `SYNC_SCOPE`:
   - `all` → `UnifiClient.fetch_clients()`: GET `/proxy/network/integration/v1/sites/{site}/clients` (Integration API), paging with `offset`/`limit` (200 per page, the API max) until `totalCount` is reached. It returns only *currently connected* clients. Records are camelCase: `id`, `type`, `name`, `macAddress`, `ipAddress` (sometimes missing), `connectedAt`, `uplinkDeviceId`, `access`. There are no `fixedIp` or `hostname` fields.
   - `fixed` → `UnifiClient.fetch_fixed_ip_clients()`: GET `/proxy/network/api/s/{site}/rest/user` (the classic known-clients list, which accepts the same API key). It returns every known client, connected or not, as snake_case records (`mac`, `name`, `hostname`, `use_fixedip`, `fixed_ip`, `last_ip`, ...) inside a `{"meta": {"rc": "ok"}, "data": [...]}` envelope. Records with `use_fixedip` and a `fixed_ip` are reshaped into the Integration shape, with `ipAddress` = the reserved IP and `fixedIp: True`. Offline reserved devices therefore stay in AdGuard.
   - Either path raises `UnifiError` on any failure (a bad page, a non-`ok` `meta.rc`). A partial list would start grace clocks for the missing devices. Both paths use `UNIFI_SITE_ID`, so it must be the site *name* (e.g. `default`), which the classic API requires.
2. `mapping.filter_by_scope()` (`fixed` keeps only `fixedIp is True`, which is now just a guard because the fixed source already filters), then `mapping.filter_excluded_macs()`.
3. `AdGuardClient.list_clients()`: GET `/control/clients`. This runs *before* the grace update, so a failed AdGuard fetch aborts the cycle without touching `last_seen.json`.
4. `mapping.to_adguard_payload()`: builds the AdGuard client dict. `ids` = [MAC, IP], `tags` = [ownership tag], name falls back `name` → `hostname` → `unknown-<last4 of MAC>`. Records without a `macAddress` are dropped.
5. `GraceTracker.update_and_get_deletable()`: stamps every in-scope MAC as seen now in `/data/last_seen.json` and returns MACs already in the file that have been absent longer than `DELETE_GRACE_HOURS`.
6. `diff.compute_diff()`: matches desired vs. AdGuard clients **by MAC** (pulled from `ids` via regex) and returns a `SyncPlan` (add / update / delete).
7. Apply the plan via `AdGuardClient` (basic auth, `/control/clients/{add,update,delete}`), or just log it when `DRY_RUN`. Per-item write failures are counted in `SyncResult.failed` and don't abort the cycle. A fetch failure from either side does abort it. `UnifiError`/`AdGuardError` are logged by stage, and anything else (e.g. an unwrapped `resp.json()` decode error) falls through to `main.py`'s generic `stage=unknown` handler.

`DRY_RUN` skips only the AdGuard writes. The grace tracker still updates `last_seen.json`, the health file still gets touched, and the `sync ok added=N updated=N deleted=N` log line reports the *planned* counts. So that line alone doesn't tell you whether writes happened.

On success `main.py` touches `/data/last_sync_ok`. The docker-compose healthcheck marks the container unhealthy if that file is older than 15 minutes. The `/data` paths are hardcoded in `main.py`, so running the loop outside the container needs a writable `/data`.

### Invariants to preserve

- **Ownership-tag fence.** `diff._is_managed()` filters AdGuard clients by `OWNERSHIP_TAG` before anything else. Untagged clients must never be updated or deleted. This is the core safety property, and changes that weaken it won't be accepted. AdGuard Home rejects any client tag outside its built-in list (`device_*`, `os_*`, `user_*`) on both add and update, so `OWNERSHIP_TAG` defaults to `os_other` and `config.py` refuses anything not in `_ADGUARD_TAGS`. The original `managed-by-unifi-sync` tag never worked against a real AdGuard. The tests mock AdGuard and would not catch this.
- **AdGuard addresses clients by name, not ID.** Updates send `{"name": <old_name>, "data": <new payload>}` and deletes send the name. A rename is therefore an update keyed by the *current* AdGuard name.
- **A delete needs two things:** the MAC must be managed in AdGuard but absent from the desired set, *and* it must appear in `deletable_macs` from the grace tracker. A MAC that has never been recorded in `last_seen.json` is never deletable. Deleting the state file (or letting it get corrupted, which is treated as empty) never causes a wrong deletion. But it doesn't just delay deletions either: any managed client that is already absent at that point never gets re-recorded, so the sync will never delete it. It has to be removed by hand.
- MACs are lowercased everywhere: config parsing, the exclude filter, `to_adguard_payload` ids, `extract_mac`, and grace keys. `_payloads_differ` compares `ids` as case-sensitive sets, and AdGuard returns MACs lowercased, so a mixed-case id would cause an update every cycle. Keep MACs lowercase.
- AdGuard matches a MAC id only through its *own* DHCP leases. Here UniFi does DHCP, so the MAC in `ids` is used only by the diff, and AdGuard identifies the device by the IP id. That is why `SYNC_SCOPE=fixed` (stable, reserved IPs) gives the most reliable names.
- Anything that shrinks the desired set makes the dropped MACs "absent", and the sync deletes them from AdGuard once the grace period passes. That includes adding an already-managed MAC to `EXCLUDE_MACS` and switching `SYNC_SCOPE` from `all` to `fixed`.
- If AdGuard already has an *untagged* client with the same MAC or name, the diff plans an add every cycle. AdGuard rejects it, and it shows up as a persistent `failed=1`. This is the fence working as intended, not a bug to "fix" by matching untagged clients.

### Tests

The unit tests need no live services. `test_sync.py` drives `run_sync_cycle` with `MagicMock` fakes for the UniFi, AdGuard and grace objects. The API client tests use `responses`, and the grace tests use `freezegun` plus `tmp_path`. `run_sync_cycle` takes keyword-only dependencies so tests can inject these fakes.

## Conventions

- Plain Python + `requests`, no framework. Errors are wrapped in module-specific exceptions (`ConfigError`, `UnifiError`, `AdGuardError`).
- If you add or change an env var, update `config.py`, `.env.example`, and the README's Configuration table together.
- Never point untested changes at a live AdGuard with `DRY_RUN=false`.
