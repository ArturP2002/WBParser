"""Product seller repository."""
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from database.models.product_seller import ProductSeller


class ProductSellerRepository:
    """Repository for ProductSeller model."""
    
    def __init__(self, session: AsyncSession):
        """Initialize repository with session."""
        self.session = session
    
    async def get_by_product(self, product_id: int) -> List[ProductSeller]:
        """Get all sellers for product."""
        result = await self.session.execute(
            select(ProductSeller)
            .where(ProductSeller.product_id == product_id)
            .order_by(ProductSeller.price.asc())
        )
        return list(result.scalars().all())
    
    async def create_or_update(
        self,
        product_id: int,
        seller_name: str,
        price: int | None,
        rating: Optional[float] = None,
    ) -> ProductSeller:
        """Create or update product seller."""
        # Если цена отсутствует, не создаём и не обновляем продавца,
        # чтобы не нарушать NOT NULL constraint в БД и не сохранять
        # бессмысленные записи без цены.
        if price is None:
            return await self._get_or_create_placeholder_seller(
                product_id=product_id,
                seller_name=seller_name,
                rating=rating,
            )
        result = await self.session.execute(
            select(ProductSeller).where(
                ProductSeller.product_id == product_id,
                ProductSeller.seller_name == seller_name,
            )
        )
        seller = result.scalar_one_or_none()
        
        if seller:
            seller.price = price
            if rating is not None:
                seller.rating = rating
        else:
            seller = ProductSeller(
                product_id=product_id,
                seller_name=seller_name,
                price=price,
                rating=rating,
            )
            self.session.add(seller)
        
        await self.session.commit()
        await self.session.refresh(seller)
        return seller

    async def _get_or_create_placeholder_seller(
        self,
        product_id: int,
        seller_name: str,
        rating: Optional[float] = None,
    ) -> ProductSeller:
        """Return existing seller if it exists, skip creating new if price is None.

        Мы не создаём новых записей с пустой ценой. Если продавец уже есть,
        просто обновляем его рейтинг (без изменения цены). Если нет — ничего
        в БД не пишем, чтобы избежать NotNullViolationError.
        """
        result = await self.session.execute(
            select(ProductSeller).where(
                ProductSeller.product_id == product_id,
                ProductSeller.seller_name == seller_name,
            )
        )
        seller = result.scalar_one_or_none()

        if seller and rating is not None:
            seller.rating = rating
            await self.session.commit()
            await self.session.refresh(seller)

        return seller
    
    async def get_best_price(self, product_id: int) -> Optional[int]:
        """Get minimum price from all sellers."""
        result = await self.session.execute(
            select(func.min(ProductSeller.price))
            .where(ProductSeller.product_id == product_id)
        )
        return result.scalar_one_or_none()
