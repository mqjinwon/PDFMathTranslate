"""Unit tests for GUI model / reasoning catalogs."""

from __future__ import annotations

import unittest

from pdf2zh.gui_models import (
    CODEX_MODELS,
    DEFAULT_CODEX_MODEL,
    DEFAULT_REASONING_EFFORT,
    MODEL_BACKEND_DEFAULT,
    REASONING_EFFORTS,
    apply_model_reasoning_envs,
    default_model_for_service_spec,
    models_for_service_spec,
    reasoning_visible_for_service_spec,
    ui_model_updates,
    ui_reasoning_updates,
)


class TestGuiModels(unittest.TestCase):
    def test_codex_defaults_are_5_6_not_5_4(self):
        self.assertEqual(DEFAULT_CODEX_MODEL, "gpt-5.6-luna")
        self.assertIn("gpt-5.6-sol", CODEX_MODELS)
        self.assertIn("gpt-5.6-terra", CODEX_MODELS)
        self.assertIn("gpt-5.6-luna", CODEX_MODELS)
        self.assertNotIn("gpt-5.4", CODEX_MODELS)
        for m in CODEX_MODELS:
            self.assertNotIn("5.4", m)

    def test_apply_codex_model_and_reasoning(self):
        envs = apply_model_reasoning_envs(
            "openai-codex", "gpt-5.6-sol", "high"
        )
        self.assertEqual(envs["OPENAI_CODEX_MODEL"], "gpt-5.6-sol")
        self.assertEqual(envs["OPENAI_CODEX_REASONING_EFFORT"], "high")

    def test_apply_grok_model_no_reasoning(self):
        envs = apply_model_reasoning_envs("grok", "grok-4.5", "high")
        self.assertEqual(envs["GROK_MODEL"], "grok-4.5")
        self.assertNotIn("OPENAI_CODEX_REASONING_EFFORT", envs)
        self.assertNotIn("OPENAI_REASONING_EFFORT", envs)

    def test_auto_backend_default_skips_envs(self):
        envs = apply_model_reasoning_envs(
            "auto", MODEL_BACKEND_DEFAULT, DEFAULT_REASONING_EFFORT
        )
        self.assertEqual(envs, {})

    def test_openai_api_envs(self):
        envs = apply_model_reasoning_envs("openai", "gpt-5.6-terra", "medium")
        self.assertEqual(envs["OPENAI_MODEL"], "gpt-5.6-terra")
        self.assertEqual(envs["OPENAI_REASONING_EFFORT"], "medium")

    def test_ui_updates_codex_visible(self):
        m = ui_model_updates("openai-codex")
        r = ui_reasoning_updates("openai-codex")
        self.assertTrue(m["visible"])
        self.assertTrue(r["visible"])
        self.assertEqual(m["value"], DEFAULT_CODEX_MODEL)
        self.assertEqual(r["value"], DEFAULT_REASONING_EFFORT)
        self.assertEqual(r["choices"], REASONING_EFFORTS)

    def test_ui_updates_auto_hidden_model(self):
        m = ui_model_updates("auto")
        r = ui_reasoning_updates("auto")
        self.assertFalse(m["visible"])
        self.assertFalse(r["visible"])

    def test_models_for_spec(self):
        self.assertEqual(models_for_service_spec("openai-codex"), CODEX_MODELS)
        self.assertEqual(
            default_model_for_service_spec("openai-codex"), DEFAULT_CODEX_MODEL
        )
        self.assertTrue(reasoning_visible_for_service_spec("openai-codex"))
        self.assertFalse(reasoning_visible_for_service_spec("grok"))


if __name__ == "__main__":
    unittest.main()
