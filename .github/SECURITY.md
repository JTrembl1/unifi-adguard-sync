# Security Policy

## Supported Versions

This is small-scale homelab tooling maintained by a single person. Only the
latest code on `main` is supported — there are no maintained release branches
or backports.

| Version | Supported |
| ------- | --------- |
| `main` (latest) | ✅ |
| Anything older | ❌ |

## Reporting a Vulnerability

Please **do not open a public issue** for security problems.

Instead, use GitHub's private vulnerability reporting:

1. Go to the repository's **Security** tab.
2. Click **Report a vulnerability**.
3. Describe the issue, how to reproduce it, and its impact.

You can expect an acknowledgement within a week. Since this is a spare-time
project, fixes are made on a best-effort basis, but credential-handling issues
will be prioritized.

## Scope

Things that are in scope and especially worth reporting:

- Leakage of UniFi API keys or AdGuard credentials (e.g., secrets appearing in
  logs, error messages, or state files).
- The sync writing to AdGuard clients it doesn't own (bypassing the
  `managed-by-unifi-sync` ownership tag), or otherwise destructive behavior
  outside the documented one-way name sync.
- Injection via untrusted device names fetched from UniFi (e.g., a hostile
  DHCP hostname breaking the AdGuard API calls or log output).
- Dependency vulnerabilities in `requests` or the Docker base image that are
  actually reachable from this code.

Out of scope:

- Vulnerabilities in UniFi Network or AdGuard Home themselves — report those
  upstream to Ubiquiti or AdGuard.
- Issues that require the attacker to already control the host, the `.env`
  file, or the Docker socket.
- Running the container with `UNIFI_VERIFY_SSL=false` — that's a documented,
  user-chosen trade-off for self-signed certificates.

## Deployment Notes

This tool holds admin credentials for AdGuard Home and an API key for the
UniFi controller. If you deploy it:

- Keep secrets in `.env` (gitignored) — never commit them.
- Run it on a trusted network segment; it needs reach to both the UniFi
  controller and the AdGuard admin API, nothing else.
- Rotate the UniFi API key and AdGuard password if you suspect exposure
  (`$EDITOR .env && docker compose up -d` — no rebuild needed).
