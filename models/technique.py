from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Boolean, Text, Float
from sqlalchemy.orm import relationship
from datetime import datetime
from .base import Base

class Technique(Base):
    """Техники и способности (шаблоны)"""
    __tablename__ = 'techniques'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    
    # Тип техники
    technique_type = Column(String(50), nullable=False)  # 
        # innate - врожденная (6 глаз, бесконечность)
        # domain - расширение территории
        # simple - простая территория
        # ability - способность (красный, фиолетовый)
        # passive - пассивная (черная молния)
    
    # Стоимость проклятой энергии
    ce_cost = Column(Integer, default=0)
    
    # Эффект
    effect_type = Column(String(50), nullable=True)  # damage, buff, debuff, heal, counter
    effect_value = Column(Integer, default=0)
    
    # Шанс срабатывания (для пассивных)
    trigger_chance = Column(Float, default=0.0)
    
    # Длительность эффекта (ходы)
    duration = Column(Integer, default=0)
    
    # Иконка
    icon = Column(String(50), default="✨")
    
    # Редкость
    rarity = Column(String(20), default="common")
    
    # Связь с пользователями
    user_techniques = relationship("UserTechnique", back_populates="technique")


class UserTechnique(Base):
    """Техники пользователя"""
    __tablename__ = 'user_techniques'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    technique_id = Column(Integer, ForeignKey('techniques.id'), nullable=False)
    
    # Уровень техники
    level = Column(Integer, default=1)
    
    # Экипирована ли
    is_equipped = Column(Boolean, default=False)
    
    # В каком слоте (1-4)
    slot_number = Column(Integer, nullable=True)
    
    # Дата получения
    obtained_at = Column(DateTime, default=datetime.utcnow)
    
    # Связи
    user = relationship("User", back_populates="techniques")
    technique = relationship("Technique", back_populates="user_techniques")


class AcademyLesson(Base):
    """Уроки в техникуме"""
    __tablename__ = 'academy_lessons'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    
    # Тип урока
    lesson_type = Column(String(50), nullable=False)  # technique, stat_boost, ability
    
    # Что дает
    reward_technique_id = Column(Integer, ForeignKey('techniques.id'), nullable=True)
    reward_stat = Column(String(20), nullable=True)  # attack, defense, speed, hp
    reward_value = Column(Integer, default=0)
    
    # Стоимость
    coin_cost = Column(Integer, default=100)
    
    # Шанс успеха
    success_chance = Column(Float, default=0.5)
    
    # Требуемый уровень
    required_level = Column(Integer, default=1)
    
    # Связь
    reward_technique = relationship("Technique")


class UserAcademyVisit(Base):
    """Посещения техникума"""
    __tablename__ = 'user_academy_visits'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    
    # Количество посещений
    total_visits = Column(Integer, default=0)
    
    # Последнее посещение
    last_visit = Column(DateTime, nullable=True)
    
    # Кулдаун в часах
    cooldown_hours = Column(Integer, default=24)
    
    def can_visit(self):
        """Можно ли посетить техникум"""
        if not self.last_visit:
            return True
        
        hours_passed = (datetime.utcnow() - self.last_visit).total_seconds() / 3600
        return hours_passed >= self.cooldown_hours
    
    def get_remaining_cooldown(self):
        """Получить оставшееся время кулдауна"""
        if not self.last_visit:
            return 0
        
        hours_passed = (datetime.utcnow() - self.last_visit).total_seconds() / 3600
        remaining = self.cooldown_hours - hours_passed
        return max(0, remaining)


class PromoCode(Base):
    """Промокоды"""
    __tablename__ = 'promo_codes'
    
    id = Column(Integer, primary_key=True)
    code = Column(String(100), nullable=False, unique=True)
    
    # Описание
    description = Column(String(500), nullable=True)
    
    # Награды
    exp_reward = Column(Integer, default=0)
    points_reward = Column(Integer, default=0)
    coins_reward = Column(Integer, default=0)
    
    # Карта (название)
    card_reward = Column(String(100), nullable=True)
    
    # Техника (название)
    technique_reward = Column(String(100), nullable=True)
    
    # Максимальное количество использований
    max_uses = Column(Integer, default=1)
    current_uses = Column(Integer, default=0)
    
    # Срок действия
    expires_at = Column(DateTime, nullable=True)
    
    # Активен ли
    is_active = Column(Boolean, default=True)


class UserPromoCode(Base):
    """Использованные промокоды"""
    __tablename__ = 'user_promo_codes'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    promo_code_id = Column(Integer, ForeignKey('promo_codes.id'), nullable=False)
    
    # Дата использования
    used_at = Column(DateTime, default=datetime.utcnow)