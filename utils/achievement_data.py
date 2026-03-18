"""
Данные достижений и титулов
"""

# Достижения
ACHIEVEMENTS = [
    # PvP достижения
    {
        "name": "Первый Бой",
        "description": "Победи в первом PvP бою",
        "achievement_type": "pvp_wins",
        "requirement_value": 1,
        "exp_reward": 100,
        "points_reward": 1,
        "title_reward": "Боец",
        "icon": "⚔️",
        "rarity": "common"
    },
    {
        "name": "Мастер PvP",
        "description": "Победи в 50 PvP боях",
        "achievement_type": "pvp_wins",
        "requirement_value": 50,
        "exp_reward": 500,
        "points_reward": 1,
        "title_reward": "PvP Мастер",
        "icon": "🏆",
        "rarity": "rare"
    },
    {
        "name": "Легенда Арены",
        "description": "Победи в 200 PvP боях",
        "achievement_type": "pvp_wins",
        "requirement_value": 200,
        "exp_reward": 2000,
        "points_reward": 1,
        "title_reward": "Легенда Арены",
        "icon": "👑",
        "rarity": "legendary"
    },
    {
        "name": "Безупречный",
        "description": "Выиграй 10 PvP боев подряд",
        "achievement_type": "pvp_streak",
        "requirement_value": 10,
        "exp_reward": 1000,
        "points_reward": 1,
        "title_reward": "Неостановимый",
        "icon": "🔥",
        "rarity": "epic"
    },
    
    # PvE достижения
    {
        "name": "Истребитель",
        "description": "Победи 10 проклятий",
        "achievement_type": "pve_wins",
        "requirement_value": 10,
        "exp_reward": 100,
        "points_reward": 1,
        "title_reward": "Истребитель",
        "icon": "👹",
        "rarity": "common"
    },
    {
        "name": "Охотник на Проклятий",
        "description": "Победи 100 проклятий",
        "achievement_type": "pve_wins",
        "requirement_value": 100,
        "exp_reward": 500,
        "points_reward": 1,
        "title_reward": "Охотник",
        "icon": "🎯",
        "rarity": "rare"
    },
    {
        "name": "Гроза Проклятий",
        "description": "Победи 500 проклятий",
        "achievement_type": "pve_wins",
        "requirement_value": 500,
        "exp_reward": 2000,
        "points_reward": 1,
        "title_reward": "Гроза",
        "icon": "⚡",
        "rarity": "legendary"
    },
    {
        "name": "Победитель Катастроф",
        "description": "Победи 20 катастрофических проклятий",
        "achievement_type": "disaster_wins",
        "requirement_value": 20,
        "exp_reward": 1500,
        "points_reward": 1,
        "title_reward": "Специальный Класс",
        "icon": "💀",
        "rarity": "epic"
    },
    
    # Уровневые достижения
    {
        "name": "Новичок",
        "description": "Достигни 5 уровня",
        "achievement_type": "level",
        "requirement_value": 5,
        "exp_reward": 50,
        "points_reward": 1,
        "title_reward": "Новичок",
        "icon": "🌱",
        "rarity": "common"
    },
    {
        "name": "Опытный Маг",
        "description": "Достигни 25 уровня",
        "achievement_type": "level",
        "requirement_value": 25,
        "exp_reward": 300,
        "points_reward": 1,
        "title_reward": "Маг",
        "icon": "📖",
        "rarity": "rare"
    },
    {
        "name": "Мастер",
        "description": "Достигни 50 уровня",
        "achievement_type": "level",
        "requirement_value": 50,
        "exp_reward": 1000,
        "points_reward": 1,
        "title_reward": "Мастер",
        "icon": "🎓",
        "rarity": "epic"
    },
    {
        "name": "Полубог",
        "description": "Достигни 100 уровня",
        "achievement_type": "level",
        "requirement_value": 100,
        "exp_reward": 5000,
        "points_reward": 1,
        "title_reward": "Полубог",
        "icon": "⭐",
        "rarity": "legendary"
    },
    
    # Карточные достижения
    {
        "name": "Коллекционер",
        "description": "Собери 10 разных карт",
        "achievement_type": "cards_collected",
        "requirement_value": 10,
        "exp_reward": 200,
        "points_reward": 1,
        "title_reward": "Коллекционер",
        "icon": "🎴",
        "rarity": "common"
    },
    {
        "name": "Легендарный Коллекционер",
        "description": "Собери 50 разных карт",
        "achievement_type": "cards_collected",
        "requirement_value": 50,
        "exp_reward": 1000,
        "points_reward": 1,
        "title_reward": "Карточный Магнат",
        "icon": "💎",
        "rarity": "epic"
    },
    {
        "name": "Макс Уровень",
        "description": "Прокачай любую карту до 50 уровня",
        "achievement_type": "card_max_level",
        "requirement_value": 50,
        "exp_reward": 500,
        "points_reward": 1,
        "title_reward": "Кузнец",
        "icon": "🔨",
        "rarity": "rare"
    },
    
    # Техники
    {
        "name": "Первые Шаги",
        "description": "Получи свою первую технику",
        "achievement_type": "techniques_obtained",
        "requirement_value": 1,
        "exp_reward": 100,
        "points_reward": 1,
        "title_reward": "Ученик",
        "icon": "✨",
        "rarity": "common"
    },
    {
        "name": "Мастер Техник",
        "description": "Получи 10 разных техник",
        "achievement_type": "techniques_obtained",
        "requirement_value": 10,
        "exp_reward": 500,
        "points_reward": 1,
        "title_reward": "Техник",
        "icon": "📜",
        "rarity": "rare"
    },
    {
        "name": "Владелец Территории",
        "description": "Используй расширение территории 20 раз",
        "achievement_type": "territories_used",
        "requirement_value": 20,
        "exp_reward": 800,
        "points_reward": 1,
        "title_reward": "Владыка",
        "icon": "🏛️",
        "rarity": "epic"
    },
    
    # Сюжет
    {
        "name": "Начало Пути",
        "description": "Пройди первый сезон сюжета",
        "achievement_type": "campaign_seasons",
        "requirement_value": 1,
        "exp_reward": 300,
        "points_reward": 1,
        "title_reward": "Герой",
        "icon": "🗡️",
        "rarity": "rare"
    },
    {
        "name": "Победитель Сукуны",
        "description": "Победи Сукуну в сюжетной кампании",
        "achievement_type": "sukuna_defeated",
        "requirement_value": 1,
        "exp_reward": 10000,
        "points_reward": 1,
        "title_reward": "Король Магов",
        "icon": "👑",
        "rarity": "mythical"
    },
    
    # Экономика
    {
        "name": "Богач",
        "description": "Накопи 10000 монет",
        "achievement_type": "coins_collected",
        "requirement_value": 10000,
        "exp_reward": 300,
        "points_reward": 1,
        "title_reward": "Богач",
        "icon": "💰",
        "rarity": "rare"
    },
    {
        "name": "Торговец",
        "description": "Продай 10 карт на рынке",
        "achievement_type": "market_sales",
        "requirement_value": 10,
        "exp_reward": 400,
        "points_reward": 1,
        "title_reward": "Торговец",
        "icon": "🏪",
        "rarity": "rare"
    },
    
    # Хардкор
    {
        "name": "Выживший",
        "description": "Достигни 50 уровня в хардкор режиме",
        "achievement_type": "hardcore_level",
        "requirement_value": 50,
        "exp_reward": 5000,
        "points_reward": 1,
        "title_reward": "Непобедимый",
        "icon": "☠️",
        "rarity": "legendary"
    },
    
    # Ежедневные
    {
        "name": "Начинающий",
        "description": "Забери 7 ежедневных наград подряд",
        "achievement_type": "daily_streak",
        "requirement_value": 7,
        "exp_reward": 200,
        "points_reward": 1,
        "title_reward": "Последовательный",
        "icon": "📅",
        "rarity": "common"
    },
    {
        "name": "Легенда Стрика",
        "description": "Забери 30 ежедневных наград подряд",
        "achievement_type": "daily_streak",
        "requirement_value": 30,
        "exp_reward": 1000,
        "points_reward": 1,
        "title_reward": "Легенда",
        "icon": "🔥",
        "rarity": "epic"
    }
]

# Титулы (дополнительные, не из достижений)
TITLES = [
    {
        "name": "Новичок",
        "description": "Только начинаешь свой путь",
        "attack_bonus": 0,
        "defense_bonus": 0,
        "speed_bonus": 0,
        "hp_bonus": 0,
        "icon": "🌱",
        "requirement": "Стартовый титул"
    },
    {
        "name": "Избранный",
        "description": "Тебя выбрала судьба",
        "attack_bonus": 5,
        "defense_bonus": 5,
        "speed_bonus": 5,
        "hp_bonus": 10,
        "icon": "✨",
        "requirement": "Получить легендарную карту"
    },
    {
        "name": "Теневой Маг",
        "description": "Владеешь силой теней",
        "attack_bonus": 10,
        "defense_bonus": 0,
        "speed_bonus": 15,
        "hp_bonus": 0,
        "icon": "🌑",
        "requirement": "Получить технику Десяти Теней"
    },
    {
        "name": "Бессмертный",
        "description": "Сила бесконечности течет в тебе",
        "attack_bonus": 0,
        "defense_bonus": 20,
        "speed_bonus": 0,
        "hp_bonus": 30,
        "icon": "∞",
        "requirement": "Получить технику Бесконечность"
    },
    {
        "name": "Король Проклятий",
        "description": "Ты равен Сукуне",
        "attack_bonus": 50,
        "defense_bonus": 30,
        "speed_bonus": 30,
        "hp_bonus": 50,
        "icon": "👹",
        "requirement": "Победить Сукуну"
    },
    {
        "name": "Верховный",
        "description": "Ты достиг вершины",
        "attack_bonus": 100,
        "defense_bonus": 100,
        "speed_bonus": 100,
        "hp_bonus": 200,
        "icon": "👑",
        "requirement": "Достичь 100 уровня"
    }
]

def get_achievement_by_type(achievement_type: str):
    """Получить достижения по типу"""
    return [a for a in ACHIEVEMENTS if a["achievement_type"] == achievement_type]

def get_title_by_name(name: str):
    """Получить титул по названию"""
    for title in TITLES:
        if title["name"] == name:
            return title
    return None
