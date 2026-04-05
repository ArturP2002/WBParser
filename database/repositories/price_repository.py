"""Product price repository."""
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from database.models.product_price import ProductPrice


class ProductPriceRepository:
    """Repository for ProductPrice model."""
    
    def __init__(self, session: AsyncSession):
        """Initialize repository with session."""
        self.session = session
    
    async def get_latest_price(self, product_id: int) -> Optional[int]:
        """Get latest price for product."""
        result = await self.session.execute(
            select(ProductPrice.price)
            .where(ProductPrice.product_id == product_id)
            .order_by(desc(ProductPrice.created_at))
            .limit(1)
        )
        return result.scalar_one_or_none()
    
    async def create(self, product_id: int, price: int) -> ProductPrice:
        """Create new price record."""
        price_record = ProductPrice(product_id=product_id, price=price)
        self.session.add(price_record)
        await self.session.commit()
        await self.session.refresh(price_record)
        return price_record
    
    async def batch_insert(self, prices: List[dict]) -> None:
        """Batch insert prices."""
        if not prices:
            return
        
        # Simple batch insert - create each price record
        for price_data in prices:
            try:
                await self.create(
                    product_id=price_data.get("product_id"),
                    price=price_data.get("price"),
                )
            except Exception as e:
                # Log error but continue
                from core.logger import logger
                logger.error(f"Error inserting price: {e}")
                continue
