"""Product model."""
from datetime import datetime
from sqlalchemy import Column, BigInteger, Integer, String, Float, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import BIGINT
from sqlalchemy.orm import relationship
from database.base_model import BaseModel


class Product(BaseModel):
    """Product model for Wildberries products."""
    
    __tablename__ = "products"

    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    wb_id = Column(BIGINT, nullable=False, index=True)
    root_id = Column(BIGINT, nullable=True, index=True)
    name = Column(String(1000), nullable=True)
    normalized_name = Column(String(1000), nullable=True, index=True)
    brand = Column(String(255), nullable=True)
    seller = Column(String(255), nullable=True)
    rating = Column(Float, nullable=True)
    url = Column(String(1000), nullable=True)
    last_seen = Column(DateTime, nullable=True)
    
    # Relationships
    user = relationship("User", backref="products")
    prices = relationship("ProductPrice", back_populates="product", cascade="all, delete-orphan")
    task_prices = relationship(
        "TaskProductPrice",
        back_populates="product",
        cascade="all, delete-orphan",
    )
    sellers = relationship("ProductSeller", back_populates="product", cascade="all, delete-orphan")
    notifications = relationship("Notification", back_populates="product")
    
    __table_args__ = (
        Index("idx_products_user", "user_id"),
        Index("idx_products_wb_id", "wb_id"),
        Index("idx_products_root", "root_id"),
        Index("idx_products_normalized", "normalized_name"),
        Index("uq_products_user_wb_id", "user_id", "wb_id", unique=True),
    )
