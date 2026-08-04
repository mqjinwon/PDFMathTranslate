# Web Subscription UX (Phase 1) + Ops (Phase 3) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the existing Gradio web UI (`pdf2zh -i`) clearly support host-side Grok/OpenAI subscription (CLI OAuth) tokens plus API keys, show auth status, and document/operate Docker with auth volume mounts and basic hardening — without browser OAuth login.

**Architecture:** Reuse `pdf2zh/auth/*` loaders and `service_chain.resolve_service` for backend selection. Add a thin `auth/status.py` that reports connection state only (no refresh on status poll). Gradio gains an Auto/Grok-OAuth/Codex-OAuth service surface and a status panel. Ops changes are compose volumes + docs; no multi-user OAuth store.

**Tech Stack:** Python 3.11–3.12, Gradio (existing), PyMuPDF/pdf2zh pipeline, existing `~/.grok/auth.json` / `~/.codex/auth.json`, Docker Compose, unittest.

## Global Constraints

- Phase 2 **out of scope**: no browser “Sign in with Grok/ChatGPT” PKCE UI, no per-browser OAuth accounts.
- Do **not** persist `GROK_PREFER_OAUTH` (or null API keys) into user config (existing rule in `BaseTranslator._PROCESS_LOCAL_ENV_KEYS`).
- Auth status poll must **not** call token refresh by default (avoid refresh-token races with CLI).
- `PDF2ZH_DEMO` must not mount or expose host subscription tokens.
- Public Gradio `share=` stays opt-in (`--share`); default off.
- Prose/docs for user-facing README sections: Korean OK for this fork if editing `docs/README_ko-KR.md`; keep code/identifiers English. Primary ops docs: English in `docs/ADVANCED.md` + short Korean note in `README.md` if that file is EN.
- Prefer smallest change; do not reintroduce hard-coded translator class lists — use `registry`.
- Hyperlink preservation: out of scope.

---

## File map

| File | Responsibility |
|------|----------------|
| **Create** `pdf2zh/auth/status.py` | Pure status reports for Grok + Codex CLI auth files |
| **Modify** `pdf2zh/auth/__init__.py` | Export status helpers |
| **Create** `pdf2zh/gui_services.py` | UI label ↔ service string + envs mapping (keep `gui.py` thinner) |
| **Modify** `pdf2zh/gui.py` | Auth panel, service dropdown, wire translate path |
| **Modify** `docker-compose.yml` | Auth mounts, restart, command/port clarity |
| **Create** `docs/WEB_SERVER.md` (or section in ADVANCED) | Runbook: host login, mount, authorized, security |
| **Modify** `README.md` and/or `docs/ADVANCED.md` | Link to web+subscription ops |
| **Create** `test/test_auth_status.py` | Status unit tests with temp auth files |
| **Create** `test/test_gui_services.py` | Label → service/envs mapping tests |

---

### Task 1: Auth status module (Grok + Codex)

**Files:**
- Create: `pdf2zh/auth/status.py`
- Modify: `pdf2zh/auth/__init__.py`
- Test: `test/test_auth_status.py`

**Interfaces:**
- Consumes: `pdf2zh.auth.grok_oauth.load_grok_credentials`, `pdf2zh.auth.codex_oauth.load_codex_credentials` (load only; no refresh)
- Produces:
  - `AuthState` Literal or enum-like strings: `"connected" | "expired" | "missing" | "error"`
  - `@dataclass AuthProviderStatus`: `provider: str`, `state: str`, `detail: str`, `expires_at: str | None`, `hint: str`
  - `def grok_auth_status(auth_path: Path | None = None) -> AuthProviderStatus`
  - `def codex_auth_status(auth_path: Path | None = None) -> AuthProviderStatus`
  - `def all_auth_status(...) -> dict[str, AuthProviderStatus]` keys `"grok"`, `"codex"`

- [x] **Step 1: Write the failing tests**

```python
# test/test_auth_status.py
import json, time, tempfile, unittest
from pathlib import Path
from pdf2zh.auth.status import grok_auth_status, codex_auth_status

class TestGrokStatus(unittest.TestCase):
    def test_missing_file(self):
        p = Path(tempfile.mkdtemp()) / "nope.json"
        s = grok_auth_status(p)
        self.assertEqual(s.state, "missing")
        self.assertIn("grok login", s.hint.lower())

    def test_connected_future_expiry(self):
        d = Path(tempfile.mkdtemp())
        auth = d / "auth.json"
        exp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() + 3600))
        auth.write_text(json.dumps({
            "https://auth.x.ai::client": {
                "key": "tok",
                "refresh_token": "rt",
                "oidc_client_id": "cid",
                "oidc_issuer": "https://auth.x.ai",
                "auth_mode": "oidc",
                "expires_at": exp,
                "email": "a@b.c",
            }
        }))
        s = grok_auth_status(auth)
        self.assertEqual(s.state, "connected")

    def test_expired(self):
        d = Path(tempfile.mkdtemp())
        auth = d / "auth.json"
        exp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - 3600))
        auth.write_text(json.dumps({
            "https://auth.x.ai::client": {
                "key": "tok",
                "refresh_token": "rt",
                "oidc_client_id": "cid",
                "oidc_issuer": "https://auth.x.ai",
                "auth_mode": "oidc",
                "expires_at": exp,
            }
        }))
        s = grok_auth_status(auth)
        self.assertEqual(s.state, "expired")

class TestCodexStatus(unittest.TestCase):
    def test_missing(self):
        s = codex_auth_status(Path(tempfile.mkdtemp()) / "auth.json")
        self.assertEqual(s.state, "missing")
        self.assertIn("codex login", s.hint.lower())
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
python -m pytest test/test_auth_status.py -v
```

Expected: import/module missing or functions undefined.

- [ ] **Step 3: Implement `pdf2zh/auth/status.py`**

```python
# Core logic sketch (full file in implementation):
# - grok: load_grok_credentials(path); if fails missing/error;
#   if expires_at and expires_at < now + 60s -> expired else connected
# - codex: load_codex_credentials; use JWT exp via credentials.access_expires_at
# - hints: "Run `grok login` on the host." / "Run `codex login` on the host."
# - NEVER call get_*_access_token / refresh_* here
```

- [ ] **Step 4: Export from `auth/__init__.py`**

```python
from pdf2zh.auth.status import (
    AuthProviderStatus,
    all_auth_status,
    codex_auth_status,
    grok_auth_status,
)
```

- [ ] **Step 5: Run tests — expect PASS**

```bash
python -m pytest test/test_auth_status.py -v
```

- [ ] **Step 6: Commit**

```bash
git add pdf2zh/auth/status.py pdf2zh/auth/__init__.py test/test_auth_status.py
git commit -m "[feat] Add Grok/Codex CLI auth status helpers for web UI"
```

---

### Task 2: GUI service label mapping

**Files:**
- Create: `pdf2zh/gui_services.py`
- Test: `test/test_gui_services.py`

**Interfaces:**
- Consumes: none from Task 1 (independent)
- Produces:
  - `SERVICE_CHOICES: list[str]` ordered for dropdown
  - `def resolve_gui_service(label: str) -> tuple[str, dict[str, str]]`  
    returns `(service_spec, envs)` where `service_spec` is e.g. `"auto"`, `"grok"`, `"openai-codex"`, `"openai"`, or other `translator.name`
  - Mapping rules (exact):

| UI label | service_spec | envs extras |
|----------|--------------|-------------|
| `Auto (recommended)` | `auto` | `{}` |
| `Grok (subscription)` | `grok` | `{"GROK_PREFER_OAUTH": "1"}` |
| `OpenAI Codex (subscription)` | `openai-codex` | `{}` |
| `Grok (API key)` | `grok` | `{}` (no prefer) |
| `OpenAI (API key)` | `openai` | `{}` |
| Other labels from `gui_service_map()` | `cls.name` | `{}` |

- Prefer subscription labels first, then API variants, then rest of `gui_service_map()` without duplicating Grok/OpenAI/Codex entries.

- [ ] **Step 1: Write failing tests**

```python
# test/test_gui_services.py
from pdf2zh.gui_services import resolve_gui_service, SERVICE_CHOICES

def test_auto():
    spec, envs = resolve_gui_service("Auto (recommended)")
    assert spec == "auto"
    assert envs == {}

def test_grok_subscription_sets_prefer_oauth():
    spec, envs = resolve_gui_service("Grok (subscription)")
    assert spec == "grok"
    assert envs.get("GROK_PREFER_OAUTH") == "1"

def test_grok_api_no_prefer():
    spec, envs = resolve_gui_service("Grok (API key)")
    assert spec == "grok"
    assert "GROK_PREFER_OAUTH" not in envs

def test_codex():
    spec, envs = resolve_gui_service("OpenAI Codex (subscription)")
    assert spec == "openai-codex"

def test_choices_include_auto_first():
    assert SERVICE_CHOICES[0].startswith("Auto")
```

- [ ] **Step 2: Run — expect FAIL**

```bash
python -m pytest test/test_gui_services.py -v
```

- [ ] **Step 3: Implement `gui_services.py`**

Use `gui_service_map()` from `pdf2zh.registry` to append remaining display names not already covered.

- [ ] **Step 4: Run — expect PASS**

```bash
python -m pytest test/test_gui_services.py -v
```

- [ ] **Step 5: Commit**

```bash
git add pdf2zh/gui_services.py test/test_gui_services.py
git commit -m "[feat] Map Gradio service labels to auto/OAuth/API backends"
```

---

### Task 3: Wire Gradio auth panel + service dropdown + translate

**Files:**
- Modify: `pdf2zh/gui.py` (imports; `translate_file`; service dropdown; new status UI; `on_select_service`)
- Modify: keep using `build_translator` — do not resurrect class lists

**Interfaces:**
- Consumes: `all_auth_status`, `resolve_gui_service`, `SERVICE_CHOICES`
- Produces: working UI behavior (manual smoke)

**`translate_file` change (conceptual):**

```python
from pdf2zh.gui_services import resolve_gui_service

service_spec, oauth_envs = resolve_gui_service(service)  # service is UI label
# merge oauth_envs into _envs after reading API key fields
_envs = {**_envs, **oauth_envs}
# pass service=service_spec into TranslateRequest / translate kwargs
# NOT the Gradio label string
```

Today `translator = service_map[service]` then `f"{translator.name}"` — replace with `resolve_gui_service` so **Auto** works (label is not a class key).

**Auth panel UI (inside `with gr.Blocks` before file upload):**

```python
auth_md = gr.Markdown(value=_format_auth_markdown(all_auth_status()))
refresh_btn = gr.Button("Refresh auth status")
refresh_btn.click(fn=lambda: _format_auth_markdown(all_auth_status()), outputs=auth_md)
```

`_format_auth_markdown` example output:

```markdown
### Subscription auth (host CLI)
- **Grok:** connected (expires …) | missing — run `grok login`
- **OpenAI Codex:** …
```

**Service dropdown:**

```python
service = gr.Dropdown(
    label="Service",
    choices=SERVICE_CHOICES,
    value=SERVICE_CHOICES[0],  # Auto
)
```

**`on_select_service`:** if label is subscription Auto/Grok(sub)/Codex, hide API key textboxes (or show only MODEL fields); if API key service, show key fields as today.

**Pre-translate guard (optional soft):** if `service_spec in ("auto", "grok", "openai-codex")` and corresponding status is `missing`/`expired`, `gr.Warning(...)` with hint — still allow attempt if auto can fall through.

- [ ] **Step 1: Implement mapping in `translate_file` + unit-level sanity**

No full Gradio test required. Add a small pure helper test if needed:

```python
# in test_gui_services.py
def test_merge_envs_prefer_oauth_wins_for_subscription():
    _, o = resolve_gui_service("Grok (subscription)")
    user = {"GROK_MODEL": "grok-4.5"}
    merged = {**user, **o}
    assert merged["GROK_PREFER_OAUTH"] == "1"
```

- [ ] **Step 2: Edit `gui.py` for dropdown, auth panel, translate_file**

- [ ] **Step 3: Static check**

```bash
python -c "from pdf2zh.gui_services import SERVICE_CHOICES, resolve_gui_service; print(SERVICE_CHOICES[:5])"
python -c "from pdf2zh.auth.status import all_auth_status; print(all_auth_status())"
```

Expected: no import errors; status prints without refresh side effects.

- [ ] **Step 4: Manual smoke (if display available)**

```bash
pdf2zh -i --serverport 7860
# UI: Auto selected; auth panel shows Grok/Codex; translate small PDF or skip if headless
```

Headless acceptable substitute:

```bash
python -c "
from pdf2zh.gui_services import resolve_gui_service
from pdf2zh.registry import build_translator
from pdf2zh.auth.status import all_auth_status
print(all_auth_status())
spec, envs = resolve_gui_service('Grok (subscription)')
# only if grok connected:
# t = build_translator(spec, 'en', 'ko', envs=envs, ignore_cache=True)
# print(t.translate('Hello', ignore_cache=True))
"
```

- [ ] **Step 5: Commit**

```bash
git add pdf2zh/gui.py test/test_gui_services.py
git commit -m "[feat] Gradio Auto/OAuth services and host auth status panel"
```

---

### Task 4: Docker Compose ops (Phase 3)

**Files:**
- Modify: `docker-compose.yml`
- Create: `docs/WEB_SERVER.md`

**Interfaces:**
- Consumes: host paths `~/.grok`, `~/.codex`
- Produces: documented runnable compose

- [ ] **Step 1: Update `docker-compose.yml`**

```yaml
services:
  pdf2zh:
    # keep existing build
    ports:
      - "7860:7860"
    environment:
      - PYTHONUNBUFFERED=1
    command: ["pdf2zh", "-i", "--serverport", "7860"]
    restart: unless-stopped
    volumes:
      # Host CLI subscription tokens (prefer rw so refresh can write back)
      - ${HOME}/.grok:/root/.grok
      - ${HOME}/.codex:/root/.codex
      - pdf2zh-config:/root/.config/PDFMathTranslate
      - ./data:/data
    # Do NOT set Gradio share here

volumes:
  pdf2zh-config:
```

Note in comments: if image USER is not root, adjust mount targets; `ro` mounts break refresh write-back.

- [ ] **Step 2: Write `docs/WEB_SERVER.md`** with sections:
  1. Host prep: `grok login`, `codex login`, verify files exist  
  2. Native: `pdf2zh -i --serverport 7860`  
  3. Optional auth: `pdf2zh -i --authorized users.txt`  
  4. Docker compose up; open `http://localhost:7860`  
  5. UI: choose Auto / Grok subscription / Codex  
  6. Token expiry: re-run login on host; Refresh status  
  7. Security: no `--share` on public net; use reverse proxy + HTTPS if exposed; demo mode without token mounts  
  8. Troubleshooting: missing auth, 401 → re-login; container home path  

- [ ] **Step 3: Link from `docs/ADVANCED.md` and `README.md`**

One short paragraph + link to `docs/WEB_SERVER.md`.

- [ ] **Step 4: Validate compose file syntax**

```bash
docker compose -f docker-compose.yml config
```

Expected: valid config (image build may be skipped).

- [ ] **Step 5: Commit**

```bash
git add docker-compose.yml docs/WEB_SERVER.md docs/ADVANCED.md README.md
git commit -m "[docs] Web server ops for CLI subscription auth mounts"
```

---

### Task 5: Integration verification + optional live translate

**Files:** none required (verification only); fix bugs if found

- [ ] **Step 1: Run unit suite**

```bash
python -m pytest test/test_auth_status.py test/test_gui_services.py test/test_service_chain.py test/test_registry.py -v
```

Expected: all PASS.

- [ ] **Step 2: Live auth status on host**

```bash
python -c "from pdf2zh.auth.status import all_auth_status; import pprint; pprint.pp({k: v.__dict__ for k,v in all_auth_status().items()})"
```

Expected: reflects real `~/.grok` / `~/.codex` without modifying tokens.

- [ ] **Step 3: Live translate via GUI mapping path**

```bash
python -c "
from pdf2zh.gui_services import resolve_gui_service
from pdf2zh.registry import build_translator
spec, envs = resolve_gui_service('Auto (recommended)')
t = build_translator(spec, 'en', 'ko', envs=envs, ignore_cache=True)
print(spec, t.name, t.translate('Hello world', ignore_cache=True))
"
```

Expected: Korean output if any backend available; else clear ValueError from auto chain.

- [ ] **Step 4: Final commit if fixes**

```bash
git add -A
git status
# commit only if there are fix commits needed
```

- [ ] **Step 5: Push when user requested** (this plan does not force push)

```bash
git push origin HEAD
```

---

## Self-review (plan author)

**1. Spec coverage (Phase 1 + 3):**
- Auth status UI → Task 1 + 3  
- Auto / Grok sub / Codex sub / API key → Task 2 + 3  
- Docker mounts + restart → Task 4  
- Security docs (authorized, share off, demo) → Task 4  
- No browser OAuth → Global Constraints  
- Config pollution → Global Constraints + Task 2 envs only process-local  

**2. Placeholder scan:** none intentionally left.

**3. Type consistency:** `AuthProviderStatus`, `resolve_gui_service` → `(str, dict[str, str])`, service specs match `registry` / `service_chain` names (`auto`, `grok`, `openai-codex`, `openai`).

---

## Out of scope reminder

- Browser OAuth login (Phase 2)  
- Celery/job queue beyond existing optional flags  
- Hyperlink repair  
- Multi-tenant per-user token DB  
