"""Tests for CLI OAuth credential reuse (Codex + Grok)."""

from __future__ import annotations

import json
import time
import unittest
from pathlib import Path
from unittest import mock

from pdf2zh.auth.codex_oauth import (
    CodexAuthError,
    get_codex_access_token,
    load_codex_credentials,
    refresh_codex_credentials,
    save_codex_credentials,
)
from pdf2zh.auth.grok_oauth import (
    GrokAuthError,
    get_grok_access_token,
    load_grok_credentials,
    refresh_grok_credentials,
    save_grok_credentials,
)
from pdf2zh.translator import OpenAICodexTranslator, GrokTranslator
from pdf2zh.config import ConfigManager


def _fake_jwt(payload: dict) -> str:
    import base64

    def enc(obj):
        raw = json.dumps(obj, separators=(",", ":")).encode()
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()

    return f"{enc({'alg':'none'})}.{enc(payload)}."


class TestCodexOAuth(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(self.id().replace(".", "_"))
        # use system temp via unittest is awkward; use NamedTemporaryFile dir
        import tempfile

        self._td = tempfile.TemporaryDirectory()
        self.auth_path = Path(self._td.name) / "auth.json"

    def tearDown(self) -> None:
        self._td.cleanup()

    def _write_auth(self, exp: float | None = None) -> None:
        if exp is None:
            exp = time.time() + 3600
        access = _fake_jwt(
            {
                "exp": int(exp),
                "https://api.openai.com/auth": {
                    "chatgpt_account_id": "acct-1",
                },
            }
        )
        data = {
            "OPENAI_API_KEY": None,
            "tokens": {
                "access_token": access,
                "refresh_token": "rt-old",
                "account_id": "acct-1",
                "id_token": "id-old",
            },
            "last_refresh": "2020-01-01T00:00:00.000000000Z",
        }
        self.auth_path.write_text(json.dumps(data), encoding="utf-8")

    def test_load_and_no_refresh_when_valid(self):
        self._write_auth(exp=time.time() + 3600)
        creds = get_codex_access_token(auth_path=self.auth_path, min_ttl=60)
        self.assertEqual(creds.account_id, "acct-1")
        self.assertEqual(creds.refresh_token, "rt-old")

    def test_refresh_writes_back(self):
        self._write_auth(exp=time.time() - 10)
        new_access = _fake_jwt(
            {
                "exp": int(time.time() + 7200),
                "https://api.openai.com/auth": {
                    "chatgpt_account_id": "acct-2",
                },
            }
        )

        class FakeResp:
            status_code = 200

            def json(self):
                return {
                    "access_token": new_access,
                    "refresh_token": "rt-new",
                    "id_token": "id-new",
                    "expires_in": 7200,
                }

        session = mock.Mock()
        session.post.return_value = FakeResp()

        creds = get_codex_access_token(
            auth_path=self.auth_path, min_ttl=60, session=session
        )
        self.assertEqual(creds.refresh_token, "rt-new")
        self.assertEqual(creds.account_id, "acct-2")
        disk = json.loads(self.auth_path.read_text(encoding="utf-8"))
        self.assertEqual(disk["tokens"]["refresh_token"], "rt-new")
        self.assertEqual(disk["tokens"]["access_token"], new_access)
        session.post.assert_called_once()
        args, kwargs = session.post.call_args
        self.assertIn("auth.openai.com/oauth/token", args[0])
        self.assertEqual(kwargs["data"]["grant_type"], "refresh_token")

    def test_missing_file(self):
        with self.assertRaises(CodexAuthError):
            load_codex_credentials(self.auth_path)


class TestGrokOAuth(unittest.TestCase):
    def setUp(self) -> None:
        import tempfile

        self._td = tempfile.TemporaryDirectory()
        self.auth_path = Path(self._td.name) / "auth.json"

    def tearDown(self) -> None:
        self._td.cleanup()

    def _write_auth(self, expires_in: float = 3600) -> None:
        exp = time.time() + expires_in
        from datetime import datetime, timezone

        expires_at = (
            datetime.fromtimestamp(exp, tz=timezone.utc)
            .isoformat()
            .replace("+00:00", "Z")
        )
        data = {
            "https://auth.x.ai::client": {
                "key": "access-old",
                "auth_mode": "oidc",
                "refresh_token": "rt-old",
                "expires_at": expires_at,
                "oidc_issuer": "https://auth.x.ai",
                "oidc_client_id": "client-1",
            }
        }
        self.auth_path.write_text(json.dumps(data), encoding="utf-8")

    def test_valid_token_no_refresh(self):
        self._write_auth(3600)
        tok = get_grok_access_token(auth_path=self.auth_path, min_ttl=60)
        self.assertEqual(tok, "access-old")

    def test_refresh_writes_back(self):
        self._write_auth(-10)

        class FakeResp:
            status_code = 200

            def json(self):
                return {
                    "access_token": "access-new",
                    "refresh_token": "rt-new",
                    "expires_in": 21600,
                }

        session = mock.Mock()
        session.post.return_value = FakeResp()
        # discovery optional
        session.get.return_value = mock.Mock(
            status_code=200,
            json=lambda: {"token_endpoint": "https://auth.x.ai/oauth2/token"},
        )

        tok = get_grok_access_token(
            auth_path=self.auth_path, min_ttl=60, session=session
        )
        self.assertEqual(tok, "access-new")
        disk = json.loads(self.auth_path.read_text(encoding="utf-8"))
        entry = next(iter(disk.values()))
        self.assertEqual(entry["key"], "access-new")
        self.assertEqual(entry["refresh_token"], "rt-new")
        session.post.assert_called()

    def test_missing_file(self):
        with self.assertRaises(GrokAuthError):
            load_grok_credentials(self.auth_path)


class TestOpenAICodexTranslator(unittest.TestCase):
    def setUp(self) -> None:
        ConfigManager.clear()
        import tempfile

        self._td = tempfile.TemporaryDirectory()
        self.auth_path = Path(self._td.name) / "auth.json"
        access = _fake_jwt(
            {
                "exp": int(time.time() + 3600),
                "https://api.openai.com/auth": {
                    "chatgpt_account_id": "acct-1",
                },
            }
        )
        self.auth_path.write_text(
            json.dumps(
                {
                    "tokens": {
                        "access_token": access,
                        "refresh_token": "rt",
                        "account_id": "acct-1",
                    }
                }
            ),
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self._td.cleanup()
        ConfigManager.clear()

    def test_do_translate_uses_responses_api(self):
        sse = (
            "data: "
            + json.dumps(
                {"type": "response.output_text.delta", "delta": "안녕"}
            )
            + "\n"
            "data: "
            + json.dumps(
                {"type": "response.output_text.delta", "delta": "하세요"}
            )
            + "\n"
            "data: [DONE]\n"
        )

        class FakeResp:
            status_code = 200
            text = ""

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def iter_lines(self, decode_unicode=True):
                for line in sse.splitlines():
                    yield line

        translator = OpenAICodexTranslator(
            "en",
            "ko",
            "gpt-5.4",
            envs={"OPENAI_CODEX_AUTH_PATH": str(self.auth_path)},
            ignore_cache=True,
        )
        with mock.patch("pdf2zh.translator.requests.post", return_value=FakeResp()) as post:
            out = translator.do_translate("Hello")
        self.assertEqual(out, "안녕하세요")
        args, kwargs = post.call_args
        self.assertEqual(
            args[0], "https://chatgpt.com/backend-api/codex/responses"
        )
        self.assertEqual(kwargs["headers"]["chatgpt-account-id"], "acct-1")
        self.assertTrue(kwargs["headers"]["Authorization"].startswith("Bearer "))
        self.assertEqual(kwargs["json"]["model"], "gpt-5.4")
        self.assertTrue(kwargs["stream"])


class TestGrokTranslatorOAuthFallback(unittest.TestCase):
    def setUp(self) -> None:
        ConfigManager.clear()
        import tempfile

        self._td = tempfile.TemporaryDirectory()
        self.auth_path = Path(self._td.name) / "auth.json"
        from datetime import datetime, timezone

        exp = (
            datetime.fromtimestamp(time.time() + 3600, tz=timezone.utc)
            .isoformat()
            .replace("+00:00", "Z")
        )
        self.auth_path.write_text(
            json.dumps(
                {
                    "https://auth.x.ai::c": {
                        "key": "oauth-token-xyz",
                        "auth_mode": "oidc",
                        "refresh_token": "rt",
                        "expires_at": exp,
                        "oidc_issuer": "https://auth.x.ai",
                        "oidc_client_id": "client",
                    }
                }
            ),
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self._td.cleanup()
        ConfigManager.clear()

    def test_uses_oauth_when_no_api_key(self):
        with mock.patch("openai.OpenAI") as OpenAI:
            client = mock.Mock()
            OpenAI.return_value = client
            # avoid network in parent init side effects
            GrokTranslator(
                "en",
                "ko",
                "grok-test",
                envs={
                    "GROK_API_KEY": None,
                    "GROK_AUTH_PATH": str(self.auth_path),
                    "GROK_MODEL": "grok-test",
                },
                ignore_cache=True,
            )
            OpenAI.assert_called()
            kwargs = OpenAI.call_args.kwargs
            self.assertEqual(kwargs["api_key"], "oauth-token-xyz")
            self.assertIn("api.x.ai", kwargs["base_url"])

    def test_prefers_explicit_api_key(self):
        with mock.patch("openai.OpenAI") as OpenAI:
            OpenAI.return_value = mock.Mock()
            GrokTranslator(
                "en",
                "ko",
                "grok-test",
                envs={
                    "GROK_API_KEY": "sk-explicit",
                    "GROK_AUTH_PATH": str(self.auth_path),
                    "GROK_MODEL": "grok-test",
                },
                ignore_cache=True,
            )
            kwargs = OpenAI.call_args.kwargs
            self.assertEqual(kwargs["api_key"], "sk-explicit")


if __name__ == "__main__":
    unittest.main()
