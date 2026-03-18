"""
Данные проклятий для PvE боев
"""

CURSES = [
    # Слабые проклятия (1-3 уровень)
    {
        "name": "Слабое проклятие",
        "description": "Обычное проклятие низкого класса.",
        "grade": 1,
        "curse_type": "weak",
        "attack": 10,
        "defense": 6,
        "speed": 12,
        "hp": 80,
        "exp_reward": 15,
        "points_reward": 1,
        "card_drop_chance": 0.5
    },
    {
        "name": "Летучая мышь",
        "description": "Проклятие в форме летучей мыши.",
        "grade": 1,
        "curse_type": "weak",
        "attack": 8,
        "defense": 5,
        "speed": 18,
        "hp": 70,
        "exp_reward": 12,
        "points_reward": 1,
        "card_drop_chance": 0.3
    },
    {
        "name": "Змеиное проклятие",
        "description": "Проклятие в форме змеи.",
        "grade": 2,
        "curse_type": "weak",
        "attack": 12,
        "defense": 8,
        "speed": 15,
        "hp": 95,
        "exp_reward": 18,
        "points_reward": 1,
        "card_drop_chance": 0.8
    },
    {
        "name": "Паучье проклятие",
        "description": "Многоногое проклятие.",
        "grade": 2,
        "curse_type": "weak",
        "attack": 11,
        "defense": 9,
        "speed": 20,
        "hp": 86,
        "exp_reward": 16,
        "points_reward": 1,
        "card_drop_chance": 0.6
    },
    {
        "name": "Проклятие-волк",
        "description": "Агрессивное проклятие в форме волка.",
        "grade": 3,
        "curse_type": "weak",
        "attack": 15,
        "defense": 10,
        "speed": 25,
        "hp": 115,
        "exp_reward": 22,
        "points_reward": 1,
        "card_drop_chance": 1.0
    },
    
    # Обычные проклятия (4-5 уровень)
    {
        "name": "Проклятие-горилла",
        "description": "Сильное проклятие с огромной силой.",
        "grade": 4,
        "curse_type": "normal",
        "attack": 20,
        "defense": 16,
        "speed": 18,
        "hp": 170,
        "exp_reward": 35,
        "points_reward": 1,
        "card_drop_chance": 2.0
    },
    {
        "name": "Проклятие-птица",
        "description": "Летающее проклятие среднего класса.",
        "grade": 4,
        "curse_type": "normal",
        "attack": 18,
        "defense": 13,
        "speed": 35,
        "hp": 140,
        "exp_reward": 32,
        "points_reward": 1,
        "card_drop_chance": 1.5
    },
    {
        "name": "Мутация",
        "description": "Искаженное проклятие.",
        "grade": 5,
        "curse_type": "normal",
        "attack": 23,
        "defense": 18,
        "speed": 25,
        "hp": 190,
        "exp_reward": 45,
        "points_reward": 1,
        "card_drop_chance": 3.0
    },
    {
        "name": "Проклятие-скелет",
        "description": "Оживленные останки.",
        "grade": 5,
        "curse_type": "normal",
        "attack": 21,
        "defense": 20,
        "speed": 22,
        "hp": 165,
        "exp_reward": 40,
        "points_reward": 1,
        "card_drop_chance": 2.5
    },
    
    # Сильные проклятия (6-7 уровень)
    {
        "name": "Проклятие-медведь",
        "description": "Огромное и мощное проклятие.",
        "grade": 6,
        "curse_type": "strong",
        "attack": 29,
        "defense": 26,
        "speed": 28,
        "hp": 250,
        "exp_reward": 65,
        "points_reward": 1,
        "card_drop_chance": 5.0
    },
    {
        "name": "Проклятие-тигр",
        "description": "Быстрое и смертоносное проклятие.",
        "grade": 6,
        "curse_type": "strong",
        "attack": 33,
        "defense": 23,
        "speed": 45,
        "hp": 220,
        "exp_reward": 70,
        "points_reward": 1,
        "card_drop_chance": 5.5
    },
    {
        "name": "Проклятие-виверна",
        "description": "Летающее драконоподобное проклятие.",
        "grade": 7,
        "curse_type": "strong",
        "attack": 36,
        "defense": 29,
        "speed": 50,
        "hp": 295,
        "exp_reward": 85,
        "points_reward": 1,
        "card_drop_chance": 7.0
    },
    {
        "name": "Проклятие-гидра",
        "description": "Многоголовое проклятие.",
        "grade": 7,
        "curse_type": "strong",
        "attack": 34,
        "defense": 32,
        "speed": 35,
        "hp": 325,
        "exp_reward": 90,
        "points_reward": 1,
        "card_drop_chance": 8.0
    },
    
    # Особые проклятия (8 уровень)
    {
        "name": "Проклятие-полковник",
        "description": "Разумное проклятие высокого класса.",
        "grade": 8,
        "curse_type": "special",
        "attack": 46,
        "defense": 39,
        "speed": 55,
        "hp": 390,
        "exp_reward": 120,
        "points_reward": 1,
        "card_drop_chance": 12.0
    },
    {
        "name": "Проклятие-генерал",
        "description": "Командир проклятий.",
        "grade": 8,
        "curse_type": "special",
        "attack": 49,
        "defense": 42,
        "speed": 60,
        "hp": 430,
        "exp_reward": 130,
        "points_reward": 1,
        "card_drop_chance": 15.0
    },
    
    # Катастрофические проклятия (9-10 уровень)
    {
        "name": "Ханами",
        "description": "Специальный класс. Проклятие леса.",
        "grade": 9,
        "curse_type": "disaster",
        "attack": 58,
        "defense": 52,
        "speed": 70,
        "hp": 540,
        "exp_reward": 180,
        "points_reward": 1,
        "card_drop_chance": 20.0
    },
    {
        "name": "Джого",
        "description": "Специальный класс. Проклятие вулкана.",
        "grade": 9,
        "curse_type": "disaster",
        "attack": 62,
        "defense": 49,
        "speed": 85,
        "hp": 510,
        "exp_reward": 190,
        "points_reward": 1,
        "card_drop_chance": 22.0
    },
    {
        "name": "Махито",
        "description": "Специальный класс. Манипуляция душой.",
        "grade": 10,
        "curse_type": "disaster",
        "attack": 65,
        "defense": 55,
        "speed": 90,
        "hp": 620,
        "exp_reward": 250,
        "points_reward": 1,
        "card_drop_chance": 30.0
    },
    {
        "name": "Рёмен Сукуна",
        "description": "Король проклятий в полной силе.",
        "grade": 10,
        "curse_type": "disaster",
        "attack": 78,
        "defense": 65,
        "speed": 110,
        "hp": 880,
        "exp_reward": 500,
        "points_reward": 1,
        "card_drop_chance": 50.0
    },
]

def get_curses_by_grade(grade: int):
    """Получить проклятия определенного уровня"""
    return [c for c in CURSES if c["grade"] == grade]

def get_curses_by_type(curse_type: str):
    """Получить проклятия определенного типа"""
    return [c for c in CURSES if c["curse_type"] == curse_type]

def get_curses_for_level(player_level: int):
    """Получить подходящие проклятия для уровня игрока"""
    # Игрок 1-5 уровня - слабые проклятия (1-3)
    # Игрок 6-15 уровня - обычные (3-5)
    # Игрок 16-30 уровня - сильные (5-7)
    # Игрок 31-50 уровня - особые (7-8)
    # Игрок 50+ уровня - катастрофические (9-10)
    
    if player_level <= 5:
        return [c for c in CURSES if c["grade"] <= 3]
    elif player_level <= 15:
        return [c for c in CURSES if 3 <= c["grade"] <= 5]
    elif player_level <= 30:
        return [c for c in CURSES if 5 <= c["grade"] <= 7]
    elif player_level <= 50:
        return [c for c in CURSES if 7 <= c["grade"] <= 8]
    else:
        return [c for c in CURSES if c["grade"] >= 8]
