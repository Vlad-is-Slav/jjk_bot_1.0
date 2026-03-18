from sqlalchemy import Column, Integer, BigInteger, String, DateTime, Float, Boolean, Text
from sqlalchemy.orm import relationship
from datetime import datetime

from config import (
    POINTS_PER_LEVEL_UP,
    COINS_PER_LEVEL_UP,
    EXP_TO_NEXT_BASE,
    EXP_TO_NEXT_MULTIPLIER,
    EXP_TO_NEXT_FLAT,
)
from .base import Base

class User(Base):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False, index=True)
    username = Column(String(100), nullable=True)
    first_name = Column(String(100), nullable=True)
    
    # Дата создания профиля
    created_at = Column(DateTime, default=datetime.utcnow)
    last_activity = Column(DateTime, default=datetime.utcnow)
    
    # Статистика игрока
    level = Column(Integer, default=1)
    experience = Column(Integer, default=0)
    experience_to_next = Column(Integer, default=EXP_TO_NEXT_BASE)
    
    # Валюты
    points = Column(Integer, default=0)  # Очки для прокачки карт
    coins = Column(BigInteger, default=1000)  # Монеты для покупок и техникума
    
    # Уровень сложности
    difficulty = Column(String(20), default="normal")  # easy, normal, hard, hardcore
    
    # Хардкор режим - если True и игрок проигрывает = персонаж удаляется
    hardcore_mode = Column(Boolean, default=False)
    hardcore_deaths = Column(Integer, default=0)
    
    # Боевая статистика
    pvp_wins = Column(Integer, default=0)
    pvp_losses = Column(Integer, default=0)
    pve_wins = Column(Integer, default=0)
    pve_losses = Column(Integer, default=0)
    total_battles = Column(Integer, default=0)
    
    # Текущая колода (5 слотов)
    slot_1_card_id = Column(Integer, nullable=True)  # Главный персонаж
    slot_2_card_id = Column(Integer, nullable=True)  # Оружие
    slot_3_card_id = Column(Integer, nullable=True)  # Шикигами
    slot_4_card_id = Column(Integer, nullable=True)  # Пакт 1
    slot_5_card_id = Column(Integer, nullable=True)  # Пакт 2
    
    # Экипированный титул
    equipped_title_id = Column(Integer, nullable=True)

    # Clan info
    clan = Column(String(20), nullable=True)
    clan_joined_at = Column(DateTime, nullable=True)
    
    # Время последнего боя
    last_battle_time = Column(DateTime, nullable=True)
    last_pve_battle_time = Column(DateTime, nullable=True)
    
    # Админ статус
    is_admin = Column(Boolean, default=False)
    is_banned = Column(Boolean, default=False)
    
    # Связи
    cards = relationship("UserCard", back_populates="user", cascade="all, delete-orphan")
    techniques = relationship("UserTechnique", back_populates="user", cascade="all, delete-orphan")
    titles = relationship("UserTitle", back_populates="user", cascade="all, delete-orphan")
    achievements = relationship("UserAchievement", back_populates="user", cascade="all, delete-orphan")
    daily_reward = relationship("DailyReward", back_populates="user", uselist=False, cascade="all, delete-orphan")
    daily_quests = relationship("UserDailyQuest", back_populates="user", cascade="all, delete-orphan")
    stats = relationship("UserStats", back_populates="user", uselist=False, cascade="all, delete-orphan")
    campaign_progress = relationship("UserCampaignProgress", back_populates="user", cascade="all, delete-orphan")
    market_listings = relationship("MarketListing", foreign_keys="MarketListing.seller_id", back_populates="seller")
    sent_trades = relationship("TradeOffer", foreign_keys="TradeOffer.sender_id", back_populates="sender")
    received_trades = relationship("TradeOffer", foreign_keys="TradeOffer.receiver_id", back_populates="receiver")
    battles_as_player1 = relationship("Battle", foreign_keys="Battle.player1_id", back_populates="player1")
    battles_as_player2 = relationship("Battle", foreign_keys="Battle.player2_id", back_populates="player2")
    profile_settings = relationship("UserProfile", back_populates="user", uselist=False, cascade="all, delete-orphan")
    quotes = relationship("UserQuote", back_populates="user", cascade="all, delete-orphan")
    
    def get_win_rate(self):
        """Получить процент побед в PvP"""
        total = self.pvp_wins + self.pvp_losses
        if total == 0:
            return 0
        return round((self.pvp_wins / total) * 100, 1)
    
    def get_total_power(self):
        """Получить общую силу игрока"""
        from sqlalchemy.orm import selectinload
        total = 0
        for card in self.cards:
            if card.is_equipped:
                total += card.get_total_power()
        return total

    def _expected_exp_to_next(self, level: int) -> int:
        exp = EXP_TO_NEXT_BASE
        for _ in range(1, max(1, int(level))):
            exp = int(exp * EXP_TO_NEXT_MULTIPLIER) + EXP_TO_NEXT_FLAT
        return exp
    
    def add_experience(self, amount: int):
        """Добавить опыт и проверить повышение уровня"""
        # Множитель сложности
        multiplier = {
            "easy": 0.5,
            "normal": 1.0,
            "medium": 1.0,
            "hard": 1.5,
            "hardcore": 2.0
        }.get(self.difficulty, 1.0)
        
        actual_exp = int(amount * multiplier)
        self.experience += actual_exp
        leveled_up = False

        # Синхронизируем требуемый опыт для текущего уровня по новой кривой
        expected_next = self._expected_exp_to_next(self.level)
        if self.experience_to_next != expected_next:
            self.experience_to_next = expected_next

        while self.experience >= self.experience_to_next:
            self.experience -= self.experience_to_next
            self.level += 1
            self.experience_to_next = int(self.experience_to_next * EXP_TO_NEXT_MULTIPLIER) + EXP_TO_NEXT_FLAT
            self.points += POINTS_PER_LEVEL_UP  # Бонус очков за уровень
            self.coins += COINS_PER_LEVEL_UP  # Бонус монет за уровень
            leveled_up = True
        
        return leveled_up, actual_exp
    
    def get_equipped_cards(self):
        """Получить все экипированные карты"""
        return [c for c in self.cards if c.is_equipped]
    
    def get_equipped_techniques(self):
        """Получить все экипированные техники"""
        return [t for t in self.techniques if t.is_equipped]
    
    def add_coins(self, amount: int, description: str = None):
        """Добавить монеты"""
        self.coins += amount
        return self.coins
    
    def spend_coins(self, amount: int) -> bool:
        """Потратить монеты"""
        if self.coins >= amount:
            self.coins -= amount
            return True
        return False
    
    def get_difficulty_multiplier(self):
        """Получить множитель наград для сложности"""
        return {
            "easy": 0.5,
            "normal": 1.0,
            "medium": 1.0,
            "hard": 1.5,
            "hardcore": 2.0
        }.get(self.difficulty, 1.0)
    
    def get_formatted_created_date(self):
        """Получить отформатированную дату создания"""
        return self.created_at.strftime("%d.%m.%Y") if self.created_at else "Неизвестно"
  
    @property
    def main_card_id(self):
        return self.slot_1_card_id

    @main_card_id.setter
    def main_card_id(self, value):
        self.slot_1_card_id = value
