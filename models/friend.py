from sqlalchemy import Column, Integer, ForeignKey, DateTime, String
from sqlalchemy.orm import relationship
from datetime import datetime
from .base import Base

class Friend(Base):
    """Система друзей"""
    __tablename__ = 'friends'
    
    id = Column(Integer, primary_key=True)
    
    # Кто отправил заявку
    requester_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    
    # Кто получил заявку
    addressee_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    
    # Статус: 'pending' (ожидание), 'accepted' (принято), 'declined' (отклонено)
    status = Column(String(20), default='pending')
    
    # Время создания
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Время принятия
    accepted_at = Column(DateTime, nullable=True)
    
    # Связи
    requester = relationship("User", foreign_keys=[requester_id])
    addressee = relationship("User", foreign_keys=[addressee_id])
    
    def get_friend_for(self, user_id: int):
        """Получить друга для конкретного пользователя"""
        if self.requester_id == user_id:
            return self.addressee
        elif self.addressee_id == user_id:
            return self.requester
        return None
