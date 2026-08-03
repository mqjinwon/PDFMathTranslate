"""Tests for single translator registry and config non-pollution."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from pdf2zh.config import ConfigManager
from pdf2zh.registry import TRANSLATORS, build_translator, get_translator_class
from pdf2zh.service_chain import resolve_service


class TestRegistry(unittest.TestCase):
    def test_openai_codex_registered(self):
        self.assertIn("openai-codex", TRANSLATORS)
        self.assertEqual(get_translator_class("openai-codex").name, "openai-codex")

    def test_grok_registered(self):
        self.assertIn("grok", TRANSLATORS)

    def test_unknown_raises(self):
        with self.assertRaises(ValueError):
            get_translator_class("no-such-backend")

    def test_build_explicit_google(self):
        t = build_translator("google", "en", "zh", ignore_cache=True)
        self.assertEqual(t.name, "google")


class TestConfigNonPollution(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.cfg = Path(self._td.name) / "config.json"
        self.cfg.write_text(
            json.dumps(
                {
                    "translators": [
                        {
                            "name": "grok",
                            "envs": {
                                "GROK_API_KEY": "user-secret-key",
                                "GROK_MODEL": "grok-4.5",
                            },
                        }
                    ]
                }
            )
        )
        ConfigManager.custome_config(str(self.cfg))

    def tearDown(self):
        # Reset singleton so later tests do not write into a deleted temp path.
        ConfigManager._instance = None
        self._td.cleanup()

    def test_prefer_oauth_does_not_wipe_api_key(self):
        with mock.patch(
            "pdf2zh.service_chain._grok_oauth_available", return_value=True
        ):
            resolved = resolve_service("auto")
        self.assertEqual(resolved.envs.get("GROK_PREFER_OAUTH"), "1")

        captured_keys = []

        def fake_openai(**kwargs):
            captured_keys.append(kwargs.get("api_key"))
            return mock.Mock()

        with mock.patch(
            "pdf2zh.auth.grok_oauth.get_grok_access_token",
            return_value="oauth-tok",
        ), mock.patch("openai.OpenAI", side_effect=fake_openai):
            # First construction: auto path prefers OAuth for this process only.
            build_translator(
                resolved.service_string(),
                "en",
                "ko",
                envs=dict(resolved.envs),
                ignore_cache=True,
            )
            self.assertEqual(captured_keys[-1], "oauth-tok")

            # Persisted config must keep the user API key and must NOT store prefer-oauth.
            data = json.loads(self.cfg.read_text(encoding="utf-8"))
            grok_env = next(
                t["envs"] for t in data["translators"] if t["name"] == "grok"
            )
            self.assertEqual(grok_env.get("GROK_API_KEY"), "user-secret-key")
            self.assertNotIn("GROK_PREFER_OAUTH", grok_env)

            # Later construction WITHOUT process prefer flag must use stored API key.
            build_translator(
                "grok",
                "en",
                "ko",
                envs={},
                ignore_cache=True,
            )
            self.assertEqual(captured_keys[-1], "user-secret-key")

    def test_stale_prefer_oauth_in_config_is_ignored(self):
        # Older builds may have written GROK_PREFER_OAUTH into config — strip on load.
        data = json.loads(self.cfg.read_text(encoding="utf-8"))
        for t in data["translators"]:
            if t["name"] == "grok":
                t["envs"]["GROK_PREFER_OAUTH"] = "1"
        self.cfg.write_text(json.dumps(data), encoding="utf-8")
        ConfigManager.custome_config(str(self.cfg))

        captured = []

        def fake_openai(**kwargs):
            captured.append(kwargs.get("api_key"))
            return mock.Mock()

        with mock.patch("openai.OpenAI", side_effect=fake_openai), mock.patch(
            "pdf2zh.auth.grok_oauth.get_grok_access_token",
            return_value="should-not-use",
        ):
            build_translator("grok", "en", "ko", envs={}, ignore_cache=True)
        self.assertEqual(captured[-1], "user-secret-key")


if __name__ == "__main__":
    unittest.main()
