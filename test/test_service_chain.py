"""Tests for auto service resolution chain."""

from __future__ import annotations

import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from pdf2zh.service_chain import resolve_service, ResolvedService


def _fake_jwt(exp: float | None = None) -> str:
    import base64

    if exp is None:
        exp = time.time() + 3600

    def enc(obj):
        raw = json.dumps(obj, separators=(",", ":")).encode()
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()

    return f"{enc({'alg': 'none'})}.{enc({'exp': int(exp)})}."


class TestResolveService(unittest.TestCase):
    def test_explicit_passthrough(self):
        r = resolve_service("google")
        self.assertEqual(r.name, "google")
        self.assertEqual(r.reason, "explicit")

        r = resolve_service("grok:my-model")
        self.assertEqual(r.name, "grok")
        self.assertEqual(r.model, "my-model")
        self.assertEqual(r.reason, "explicit")

    def test_auto_prefers_grok_oauth(self):
        with (
            mock.patch(
                "pdf2zh.service_chain._grok_oauth_available", return_value=True
            ),
            mock.patch(
                "pdf2zh.service_chain._openai_codex_available", return_value=True
            ),
            mock.patch.dict("os.environ", {"GROK_API_KEY": "sk-x", "OPENAI_API_KEY": "sk-o"}, clear=False),
        ):
            r = resolve_service("auto")
        self.assertEqual(r.name, "grok")
        self.assertEqual(r.reason, "grok-oauth")
        self.assertIsNone(r.envs.get("GROK_API_KEY"))

    def test_auto_falls_back_to_openai_codex(self):
        with (
            mock.patch(
                "pdf2zh.service_chain._grok_oauth_available", return_value=False
            ),
            mock.patch(
                "pdf2zh.service_chain._openai_codex_available", return_value=True
            ),
            mock.patch.dict("os.environ", {}, clear=False),
        ):
            # Ensure keys not required
            r = resolve_service("auto")
        self.assertEqual(r.name, "openai-codex")
        self.assertEqual(r.reason, "openai-codex-oauth")

    def test_auto_falls_back_to_openai_api(self):
        with (
            mock.patch(
                "pdf2zh.service_chain._grok_oauth_available", return_value=False
            ),
            mock.patch(
                "pdf2zh.service_chain._openai_codex_available", return_value=False
            ),
            mock.patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test"}, clear=False),
        ):
            r = resolve_service("auto")
        self.assertEqual(r.name, "openai")
        self.assertEqual(r.reason, "openai-api-key")

    def test_auto_falls_back_to_grok_api(self):
        with (
            mock.patch(
                "pdf2zh.service_chain._grok_oauth_available", return_value=False
            ),
            mock.patch(
                "pdf2zh.service_chain._openai_codex_available", return_value=False
            ),
            mock.patch.dict(
                "os.environ",
                {"GROK_API_KEY": "xai-test", "OPENAI_API_KEY": ""},
                clear=False,
            ),
        ):
            # empty OPENAI_API_KEY should not count
            import os

            os.environ.pop("OPENAI_API_KEY", None)
            r = resolve_service("auto")
        self.assertEqual(r.name, "grok")
        self.assertEqual(r.reason, "grok-api-key")

    def test_auto_raises_when_nothing_available(self):
        with (
            mock.patch(
                "pdf2zh.service_chain._grok_oauth_available", return_value=False
            ),
            mock.patch(
                "pdf2zh.service_chain._openai_codex_available", return_value=False
            ),
            mock.patch.dict("os.environ", {}, clear=True),
        ):
            with self.assertRaises(ValueError) as ctx:
                resolve_service("auto")
        self.assertIn("No translation backend", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
