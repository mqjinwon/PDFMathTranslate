"""Tests for bibliography / references section skip detection."""

import unittest

from pdf2zh.converter import APPENDIX_SECTION_RE, REFERENCE_SECTION_RE


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


if __name__ == "__main__":
    unittest.main()
