"""Seller grouper for products."""
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from database.repositories.product_seller_repository import ProductSellerRepository
from database.models.product_seller import ProductSeller
from core.logger import logger


class SellerGrouper:
    """Group sellers for products."""
    
    def __init__(self, session: AsyncSession):
        """Initialize seller grouper."""
        self.session = session
        self.seller_repo = ProductSellerRepository(session)
    
    async def get_sellers(self, product_id: int) -> List[ProductSeller]:
        """Get all sellers for product."""
        return await self.seller_repo.get_by_product(product_id)
    
    async def get_best_price(self, product_id: int) -> Optional[int]:
        """Get minimum price from all sellers."""
        return await self.seller_repo.get_best_price(product_id)
    
    async def group_sellers_by_root_id(
        self,
        root_id: int,
        sellers_data: List[dict],
    ) -> None:
        """Group sellers for products with same root_id."""
        # This will be called after products are created/updated
        # Implementation depends on how we store root_id relationships
        pass
