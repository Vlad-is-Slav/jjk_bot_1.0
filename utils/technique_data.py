"""
Данные техник и способностей
"""

import json

# Врожденные техники (4 слот)
INNATE_TECHNIQUES = [
    {
        "name": "Шесть Глаз",
        "description": "Легендарные глаза клана Годжо. Позволяют использовать бесконечность с минимальными затратами CE.",
        "technique_type": "innate",
        "ce_cost": 0,
        "effect_type": "passive",
        "effect_value": 60,  # -?% стоимости CE
        "icon": "👁️",
        "rarity": "legendary"
    },
    {
        "name": "Бесконечность",
        "description": "Техника, создающая бесконечное расстояние между врагом и тобой. Автоматическая защита.",
        "technique_type": "innate",
        "ce_cost": 10,
        "effect_type": "buff",
        "effect_value": 100,  # 100% шанс заблокировать урон
        "icon": "♾️",
        "rarity": "legendary"
    },
    {
        "name": "Десять Теней",
        "description": "Техника Фушигуро. Позволяет использовать силу шикигами.",
        "technique_type": "innate",
        "ce_cost": 15,
        "effect_type": "buff",
        "effect_value": 30,  # +30% к атаке шикигами
        "icon": "🐺",
        "rarity": "epic"
    },
    {
        "name": "Кража Духов",
        "description": "Поглощение проклятий и использование их силы.",
        "technique_type": "innate",
        "ce_cost": 25,
        "effect_type": "heal",
        "effect_value": 20,  # Восстановление 20% HP
        "icon": "👻",
        "rarity": "legendary"
    },
    {
        "name": "Проклятая Черепаха",
        "description": "Усиление физических способностей за счет проклятой энергии.",
        "technique_type": "innate",
        "ce_cost": 10,
        "effect_type": "buff",
        "effect_value": 25,  # +25% к атаке
        "icon": "🐢",
        "rarity": "rare"
    },
    {
        "name": "Кровавая Магия",
        "description": "Контроль над кровью для атаки и защиты.",
        "technique_type": "innate",
        "ce_cost": 15,
        "effect_type": "damage",
        "effect_value": 40,
        "icon": "🩸",
        "rarity": "rare"
    },
    {
        "name": "Кукольник",
        "description": "Управление куклами на расстоянии.",
        "technique_type": "innate",
        "ce_cost": 12,
        "effect_type": "buff",
        "effect_value": 20,
        "icon": "🎭",
        "rarity": "rare"
    },
    {
        "name": "Проклятие Сукуны",
        "description": "Сила Короля Проклятий. Невероятная мощь.",
        "technique_type": "innate",
        "ce_cost": 30,
        "effect_type": "damage",
        "effect_value": 100,
        "icon": "👹",
        "rarity": "mythical"
    }
]

# Способности (активные)
ABILITIES = [
    {
        "name": "Красный",
        "description": "Притяжение - обратная сила бесконечности. Мощная атака.",
        "technique_type": "ability",
        "ce_cost": 30,
        "effect_type": "damage",
        "effect_value": 80,
        "icon": "🔴",
        "rarity": "legendary"
    },
    {
        "name": "Фиолетовый",
        "description": "Воображаемая масса - смесь притяжения и отталкивания. Разрушительная сила.",
        "technique_type": "ability",
        "ce_cost": 50,
        "effect_type": "damage",
        "effect_value": 150,
        "icon": "🟣",
        "rarity": "legendary"
    },
    {
        "name": "Черная Молния",
        "description": "Критический удар с шансом оглушения. Шанс зависит от карты.",
        "technique_type": "passive",
        "ce_cost": 0,
        "effect_type": "damage",
        "effect_value": 200,  # 200% от обычного урона
        "trigger_chance": 0,  # Задается в карте
        "icon": "⚡",
        "rarity": "epic"
    },
    {
        "name": "Простая Территория",
        "description": "Базовая защитная техника. Блокирует эффекты чужой территории.",
        "technique_type": "simple",
        "ce_cost": 0,
        "effect_type": "counter",
        "effect_value": 100,  # Блокировка территории
        "duration": 2,
        "icon": "🛡️",
        "rarity": "rare"
    },
    {
        "name": "Расширение Территории",
        "description": "Создание собственного пространства с особыми правилами.",
        "technique_type": "domain",
        "ce_cost": 60,
        "effect_type": "buff",
        "effect_value": 50,  # +50% к урону
        "duration": 3,
        "icon": "🏛️",
        "rarity": "epic"
    },
    {
        "name": "Безграничная Пустота",
        "description": "Территория Годжо. Перегружает разум врага бесконечной информацией.",
        "technique_type": "domain",
        "ce_cost": 80,
        "effect_type": "damage",
        "effect_value": 200,
        "duration": 3,
        "icon": "🌌",
        "rarity": "legendary"
    },
    {
        "name": "Храм Змеи",
        "description": "Территория с ядовитыми атаками.",
        "technique_type": "domain",
        "ce_cost": 50,
        "effect_type": "damage",
        "effect_value": 100,
        "duration": 3,
        "icon": "🐍",
        "rarity": "epic"
    },
    {
        "name": "Каминого",
        "description": "Речевая магия. Усиленные команды.",
        "technique_type": "ability",
        "ce_cost": 20,
        "effect_type": "buff",
        "effect_value": 35,
        "icon": "🗣️",
        "rarity": "rare"
    },
    {
        "name": "Бугорок",
        "description": "Техника Тодо. Обмен местами с объектом.",
        "technique_type": "ability",
        "ce_cost": 25,
        "effect_type": "buff",
        "effect_value": 40,
        "icon": "👏",
        "rarity": "epic"
    },
    {
        "name": "Пропорция",
        "description": "Техника Нанами. Точные удары по слабым точкам.",
        "technique_type": "ability",
        "ce_cost": 20,
        "effect_type": "damage",
        "effect_value": 60,
        "icon": "📐",
        "rarity": "rare"
    }
]

# Пакты
PACTS = [
    {
        "name": "Пакт с Проклятием",
        "description": "Обмен HP на мощную атаку.",
        "technique_type": "pact",
        "ce_cost": 15,
        "effect_type": "damage",
        "effect_value": 70,
        "icon": "📜",
        "rarity": "rare"
    },
    {
        "name": "Союз Шикигами",
        "description": "Усиление шикигами в колоде.",
        "technique_type": "pact",
        "ce_cost": 20,
        "effect_type": "buff",
        "effect_value": 45,
        "icon": "🤝",
        "rarity": "epic"
    },
    {
        "name": "Клятва Молчания",
        "description": "Запрет на использование техник врагом.",
        "technique_type": "pact",
        "ce_cost": 35,
        "effect_type": "debuff",
        "effect_value": 100,
        "duration": 2,
        "icon": "🤐",
        "rarity": "legendary"
    }
]

# Объединяем все техники
ALL_TECHNIQUES = INNATE_TECHNIQUES + ABILITIES + PACTS

def get_technique_by_name(name: str):
    """Получить технику по названию"""
    for tech in ALL_TECHNIQUES:
        if tech["name"] == name:
            return tech
    return None

def get_techniques_by_type(technique_type: str):
    """Получить техники по типу"""
    return [t for t in ALL_TECHNIQUES if t["technique_type"] == technique_type]

def get_techniques_by_rarity(rarity: str):
    """Получить техники по редкости"""
    return [t for t in ALL_TECHNIQUES if t["rarity"] == rarity]