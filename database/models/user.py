"""User model."""
from sqlalchemy import Column, BigInteger, String, Index
from sqlalchemy.dialects.postgresql import BIGINT
from database.base_model import BaseModel


class User(BaseModel):
    """User model for Telegram users."""
    
    __tablename__ = "users"
    
    telegram_id = Column(BIGINT, unique=True, nullable=False, index=True)
    username = Column(String(255), nullable=True)
    
    __table_args__ = (
        Index("idx_users_telegram_id", "telegram_id"),
    )
