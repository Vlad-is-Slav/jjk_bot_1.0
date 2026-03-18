from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Boolean, BigInteger
from sqlalchemy.orm import relationship
from datetime import datetime, date
from .base import Base

class DailyReward(Base):
    """Ежедневные награды пользователя"""
    __tablename__ = 'daily_rewards'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, unique=True)
    
    # Текущий день стрика (1-7, потом сбрасывается или продолжается)
    current_streak = Column(Integer, default=0)
    max_streak = Column(Integer, default=0)
    
    # Последний сбор награды
    last_claim_date = Column(DateTime, nullable=True)
    
    # Связь с пользователем
    user = relationship("User", back_populates="daily_reward")
    
    def get_today_reward(self):
        """Получить награду за сегодня"""
        rewards = {
            1: {"exp": 50, "points": 1, "coins": 100, "name": "День 1"},
            2: {"exp": 75, "points": 1, "coins": 150, "name": "День 2"},
            3: {"exp": 100, "points": 1, "coins": 200, "name": "День 3"},
            4: {"exp": 125, "points": 1, "coins": 250, "name": "День 4"},
            5: {"exp": 150, "points": 1, "coins": 300, "name": "День 5"},
            6: {"exp": 200, "points": 1, "coins": 400, "name": "День 6"},
            7: {"exp": 500, "points": 1, "coins": 1000, "card_chance": True, "name": "День 7 - БОНУС!"}
        }
        day = ((self.current_streak) % 7) + 1
        return rewards.get(day, rewards[1])
    
    def can_claim(self):
        """Можно ли забрать награду"""
        if not self.last_claim_date:
            return True
        
        last_date = self.last_claim_date.date() if isinstance(self.last_claim_date, datetime) else self.last_claim_date
        today = date.today()
        
        # Уже забрали сегодня
        if last_date == today:
            return False
        
        return True
    
    def claim(self):
        """Забрать награду"""
        if not self.can_claim():
            return None
        
        last_date = self.last_claim_date.date() if self.last_claim_date else None
        today = date.today()
        
        # Проверяем стрик
        if last_date and (today - last_date).days == 1:
            self.current_streak += 1
        else:
            self.current_streak = 1
        
        if self.current_streak > self.max_streak:
            self.max_streak = self.current_streak
        
        self.last_claim_date = datetime.utcnow()
        
        return self.get_today_reward()


class DailyQuest(Base):
    """Ежедневные задания (шаблоны)"""
    __tablename__ = 'daily_quests'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    description = Column(String(500), nullable=False)
    
    # Тип задания
    quest_type = Column(String(50), nullable=False)  # pve_battles, pvp_battles, win_battles, upgrade_cards, etc.
    
    # Требуемое значение
    requirement = Column(Integer, default=1)
    
    # Награды
    exp_reward = Column(Integer, default=0)
    points_reward = Column(Integer, default=0)
    coins_reward = Column(Integer, default=0)
    
    # Сложность
    difficulty = Column(String(20), default="easy")  # easy, medium, hard


class UserDailyQuest(Base):
    """Задания пользователя на сегодня"""
    __tablename__ = 'user_daily_quests'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    quest_id = Column(Integer, ForeignKey('daily_quests.id'), nullable=False)
    
    # Прогресс
    progress = Column(Integer, default=0)
    completed = Column(Boolean, default=False)
    claimed = Column(Boolean, default=False)  # Награда забрана
    
    # Дата
    assigned_date = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    
    # Связи
    user = relationship("User", back_populates="daily_quests")
    quest = relationship("DailyQuest")
    
    def is_today(self):
        """Задание на сегодня?"""
        if not self.assigned_date:
            return False
        return self.assigned_date.date() == date.today()


class UserStats(Base):
    """Расширенная статистика пользователя"""
    __tablename__ = 'user_stats'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, unique=True)
    
    # Счетчики для достижений
    total_pve_battles = Column(Integer, default=0)
    total_pvp_battles = Column(Integer, default=0)
    total_damage_dealt = Column(BigInteger, default=0)
    total_damage_taken = Column(BigInteger, default=0)
    cards_upgraded = Column(Integer, default=0)
    cards_collected = Column(Integer, default=0)
    abilities_used = Column(Integer, default=0)
    territories_used = Column(Integer, default=0)
    
    # Для ежедневных заданий
    pve_battles_today = Column(Integer, default=0)
    pvp_battles_today = Column(Integer, default=0)
    wins_today = Column(Integer, default=0)
    
    # Последний сброс дневной статистики
    last_reset = Column(DateTime, default=datetime.utcnow)
    
    # Связь
    user = relationship("User", back_populates="stats")
    
    def reset_daily(self):
        """Сбросить дневную статистику"""
        self.pve_battles_today = 0
        self.pvp_battles_today = 0
        self.wins_today = 0
        self.last_reset = datetime.utcnow()
