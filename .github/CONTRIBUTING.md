# Contributing

Thanks for your interest! This is a small, single-maintainer homelab tool with
a deliberately narrow scope: **one-way device-name sync from UniFi Network to
AdGuard Home**. Contributions are welcome, but please keep that scope in mind
— features outside it (two-way sync, DNS rewrites, service hostnames) will
likely be declined.

## Before You Start

- **Bugs**: Open an issue with logs (`docker compose logs`), your config
  (redact secrets!), and UniFi/AdGuard versions.
- **Features**: Open an issue first to discuss before writing code. This
  avoids wasted effort on out-of-scope work.
- **Security issues**: Do NOT open a public issue — see
  [SECURITY.md](SECURITY.md).

## Development Setup

Requires Python 3.12+.

```bash
git clone git@github.com:JTrembl1/unifi-adguard-sync.git
cd unifi-adguard-sync
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

## Running Tests

```bash
python -m pytest -v
```

All tests must pass. New behavior needs new tests — the suite uses `responses`
for HTTP mocking and `freezegun` for time-dependent logic (the deletion grace
period), so no live UniFi or AdGuard instance is needed.

If you want to test against real hardware, use `MODE=connectivity-check` and
`DRY_RUN=true` (see the README) — never point untested changes at a live
AdGuard with `DRY_RUN=false`.

## Pull Requests

- Keep PRs small and focused — one change per PR.
- Match the existing code style; the codebase is plain Python with `requests`,
  no framework.
- Update the README if you change configuration variables or operational
  behavior.
- Describe how you tested the change (unit tests, dry-run against real
  hardware, etc.).

## Ground Rules

- Never commit secrets. Credentials belong in `.env`, which is gitignored.
- The ownership-tag fence (`OWNERSHIP_TAG`, `os_other` by default) is the core safety
  invariant: the tool must never modify AdGuard clients it doesn't own.
  Changes that weaken it will not be merged.
- Be respectful — see the [Code of Conduct](CODE_OF_CONDUCT.md).
