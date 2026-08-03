"""Unit tests for translation post-processing (source-echo / label strip)."""

import unittest

from pdf2zh.translator import sanitize_translation


class TestSanitizeTranslation(unittest.TestCase):
    def test_strips_translated_text_label(self):
        src = "Hello world"
        out = sanitize_translation(src, "**Translated Text:** 안녕하세요 세계")
        self.assertEqual(out, "안녕하세요 세계")

    def test_strips_source_prefix_echo(self):
        src = (
            "The recent mainstream RL applications rely on privileged learning "
            "methods [19]."
        )
        raw = (
            src
            + "\n\n"
            + "최근 주류 RL 응용은 특권 학습 방법에 의존한다 [19]."
        )
        out = sanitize_translation(src, raw)
        self.assertNotIn("The recent mainstream", out)
        self.assertIn("특권", out)

    def test_keeps_clean_translation(self):
        src = "Hello world"
        out = sanitize_translation(src, "안녕하세요 세계")
        self.assertEqual(out, "안녕하세요 세계")

    def test_inline_label_artifact(self):
        src = "Keywords: Locomotion"
        raw = "Keywords: 이동**Translated Text:** 이동, 학습"
        out = sanitize_translation(src, raw)
        self.assertNotIn("Translated", out)

    def test_empty(self):
        self.assertEqual(sanitize_translation("a", ""), "")
        self.assertEqual(sanitize_translation("a", None), "")


if __name__ == "__main__":
    unittest.main()
