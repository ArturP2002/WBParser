"""Wildberries API models."""
from typing import Optional
import unicodedata
from pydantic import BaseModel, Field, ConfigDict
from core.logger import logger


class WBProduct(BaseModel):
    """Wildberries product model."""
    
    model_config = ConfigDict(
        populate_by_name=True,
        validate_by_name=True,
    )
    
    id: int
    name: str
    price: Optional[int] = None  # Price will be fetched from Cards API
    supplier: Optional[str] = None
    supplier_rating: Optional[float] = None  # Seller/supplier rating (supplierRating from WB API)
    rating: Optional[float] = None  # Product review rating
    url: Optional[str] = None
    root: Optional[int] = None
    brand: Optional[str] = None


class WBSearchResponse(BaseModel):
    """Wildberries search response model."""
    
    products: list[WBProduct] = Field(default_factory=list)

    @staticmethod
    def _normalize_key(key: object) -> str:
        """Normalize keys to avoid WB hidden unicode/control chars issues."""
        text = str(key)
        text = text.replace("\ufeff", "")
        text = "".join(ch for ch in text if unicodedata.category(ch) != "Cf")
        return text.strip()

    @classmethod
    def _normalize_dict_keys(cls, payload: dict) -> dict:
        """Normalize dict keys, avoiding collisions from duplicate normalized keys."""
        normalized: dict = {}
        for key, value in payload.items():
            norm_key = cls._normalize_key(key)
            # Avoid overwriting if two keys normalize to the same value
            # (e.g., "products" and "\ufeffproducts" both become "products")
            if norm_key not in normalized:
                normalized[norm_key] = value
            # If collision, prefer the first occurrence (original key without BOM)
            # This is safe because we process keys in order
        return normalized

    @staticmethod
    def _extract_price_rub(product_data: dict) -> Optional[int]:
        """Extract price in rubles from WB search payload if available.

        WB может отдавать цену в нескольких форматах, проверяем их в порядке приоритета:
        1. sizes[0].price.product (наиболее частый формат в v18 API, в копейках ×100)
        2. sizes[0].price.total (цена со скидкой, в копейках ×100)
        3. sizes[0].price.basic (базовая цена, в копейках ×100)
        4. salePriceU (цена со скидкой, в копейках ×100)
        5. priceU (обычная цена, в копейках ×100)
        6. price (отдельное поле, может быть в рублях или копейках)
        
        Все цены в копейках ×100, поэтому делим на 100 для получения рублей.
        """
        price = None
        
        # 1) Формат sizes[0].price (приоритет - это основной формат в WB API)
        sizes = product_data.get("sizes")
        if isinstance(sizes, list) and len(sizes) > 0:
            first_size = sizes[0]
            if isinstance(first_size, dict):
                price_obj = first_size.get("price")
                if isinstance(price_obj, dict):
                    # Проверяем в порядке: product (наиболее частый) → total → basic
                    price_kopecks = (
                        price_obj.get("product") 
                        or price_obj.get("total") 
                        or price_obj.get("basic")
                    )
                    if price_kopecks is not None:
                        try:
                            price = int(price_kopecks)
                        except (TypeError, ValueError):
                            pass
        
        # 2) Новый формат: salePriceU (цена со скидкой, в копейках ×100)
        if price is None:
            sale_price_u = product_data.get("salePriceU")
            if isinstance(sale_price_u, (int, float)) and sale_price_u > 0:
                try:
                    price = int(sale_price_u)
                except (TypeError, ValueError):
                    pass
        
        # 3) Новый формат: priceU (обычная цена, в копейках ×100)
        if price is None:
            price_u = product_data.get("priceU")
            if isinstance(price_u, (int, float)) and price_u > 0:
                try:
                    price = int(price_u)
                except (TypeError, ValueError):
                    pass
        
        # 4) Отдельное поле "price" (может быть в рублях или копейках)
        if price is None:
            price_value = product_data.get("price")
            if isinstance(price_value, (int, float)) and price_value > 0:
                try:
                    # Если значение похоже на цену в копейках ×100 (больше 10_000), делим на 100
                    if price_value > 10_000:
                        price = int(price_value)
                    else:
                        # Уже в рублях, умножаем на 100 для консистентности
                        price = int(price_value) * 100
                except (TypeError, ValueError):
                    pass
        
        # Конвертируем из копеек ×100 в рубли
        if price is not None:
            try:
                return price // 100
            except (TypeError, ValueError):
                return None
        
        return None

    @classmethod
    def _get_products_list(cls, data: dict) -> list | None:
        """Get products list from top-level or nested WB response formats."""
        products = data.get("products")
        if isinstance(products, list):
            return products

        nested = data.get("data")
        if isinstance(nested, dict):
            nested = cls._normalize_dict_keys(nested)
            nested_products = nested.get("products")
            if isinstance(nested_products, list):
                return nested_products

        return None
    
    @classmethod
    def from_api_response(cls, data: dict) -> "WBSearchResponse":
        """Create response from API data.
        
        Supports multiple response structures:
        1. New format: {"products": [...], "total": N, "metadata": {...}}
        2. Old format: {"data": {"products": [...]}}
        """
        products: list[WBProduct] = []

        logger.debug(f"Parsing API response. Data type: {type(data)}")
        if not isinstance(data, dict):
            logger.error(f"API response is not a dict! Type: {type(data)}")
            return cls(products=[])

        normalized_data = cls._normalize_dict_keys(data)
        logger.debug(f"Response keys: {list(normalized_data.keys())}")

        products_list = cls._get_products_list(normalized_data)
        if products_list is None:
            logger.warning(
                "Could not find products in API response. Keys: {}",
                list(normalized_data.keys()),
            )
            return cls(products=[])

        logger.debug(f"Parsing {len(products_list)} products from API response")
        
        # Debug: log first product structure for diagnostics
        if products_list and len(products_list) > 0:
            first_raw = products_list[0]
            if isinstance(first_raw, dict):
                # Log key price-related fields from first product
                logger.info(
                    "First product price fields (debug): "
                    f"salePriceU={first_raw.get('salePriceU')}, "
                    f"priceU={first_raw.get('priceU')}, "
                    f"has_sizes={bool(first_raw.get('sizes'))}, "
                    f"sizes_price_keys={list(first_raw.get('sizes', [{}])[0].get('price', {}).keys()) if isinstance(first_raw.get('sizes'), list) and len(first_raw.get('sizes', [])) > 0 else 'N/A'}"
                )

        for idx, raw_product in enumerate(products_list):
            try:
                if not isinstance(raw_product, dict):
                    raw_product = dict(raw_product)

                product_data = cls._normalize_dict_keys(raw_product)
                product_id = product_data.get("id")
                product_name = product_data.get("name")

                if product_id is None or product_name is None:
                    if idx < 5:
                        logger.warning(
                            "Product {} missing required fields (id/name). Keys: {}",
                            idx,
                            list(product_data.keys())[:10],
                        )
                    continue

                # Generate URL if not provided by API
                # Use product_id (nm_id) for URL - this is more stable than root_id
                # WB catalog URLs use nm_id, not seller article (root)
                if "url" not in product_data or not product_data.get("url"):
                    product_data["url"] = (
                        f"https://www.wildberries.ru/catalog/{product_id}/detail.aspx"
                    )

                # Extract price with debug logging for first few products
                extracted_price = cls._extract_price_rub(product_data)
                if idx < 3 and extracted_price is None:
                    # Debug: log raw price fields for first products without price
                    logger.debug(
                        f"Product {idx} (id={product_id}) price extraction failed. "
                        f"Raw fields: salePriceU={product_data.get('salePriceU')}, "
                        f"priceU={product_data.get('priceU')}, "
                        f"sizes={product_data.get('sizes')[:1] if isinstance(product_data.get('sizes'), list) else None}"
                    )
                
                product = WBProduct(
                    id=int(product_id),
                    name=str(product_name),
                    price=extracted_price,
                    supplier=product_data.get("supplier"),
                    supplier_rating=product_data.get("supplierRating"),
                    rating=product_data.get("reviewRating") or product_data.get("rating"),
                    url=product_data.get("url"),
                    root=product_data.get("root"),
                    brand=product_data.get("brand"),
                )
                products.append(product)
            except Exception as e:
                logger.warning(f"Failed to parse product {idx}: {type(e).__name__}: {e}")
                continue

        logger.debug(
            "Successfully parsed %s products from %s total",
            len(products),
            len(products_list),
        )
        return cls(products=products)
