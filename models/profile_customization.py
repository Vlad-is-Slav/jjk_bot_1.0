from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship

from .base import Base


class UserProfile(Base):
    """Кастомизация профиля пользователя."""
    __tablename__ = "user_profiles"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True)
    avatar_card_id = Column(Integer, ForeignKey("user_cards.id"), nullable=True)
    avatar_file_id = Column(String(255), nullable=True)
    avatar_file_unique_id = Column(String(255), nullable=True)
    favorite_quote = Column(String(255), nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="profile_settings")
    avatar_card = relationship("UserCard")


class UserQuote(Base):
    """Цитаты, разблокированные пользователем."""
    __tablename__ = "user_quotes"
    __table_args__ = (
        UniqueConstraint("user_id", "quote_text", name="uq_user_quote_text"),
    )

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    card_name = Column(String(100), nullable=False)
    quote_text = Column(String(255), nullable=False)
    obtained_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="quotes")
