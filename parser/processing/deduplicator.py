"""Product deduplicator: one WB catalog card (nm / wb_id) = one product."""
from typing import Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from parser.wb.wb_models import WBProduct
from database.repositories.product_repository import ProductRepository
from database.models.product import Product
from core.logger import logger


class Deduplicator:
    """Match products by Wildberries nm_id (wb_id) within one bot user.

    Same WB card is a separate DB row per user. Same model from different
    sellers stays separate cards (different nm_id), mirroring the site.
    """

    def __init__(self, session: AsyncSession):
        """Initialize deduplicator."""
        self.session = session
        self.product_repo = ProductRepository(session)

    async def deduplicate(
        self,
        wb_product: WBProduct,
        user_id: int,
    ) -> Tuple[Optional[Product], bool]:
        """Return existing row for this nm_id for the user or mark as new.

        Returns:
            Tuple of (existing_product, is_new)
        """
        existing = await self.product_repo.get_by_wb_id(wb_product.id, user_id)
        if existing:
            logger.debug(f"Found product by wb_id: {wb_product.id}")
            return existing, False

        logger.debug(f"New product: {wb_product.id}")
        return None, True
