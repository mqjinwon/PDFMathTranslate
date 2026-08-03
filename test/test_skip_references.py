"""Tests for bibliography / references section skip detection."""

import unittest

from pdf2zh.section_policy import (
    APPENDIX_SECTION_RE,
    REFERENCE_SECTION_RE,
    SectionState,
    apply_section_policy,
    skip_flags_for_paragraphs,
)


class TestReferenceSectionDetection(unittest.TestCase):
    def test_matches_common_headings(self):
        for s in [
            "References",
            "REFERENCES",
            "Reference",
            "Bibliography",
            "Works Cited",
            "7 References",
            "7. References",
            "참고문헌",
            "参考文献",
        ]:
            self.assertTrue(REFERENCE_SECTION_RE.match(s), s)

    def test_rejects_body_sentences(self):
        for s in [
            "We cite several references in this section.",
            "Related work and references are discussed below.",
            "Introduction",
            "[1] A. Smith, Paper title.",
        ]:
            self.assertFalse(REFERENCE_SECTION_RE.match(s), s)


class TestAppendixSectionDetection(unittest.TestCase):
    def test_matches_appendix_headings(self):
        for s in [
            "Appendix",
            "APPENDIX",
            "Appendix A",
            "A Appendix",
            "A. Appendix",
            "Appendices",
            "Supplementary Material",
            "부록",
            "附录",
        ]:
            self.assertTrue(APPENDIX_SECTION_RE.match(s), s)

    def test_rejects_non_appendix(self):
        for s in [
            "References",
            "In the appendix we show more results.",
            "A.3 Domain Randomizations",
        ]:
            self.assertFalse(APPENDIX_SECTION_RE.match(s), s)


class TestSectionStateMachine(unittest.TestCase):
    def test_references_then_appendix_sequence(self):
        paras = [
            "Introduction body text about methods.",
            "References",
            "[1] A. Smith. Paper title. 2020.",
            "[2] B. Jones. Other paper. 2021.",
            "A Appendix",
            "Appendix details and extra experiments.",
        ]
        flags, state = skip_flags_for_paragraphs(paras)
        self.assertEqual(
            flags,
            [False, True, True, True, False, False],
        )
        self.assertFalse(state.in_references)

    def test_sticky_across_calls(self):
        st = SectionState()
        skip, st = apply_section_policy("References", st)
        self.assertTrue(skip)
        self.assertTrue(st.in_references)
        skip, st = apply_section_policy("[15] Foo et al.", st)
        self.assertTrue(skip)
        skip, st = apply_section_policy("Appendix", st)
        self.assertFalse(skip)
        self.assertFalse(st.in_references)

    def test_disabled(self):
        flags, _ = skip_flags_for_paragraphs(
            ["References", "[1] X"], skip_references=False
        )
        self.assertEqual(flags, [False, False])


if __name__ == "__main__":
    unittest.main()
