"""Модель уведомлений"""
from datetime import datetime
from sqlalchemy import Column, Integer, ForeignKey, Index, DateTime
from sqlalchemy.orm import relationship
from database.base_model import BaseModel


class Notification(BaseModel):
    """Модель уведомлений для дедупликации"""
    
    __tablename__ = "notifications"
    
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    price = Column(Integer, nullable=False)
    sent_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Связи
    user = relationship("User", backref="notifications")
    product = relationship("Product", back_populates="notifications")
    
    __table_args__ = (
        Index("idx_notifications_user_product", "user_id", "product_id"),
    )
