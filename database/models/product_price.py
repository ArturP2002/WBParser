"""Product price model."""
from sqlalchemy import Column, Integer, ForeignKey, Index
from sqlalchemy.orm import relationship
from database.base_model import BaseModel


class ProductPrice(BaseModel):
    """Product price model for price history."""
    
    __tablename__ = "product_prices"
    
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    price = Column(Integer, nullable=False)
    
    # Relationships
    product = relationship("Product", back_populates="prices")
    
    __table_args__ = (
        Index("idx_prices_product", "product_id"),
    )
