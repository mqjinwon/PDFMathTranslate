# CLI OAuth Reuse for OpenAI Codex and Grok

**Date:** 2026-08-03  
**Status:** Approved for implementation  
**Approach:** Thin credential layer + translator extensions (CLI token reuse only)

## Goals

- Reuse existing CLI logins: `~/.codex/auth.json` (ChatGPT/Codex OAuth) and `~/.grok/auth.json` (xAI OIDC).
- No in-app browser login UI in v1.
- On token refresh, write back to the CLI auth files (file-locked) so Codex/Grok CLIs stay in sync.
- Keep existing API-key paths intact.

## Non-goals

- Multi-account profiles, GUI OAuth buttons, reverse proxies, new optional dependencies.

## Decisions

| Topic | Choice |
|-------|--------|
| Auth source | CLI files only |
| OpenAI | New service `openai-codex` using Codex Responses API |
| Grok | Existing `grok` service: API key if set, else OAuth fallback |
| Refresh | Write-back to CLI auth files with exclusive file lock |
| HTTP | Use existing `requests` (no new deps) |

## Architecture

```
pdf2zh/auth/
  __init__.py          # public helpers
  lock.py              # cross-process file lock
  codex_oauth.py       # load/refresh/save ~/.codex/auth.json
  grok_oauth.py        # load/refresh/save ~/.grok/auth.json

translator.py
  OpenAICodexTranslator  # name=openai-codex, Responses SSE
  GrokTranslator         # GROK_API_KEY or get_grok_access_token()
```

## OpenAI Codex path

1. Read `~/.codex/auth.json` → `tokens.access_token`, `refresh_token`, `account_id`.
2. If access JWT near expiry (or missing), POST refresh to `https://auth.openai.com/oauth/token` with client_id `app_EMoamEEZ73f0CkXaXp7hrann`, write updated tokens back under lock.
3. Call `POST https://chatgpt.com/backend-api/codex/responses` with:
   - `Authorization: Bearer <access>`
   - `chatgpt-account-id: <account_id>`
   - `OpenAI-Beta: responses=experimental`
   - SSE stream body (Responses API input format)
4. Parse `response.output_text.delta` events into final text.

Service name: `openai-codex`  
Usage: `pdf2zh example.pdf -s openai-codex` or `-s openai-codex:gpt-5.4`

## Grok path

1. If `GROK_API_KEY` is set (env/config), use it as today against `GROK_BASE_URL` (default `https://api.x.ai/v1`).
2. Else load `~/.grok/auth.json` (OIDC entry with `key`, `refresh_token`, `oidc_client_id`, `expires_at`).
3. If near expiry, POST `https://auth.x.ai/oauth2/token` (from OIDC discovery), update `key`/`refresh_token`/`expires_at` under lock.
4. Use access token as Bearer with existing OpenAI-compatible client.

## Error handling

- Missing auth file / tokens → clear `ValueError` instructing `codex login` or `grok login`.
- Refresh fails (`refresh_token_reused`, 401) → instruct re-login; do not silently fall back to stale access.
- Concurrent refresh → exclusive lock on `<auth>.lock` next to the auth file.

## Testing

- Unit tests: load/refresh/write with temp auth files; translator with mocked HTTP.
- Live: Grok OAuth translation via real `GrokTranslator` when host has valid `~/.grok/auth.json`.
- Codex live depends on valid non-reused refresh/access tokens in `~/.codex/auth.json`.

## Registration surfaces

- CLI service list in `pdf2zh.py`
- GUI `service_map` in `gui.py`
- Converter translator list in `converter.py`
