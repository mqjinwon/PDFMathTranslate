# Web Server + Host Subscription Auth (Ops Runbook)

Run the Gradio UI (`pdf2zh -i`) with **host-side** Grok / OpenAI Codex CLI OAuth tokens. This is Phase 1+3 of the subscription UX: **no browser OAuth login**.

See also: [ADVANCED.md](./ADVANCED.md) (services, authorized mode).

---

## 1. Host prep (CLI login)

On the machine that will host tokens (or the Docker host):

```bash
# Grok Build subscription (writes ~/.grok/auth.json)
grok login

# OpenAI Codex / ChatGPT subscription (writes ~/.codex/auth.json)
codex login
```

Verify files exist:

```bash
ls -la ~/.grok/auth.json ~/.codex/auth.json
```

Optional Python check (no network refresh on status poll):

```bash
python -c "from pdf2zh.auth.status import all_auth_status; print(all_auth_status())"
```

---

## 2. Native (no Docker)

```bash
# Install editable if developing from this repo
# uv pip install -e .

pdf2zh -i --serverport 7860
# Open http://localhost:7860
```

In the UI:

1. Check **Subscription auth (host CLI)** panel (Grok / OpenAI Codex).
2. Click **Refresh auth status** after re-login (status does **not** call token refresh APIs).
3. Choose **Service**:
   - **Auto (recommended)** — Grok OAuth → Codex OAuth / OpenAI API → Grok API (model = backend default)
   - **Grok (subscription)** — forces OAuth via `GROK_PREFER_OAUTH=1` (process-local only)
   - **OpenAI Codex (subscription)** — Codex Responses API
   - **Grok (API key)** / **OpenAI (API key)** — key fields as usual
4. Choose **Model** (when visible):
   - Codex / OpenAI API: `gpt-5.6-luna` (default), `gpt-5.6-terra`, `gpt-5.6-sol`
   - Grok: `grok-4.5` (default), `grok-4`, `grok-3-mini`
5. Choose **Reasoning effort** (OpenAI / Codex only): `low` · `medium` (default) · `high` · `xhigh` · `max`  
   Prefer **medium** for translation volume; Sol + high/max is slow and expensive.

---

## 3. Optional Gradio HTTP basic auth

```bash
# users.txt: one "user:password" per line
pdf2zh -i --serverport 7860 --authorized users.txt
# Optional custom login page:
# pdf2zh -i --authorized users.txt auth.html
```

---

## 4. Docker Compose

```bash
# From repo root; requires Docker + Compose
mkdir -p data
docker compose -f docker-compose.yml up --build
# Open http://localhost:7860
```

Compose mounts (see `docker-compose.yml`):

| Host path | Container path | Purpose |
|-----------|----------------|---------|
| `$HOME/.grok` | `/root/.grok` | Grok CLI OAuth |
| `$HOME/.codex` | `/root/.codex` | Codex CLI OAuth |
| named volume `pdf2zh-config` | `/root/.config/PDFMathTranslate` | app config |
| `./data` | `/data` | optional I/O |

Notes:

- Mounts are **read-write** so token refresh can write back. `:ro` breaks refresh write-back.
- If the image runs as non-root, change mount targets to that user's home.
- Command is `pdf2zh -i --serverport 7860` with `restart: unless-stopped`.
- Do **not** add Gradio `--share` in compose for public networks.

---

## 5. Token expiry

1. Re-run `grok login` / `codex login` on the **host**.
2. Click **Refresh auth status** in the UI (or restart the container if mounts were wrong).
3. Retry translate.

Status states: `connected` | `expired` | `missing` | `error`.

---

## 6. Security

| Rule | Detail |
|------|--------|
| No public `--share` by default | `--share` creates a public Gradio link; keep opt-in only. |
| Reverse proxy + HTTPS | If exposing beyond localhost, put nginx/Caddy TLS in front; prefer `--authorized`. |
| Demo mode | `PDF2ZH_DEMO` must **not** mount host `~/.grok` / `~/.codex`. Public demos stay Google-only. |
| Tokens are host secrets | Treat `auth.json` like passwords; do not bake into images or commit. |
| `GROK_PREFER_OAUTH` | Process-local only; not written into user config files. |

---

## 7. Troubleshooting

| Symptom | Check |
|---------|--------|
| Auth panel: **missing** | Host `grok login` / `codex login`; path exists; Docker volume points at `$HOME/.grok` / `$HOME/.codex`. |
| Auth panel: **expired** | Re-login on host; ensure mounts are rw. |
| 401 / unauthorized during translate | Token refresh failed; re-login; check clock skew; confirm container home is `/root` if using default mounts. |
| Auto fails with no backends | No OAuth files and no `GROK_API_KEY` / `OPENAI_API_KEY`. |
| Demo still asks for keys | Expected: demo does not use subscription mounts. |
| Config pollution of prefer-oauth | Should not appear in `~/.config/PDFMathTranslate`; file a bug if it does. |

Validate compose syntax without building:

```bash
docker compose -f docker-compose.yml config
```
