"""Tests for compact Korean academic style injection."""

import unittest

from pdf2zh.style_prompt import default_system_prompt, is_korean_target
from pdf2zh.translator import BaseTranslator


class TestStylePrompt(unittest.TestCase):
    def test_korean_detection(self):
        self.assertTrue(is_korean_target("ko"))
        self.assertTrue(is_korean_target("ko-KR"))
        self.assertFalse(is_korean_target("en"))
        self.assertFalse(is_korean_target("zh"))

    def test_ko_system_includes_plain_endings(self):
        s = default_system_prompt("ko")
        self.assertIn("~습니다", s)
        self.assertIn("~다", s)
        self.assertIn("어렵다", s)
        self.assertIn("formula", s.lower() or "v0" in s or "{v" in s)

    def test_non_ko_system_omits_korean_style(self):
        s = default_system_prompt("en")
        self.assertNotIn("어렵다", s)
        self.assertIn("machine translation", s)

    def test_base_prompt_uses_style_for_ko(self):
        # BaseTranslator is abstract for do_translate; only exercise prompt().
        class _T(BaseTranslator):
            name = "style_test"

            def do_translate(self, text: str) -> str:
                return text

        t = _T("en", "ko", "m", ignore_cache=True)
        msgs = t.prompt("Hello")
        self.assertEqual(msgs[0]["role"], "system")
        self.assertIn("어렵다", msgs[0]["content"])
        self.assertIn("Hello", msgs[1]["content"])


if __name__ == "__main__":
    unittest.main()
