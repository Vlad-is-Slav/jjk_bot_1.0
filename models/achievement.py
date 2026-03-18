from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Boolean, BigInteger
from sqlalchemy.orm import relationship
from datetime import datetime
from .base import Base

class Achievement(Base):
    """Достижения (шаблоны)"""
    __tablename__ = 'achievements'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    description = Column(String(500), nullable=False)
    
    # Тип достижения
    achievement_type = Column(String(50), nullable=False)  # pvp_wins, pve_wins, level, cards_collected, etc.
    
    # Требуемое значение
    requirement_value = Column(Integer, default=1)
    
    # Награды
    exp_reward = Column(Integer, default=0)
    points_reward = Column(Integer, default=0)
    title_reward = Column(String(100), nullable=True)  # Титул за достижение
    
    # Иконка
    icon = Column(String(50), default="🏆")
    
    # Редкость
    rarity = Column(String(20), default="common")  # common, rare, epic, legendary
    
    # Связь с пользователями
    user_achievements = relationship("UserAchievement", back_populates="achievement")


class UserAchievement(Base):
    """Достижения пользователя"""
    __tablename__ = 'user_achievements'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    achievement_id = Column(Integer, ForeignKey('achievements.id'), nullable=False)
    
    # Прогресс
    progress = Column(Integer, default=0)
    completed = Column(Boolean, default=False)
    
    # Дата получения
    completed_at = Column(DateTime, nullable=True)
    
    # Связи
    user = relationship("User", back_populates="achievements")
    achievement = relationship("Achievement", back_populates="user_achievements")


class Title(Base):
    """Титулы (шаблоны)"""
    __tablename__ = 'titles'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    description = Column(String(500), nullable=True)
    
    # Бонусы от титула
    attack_bonus = Column(Integer, default=0)
    defense_bonus = Column(Integer, default=0)
    speed_bonus = Column(Integer, default=0)
    hp_bonus = Column(Integer, default=0)
    
    # Иконка
    icon = Column(String(50), default="👑")
    
    # Как получить
    requirement = Column(String(500), nullable=True)
    
    # Связь с пользователями
    user_titles = relationship("UserTitle", back_populates="title")


class UserTitle(Base):
    """Титулы пользователя"""
    __tablename__ = 'user_titles'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    title_id = Column(Integer, ForeignKey('titles.id'), nullable=False)
    
    # Экипирован ли
    is_equipped = Column(Boolean, default=False)
    
    # Дата получения
    obtained_at = Column(DateTime, default=datetime.utcnow)
    
    # Связи
    user = relationship("User", back_populates="titles")
    title = relationship("Title", back_populates="user_titles")