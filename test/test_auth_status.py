"""Unit tests for CLI auth status (no token refresh)."""

from __future__ import annotations

import json
import tempfile
import time
import unittest
from pathlib import Path

from pdf2zh.auth.status import (
    all_auth_status,
    codex_auth_status,
    grok_auth_status,
)


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
        auth.write_text(
            json.dumps(
                {
                    "https://auth.x.ai::client": {
                        "key": "tok",
                        "refresh_token": "rt",
                        "oidc_client_id": "cid",
                        "oidc_issuer": "https://auth.x.ai",
                        "auth_mode": "oidc",
                        "expires_at": exp,
                        "email": "a@b.c",
                    }
                }
            )
        )
        s = grok_auth_status(auth)
        self.assertEqual(s.state, "connected")

    def test_expired(self):
        d = Path(tempfile.mkdtemp())
        auth = d / "auth.json"
        exp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - 3600))
        auth.write_text(
            json.dumps(
                {
                    "https://auth.x.ai::client": {
                        "key": "tok",
                        "refresh_token": "rt",
                        "oidc_client_id": "cid",
                        "oidc_issuer": "https://auth.x.ai",
                        "auth_mode": "oidc",
                        "expires_at": exp,
                    }
                }
            )
        )
        s = grok_auth_status(auth)
        self.assertEqual(s.state, "expired")

    def test_error_invalid_json(self):
        d = Path(tempfile.mkdtemp())
        auth = d / "auth.json"
        auth.write_text("not-json{{{")
        s = grok_auth_status(auth)
        self.assertEqual(s.state, "error")


class TestCodexStatus(unittest.TestCase):
    def test_missing(self):
        s = codex_auth_status(Path(tempfile.mkdtemp()) / "auth.json")
        self.assertEqual(s.state, "missing")
        self.assertIn("codex login", s.hint.lower())

    def test_connected_with_valid_jwt(self):
        # JWT with exp far in the future (no signature verify; status only decodes payload)
        import base64

        def b64url(data: bytes) -> str:
            return base64.urlsafe_b64encode(data).rstrip(b"=").decode()

        header = b64url(b'{"alg":"none"}')
        exp = int(time.time()) + 7200
        payload = b64url(
            json.dumps({"exp": exp, "https://api.openai.com/auth": {}}).encode()
        )
        token = f"{header}.{payload}.sig"
        d = Path(tempfile.mkdtemp())
        auth = d / "auth.json"
        auth.write_text(
            json.dumps(
                {
                    "tokens": {
                        "access_token": token,
                        "refresh_token": "rt",
                    }
                }
            )
        )
        s = codex_auth_status(auth)
        self.assertEqual(s.state, "connected")

    def test_expired_jwt(self):
        import base64

        def b64url(data: bytes) -> str:
            return base64.urlsafe_b64encode(data).rstrip(b"=").decode()

        header = b64url(b'{"alg":"none"}')
        exp = int(time.time()) - 7200
        payload = b64url(json.dumps({"exp": exp}).encode())
        token = f"{header}.{payload}.sig"
        d = Path(tempfile.mkdtemp())
        auth = d / "auth.json"
        auth.write_text(
            json.dumps(
                {
                    "tokens": {
                        "access_token": token,
                        "refresh_token": "rt",
                    }
                }
            )
        )
        s = codex_auth_status(auth)
        self.assertEqual(s.state, "expired")


class TestAllAuthStatus(unittest.TestCase):
    def test_keys(self):
        d = Path(tempfile.mkdtemp())
        result = all_auth_status(
            grok_path=d / "g.json",
            codex_path=d / "c.json",
        )
        self.assertIn("grok", result)
        self.assertIn("codex", result)
        self.assertEqual(result["grok"].state, "missing")
        self.assertEqual(result["codex"].state, "missing")


if __name__ == "__main__":
    unittest.main()
