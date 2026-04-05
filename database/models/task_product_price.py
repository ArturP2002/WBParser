"""Per-task price history for event detection (isolated from other users/tasks)."""
from sqlalchemy import Column, Integer, ForeignKey, Index
from sqlalchemy.orm import relationship
from database.base_model import BaseModel


class TaskProductPrice(BaseModel):
    """Price snapshot for a (search_task, product) pair."""

    __tablename__ = "task_product_prices"

    task_id = Column(Integer, ForeignKey("search_tasks.id", ondelete="CASCADE"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    price = Column(Integer, nullable=False)

    task = relationship("SearchTask", backref="task_product_prices")
    product = relationship("Product", back_populates="task_prices")

    __table_args__ = (
        Index("idx_task_product_prices_lookup", "task_id", "product_id"),
    )
