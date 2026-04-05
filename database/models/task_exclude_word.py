"""Task exclude word model."""
from sqlalchemy import Column, Integer, String, ForeignKey, Index
from sqlalchemy.orm import relationship
from database.base_model import BaseModel


class TaskExcludeWord(BaseModel):
    """Task exclude word model for filtering products."""
    
    __tablename__ = "task_exclude_words"
    
    task_id = Column(Integer, ForeignKey("search_tasks.id", ondelete="CASCADE"), nullable=False)
    word = Column(String(100), nullable=False)
    
    # Relationships
    task = relationship("SearchTask", back_populates="exclude_words")
    
    __table_args__ = (
        Index("idx_exclude_task", "task_id"),
    )
