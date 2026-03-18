from sqlalchemy import Column, Integer, String, Float
from .base import Base

class Curse(Base):
    """Проклятия для PvE боев"""
    __tablename__ = 'curses'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    description = Column(String(500), nullable=True)
    
    # Уровень сложности (1-10)
    grade = Column(Integer, default=1)
    
    # Тип: 'weak', 'normal', 'strong', 'special', 'disaster'
    curse_type = Column(String(20), default='weak')
    
    # Характеристики
    attack = Column(Integer, default=10)
    defense = Column(Integer, default=10)
    speed = Column(Integer, default=10)
    hp = Column(Integer, default=50)
    max_hp = Column(Integer, default=50)
    
    # Награды за победу
    exp_reward = Column(Integer, default=10)
    points_reward = Column(Integer, default=1)
    
    # Шанс выпадения карты (в процентах)
    card_drop_chance = Column(Float, default=0.0)
    
    # зображение
    image_url = Column(String(500), nullable=True)
    
    def take_damage(self, damage: int):
        """Получить урон"""
        actual_damage = max(1, int(damage - self.defense * 0.3))
        self.hp = max(0, self.hp - actual_damage)
        return actual_damage

    def take_true_damage(self, damage: int):
        """ ,  ."""
        actual_damage = max(1, int(damage))
        self.hp = max(0, self.hp - actual_damage)
        return actual_damage
    
    def is_alive(self):
        """Проверить, живо ли проклятие"""
        return self.hp > 0
    
    def reset_hp(self):
        """Сбросить HP для нового боя"""
        self.hp = self.max_hp
