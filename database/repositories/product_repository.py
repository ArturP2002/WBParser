"""Product repository."""
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database.models.product import Product


class ProductRepository:
    """Repository for Product model."""
    
    def __init__(self, session: AsyncSession):
        """Initialize repository with session."""
        self.session = session
    
    async def get_by_wb_id(self, wb_id: int) -> Optional[Product]:
        """Get product by wb_id."""
        result = await self.session.execute(
            select(Product).where(Product.wb_id == wb_id)
        )
        return result.scalar_one_or_none()
    
    async def get_by_root_id(self, root_id: int) -> Optional[Product]:
        """Get product by root_id."""
        result = await self.session.execute(
            select(Product).where(Product.root_id == root_id)
        )
        return result.scalar_one_or_none()
    
    async def get_by_normalized_name(
        self, 
        normalized_name: str
    ) -> List[Product]:
        """Get products by normalized_name (for fuzzy matching)."""
        result = await self.session.execute(
            select(Product).where(Product.normalized_name == normalized_name)
        )
        return list(result.scalars().all())
    
    async def create_or_update(
        self,
        wb_id: int,
        name: Optional[str] = None,
        root_id: Optional[int] = None,
        normalized_name: Optional[str] = None,
        brand: Optional[str] = None,
        seller: Optional[str] = None,
        rating: Optional[float] = None,
        url: Optional[str] = None,
    ) -> Product:
        """Create or update product."""
        product = await self.get_by_wb_id(wb_id)
        
        if product:
            # Update existing product
            if name is not None:
                product.name = name
            if root_id is not None:
                product.root_id = root_id
            if normalized_name is not None:
                product.normalized_name = normalized_name
            if brand is not None:
                product.brand = brand
            if seller is not None:
                product.seller = seller
            if rating is not None:
                product.rating = rating
            # Update URL if provided, or if product doesn't have URL yet
            if url is not None:
                product.url = url
            elif not product.url and wb_id:
                # Generate URL using wb_id (nm_id) - this is the stable catalog URL format
                product.url = f"https://www.wildberries.ru/catalog/{wb_id}/detail.aspx"
        else:
            # Create new product
            product = Product(
                wb_id=wb_id,
                name=name,
                root_id=root_id,
                normalized_name=normalized_name,
                brand=brand,
                seller=seller,
                rating=rating,
                url=url,
            )
            self.session.add(product)
        
        await self.session.commit()
        await self.session.refresh(product)
        return product
    
    async def batch_insert(self, products: List[dict]) -> None:
        """Batch insert products."""
        if not products:
            return
        
        # Simple batch insert - create or update each product
        for product_data in products:
            try:
                await self.create_or_update(**product_data)
            except Exception as e:
                # Log error but continue with other products
                from core.logger import logger
                logger.error(f"Error inserting product: {e}")
                continue
