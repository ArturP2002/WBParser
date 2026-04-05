"""Repository for per-task product price history."""
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from database.models.task_product_price import TaskProductPrice


class TaskProductPriceRepository:
    """Latest / stored prices scoped to (search_task, product)."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_latest_price(self, task_id: int, product_id: int) -> Optional[int]:
        result = await self.session.execute(
            select(TaskProductPrice.price)
            .where(
                TaskProductPrice.task_id == task_id,
                TaskProductPrice.product_id == product_id,
            )
            .order_by(desc(TaskProductPrice.created_at))
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def create(self, task_id: int, product_id: int, price: int) -> TaskProductPrice:
        row = TaskProductPrice(task_id=task_id, product_id=product_id, price=price)
        self.session.add(row)
        await self.session.commit()
        await self.session.refresh(row)
        return row
