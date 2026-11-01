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

Two systemd units, both running as a dedicated unprivileged user, `Restart=on-failure`, logs to journald:

| Unit | Runs |
|---|---|
| `llm-iq-monitor.service` | Runner ([architecture.md](architecture.md#processes)) |
| `llm-iq-monitor-web.service` | `datasette serve` on `127.0.0.1:2839` with `deploy/metadata.yaml`, `--cors`, `--static`, `--template-dir`, and the settings `default_allow_sql off`, `allow_download off`, `default_cache_ttl 60`, `max_returned_rows 2000` |

Install: code and virtualenv in `/opt/llm-iq-monitor`; `uv lock` / `uv sync --frozen` build the virtualenv; systemd runs `.venv/bin/python` directly (no `uv run`, no `pipx`, no Docker Compose). Release: pull the repo on the host, `uv sync --frozen`, restart both units. Before bumping `dataset_version`, dry-run it with the CLI ([benchmark.md](benchmark.md#dataset-versioning)).

## Environment

| Variable | Default | Meaning |
|---|---|---|
| `LLM_IQ_CONFIG_DIR` | `/etc/llm-iq-monitor` | Holds `settings.toml` and `secrets.env` |
| `LLM_IQ_DATA_DIR` | `/var/lib/llm-iq-monitor` | SQLite and backups |

All other settings, including the gateway URL and key, are in [config.md](config.md).

## Secrets

- The key is entered through the config menu ([config.md](config.md#interactive-menu)) on the host and stored in `$LLM_IQ_CONFIG_DIR/secrets.env`, mode 600, owned by the service user; the Runner unit reads it through `EnvironmentFile`. The Web unit does not read it.
- The agent never handles the key; the user types it into the menu.
- The repo contains no key and no `secrets.env`.

## Code sandbox

Model-written code is untrusted and must never run in the Runner process. Default: one-shot Docker container per code question, because Docker is already installed.

- `docker run --rm --network none --read-only --cap-drop ALL --security-opt no-new-privileges --memory 256m --cpus 0.5 --pids-limit 64 --user 65534:65534 --tmpfs /tmp:rw,noexec,nosuid,size=32m`; source and tests mounted read-only; no Docker socket, no host env.
- Image `python:3.11-slim`, pulled once ahead of time.
- 10 s wall limit per question, enforced by the Runner, which also removes the container. A timeout counts as a failed test, not as an error.
- Pass condition: all hidden tests pass ([benchmark.md](benchmark.md#scoring)).
- Caveat: the Runner's user needs access to the Docker daemon, which is root-equivalent on the host. Alternative: nsjail. Choice is open: [decisions.md](decisions.md).
