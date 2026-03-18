"""
Данные карт персонажей и поддержки
Основано на "Магическая битва" (Jujutsu Kaisen)
"""

# Список доступных карт персонажей
CHARACTER_CARDS = [
    {
        "name": 'Годжо Сатору',
        "description": 'Сильнейший маг. Владелец Безграничной и Шести Глаз.',
        "rarity": 'legendary',
        "base_attack": 75,
        "base_defense": 60,
        "base_speed": 95,
        "base_hp": 320,
        "growth_multiplier": 1.15
    },
    {
        "name": 'Инумаки Тогэ',
        "description": 'Наследник Каминого. Речевая магия.',
        "rarity": 'rare',
        "base_attack": 42,
        "base_defense": 38,
        "base_speed": 60,
        "base_hp": 205,
        "growth_multiplier": 1.08
    },
    {
        "name": 'Итадори Юдзи',
        "description": 'Сосуд Сукуны. Обладает невероятной физической силой.',
        "rarity": 'epic',
        "base_attack": 58,
        "base_defense": 50,
        "base_speed": 70,
        "base_hp": 285,
        "growth_multiplier": 1.12
    },
    {
        "name": 'Рёмен Сукуна',
        "description": 'Король проклятий. Хозяин «Храма Злобы» и техник рассечения.',
        "rarity": 'legendary',
        "base_attack": 75,
        "base_defense": 60,
        "base_speed": 90,
        "base_hp": 330,
        "growth_multiplier": 1.15
    },
    {
        "name": 'Камо Норitoshi',
        "description": 'Наследник Кровавой магии.',
        "rarity": 'common',
        "base_attack": 32,
        "base_defense": 28,
        "base_speed": 40,
        "base_hp": 175,
        "growth_multiplier": 1.05
    },
    {
        "name": 'Маки Дзэнин',
        "description": 'Мастер оружия. Нулевая целостность.',
        "rarity": 'epic',
        "base_attack": 56,
        "base_defense": 46,
        "base_speed": 78,
        "base_hp": 245,
        "growth_multiplier": 1.1
    },
    {
        "name": 'Миwa Касуми',
        "description": 'Маг-новичок с мечом.',
        "rarity": 'common',
        "base_attack": 30,
        "base_defense": 26,
        "base_speed": 45,
        "base_hp": 165,
        "growth_multiplier": 1.05
    },
    {
        "name": 'Мута Кокичи',
        "description": 'Мехамару в кукле.',
        "rarity": 'common',
        "base_attack": 27,
        "base_defense": 30,
        "base_speed": 50,
        "base_hp": 160,
        "growth_multiplier": 1.04
    },
    {
        "name": 'Нанами Кенто',
        "description": 'Бывший офисный работник. Мастер пропорции.',
        "rarity": 'rare',
        "base_attack": 47,
        "base_defense": 44,
        "base_speed": 55,
        "base_hp": 215,
        "growth_multiplier": 1.09
    },
    {
        "name": 'Панда',
        "description": 'Абнормальный труп. Три ядра.',
        "rarity": 'rare',
        "base_attack": 45,
        "base_defense": 50,
        "base_speed": 50,
        "base_hp": 250,
        "growth_multiplier": 1.08
    },
    {
        "name": 'Фушигуро Мегуми',
        "description": 'Владелец Десяти Теней. Такумадау.',
        "rarity": 'epic',
        "base_attack": 54,
        "base_defense": 46,
        "base_speed": 75,
        "base_hp": 255,
        "growth_multiplier": 1.11
    },
    {
        "name": 'Тоджи Фушигуро',
        "description": 'Проклятие небес. Нулевая проклятая энергия, невероятная сила и скорость.',
        "rarity": 'legendary',
        "base_attack": 70,
        "base_defense": 54,
        "base_speed": 98,
        "base_hp": 305,
        "base_ce": 0,
        "ce_regen": 0,
        "growth_multiplier": 1.14
    },
    {
        "name": 'Хакари Киндзи',
        "description": 'Игрок удачи. Его территория запускает «джекпот».',
        "rarity": 'epic',
        "base_attack": 60,
        "base_defense": 48,
        "base_speed": 72,
        "base_hp": 280,
        "growth_multiplier": 1.12
    },
    {
        "name": 'Хигурума',
        "description": 'Судья',
        "rarity": 'legendary',
        "base_attack": 58,
        "base_defense": 48,
        "base_speed": 70,
        "base_hp": 295,
        "growth_multiplier": 1.15
    },
            {
        "name": "Баттлердан",
        "description": "Мастер дебатов, вооружён клиньями и ключом.",
        "rarity": "legendary",
        "base_attack": 68,
        "base_defense": 56,
        "base_speed": 84,
        "base_hp": 310,
        "growth_multiplier": 1.14
    },
            {
        "name": "Годжослав",
        "description": "Ученик класса Годжо, изобретатель бесконечных белых.",
        "rarity": "legendary",
        "base_attack": 70,
        "base_defense": 60,
        "base_speed": 88,
        "base_hp": 315,
        "growth_multiplier": 1.14
    },
  ]

# Карты шикигами (поддержка)
SHIKIGAMI_CARDS = [
    {
        "name": "Великая Змея",
        "description": "Шикигами Фушигуро. Мощная змея.",
        "rarity": "epic",
        "base_attack": 36,
        "base_defense": 40,
        "base_speed": 45,
        "base_hp": 150,
        "growth_multiplier": 1.09,
    },
    {
        "name": "Колесница Серебряного Льва",
        "description": "Стремительный шикигами с сильной защитой.",
        "rarity": "epic",
        "base_attack": 33,
        "base_defense": 44,
        "base_speed": 70,
        "base_hp": 145,
        "growth_multiplier": 1.09,
    },
    {
        "name": "Кукла Мехамару",
        "description": "Мехамару в кукле. Надёжная поддержка.",
        "rarity": "common",
        "base_attack": 22,
        "base_defense": 18,
        "base_speed": 40,
        "base_hp": 95,
        "growth_multiplier": 1.05,
    },
    {
        "name": "Кукла Панды",
        "description": "Кукольное тело с хорошим балансом характеристик.",
        "rarity": "rare",
        "base_attack": 33,
        "base_defense": 36,
        "base_speed": 40,
        "base_hp": 125,
        "growth_multiplier": 1.07,
    },
    {
        "name": "Махорага",
        "description": "Божественный шикигами. Адаптируется к атакам.",
        "rarity": "legendary",
        "base_attack": 50,
        "base_defense": 44,
        "base_speed": 50,
        "base_hp": 185,
        "growth_multiplier": 1.12,
    },
    {
        "name": "Нуэ",
        "description": "Летающий шикигами с высокой скоростью.",
        "rarity": "epic",
        "base_attack": 39,
        "base_defense": 28,
        "base_speed": 65,
        "base_hp": 130,
        "growth_multiplier": 1.1,
    },
    {
        "name": "Пес",
        "description": "Быстрый шикигами ближнего боя.",
        "rarity": "rare",
        "base_attack": 28,
        "base_defense": 24,
        "base_speed": 55,
        "base_hp": 115,
        "growth_multiplier": 1.07,
    },
]

# Оружие (проклятые предметы, слот оружия)
WEAPON_CARDS = [
    {
        "name": "Игривое облако",
        "description": "Проклятое оружие. Увеличивает урон обычных атак.",
        "rarity": "epic",
        "base_attack": 0,
        "base_defense": 0,
        "base_speed": 0,
        "base_hp": 0,
        "base_ce": 0,
        "ce_regen": 0,
        "growth_multiplier": 1.0,
    },
    {
        "name": "Клинок ясности души",
        "description": "Проклятый клинок. Игнорирует защиту цели.",
        "rarity": "legendary",
        "base_attack": 0,
        "base_defense": 0,
        "base_speed": 0,
        "base_hp": 0,
        "base_ce": 0,
        "ce_regen": 0,
        "growth_multiplier": 1.0,
    },
    {
        "name": "Перевернутое небесное копье",
        "description": "Пробивает бесконечность, отключая её защиту.",
        "rarity": "legendary",
        "base_attack": 0,
        "base_defense": 0,
        "base_speed": 0,
        "base_hp": 0,
        "base_ce": 0,
        "ce_regen": 0,
        "growth_multiplier": 1.0,
    },
]

# Пакты (пакт-слот)
PACT_CARDS = [
    {
        "name": "Пакт силы",
        "description": "Следующая атака +50%, CE реген -40%.",
        "rarity": "rare",
        "base_attack": 0,
        "base_defense": 0,
        "base_speed": 0,
        "base_hp": 0,
        "base_ce": 0,
        "ce_regen": 0,
        "growth_multiplier": 1.0,
    },
]


ALL_CARDS = CHARACTER_CARDS + SHIKIGAMI_CARDS + WEAPON_CARDS + PACT_CARDS

# Шансы редкости по умолчанию
RARITY_CHANCES = {'common': 50, 'rare': 30, 'epic': 15, 'legendary': 4.5, 'mythical': 0.5}


def get_cards_by_rarity(rarity: str):
    """Получить все карты заданной редкости"""
    return [card for card in ALL_CARDS if card["rarity"] == rarity]


def get_character_cards():
    """Получить список карт персонажей"""
    return CHARACTER_CARDS


def get_support_cards():
    """Получить список карт поддержки"""
    return SHIKIGAMI_CARDS + WEAPON_CARDS
