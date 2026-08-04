"""Unit tests for Gradio service label mapping."""

from __future__ import annotations

import unittest

from pdf2zh.gui_services import SERVICE_CHOICES, resolve_gui_service


class TestResolveGuiService(unittest.TestCase):
    def test_auto(self):
        spec, envs = resolve_gui_service("Auto (recommended)")
        self.assertEqual(spec, "auto")
        self.assertEqual(envs, {})

    def test_grok_subscription_sets_prefer_oauth(self):
        spec, envs = resolve_gui_service("Grok (subscription)")
        self.assertEqual(spec, "grok")
        self.assertEqual(envs.get("GROK_PREFER_OAUTH"), "1")

    def test_grok_api_no_prefer(self):
        spec, envs = resolve_gui_service("Grok (API key)")
        self.assertEqual(spec, "grok")
        self.assertNotIn("GROK_PREFER_OAUTH", envs)

    def test_codex(self):
        spec, envs = resolve_gui_service("OpenAI Codex (subscription)")
        self.assertEqual(spec, "openai-codex")
        self.assertEqual(envs, {})

    def test_openai_api(self):
        spec, envs = resolve_gui_service("OpenAI (API key)")
        self.assertEqual(spec, "openai")
        self.assertEqual(envs, {})

    def test_choices_include_auto_first(self):
        self.assertTrue(SERVICE_CHOICES[0].startswith("Auto"))

    def test_choices_include_subscription_and_api(self):
        self.assertIn("Grok (subscription)", SERVICE_CHOICES)
        self.assertIn("OpenAI Codex (subscription)", SERVICE_CHOICES)
        self.assertIn("Grok (API key)", SERVICE_CHOICES)
        self.assertIn("OpenAI (API key)", SERVICE_CHOICES)

    def test_merge_envs_prefer_oauth_wins_for_subscription(self):
        _, o = resolve_gui_service("Grok (subscription)")
        user = {"GROK_MODEL": "grok-4.5"}
        merged = {**user, **o}
        self.assertEqual(merged["GROK_PREFER_OAUTH"], "1")
        self.assertEqual(merged["GROK_MODEL"], "grok-4.5")

    def test_registry_tail_resolves(self):
        # Google should appear after fixed labels and resolve to "google"
        if "Google" in SERVICE_CHOICES:
            spec, envs = resolve_gui_service("Google")
            self.assertEqual(spec, "google")
            self.assertEqual(envs, {})


if __name__ == "__main__":
    unittest.main()
