"""Search task model."""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, Index
from sqlalchemy.orm import relationship
from database.base_model import BaseModel


class SearchTask(BaseModel):
    """Search task model for monitoring products."""
    
    __tablename__ = "search_tasks"
    
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    query = Column(String(500), nullable=False)
    price_min = Column(Integer, nullable=True)
    price_max = Column(Integer, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    last_check = Column(DateTime, nullable=True)
    
    # Relationships
    user = relationship("User", backref="search_tasks")
    exclude_words = relationship("TaskExcludeWord", back_populates="task", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index("idx_tasks_user", "user_id"),
        Index("idx_tasks_active", "is_active"),
    )
