import unittest
from unittest.mock import AsyncMock, patch

import orjson

from parser.processing.filters import price_in_range
from parser.wb.wb_api import WBAPI
from parser.wb.wb_models import WBProduct, WBSearchResponse


class _FakeResponse:
    def __init__(self, payload: dict):
        self.content = orjson.dumps(payload)


class TestWBAPIPriceFetch(unittest.IsolatedAsyncioTestCase):
    async def test_fetch_prices_uses_semicolon_and_required_params(self):
        api = WBAPI()
        captured_calls = []

        async def fake_get(url, params=None, retries=None):
            captured_calls.append((url, params))
            nm = params["nm"].split(";")
            products = []
            for product_id in nm:
                products.append(
                    {
                        "id": int(product_id),
                        "sizes": [{"price": {"total": 1234500}}],
                    }
                )
            return _FakeResponse({"products": products})

        with patch("parser.wb.wb_api.http_client.get", new=AsyncMock(side_effect=fake_get)):
            with patch("parser.wb.wb_api.config.WB_CARDS_API_BATCH_SIZE", 30):
                prices = await api._fetch_prices(list(range(1, 36)))

        self.assertEqual(len(captured_calls), 2)
        first_url, first_params = captured_calls[0]
        self.assertEqual(first_url, "https://card.wb.ru/cards/v4/detail")
        self.assertEqual(first_params["appType"], "1")
        self.assertEqual(first_params["curr"], "rub")
        self.assertEqual(first_params["dest"], "-1257786")
        self.assertIn(";", first_params["nm"])
        self.assertEqual(len(prices), 35)
        self.assertEqual(prices[1], 12345)


class TestFilters(unittest.TestCase):
    def test_price_in_range_with_none_price_returns_false(self):
        product = WBProduct(id=1, name="item", price=None)
        self.assertFalse(price_in_range(product, 100, 200))


class TestWBSearchResponseParsing(unittest.TestCase):
    def test_parses_products_with_zero_width_key(self):
        data = {
            "products\u200b": [
                {
                    "id\u200b": 1001,
                    "name\u200b": "Keyboard",
                    "sizes": [{"price": {"total": 550000}}],
                }
            ]
        }
        response = WBSearchResponse.from_api_response(data)
        self.assertEqual(len(response.products), 1)
        self.assertEqual(response.products[0].id, 1001)
        self.assertEqual(response.products[0].price, 5500)

    def test_parses_bom_products_key(self):
        data = {
            "\ufeffproducts": [
                {
                    "id": 101,
                    "name": "Phone",
                    "sizes": [{"price": {"total": 10999000}}],
                }
            ]
        }
        response = WBSearchResponse.from_api_response(data)
        self.assertEqual(len(response.products), 1)
        self.assertEqual(response.products[0].id, 101)
        self.assertEqual(response.products[0].price, 109990)

    def test_parses_nested_data_products(self):
        data = {
            "data": {
                "products": [
                    {
                        "id": 102,
                        "name": "Case",
                        "sizes": [{"price": {"product": 99900}}],
                    }
                ]
            }
        }
        response = WBSearchResponse.from_api_response(data)
        self.assertEqual(len(response.products), 1)
        self.assertEqual(response.products[0].id, 102)
        self.assertEqual(response.products[0].price, 999)


if __name__ == "__main__":
    unittest.main()
