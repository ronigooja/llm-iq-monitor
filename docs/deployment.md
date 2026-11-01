# Deployment

## Host

| Item | Value (observed 2026-11-02) |
|---|---|
| Access | `ssh root@50.114.114.252` |
| OS | Debian 12, x86_64 |
| Resources | 1 vCPU, 1.9 GB RAM, about 4.4 GB free disk |
| Software | Python 3.11.2, nginx, Docker, sqlite3 |
| Other services | llm-auth-bridge (Docker, 127.0.0.1:5988), openlist (127.0.0.1:5244); do not touch |
| Port 443 | held by `xboard-node` on `*:443`; nginx sites listen on `127.0.0.1:444` |

Constraints that drive the design: low CPU and RAM, little disk ([data-model.md](data-model.md#retention)), shared host.

## nginx

Already configured by the user; do not modify.

- Site file: `/etc/nginx/sites-available/iq.z0e.dev`, enabled in `sites-enabled`.
- Port 80: serves ACME path, otherwise 301 to HTTPS.
- HTTPS: `127.0.0.1:444`, Cloudflare Origin certificate at `/etc/nginx/ssl/iq.z0e.dev/` (`cert.pem`, `key.pem`, `cloudflare_origin_ca.pem`), `ssl_verify_client on` (Cloudflare authenticated origin pulls). Only Cloudflare-proxied traffic reaches the app.
- Proxy target: `http://127.0.0.1:2839`.
- `nginx -t` passed on 2026-11-02.

The app must listen on `127.0.0.1:2839`. Abuse control for the public API (rate limits, caching) belongs here or in Cloudflare, not in the app.

DNS check note: the local resolver on the developer machine returns a fake-IP (`198.18.x.x`). Verify DNS against a public resolver, for example `dig @1.1.1.1 iq.z0e.dev`.

## Service

- systemd unit `llm-iq-monitor.service`, running as a dedicated unprivileged user.
- Install path `/opt/llm-iq-monitor` (code and virtualenv), data in `/var/lib/llm-iq-monitor`.
- Restart on failure; logs to journald.
- The user is in the `docker` group only if the sandbox below needs it.

## Environment

| Variable | Meaning |
|---|---|
| `GATEWAY_BASE_URL` | Gateway base URL, currently `https://ai.nodemgr.uk/v1` (from the developer's opencode config) |
| `GATEWAY_API_KEY` | Gateway key, see Secrets |
| `DATA_DIR` | SQLite and backups |
| `BIND_ADDR` | `127.0.0.1:2839` |

Reachability of the gateway from the host is not yet verified.

## Secrets

- The key lives only in a root-owned file with mode 600 on the host, loaded through systemd `EnvironmentFile`.
- The repo contains `deploy/env.example` with variable names only.
- Who fills in the key is open: [decisions.md](decisions.md).

## Code sandbox

Model-written code is untrusted. Each code question runs in a one-shot container:

- `docker run --rm --network none --read-only --memory 256m --cpus 0.5 --pids-limit 64 --cap-drop ALL --user 65534`, source and tests mounted read-only, writable tmpfs for scratch.
- Image: `python:3.11-slim` from Docker Hub, pulled once ahead of time into `/var/lib/docker`.
- Limits: 10 s wall time per question; a timeout counts as a failed test, not as an error.
- Pass condition: all hidden tests pass ([benchmark.md](benchmark.md#scoring)).

Docker as the sandbox is not yet confirmed: [decisions.md](decisions.md).

## Release

- Deploy by pulling the repo on the host and restarting the unit.
- Before bumping `dataset_version`, dry-run it with the CLI ([benchmark.md](benchmark.md#dataset-versioning)).
