from sqlalchemy import Column, Integer, String, Boolean

from .base import Base


class ClanDaily(Base):
    __tablename__ = "clan_daily"

    id = Column(Integer, primary_key=True)
    clan_name = Column(String(50), index=True, nullable=False)
    date = Column(String(10), index=True, nullable=False)
    pve_wins = Column(Integer, default=0)
    pvp_wins = Column(Integer, default=0)
    battles = Column(Integer, default=0)
    claimed_pve = Column(Boolean, default=False)
    claimed_pvp = Column(Boolean, default=False)
    claimed_battles = Column(Boolean, default=False)
