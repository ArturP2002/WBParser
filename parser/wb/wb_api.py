"""Wildberries API client."""
import asyncio
import orjson
from typing import Any, List
from infrastructure.http.http_client import http_client
from core.config import config
from core.logger import logger
from core.exceptions import WBAPIError
from parser.wb.wb_models import WBProduct, WBSearchResponse


class WBAPI:
    """Wildberries API client."""
    
    def __init__(self):
        """Initialize WB API client."""
        # For v18+, use u-search.wb.ru (newer endpoint with better data)
        if config.WB_API_VERSION in ("v18", "18"):
            self.base_url = "https://u-search.wb.ru"
        else:
            self.base_url = config.WB_API_BASE_URL
        self.search_endpoint = config.WB_API_SEARCH_ENDPOINT
        self.cards_base_url = config.WB_CARDS_API_BASE_URL
        self.cards_endpoint = config.WB_CARDS_API_ENDPOINT
        logger.info(
            f"WB API initialized: version={config.WB_API_VERSION}, "
            f"base_url={self.base_url}, endpoint={self.search_endpoint}"
        )

    def _parse_json_response(self, response: Any, *, context: str) -> Any:
        """
        Parse JSON response with tolerant UTF-8 handling.

        WB иногда отдаёт “битый” UTF-8 (кодирует surrogate code points),
        из-за чего `orjson.loads(response.content)` падает. Поэтому есть
        fallback: `response.text` и затем `decode('utf-8', errors='replace')`.
        """
        content = getattr(response, "content", b"")
        try:
            # orjson is the fastest, but it's strict about UTF-8 validity.
            return orjson.loads(content)
        except Exception as e1:
            logger.debug(
                f"orjson.loads(response.content) failed for {context}: {e1}. "
                f"Trying response.text() fallback..."
            )

        text = getattr(response, "text", None)
        if text:
            try:
                return orjson.loads(text)
            except Exception as e2:
                logger.debug(
                    f"orjson.loads(response.text) failed for {context}: {e2}. "
                    f"Trying decode(..., errors='replace') fallback..."
                )

        # Final fallback: force a lossy-but-valid unicode string, then parse.
        decoded = content.decode("utf-8", errors="replace")
        return orjson.loads(decoded)

    def _clean_dict_key(self, key: Any) -> str:
        """
        Recreate a new `str` object for dict keys.

        Practical reason: в окружении с orjson ключи иногда приходят со
        “битым” хэш-кэшем, из-за чего `.get("products")` может возвращать
        `None`, хотя ключ визуально есть. encode/decode принудительно
        создаёт новый объект строки с корректным хэшем.
        """
        text = str(key)
        return text.encode("utf-8", errors="replace").decode("utf-8")
    
    async def search(
        self, 
        query: str, 
        page: int = 1,
    ) -> List[WBProduct]:
        """Search products on Wildberries (single page).
        
        Args:
            query: Search query
            page: Page number (default: 1)
        
        Returns:
            List of products
        """
        # TEST/STUB MODE: return fake products without calling real WB API
        if config.WB_STUB_MODE:
            logger.info(
                f"[WB_STUB_MODE] Returning stub products for query='{query}', page={page} "
                "(no real request to WB API)"
            )
            return self._stub_products(query=query, page=page)

        # Use 'query' parameter for /exactmatch/ru/common/v4/search endpoint
        # WB ignores the 'limit' param; each page returns ~100 products.
        params = {
            "query": query,
            "resultset": "catalog",
            "page": page,
            # Additional parameters for API
            "dest": config.WB_API_DEST,
            "regions": config.WB_API_REGIONS,
            "appType": config.WB_API_APPTYPE,
            "curr": config.WB_API_CURR,
            "lang": config.WB_API_LANG,
            "locale": config.WB_API_LOCALE,
            "spp": config.WB_API_SPP,
        }
        
        logger.debug(f"API request parameters: {params}")
        
        url = f"{self.base_url}{self.search_endpoint}"
        
        try:
            logger.info(f"Searching WB: query='{query}' (page {page})")
            logger.debug(f"Request URL: {url} with params: {params}")
            
            response = await http_client.get(url, params=params)
            
            # Log response status (only if not 200)
            if response.status_code != 200:
                logger.warning(f"Response status: {response.status_code}")
            else:
                logger.debug(f"Response status: {response.status_code}")
            
            # Parse JSON response
            # orjson strict-mode might reject invalid UTF-8 from WB.
            data = self._parse_json_response(
                response,
                context=f"WB search (query='{query}', page={page})",
            )
            
            # Log response structure for debugging
            if isinstance(data, dict):
                logger.debug(f"API response keys: {list(data.keys())}")
                if "total" in data:
                    logger.debug(f"API total field: {data.get('total')}")
                if "metadata" in data:
                    metadata = data.get("metadata", {})
                    if isinstance(metadata, dict):
                        logger.debug(f"API metadata keys: {list(metadata.keys())}")
                        if "is_empty" in metadata:
                            logger.debug(f"API metadata.is_empty: {metadata.get('is_empty')}")
            
            # Parse response
            search_response = WBSearchResponse.from_api_response(data)

            # Log results
            if len(search_response.products) > 0:
                logger.info(
                    f"✅ WB API response: found {len(search_response.products)} products for query '{query}'"
                )
            else:
                logger.warning(
                    f"⚠️ WB API response: found 0 products for query '{query}'. "
                    f"Response structure: {list(data.keys()) if isinstance(data, dict) else type(data)}"
                )
                if isinstance(data, dict) and "total" in data:
                    logger.info(f"API reported total={data.get('total')} products, but parsed 0")
                return search_response.products

            # Log price extraction statistics
            total_products = len(search_response.products)
            products_with_price = sum(1 for p in search_response.products if p.price is not None)
            products_without_price = total_products - products_with_price
            
            if products_without_price > 0:
                logger.info(
                    f"Price extraction: {products_with_price}/{total_products} products have prices, "
                    f"{products_without_price} missing (extracted from search API response)"
                )
            else:
                logger.debug(
                    f"Price extraction: all {total_products} products have prices extracted successfully"
                )

            return search_response.products
            
        except WBAPIError:
            # Re-raise WBAPIError as-is
            raise
        except Exception as e:
            # Use repr to avoid empty exception messages in logs.
            logger.error(
                f"Error searching WB API: {type(e).__name__}: {e!r}",
                exc_info=True,
            )
            raise WBAPIError(
                f"Failed to search products: {type(e).__name__}: {e!r}"
            ) from e

    def _stub_products(self, query: str, page: int = 1) -> List[WBProduct]:
        """Return a small static list of products for testing without WB API."""
        # We keep prices well inside typical test ranges (e.g. 0-100000000 and 500-1000000),
        # so that products are not filtered out by price.
        base_products = [
            WBProduct(
                id=1000001,
                name=f"{query} Test Product 1",
                price=100_000,
                supplier="Test Seller A",
                supplier_rating=4.9,
                rating=4.8,
                url="https://www.wildberries.ru/catalog/1000001/detail.aspx",
                root=1000001,
                brand="TestBrand",
            ),
            WBProduct(
                id=1000002,
                name=f"{query} Test Product 2",
                price=500_000,
                supplier="Test Seller B",
                supplier_rating=4.6,
                rating=4.5,
                url="https://www.wildberries.ru/catalog/1000002/detail.aspx",
                root=1000002,
                brand="AnotherBrand",
            ),
            WBProduct(
                id=1000003,
                name=f"{query} Cheap Test Product",
                price=900_000,
                supplier="Budget Seller",
                supplier_rating=4.1,
                rating=4.2,
                url="https://www.wildberries.ru/catalog/1000003/detail.aspx",
                root=1000003,
                brand="CheapBrand",
            ),
        ]

        # Only first page returns data in stub mode; others are empty to emulate pagination.
        if page != 1:
            return []

        return base_products
    
    async def search_all_pages(
        self,
        query: str,
        max_pages: int | None = None,
    ) -> List[WBProduct]:
        """Search products across multiple pages (up to 1000 products).

        Iterates pages 1..max_pages, collecting products from each page.
        Stops early when a page returns no products (end of results).
        Uses total from first page to optimize pagination.
        Adds rate-limiting between page requests to avoid 429 errors.

        Args:
            query: Search query
            max_pages: Maximum number of pages to fetch (1-10, default from config).
                       Each page returns ~100 products.

        Returns:
            Merged list of products from all pages.
        """
        if max_pages is None:
            max_pages = config.WB_API_MAX_PAGES
        # Clamp to [1, 10]
        max_pages = max(1, min(max_pages, 10))

        all_products: List[WBProduct] = []
        seen_ids: set[int] = set()
        total_products = None  # Will be set from first page response

        for page in range(1, max_pages + 1):
            page_products = await self.search(query, page=page)

            if not page_products:
                logger.info(
                    "Page %s returned 0 products for query '%s', stopping pagination",
                    page,
                    query,
                )
                break

            # On first page, try to get total from response to optimize pagination
            if page == 1 and total_products is None:
                # Estimate total from first page (usually ~100 products per page)
                # If we got 100 products, there might be more pages
                # If we got less, likely this is the last page
                if len(page_products) < 100:
                    # Likely last page, adjust max_pages
                    max_pages = 1
                    logger.debug(
                        f"First page returned {len(page_products)} products, "
                        f"likely last page - stopping pagination"
                    )

            # Deduplicate across pages (WB may return overlapping results)
            new_count = 0
            for product in page_products:
                if product.id not in seen_ids:
                    seen_ids.add(product.id)
                    all_products.append(product)
                    new_count += 1

            logger.info(
                "Page %s: %s products fetched, %s new (total so far: %s) for query '%s'",
                page,
                len(page_products),
                new_count,
                len(all_products),
                query,
            )

            # If this page returned fewer new products than expected, likely last page
            if new_count == 0:
                logger.info(
                    "Page %s returned only duplicates, stopping pagination", page
                )
                break

            # Rate limiting: add delay between page requests to avoid 429 errors
            # Only delay if not the last page
            if page < max_pages:
                # Use config delay or default 0.2s
                delay = getattr(config, 'WB_REQUEST_DELAY_MIN', 0.2)
                await asyncio.sleep(delay)

        logger.info(
            "✅ search_all_pages: collected %s unique products across %s page(s) for query '%s'",
            len(all_products),
            min(page, max_pages) if all_products else 0,
            query,
        )

        # Fetch accurate final prices from Cards API (handles discounts correctly).
        # The search API may return 0 or missing salePriceU for some products.
        if all_products and not config.WB_STUB_MODE:
            product_ids = [p.id for p in all_products]
            try:
                prices = await self._fetch_prices(product_ids)
                updated = 0
                for product in all_products:
                    fetched = prices.get(product.id)
                    if fetched is not None:
                        product.price = fetched
                        updated += 1
                logger.info(
                    "Cards API: updated prices for %s/%s products for query '%s'",
                    updated,
                    len(all_products),
                    query,
                )
            except Exception as e:
                logger.warning(
                    "Failed to fetch prices from Cards API for query '%s': %s. "
                    "Using prices from search API response.",
                    query,
                    e,
                )

        return all_products

    async def _fetch_prices(self, product_ids: List[int]) -> dict[int, int]:
        """Fetch prices for products from Cards API.
        
        Args:
            product_ids: List of product IDs (nm)
        
        Returns:
            Dictionary mapping product ID to price in rubles
        """
        if not product_ids:
            return {}
        
        prices: dict[int, int] = {}
        batch_size = config.WB_CARDS_API_BATCH_SIZE
        
        # Split IDs into batches
        for i in range(0, len(product_ids), batch_size):
            batch_ids = product_ids[i:i + batch_size]
            ids_str = ";".join(map(str, batch_ids))

            url = f"{self.cards_base_url}{self.cards_endpoint}"
            params = {
                "appType": config.WB_API_APPTYPE,
                "curr": config.WB_API_CURR,
                "dest": config.WB_API_DEST,
                "spp": config.WB_API_SPP,
                "nm": ids_str,
            }
            
            try:
                batch_no = i // batch_size + 1
                logger.debug(
                    f"Fetching prices for {len(batch_ids)} products (batch {batch_no})"
                )
                response = await http_client.get(url, params=params)
                
                # Parse JSON response
                try:
                    data_raw = self._parse_json_response(
                        response,
                        context=f"Cards API (batch {batch_no})",
                    )
                    # Normalize keys to strings
                    if isinstance(data_raw, dict):
                        data = {self._clean_dict_key(k): v for k, v in data_raw.items()}
                    else:
                        data = data_raw
                except Exception as e:
                    logger.error(f"Failed to parse Cards API JSON response: {e}")
                    logger.warning(f"Response content (first 500 chars): {response.content[:500]}")
                    continue
                
                # Extract prices from response
                # v1 format: {"products": [...]}
                # v2 format: {"data": {"products": [...]}}
                if isinstance(data, dict):
                    # Try v2 format first (data.products), then v1 (products)
                    data_wrapper = data.get("data")
                    if isinstance(data_wrapper, dict):
                        products_list = data_wrapper.get("products")
                    else:
                        products_list = None
                    if products_list is None:
                        products_list = data.get("products") or data.get("\ufeffproducts")
                else:
                    products_list = None

                if products_list is not None:
                    if not isinstance(products_list, list):
                        logger.warning(f"Cards API 'products' is not a list: {type(products_list)}")
                        continue
                    
                    for product in products_list:
                        if not isinstance(product, dict):
                            continue
                        
                        # Normalize product keys
                        product = {self._clean_dict_key(k): v for k, v in product.items()}
                        
                        product_id = product.get("id")
                        if product_id is None:
                            continue
                        
                        product_id = int(product_id)
                        
                        # Extract price from sizes[0].price.total or sizes[0].price.product
                        sizes = product.get("sizes", [])
                        if sizes and isinstance(sizes, list) and len(sizes) > 0:
                            first_size = sizes[0]
                            if isinstance(first_size, dict):
                                first_size = {self._clean_dict_key(k): v for k, v in first_size.items()}
                                price_obj = first_size.get("price")
                                if isinstance(price_obj, dict):
                                    price_obj = {self._clean_dict_key(k): v for k, v in price_obj.items()}
                                    # Use 'total' price (with discount) or 'product' price
                                    price_kopecks = price_obj.get("total") or price_obj.get("product")
                                    if price_kopecks is not None:
                                        # Convert from kopecks to rubles
                                        price_rubles = int(price_kopecks) // 100
                                        prices[product_id] = price_rubles
                                        logger.debug(f"✅ Found price for product {product_id}: {price_rubles} руб")
                                    else:
                                        logger.debug(f"Product {product_id} has no price in price object: {price_obj}")
                                else:
                                    logger.debug(f"Product {product_id} first_size.price is not a dict: {type(price_obj)}")
                            else:
                                logger.debug(f"Product {product_id} first_size is not a dict: {type(first_size)}")
                        else:
                            logger.debug(f"Product {product_id} has no sizes or sizes is empty")
                else:
                    logger.warning(
                        "Cards API response has no 'products' key in batch %s. Keys: %s",
                        batch_no,
                        list(data.keys()) if isinstance(data, dict) else "not a dict",
                    )
                
            except Exception as e:
                logger.warning(
                    "Failed to fetch prices for batch %s (%s ids): %s",
                    i // batch_size + 1,
                    len(batch_ids),
                    e,
                )
                # Continue with next batch instead of failing completely
                continue
        
        logger.info(f"✅ Fetched prices for {len(prices)} out of {len(product_ids)} products")
        return prices


# Global WB API instance
wb_api = WBAPI()
