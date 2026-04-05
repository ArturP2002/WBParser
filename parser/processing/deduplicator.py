"""Product deduplicator with 3 levels."""
import asyncio
from typing import Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from parser.wb.wb_models import WBProduct
from database.repositories.product_repository import ProductRepository
from database.repositories.product_seller_repository import ProductSellerRepository
from database.models.product import Product
from parser.processing.product_normalizer import ProductNormalizer
from rapidfuzz import fuzz
from core.logger import logger


class Deduplicator:
    """Product deduplicator with 3 levels."""
    
    def __init__(self, session: AsyncSession):
        """Initialize deduplicator."""
        self.session = session
        self.product_repo = ProductRepository(session)
        self.seller_repo = ProductSellerRepository(session)
        self.normalizer = ProductNormalizer()
    
    async def deduplicate(
        self, 
        wb_product: WBProduct
    ) -> Tuple[Optional[Product], bool]:
        """Deduplicate product using 3 levels.
        
        Returns:
            Tuple of (existing_product, is_new)
        """
        # Level 1: Check wb_id
        existing = await self.product_repo.get_by_wb_id(wb_product.id)
        if existing:
            logger.debug(f"Found product by wb_id: {wb_product.id}")
            return existing, False
        
        # Level 2: Check root_id
        if wb_product.root:
            existing = await self.product_repo.get_by_root_id(wb_product.root)
            if existing:
                logger.debug(f"Found product by root_id: {wb_product.root}")
                # Group seller
                await self._group_seller(existing.id, wb_product)
                return existing, False
        
        # Level 3: Normalize and fuzzy match
        # Run normalization in thread to avoid blocking event loop
        normalized_name = await asyncio.to_thread(
            self.normalizer.normalize, wb_product.name
        )
        if normalized_name:
            candidates = await self.product_repo.get_by_normalized_name(normalized_name)
            for candidate in candidates:
                # Fuzzy matching with threshold - run in thread to avoid blocking
                similarity = await asyncio.to_thread(
                    fuzz.ratio,
                    normalized_name,
                    candidate.normalized_name or ""
                )
                if similarity >= 85:  # 85% similarity threshold
                    logger.debug(
                        f"Found product by normalized_name (similarity: {similarity}%)"
                    )
                    # Group seller if root_id matches
                    if wb_product.root and candidate.root_id == wb_product.root:
                        await self._group_seller(candidate.id, wb_product)
                    return candidate, False
        
        # New product
        logger.debug(f"New product: {wb_product.id}")
        return None, True
    
    async def _group_seller(
        self, 
        product_id: int, 
        wb_product: WBProduct
    ) -> None:
        """Group seller for existing product."""
        if wb_product.supplier:
            await self.seller_repo.create_or_update(
                product_id=product_id,
                seller_name=wb_product.supplier,
                price=wb_product.price,
                rating=wb_product.rating,
            )
