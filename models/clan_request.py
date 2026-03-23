from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import relationship

from .base import Base


class ClanJoinRequest(Base):
    __tablename__ = "clan_join_requests"
    __table_args__ = (
        Index("ix_clan_join_requests_clan_created", "clan_name", "created_at"),
    )

    id = Column(Integer, primary_key=True)
    clan_name = Column(String(50), nullable=False, index=True)
    requester_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    requester = relationship("User", foreign_keys=[requester_id])
