"""
Данные сюжетной кампании
"""

# Сезоны кампании
CAMPAIGN_SEASONS = [
    {
        "name": "Сезон 1: Пробуждение",
        "description": "Ты только стал магом. Научись сражаться и познай основы проклятой энергии.",
        "season_number": 1,
        "required_level": 1,
        "exp_reward": 500,
        "points_reward": 1,
        "card_reward": "Итадори Юдзи"
    },
    {
        "name": "Сезон 2: Токийский Техникум",
        "description": "Поступи в техникум и найди союзников. Сражайся бок о бок с другими магами.",
        "season_number": 2,
        "required_level": 10,
        "exp_reward": 1000,
        "points_reward": 1,
        "card_reward": "Фушигуро Мегуми"
    },
    {
        "name": "Сезон 3: Киото",
        "description": "События в Киото. Соревнование техникумов и первые серьезные враги.",
        "season_number": 3,
        "required_level": 20,
        "exp_reward": 1500,
        "points_reward": 1,
        "card_reward": "Тодо Аой"
    },
    {
        "name": "Сезон 4: Инцидент в Сибуе",
        "description": "Катастрофа в Сибуе. Специальные классы проклятий выходят на охоту.",
        "season_number": 4,
        "required_level": 35,
        "exp_reward": 3000,
        "points_reward": 1,
        "card_reward": "Маки Дзэнин"
    },
    {
        "name": "Сезон 5: Игра Отборочных",
        "description": "Смертельная игра между магами. Только сильнейшие выживут.",
        "season_number": 5,
        "required_level": 50,
        "exp_reward": 5000,
        "points_reward": 1,
        "card_reward": "Хакари Киндзи"
    },
    {
        "name": "Сезон 6: Возвращение",
        "description": "После долгого перерыва мир изменился. Новые угрозы на горизонте.",
        "season_number": 6,
        "required_level": 70,
        "exp_reward": 8000,
        "points_reward": 1,
        "card_reward": "Оккоцу Юта"
    },
    {
        "name": "Сезон 7: Финальная Битва",
        "description": "Все решается сейчас. Сразись с Королем Проклятий - Сукуной!",
        "season_number": 7,
        "required_level": 100,
        "exp_reward": 50000,
        "points_reward": 1,
        "card_reward": "Сукуна (Союзник)"
    }
]

# Уровни сезонов
CAMPAIGN_LEVELS = {
    # Сезон 1
    1: [
        {
            "name": "Первая Тренировка",
            "description": "Твой первый бой. Сразись со слабым проклятием.",
            "level_type": "battle",
            "enemy_name": "Слабое Проклятие",
            "enemy_attack": 15,
            "enemy_defense": 10,
            "enemy_speed": 12,
            "enemy_hp": 50,
            "exp_reward": 30,
            "points_reward": 1,
            "coins_reward": 50,
            "card_drop_chance": 0
        },
        {
            "name": "Пробуждение Энергии",
            "description": "Научись использовать проклятую энергию.",
            "level_type": "battle",
            "enemy_name": "Проклятие-Ворон",
            "enemy_attack": 20,
            "enemy_defense": 15,
            "enemy_speed": 18,
            "enemy_hp": 70,
            "exp_reward": 40,
            "points_reward": 1,
            "coins_reward": 70,
            "card_drop_chance": 5
        },
        {
            "name": "Первый Босс",
            "description": "Твой первый серьезный враг.",
            "level_type": "boss",
            "enemy_name": "Проклятие-Волк",
            "enemy_attack": 30,
            "enemy_defense": 25,
            "enemy_speed": 28,
            "enemy_hp": 120,
            "exp_reward": 100,
            "points_reward": 1,
            "coins_reward": 150,
            "card_drop_chance": 20,
            "card_drop_name": "Проклятое Оружие"
        }
    ],
    # Сезон 2
    2: [
        {
            "name": "Вступление в Техникум",
            "description": "Докажи, что ты достоин учиться в Токийском Техникуме.",
            "level_type": "battle",
            "enemy_name": "Испытательное Проклятие",
            "enemy_attack": 35,
            "enemy_defense": 30,
            "enemy_speed": 32,
            "enemy_hp": 150,
            "exp_reward": 60,
            "points_reward": 1,
            "coins_reward": 100,
            "card_drop_chance": 10
        },
        {
            "name": "Тренировка с Наставником",
            "description": "Сражайся бок о бок с опытным магом.",
            "level_type": "battle",
            "enemy_name": "Проклятие-Горилла",
            "enemy_attack": 45,
            "enemy_defense": 40,
            "enemy_speed": 25,
            "enemy_hp": 200,
            "exp_reward": 80,
            "points_reward": 1,
            "coins_reward": 130,
            "card_drop_chance": 15
        },
        {
            "name": "Первая Командная Битва",
            "description": "Сражайся вместе с союзниками.",
            "level_type": "battle",
            "enemy_name": "Стая Проклятий",
            "enemy_attack": 40,
            "enemy_defense": 35,
            "enemy_speed": 40,
            "enemy_hp": 250,
            "exp_reward": 120,
            "points_reward": 1,
            "coins_reward": 180,
            "card_drop_chance": 25
        },
        {
            "name": "Босс: Проклятие-Тигр",
            "description": "Мощное проклятие требует всего твоего мастерства.",
            "level_type": "boss",
            "enemy_name": "Проклятие-Тигр",
            "enemy_attack": 55,
            "enemy_defense": 45,
            "enemy_speed": 50,
            "enemy_hp": 300,
            "exp_reward": 200,
            "points_reward": 1,
            "coins_reward": 300,
            "card_drop_chance": 40,
            "card_drop_name": "Шикигами Нуэ"
        }
    ],
    # Сезон 3
    3: [
        {
            "name": "Дорога в Киото",
            "description": "Проклятия атакуют по пути.",
            "level_type": "battle",
            "enemy_name": "Проклятие-Птица",
            "enemy_attack": 50,
            "enemy_defense": 40,
            "enemy_speed": 55,
            "enemy_hp": 180,
            "exp_reward": 100,
            "points_reward": 1,
            "coins_reward": 150,
            "card_drop_chance": 15
        },
        {
            "name": "Дружеское Соревнование",
            "description": "Сразись с магом из Киото.",
            "level_type": "battle",
            "enemy_name": "Маг Киото",
            "enemy_attack": 60,
            "enemy_defense": 55,
            "enemy_speed": 58,
            "enemy_hp": 250,
            "exp_reward": 150,
            "points_reward": 1,
            "coins_reward": 200,
            "card_drop_chance": 20
        },
        {
            "name": "Босс: Махито",
            "description": "Специальный класс - манипуляция душой.",
            "level_type": "boss",
            "enemy_name": "Махито",
            "enemy_attack": 80,
            "enemy_defense": 60,
            "enemy_speed": 70,
            "enemy_hp": 400,
            "exp_reward": 400,
            "points_reward": 1,
            "coins_reward": 500,
            "card_drop_chance": 50,
            "card_drop_name": "Техника Души"
        }
    ],
    # Сезон 4
    4: [
        {
            "name": "Начало Инцидента",
            "description": "Сибуя в осаде.",
            "level_type": "battle",
            "enemy_name": "Проклятие-Полковник",
            "enemy_attack": 70,
            "enemy_defense": 65,
            "enemy_speed": 60,
            "enemy_hp": 300,
            "exp_reward": 150,
            "points_reward": 1,
            "coins_reward": 250,
            "card_drop_chance": 20
        },
        {
            "name": "Ханами",
            "description": "Проклятие леса.",
            "level_type": "boss",
            "enemy_name": "Ханами",
            "enemy_attack": 90,
            "enemy_defense": 80,
            "enemy_speed": 70,
            "enemy_hp": 500,
            "exp_reward": 500,
            "points_reward": 1,
            "coins_reward": 700,
            "card_drop_chance": 60,
            "card_drop_name": "Техника Растений"
        },
        {
            "name": "Джого",
            "description": "Проклятие вулкана.",
            "level_type": "boss",
            "enemy_name": "Джого",
            "enemy_attack": 100,
            "enemy_defense": 75,
            "enemy_speed": 85,
            "enemy_hp": 450,
            "exp_reward": 600,
            "points_reward": 1,
            "coins_reward": 800,
            "card_drop_chance": 65,
            "card_drop_name": "Огненная Техника"
        },
        {
            "name": "Дагон",
            "description": "Морское проклятие.",
            "level_type": "boss",
            "enemy_name": "Дагон",
            "enemy_attack": 85,
            "enemy_defense": 90,
            "enemy_speed": 65,
            "enemy_hp": 550,
            "exp_reward": 550,
            "points_reward": 1,
            "coins_reward": 750,
            "card_drop_chance": 60,
            "card_drop_name": "Водная Техника"
        }
    ],
    # Сезон 5
    5: [
        {
            "name": "Вход в Игру",
            "description": "Правила просты - побеждай или погибни.",
            "level_type": "battle",
            "enemy_name": "Участник Игры",
            "enemy_attack": 90,
            "enemy_defense": 85,
            "enemy_speed": 88,
            "enemy_hp": 400,
            "exp_reward": 200,
            "points_reward": 1,
            "coins_reward": 350,
            "card_drop_chance": 25
        },
        {
            "name": "Смертельная Зона",
            "description": "Опасная территория.",
            "level_type": "battle",
            "enemy_name": "Охотник за Головами",
            "enemy_attack": 100,
            "enemy_defense": 90,
            "enemy_speed": 95,
            "enemy_hp": 500,
            "exp_reward": 300,
            "points_reward": 1,
            "coins_reward": 450,
            "card_drop_chance": 35
        },
        {
            "name": "Финал Игры",
            "description": "Последний противник.",
            "level_type": "boss",
            "enemy_name": "Мастер Игры",
            "enemy_attack": 120,
            "enemy_defense": 110,
            "enemy_speed": 115,
            "enemy_hp": 700,
            "exp_reward": 800,
            "points_reward": 1,
            "coins_reward": 1000,
            "card_drop_chance": 70,
            "card_drop_name": "Техника Игрока"
        }
    ],
    # Сезон 6
    6: [
        {
            "name": "Новый Мир",
            "description": "Все изменилось.",
            "level_type": "battle",
            "enemy_name": "Проклятие Нового Поколения",
            "enemy_attack": 110,
            "enemy_defense": 100,
            "enemy_speed": 105,
            "enemy_hp": 500,
            "exp_reward": 250,
            "points_reward": 1,
            "coins_reward": 400,
            "card_drop_chance": 30
        },
        {
            "name": "Возвращение Легенды",
            "description": "Старый враг вернулся.",
            "level_type": "boss",
            "enemy_name": "Возрожденное Проклятие",
            "enemy_attack": 130,
            "enemy_defense": 120,
            "enemy_speed": 125,
            "enemy_hp": 800,
            "exp_reward": 1000,
            "points_reward": 1,
            "coins_reward": 1200,
            "card_drop_chance": 75,
            "card_drop_name": "Техника Возрождения"
        },
        {
            "name": "Предательство",
            "description": "Бывший союзник стал врагом.",
            "level_type": "boss",
            "enemy_name": "Павший Маг",
            "enemy_attack": 140,
            "enemy_defense": 130,
            "enemy_speed": 135,
            "enemy_hp": 900,
            "exp_reward": 1200,
            "points_reward": 1,
            "coins_reward": 1500,
            "card_drop_chance": 80,
            "card_drop_name": "Техника Падшего"
        }
    ],
    # Сезон 7 - Финал
    7: [
        {
            "name": "Приближение Тьмы",
            "description": "Сукуна пробуждается.",
            "level_type": "battle",
            "enemy_name": "Аватар Сукуны",
            "enemy_attack": 150,
            "enemy_defense": 140,
            "enemy_speed": 145,
            "enemy_hp": 1000,
            "exp_reward": 500,
            "points_reward": 1,
            "coins_reward": 800,
            "card_drop_chance": 50
        },
        {
            "name": "Малое Проявление",
            "description": "Часть силы Короля.",
            "level_type": "boss",
            "enemy_name": "Сукуна (20%)",
            "enemy_attack": 180,
            "enemy_defense": 160,
            "enemy_speed": 170,
            "enemy_hp": 1500,
            "exp_reward": 2000,
            "points_reward": 1,
            "coins_reward": 2500,
            "card_drop_chance": 85,
            "card_drop_name": "Проклятие Сукуны"
        },
        {
            "name": "Полная Сила",
            "description": "Сукуна в полном могуществе.",
            "level_type": "boss",
            "enemy_name": "Сукуна (100%)",
            "enemy_attack": 250,
            "enemy_defense": 220,
            "enemy_speed": 240,
            "enemy_hp": 3000,
            "exp_reward": 5000,
            "points_reward": 1,
            "coins_reward": 5000,
            "card_drop_chance": 95,
            "card_drop_name": "Сила Сукуны"
        },
        {
            "name": "ФИНАЛЬНАЯ БИТВА",
            "description": "Решающая битва за судьбу мира!",
            "level_type": "boss",
            "enemy_name": "РЁМЕН СУКУНА",
            "enemy_attack": 350,
            "enemy_defense": 300,
            "enemy_speed": 320,
            "enemy_hp": 5000,
            "exp_reward": 50000,
            "points_reward": 1,
            "coins_reward": 50000,
            "card_drop_chance": 100,
            "card_drop_name": "СУКУНА (СОЮЗНИК)"
        }
    ]
}

# Боссы для специальных боев
SPECIAL_BOSSES = [
    {
        "name": "Сукуна (Пробужденный)",
        "description": "Король Проклятий в полной силе. Требуется уровень 100.",
        "attack": 300,
        "defense": 250,
        "speed": 280,
        "hp": 4000,
        "exp_reward": 10000,
        "points_reward": 1,
        "coins_reward": 10000,
        "special_reward": "Титул 'Победитель Сукуны'",
        "required_level": 100,
        "cooldown_hours": 72
    },
    {
        "name": "Гето Сугуру",
        "description": "Маг-проклятие. Требуется уровень 80.",
        "attack": 200,
        "defense": 180,
        "speed": 190,
        "hp": 2500,
        "exp_reward": 5000,
        "points_reward": 1,
        "coins_reward": 5000,
        "special_reward": "Техника Кражи Духов",
        "required_level": 80,
        "cooldown_hours": 48
    },
    {
        "name": "Джого (Полная Сила)",
        "description": "Вулканическое проклятие. Требуется уровень 60.",
        "attack": 180,
        "defense": 150,
        "speed": 170,
        "hp": 2000,
        "exp_reward": 3000,
        "points_reward": 1,
        "coins_reward": 3000,
        "special_reward": "Огненная Техника",
        "required_level": 60,
        "cooldown_hours": 24
    }
]

def get_season_levels(season_number: int):
    """Получить уровни сезона"""
    return CAMPAIGN_LEVELS.get(season_number, [])

def get_season_by_number(season_number: int):
    """Получить данные сезона"""
    for season in CAMPAIGN_SEASONS:
        if season["season_number"] == season_number:
            return season
    return None
