from sqlalchemy import Column, Integer, String, ForeignKey, Boolean, Float
from sqlalchemy.orm import relationship
from .base import Base

class Card(Base):
    """Шаблон карты (справочник всех доступных карт)"""
    __tablename__ = 'cards'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    description = Column(String(500), nullable=True)
    
    # Тип карты: 'character' (персонаж), 'support' (поддержка), 'weapon' (оружие), 'artifact' (артефакт), 'pact' (пакт)
    card_type = Column(String(20), default='character')
    
    # Редкость: common, rare, epic, legendary, mythical
    rarity = Column(String(20), default='common')
    
    # Базовые характеристики
    base_attack = Column(Integer, default=10)
    base_defense = Column(Integer, default=10)
    base_speed = Column(Integer, default=10)
    base_hp = Column(Integer, default=100)
    
    # Проклятая энергия
    base_ce = Column(Integer, default=100)  # Базовое количество проклятой энергии
    ce_regen = Column(Integer, default=10)  # Восстановление CE за ход
    
    # Множитель роста характеристик при прокачке
    growth_multiplier = Column(Float, default=1.1)
    
    # Врожденная техника (для 4 слота)
    innate_technique = Column(String(100), nullable=True)
    
    # Способности карты (JSON)
    abilities = Column(String(1000), nullable=True)
    
    # Шанс черной молнии (%)
    black_flash_chance = Column(Float, default=2.0)
    
    # зображение
    image_url = Column(String(500), nullable=True)
    
    # Связь с картами игроков
    user_cards = relationship("UserCard", back_populates="card_template")


class UserCard(Base):
    """Карта конкретного игрока (с прокачкой)"""
    __tablename__ = 'user_cards'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    card_id = Column(Integer, ForeignKey('cards.id'), nullable=False)
    
    # Уровень прокачки карты
    level = Column(Integer, default=1)
    
    # Текущие характеристики
    attack = Column(Integer, default=0)
    defense = Column(Integer, default=0)
    speed = Column(Integer, default=0)
    hp = Column(Integer, default=0)
    max_hp = Column(Integer, default=0)
    
    # Проклятая энергия
    ce = Column(Integer, default=0)  # Текущая CE
    max_ce = Column(Integer, default=100)  # Максимальная CE

    # Бонусы от классовых очков
    bonus_attack = Column(Integer, default=0)
    bonus_defense = Column(Integer, default=0)
    bonus_speed = Column(Integer, default=0)
    bonus_hp = Column(Integer, default=0)
    bonus_ce = Column(Integer, default=0)
    bonus_ce_regen = Column(Integer, default=0)
    domain_level = Column(Integer, default=0)
    rct_level = Column(Integer, default=0)
    
    # Стоимость следующей прокачки
    upgrade_cost = Column(Integer, default=1)
    
    # Экипирована ли карта
    is_equipped = Column(Boolean, default=False)
    
    # В каком слоте (1-4)
    slot_number = Column(Integer, nullable=True)
    
    # Связи
    user = relationship("User", back_populates="cards")
    card_template = relationship("Card", back_populates="user_cards")
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if self.card_template:
            self.recalculate_stats()
    
    def recalculate_stats(self):
        """Пересчитать характеристики на основе уровня"""
        if not self.card_template:
            return

        card_type = (self.card_template.card_type or "").lower()
        if card_type in {"weapon", "pact"}:
            # Оружие и пакты не прокачиваются и не получают CE/домены.
            self.level = 1
            self.bonus_attack = 0
            self.bonus_defense = 0
            self.bonus_speed = 0
            self.bonus_hp = 0
            self.bonus_ce = 0
            self.bonus_ce_regen = 0
            self.domain_level = 0
            self.rct_level = 0

            base_attack = self.card_template.base_attack
            base_defense = self.card_template.base_defense
            base_speed = self.card_template.base_speed
            base_hp = self.card_template.base_hp
            base_ce = getattr(self.card_template, "base_ce", 0) or 0

            self.attack = int(base_attack)
            self.defense = int(base_defense)
            self.speed = int(base_speed)
            self.max_hp = int(base_hp)
            self.hp = min(self.hp or self.max_hp, self.max_hp)

            self.max_ce = int(base_ce)
            self.ce = min(self.ce or self.max_ce, self.max_ce)

            self.upgrade_cost = 0
            return
        
        base_attack = self.card_template.base_attack
        base_defense = self.card_template.base_defense
        base_speed = self.card_template.base_speed
        base_hp = self.card_template.base_hp
        base_ce = self.card_template.base_ce

        # Сохраняем старые прокачки, если бонусы ещё не заполнены или потерялись.
        if self.attack is not None and self.attack > base_attack and not self.bonus_attack:
            self.bonus_attack = max(0, self.attack - base_attack)
        if self.defense is not None and self.defense > base_defense and not self.bonus_defense:
            self.bonus_defense = max(0, self.defense - base_defense)
        if self.speed is not None and self.speed > base_speed and not self.bonus_speed:
            self.bonus_speed = max(0, self.speed - base_speed)
        if self.max_hp is not None and self.max_hp > base_hp and not self.bonus_hp:
            self.bonus_hp = max(0, self.max_hp - base_hp)
        if self.max_ce is not None and self.max_ce > base_ce and not self.bonus_ce:
            self.bonus_ce = max(0, self.max_ce - base_ce)

        self.attack = int(base_attack + (self.bonus_attack or 0))
        self.defense = int(base_defense + (self.bonus_defense or 0))
        self.speed = int(base_speed + (self.bonus_speed or 0))
        self.max_hp = int(base_hp + (self.bonus_hp or 0))
        self.hp = min(self.hp or self.max_hp, self.max_hp)

        self.max_ce = int(base_ce + (self.bonus_ce or 0))
        self.ce = min(self.ce or self.max_ce, self.max_ce)

        # Стоимость прокачки фиксирована: 1 очко
        self.upgrade_cost = 1
    
    def apply_stat_upgrade(self, stat: str, amount: int) -> bool:
        """Улучшить один параметр за классовое очко."""
        if self.card_template and (self.card_template.card_type or "").lower() in {"weapon", "pact"}:
            return False
        stat = (stat or "").lower().strip()
        if stat == "attack":
            self.bonus_attack = (self.bonus_attack or 0) + amount
        elif stat == "defense":
            self.bonus_defense = (self.bonus_defense or 0) + amount
        elif stat == "speed":
            self.bonus_speed = (self.bonus_speed or 0) + amount
        elif stat == "hp":
            self.bonus_hp = (self.bonus_hp or 0) + amount
        elif stat == "ce":
            self.bonus_ce = (self.bonus_ce or 0) + amount
        elif stat == "ce_regen":
            self.bonus_ce_regen = (self.bonus_ce_regen or 0) + amount
        elif stat == "domain":
            self.domain_level = (self.domain_level or 0) + amount
        elif stat == "rct":
            self.rct_level = (self.rct_level or 0) + amount
        else:
            return False

        self.level += 1
        self.recalculate_stats()
        return True

    def upgrade(self):
        """Старый метод прокачки (оставлен для совместимости)."""
        self.level += 1
        self.recalculate_stats()
        return True
    
    def get_total_power(self):
        """Получить общую силу карты"""
        return self.attack + self.defense + self.speed + self.max_hp // 10 + self.max_ce // 20
    
    def heal(self):
        """Восстановить HP и CE до максимума"""
        self.hp = self.max_hp
        self.ce = self.max_ce
    
    def regen_ce(self):
        """Восстановить CE за ход"""
        if self.card_template:
            self.ce = min(self.max_ce, self.ce + self.get_ce_regen())

    def get_ce_regen(self) -> int:
        """  CE  ."""
        base_regen = self.card_template.ce_regen if self.card_template else 0
        return int(base_regen + (self.bonus_ce_regen or 0))
    
    def take_damage(self, damage: int):
        """Получить урон, учитывая защиту"""
        actual_damage = max(1, int(damage - self.defense))
        self.hp = max(0, self.hp - actual_damage)
        return actual_damage

    def take_true_damage(self, damage: int):
        """ ,  ."""
        actual_damage = max(1, int(damage))
        self.hp = max(0, self.hp - actual_damage)
        return actual_damage
    
    def spend_ce(self, amount: int) -> bool:
        """Потратить CE"""
        if self.ce >= amount:
            self.ce -= amount
            return True
        return False
    
    def is_alive(self):
        """Проверить, жива ли карта"""
        return self.hp > 0
    
    def check_black_flash(self) -> bool:
        """Проверить срабатывание черной молнии"""
        import random
        chance = self.card_template.black_flash_chance if self.card_template else 2.0
        return random.random() * 100 < chance
    
    def get_abilities(self):
        """Получить список способностей карты"""
        if not self.card_template or not self.card_template.abilities:
            return []
        import json
        try:
            return json.loads(self.card_template.abilities)
        except:
            return []

