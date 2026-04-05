"""Tests for search relevance normalization (no heavy parser imports)."""
import unittest

from parser.processing.filters import is_relevant_to_query, normalize_text_for_relevance
from parser.wb.wb_models import WBProduct


class TestRelevanceFilter(unittest.TestCase):
    def test_normalize_merges_cyrillic_gb(self):
        self.assertEqual(
            normalize_text_for_relevance("iPhone 17 512 Гб white"),
            "iphone 17 512gb white",
        )

    def test_query_512gb_matches_title_cyrillic_gb(self):
        p = WBProduct(
            id=1,
            name="Смартфон iPhone 17 512 Гб eSIM Белый",
            price=1,
        )
        self.assertTrue(is_relevant_to_query(p, "iphone 17 512gb"))

    def test_query_ayfon_matches_iphone_title(self):
        p = WBProduct(id=1, name="Смартфон iPhone 17 512GB", price=1)
        self.assertTrue(is_relevant_to_query(p, "айфон 17 512"))

    def test_bare_512_in_query_matches_512gb_in_title(self):
        p = WBProduct(id=1, name="iPhone 17 512Gb eSIM", price=1)
        self.assertTrue(is_relevant_to_query(p, "iphone 17 512"))


if __name__ == "__main__":
    unittest.main()
