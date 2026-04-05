"""Product seller model."""
from sqlalchemy import Column, Integer, String, Float, ForeignKey, Index
from sqlalchemy.orm import relationship
from database.base_model import BaseModel


class ProductSeller(BaseModel):
    """Product seller model for grouping sellers."""
    
    __tablename__ = "product_sellers"
    
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    seller_name = Column(String(255), nullable=False)
    price = Column(Integer, nullable=False)
    rating = Column(Float, nullable=True)
    
    # Relationships
    product = relationship("Product", back_populates="sellers")
    
    __table_args__ = (
        Index("idx_product_sellers", "product_id"),
    )
