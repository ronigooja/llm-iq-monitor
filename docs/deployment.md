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
- Port 80: serves the ACME path, otherwise 301 to HTTPS.
- HTTPS: `127.0.0.1:444`, Cloudflare Origin certificate at `/etc/nginx/ssl/iq.z0e.dev/`, `ssl_verify_client on` (Cloudflare authenticated origin pulls). Only Cloudflare-proxied traffic reaches the app.
- Proxy target: `http://127.0.0.1:2839`, which the Web service must listen on.
- `nginx -t` passed on 2026-11-02.

Abuse control for the public API (rate limits, caching) belongs here or in Cloudflare, not in the app.

DNS check note: the developer machine's resolver returns a fake-IP (`198.18.x.x`). Verify DNS against a public resolver, for example `dig @1.1.1.1 iq.z0e.dev`.

## Services

Three systemd units, all running as a dedicated unprivileged user, `Restart=on-failure`, logs to journald:

| Unit | Runs |
|---|---|
| `llm-iq-monitor.service` | Runner ([architecture.md](architecture.md#processes)) |
| `llm-iq-monitor-admin.service` | Admin console on `127.0.0.1:2840`, public path `/admin/` ([below](#admin-console)) |
| `llm-iq-monitor-web.service` | `datasette serve` (plus the `datasette-auth-tokens` plugin) on `127.0.0.1:2839` with `deploy/metadata.yaml`, `--cors`, `--static`, `--template-dir`, and the settings `default_allow_sql off`, `allow_download off`, `default_cache_ttl 60`, `max_returned_rows 2000` |

Install: code and virtualenv in `/opt/llm-iq-monitor`; `uv lock` / `uv sync --frozen` build the virtualenv; systemd runs `.venv/bin/python` directly (no `uv run`, no `pipx`, no Docker Compose). Release: pull the repo on the host, `uv sync --frozen`, restart both units. Before bumping `dataset_version`, dry-run it with the CLI ([benchmark.md](benchmark.md#dataset-versioning)).

## Environment

| Variable | Default | Meaning |
|---|---|---|
| `LLM_IQ_CONFIG_DIR` | `/etc/llm-iq-monitor` | Holds `settings.toml` and `secrets.env` |
| `LLM_IQ_DATA_DIR` | `/var/lib/llm-iq-monitor` | SQLite and backups |

All other settings, including the gateway URL and key, are in [config.md](config.md).

## Host command

The CLI must run as the service user with the two directories above. The host has a wrapper `/usr/local/bin/llm-iq-monitor` (not part of the repo) that does this:

```sh
#!/bin/sh
cd /opt/llm-iq-monitor || exit 1
exec runuser -u llm-iq-monitor -- env LLM_IQ_DATA_DIR=/var/lib/llm-iq-monitor LLM_IQ_CONFIG_DIR=/etc/llm-iq-monitor .venv/bin/llm-iq-monitor "$@"
```

Then `llm-iq-monitor config show`, `llm-iq-monitor config set KEY VALUE`, `llm-iq-monitor manual MODEL` and `llm-iq-monitor migrate` work from any directory.

## Secrets

- The key is entered in the admin console or piped to `config set-key` on the host, and stored in `$LLM_IQ_CONFIG_DIR/secrets.env`, mode 600, owned by the service user; the Runner unit reads it through `EnvironmentFile`. The Web unit does not read it.
- The agent never handles the key; the user enters it in the console.
- The repo contains no key and no `secrets.env`.

## Rating key

- A random token that unlocks the `rate` query ([api.md](api.md#exposure-rules)). Stored in `$LLM_IQ_CONFIG_DIR/rating.env` as `RATING_TOKEN=...`, mode 600, readable by the service user; the Web unit reads it through `EnvironmentFile`. The Runner does not read it.
- Generated on the host by the setup step and never printed by the agent. The user reads it with `cat` on the host and types it into the UI page.
- Rotate by replacing the file contents and restarting the Web unit.
- `datasette-auth-tokens` 0.3 (Apache-2.0) reads it from `deploy/metadata.yaml` through an environment reference.

## Code sandbox

Model-written code is untrusted and must never run in the Runner process. Default: one-shot Docker container per code question, because Docker is already installed.

- `docker run --rm --network none --read-only --cap-drop ALL --security-opt no-new-privileges --memory 256m --cpus 0.5 --pids-limit 64 --user 65534:65534 --tmpfs /tmp:rw,noexec,nosuid,size=32m`; source and tests mounted read-only; no Docker socket, no host env.
- Image `python:3.11-slim`, pulled once ahead of time.
- 10 s wall limit per question, enforced by the Runner, which also removes the container. A timeout counts as a failed test, not as an error.
- Pass condition: all hidden tests pass ([benchmark.md](benchmark.md#scoring)).
- Risk accepted by the user: the Runner's user must reach the Docker daemon, which is root-equivalent on the host. Mitigations: the Runner uses a dedicated non-root user, accepts no external requests and handles model replies only as text; the public Datasette process never touches Docker.

## Admin console

- Unit `llm-iq-monitor-admin.service` (`deploy/llm-iq-monitor-admin.service`), the only process besides the CLI that writes `settings.toml` and `secrets.env`. The Runner reloads settings by itself.
- Public through nginx: forward `location /admin/` to `127.0.0.1:2840` without stripping the prefix (`deploy/nginx-admin.conf.example`), with `X-Forwarded-For` set from `$http_cf_connecting_ip` only: the lockout keys on it, and a client-supplied value would bypass it.
- Admin token: `ADMIN_TOKEN` in `/etc/llm-iq-monitor/admin.env` (mode 600, service user), at least 24 characters; the service refuses to start without it. The user reads it with `cat`; the agent never reads it.
- Session cookie `HttpOnly; Secure; SameSite=Strict; Path=/admin`, 12 h, kept in memory (a restart logs everyone out). Every POST/PUT needs header `X-Admin: 1`. 5 failed logins per client IP lock it for 15 minutes. Responses are `no-store`; the gateway key never appears in a response or log.
