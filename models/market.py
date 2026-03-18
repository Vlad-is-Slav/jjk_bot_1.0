from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Boolean, BigInteger, Float
from sqlalchemy.orm import relationship
from datetime import datetime
from .base import Base

class MarketListing(Base):
    """Лоты на рынке"""
    __tablename__ = 'market_listings'
    
    id = Column(Integer, primary_key=True)
    seller_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    
    # Тип лота: card, technique, item
    listing_type = Column(String(20), default="card")
    
    # ID предмета
    item_id = Column(Integer, nullable=False)  # ID карты или техники
    
    # Название (для отображения)
    item_name = Column(String(100), nullable=False)
    
    # Характеристики для отображения
    item_level = Column(Integer, default=1)
    item_rarity = Column(String(20), default="common")
    
    # Цена
    price = Column(BigInteger, default=0)
    
    # Дата создания
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Продано ли
    sold = Column(Boolean, default=False)
    sold_at = Column(DateTime, nullable=True)
    buyer_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    
    # Связи
    seller = relationship("User", foreign_keys=[seller_id], back_populates="market_listings")
    buyer = relationship("User", foreign_keys=[buyer_id])


class TradeOffer(Base):
    """Предложения обмена между игроками"""
    __tablename__ = 'trade_offers'
    
    id = Column(Integer, primary_key=True)
    sender_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    receiver_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    
    # Что предлагает отправитель
    sender_card_id = Column(Integer, nullable=True)
    sender_coins = Column(BigInteger, default=0)
    
    # Что хочет получить
    requested_card_id = Column(Integer, nullable=True)
    requested_coins = Column(BigInteger, default=0)
    
    # Статус
    status = Column(String(20), default="pending")  # pending, accepted, declined, cancelled
    
    # Даты
    created_at = Column(DateTime, default=datetime.utcnow)
    responded_at = Column(DateTime, nullable=True)
    
    # Связи
    sender = relationship("User", foreign_keys=[sender_id], back_populates="sent_trades")
    receiver = relationship("User", foreign_keys=[receiver_id], back_populates="received_trades")


class CoinTransaction(Base):
    """История транзакций монет"""
    __tablename__ = 'coin_transactions'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    
    # Тип транзакции
    transaction_type = Column(String(50), nullable=False)  # earn, spend, trade, market
    
    # Сумма (положительная или отрицательная)
    amount = Column(BigInteger, default=0)
    
    # Описание
    description = Column(String(500), nullable=True)
    
    # Баланс после транзакции
    balance_after = Column(BigInteger, default=0)
    
    # Дата
    created_at = Column(DateTime, default=datetime.utcnow)