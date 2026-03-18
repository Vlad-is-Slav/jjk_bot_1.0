from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from .base import Base

class Battle(Base):
    """История боев"""
    __tablename__ = 'battles'
    
    id = Column(Integer, primary_key=True)
    
    # Тип боя: 'pvp', 'pve'
    battle_type = Column(String(10), default='pve')
    
    # Игрок 1 (всегда есть)
    player1_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    
    # Игрок 2 (для PvP)
    player2_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    
    # ID проклятия (для PvE)
    curse_id = Column(Integer, nullable=True)
    curse_name = Column(String(100), nullable=True)  # Для истории
    
    # Победитель
    winner_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    
    # Лог боя (JSON или текст)
    battle_log = Column(Text, nullable=True)
    
    # Награды
    exp_gained = Column(Integer, default=0)
    points_gained = Column(Integer, default=0)
    
    # Время боя
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Связи
    player1 = relationship("User", foreign_keys=[player1_id], back_populates="battles_as_player1")
    player2 = relationship("User", foreign_keys=[player2_id], back_populates="battles_as_player2")
    
    def get_opponent_name(self, viewer_id: int):
        """Получить имя противника для конкретного игрока"""
        if self.battle_type == 'pve':
            return self.curse_name or "Проклятие"
        
        if self.player1_id == viewer_id:
            return self.player2.username or f"Игрок #{self.player2_id}" if self.player2 else "Неизвестно"
        else:
            return self.player1.username or f"Игрок #{self.player1_id}"