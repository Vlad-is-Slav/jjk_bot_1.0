"""
Данные ежедневных заданий
"""

DAILY_QUESTS = [
    # Легкие задания
    {
        "name": "Тренировка",
        "description": "Проведи 3 боя на арене проклятий",
        "quest_type": "pve_battles",
        "requirement": 3,
        "exp_reward": 50,
        "points_reward": 1,
        "coins_reward": 100,
        "difficulty": "easy"
    },
    {
        "name": "Победная Серия",
        "description": "Победи в 2 боях на арене",
        "quest_type": "pve_wins",
        "requirement": 2,
        "exp_reward": 60,
        "points_reward": 1,
        "coins_reward": 120,
        "difficulty": "easy"
    },
    {
        "name": "Прокачка",
        "description": "Улучши любую карту 1 раз",
        "quest_type": "upgrade_cards",
        "requirement": 1,
        "exp_reward": 40,
        "points_reward": 1,
        "coins_reward": 80,
        "difficulty": "easy"
    },
    {
        "name": "Посещение Техникума",
        "description": "Сходи в техникум 1 раз",
        "quest_type": "academy_visit",
        "requirement": 1,
        "exp_reward": 50,
        "points_reward": 1,
        "coins_reward": 100,
        "difficulty": "easy"
    },
    {
        "name": "Сообщения",
        "description": "Напиши 10 сообщений в боте",
        "quest_type": "send_messages",
        "requirement": 10,
        "exp_reward": 30,
        "points_reward": 1,
        "coins_reward": 50,
        "difficulty": "easy"
    },
    
    # Средние задания
    {
        "name": "Опытный Боец",
        "description": "Проведи 5 боев на арене проклятий",
        "quest_type": "pve_battles",
        "requirement": 5,
        "exp_reward": 100,
        "points_reward": 1,
        "coins_reward": 200,
        "difficulty": "medium"
    },
    {
        "name": "PvP Мастер",
        "description": "Победи в 3 PvP боях",
        "quest_type": "pvp_wins",
        "requirement": 3,
        "exp_reward": 150,
        "points_reward": 1,
        "coins_reward": 300,
        "difficulty": "medium"
    },
    {
        "name": "Истребитель",
        "description": "Победи 5 проклятий",
        "quest_type": "pve_wins",
        "requirement": 5,
        "exp_reward": 120,
        "points_reward": 1,
        "coins_reward": 250,
        "difficulty": "medium"
    },
    {
        "name": "Коллекционер",
        "description": "Получи 2 новые карты",
        "quest_type": "obtain_cards",
        "requirement": 2,
        "exp_reward": 80,
        "points_reward": 1,
        "coins_reward": 150,
        "difficulty": "medium"
    },
    {
        "name": "Техники",
        "description": "Используй способности 10 раз",
        "quest_type": "use_abilities",
        "requirement": 10,
        "exp_reward": 100,
        "points_reward": 1,
        "coins_reward": 200,
        "difficulty": "medium"
    },
    {
        "name": "Сюжет",
        "description": "Пройди 2 уровня в сюжетной кампании",
        "quest_type": "campaign_levels",
        "requirement": 2,
        "exp_reward": 150,
        "points_reward": 1,
        "coins_reward": 300,
        "difficulty": "medium"
    },
    
    # Сложные задания
    {
        "name": "Марафон",
        "description": "Проведи 10 боев на арене",
        "quest_type": "pve_battles",
        "requirement": 10,
        "exp_reward": 200,
        "points_reward": 1,
        "coins_reward": 400,
        "difficulty": "hard"
    },
    {
        "name": "PvP Легенда",
        "description": "Победи в 5 PvP боях",
        "quest_type": "pvp_wins",
        "requirement": 5,
        "exp_reward": 300,
        "points_reward": 1,
        "coins_reward": 600,
        "difficulty": "hard"
    },
    {
        "name": "Катастрофа",
        "description": "Победи 3 катастрофических проклятия",
        "quest_type": "disaster_wins",
        "requirement": 3,
        "exp_reward": 250,
        "points_reward": 1,
        "coins_reward": 500,
        "difficulty": "hard"
    },
    {
        "name": "Босс",
        "description": "Победи любого босса",
        "quest_type": "boss_defeat",
        "requirement": 1,
        "exp_reward": 400,
        "points_reward": 1,
        "coins_reward": 800,
        "difficulty": "hard"
    },
    {
        "name": "Мастер Прокачки",
        "description": "Улучши карты 5 раз",
        "quest_type": "upgrade_cards",
        "requirement": 5,
        "exp_reward": 150,
        "points_reward": 1,
        "coins_reward": 300,
        "difficulty": "hard"
    },
    {
        "name": "Территории",
        "description": "Используй расширение территории 5 раз",
        "quest_type": "use_domains",
        "requirement": 5,
        "exp_reward": 300,
        "points_reward": 1,
        "coins_reward": 600,
        "difficulty": "hard"
    }
]

def get_quests_by_difficulty(difficulty: str):
    """Получить задания по сложности"""
    return [q for q in DAILY_QUESTS if q["difficulty"] == difficulty]

def get_random_quests(count: int = 3):
    """Получить случайные задания"""
    import random
    easy = [q for q in DAILY_QUESTS if q["difficulty"] == "easy"]
    medium = [q for q in DAILY_QUESTS if q["difficulty"] == "medium"]
    hard = [q for q in DAILY_QUESTS if q["difficulty"] == "hard"]
    
    quests = []
    quests.extend(random.sample(easy, min(2, len(easy))))
    quests.extend(random.sample(medium, min(2, len(medium))))
    quests.extend(random.sample(hard, min(1, len(hard))))
    
    return quests[:count]
