"""Notification service for formatting messages."""
from typing import List, Optional
from database.models.product import Product
from database.models.product_seller import ProductSeller
from core.logger import logger


class NotificationService:
    """Service for formatting notifications."""
    
    @staticmethod
    def format_notification(
        product: Product,
        price: int,
        sellers: List[ProductSeller],
        event_type: str,
        price_old: Optional[int] = None,
        price_new: Optional[int] = None,
    ) -> str:
        """Format notification message.
        
        Format:
        Название товара
        
        https://www.wildberries.ru/...
        
        Прод: RAS STORE | 4.9 ⭐
        Цена: 62423/65000 руб
        """
        message = f"{product.name}\n\n"
        
        # Get or generate URL
        url = product.url
        if not url and hasattr(product, 'wb_id') and product.wb_id:
            # Generate URL using wb_id (nm_id) - this is the stable catalog URL format
            url = f"https://www.wildberries.ru/catalog/{product.wb_id}/detail.aspx"
        
        if url:
            message += f"{url}\n\n"
        
        # Seller and rating (combined in one line)
        seller_name = None
        seller_rating = None
        
        # Determine current price for seller matching
        current_price = price_new if price_new is not None else price
        
        if sellers:
            # Use first seller that matches current price, or first seller
            matching_seller = next((s for s in sellers if s.price == current_price), None)
            seller = matching_seller if matching_seller else sellers[0]
            seller_name = seller.seller_name
            seller_rating = seller.rating
        elif product.seller:
            seller_name = product.seller
            seller_rating = product.rating
        
        if seller_name:
            seller_line = f"Прод: {seller_name}"
            if seller_rating:
                seller_line += f" | {seller_rating} ⭐"
            message += f"{seller_line}\n"
        
        # Price: current/max format
        current_price = price_new if price_new is not None else price
        max_price = current_price
        
        if price_old:
            max_price = max(current_price, price_old)
        elif sellers:
            # Find max price among all sellers
            max_price = max((s.price for s in sellers), default=current_price)
        
        if max_price != current_price:
            message += f"Цена: {current_price}/{max_price} руб"
        else:
            message += f"Цена: {current_price} руб"
        
        # Event type indicator
        if event_type == "enter_range":
            message += " 🎯"
        elif event_type == "price_drop":
            message += " ⬇️"
        
        return message
