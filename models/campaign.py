from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Boolean, Text, Float
from sqlalchemy.orm import relationship
from datetime import datetime
from .base import Base

class CampaignSeason(Base):
    """Сезоны сюжетной кампании"""
    __tablename__ = 'campaign_seasons'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    
    # Номер сезона
    season_number = Column(Integer, nullable=False)
    
    # Требуемый уровень для начала
    required_level = Column(Integer, default=1)
    
    # Активен ли сезон
    is_active = Column(Boolean, default=True)
    
    # Награда за прохождение сезона
    exp_reward = Column(Integer, default=100)
    points_reward = Column(Integer, default=10)
    card_reward = Column(String(100), nullable=True)  # Название карты
    
    # Связь с уровнями
    levels = relationship("CampaignLevel", back_populates="season", order_by="CampaignLevel.level_number")


class CampaignLevel(Base):
    """Уровни в сезоне"""
    __tablename__ = 'campaign_levels'
    
    id = Column(Integer, primary_key=True)
    season_id = Column(Integer, ForeignKey('campaign_seasons.id'), nullable=False)
    
    # Номер уровня в сезоне
    level_number = Column(Integer, nullable=False)
    
    # Название и описание
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    
    # Тип уровня: battle, boss, story
    level_type = Column(String(20), default="battle")
    
    # Враг (если битва)
    enemy_name = Column(String(100), nullable=True)
    enemy_attack = Column(Integer, default=10)
    enemy_defense = Column(Integer, default=10)
    enemy_speed = Column(Integer, default=10)
    enemy_hp = Column(Integer, default=100)
    
    # Награды
    exp_reward = Column(Integer, default=20)
    points_reward = Column(Integer, default=2)
    coins_reward = Column(Integer, default=50)
    
    # Шанс выпадения карты
    card_drop_chance = Column(Float, default=5.0)
    card_drop_name = Column(String(100), nullable=True)
    
    # Связи
    season = relationship("CampaignSeason", back_populates="levels")
    user_progress = relationship("UserCampaignProgress", back_populates="level")


class UserCampaignProgress(Base):
    """Прогресс пользователя в кампании"""
    __tablename__ = 'user_campaign_progress'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    level_id = Column(Integer, ForeignKey('campaign_levels.id'), nullable=False)
    
    # Прогресс
    attempts = Column(Integer, default=0)
    completed = Column(Boolean, default=False)
    
    # Дата прохождения
    completed_at = Column(DateTime, nullable=True)
    
    # Награда забрана
    reward_claimed = Column(Boolean, default=False)
    
    # Связи
    user = relationship("User", back_populates="campaign_progress")
    level = relationship("CampaignLevel", back_populates="user_progress")


class BossBattle(Base):
    """Специальные битвы с боссами"""
    __tablename__ = 'boss_battles'
    
    id = Column(Integer, primary_key=True)
    
    # Название босса
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    
    # Характеристики босса
    attack = Column(Integer, default=100)
    defense = Column(Integer, default=80)
    speed = Column(Integer, default=70)
    hp = Column(Integer, default=500)
    max_hp = Column(Integer, default=500)
    
    # Способности босса
    abilities = Column(Text, nullable=True)  # JSON с способностями
    
    # Награды
    exp_reward = Column(Integer, default=500)
    points_reward = Column(Integer, default=50)
    coins_reward = Column(Integer, default=1000)
    
    # Уникальная награда
    special_reward = Column(String(200), nullable=True)
    
    # Требования
    required_level = Column(Integer, default=50)
    
    # Кулдаун между попытками (часы)
    cooldown_hours = Column(Integer, default=24)


class UserBossAttempt(Base):
    """Попытки пользователя победить босса"""
    __tablename__ = 'user_boss_attempts'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    boss_id = Column(Integer, ForeignKey('boss_battles.id'), nullable=False)
    
    # Количество попыток
    attempts = Column(Integer, default=0)
    
    # Победил ли
    defeated = Column(Boolean, default=False)
    defeated_at = Column(DateTime, nullable=True)
    
    # Последняя попытка
    last_attempt = Column(DateTime, nullable=True)
    
    # Награда забрана
    reward_claimed = Column(Boolean, default=False)