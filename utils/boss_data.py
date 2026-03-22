"""Boss encounters for the battle menu."""

BOSSES = [
    {
        "key": "hanami",
        "name": "Ханами",
        "description": "Катастрофическое проклятие леса. Очень живучий босс с доменом и сокрушительными ударами.",
        "min_level": 10,
        "exp_reward": 280,
        "one_time": True,
        "card": {
            "attack": 96,
            "defense": 82,
            "speed": 72,
            "hp": 980,
            "max_ce": 210,
            "ce_regen": 18,
            "domain_level": 2,
        },
        "profile": {
            "domain_name": "Цветущий гнев",
            "domain_dot_pct": 0.14,
            "domain_damage_bonus": 0.22,
            "domain_effect": "dot",
            "specials": [
                {"key": "roots", "name": "Корни-ловушки", "icon": "🌿", "ce_cost": 1100, "multiplier": 1.45, "flat": 180},
                {"key": "blossom", "name": "Цветочный обвал", "icon": "🌸", "ce_cost": 1800, "multiplier": 1.75, "flat": 260},
            ],
        },
        "rewards": {
            "coins": 3500,
            "title": {
                "name": "Покоритель Ханами",
                "description": "Выдержал натиск катастрофического проклятия леса.",
                "icon": "🌿",
            },
            "random_card": True,
        },
    },
    {
        "key": "jogo",
        "name": "Джого",
        "description": "Огненный катастрофический дух. Быстрый босс с очень сильными спецатаками.",
        "min_level": 18,
        "exp_reward": 420,
        "one_time": True,
        "card": {
            "attack": 112,
            "defense": 78,
            "speed": 94,
            "hp": 1080,
            "max_ce": 260,
            "ce_regen": 22,
            "domain_level": 3,
        },
        "profile": {
            "domain_name": "Пылающий кратер",
            "domain_dot_pct": 0.16,
            "domain_damage_bonus": 0.28,
            "domain_effect": "gojo_crit",
            "specials": [
                {"key": "ember", "name": "Вулканический залп", "icon": "🔥", "ce_cost": 1400, "multiplier": 1.55, "flat": 220},
                {"key": "eruption", "name": "Извержение", "icon": "🌋", "ce_cost": 2400, "multiplier": 2.0, "flat": 340},
            ],
        },
        "rewards": {
            "coins": 6500,
            "title": {
                "name": "Укротитель вулкана",
                "description": "Победил Джого и пережил пламя катастрофы.",
                "icon": "🌋",
            },
            "random_card": True,
        },
    },
    {
        "key": "dagon",
        "name": "Дагон",
        "description": "Владыка морских глубин. Засыпает арену шикигами и давит врага доменом-океаном.",
        "min_level": 26,
        "exp_reward": 620,
        "one_time": True,
        "card": {
            "attack": 122,
            "defense": 96,
            "speed": 86,
            "hp": 1320,
            "max_ce": 315,
            "ce_regen": 26,
            "domain_level": 3,
        },
        "profile": {
            "domain_name": "Горизонт плена скандхи",
            "domain_dot_pct": 0.17,
            "domain_damage_bonus": 0.26,
            "domain_effect": "dot",
            "specials": [
                {"key": "tidal", "name": "Приливный обвал", "icon": "🌊", "ce_cost": 1700, "multiplier": 1.65, "flat": 250},
                {"key": "swarm", "name": "Стая глубин", "icon": "🦑", "ce_cost": 2600, "multiplier": 2.05, "flat": 360},
            ],
        },
        "rewards": {
            "coins": 9000,
            "title": {
                "name": "Покоритель глубин",
                "description": "Сломил Дагона и пережил его океанический домен.",
                "icon": "🌊",
            },
            "random_card": True,
        },
    },
    {
        "key": "mahito",
        "name": "Махито",
        "description": "Искажённая душа человечества. Опасен и в ближнем бою, и через атаки по душе.",
        "min_level": 34,
        "exp_reward": 900,
        "one_time": True,
        "card": {
            "attack": 138,
            "defense": 94,
            "speed": 102,
            "hp": 1460,
            "max_ce": 360,
            "ce_regen": 30,
            "domain_level": 4,
            "rct_level": 1,
        },
        "profile": {
            "domain_name": "Мгновенное воплощение совершенства",
            "domain_dot_pct": 0.18,
            "domain_damage_bonus": 0.31,
            "domain_effect": "soul_dot",
            "specials": [
                {"key": "idle_touch", "name": "Преобразование души", "icon": "🫳", "ce_cost": 1900, "multiplier": 1.8, "flat": 290},
                {"key": "distortion", "name": "Искажённый обвал", "icon": "🧬", "ce_cost": 3100, "multiplier": 2.2, "flat": 420},
            ],
        },
        "rewards": {
            "coins": 13500,
            "title": {
                "name": "Ломатель душ",
                "description": "Сумел одолеть Махито и не дать исказить свою душу.",
                "icon": "🧬",
            },
            "random_card": True,
        },
    },
    {
        "key": "kenjaku",
        "name": "Кендзяку",
        "description": "Древний манипулятор, управляющий проклятиями и чужими техниками. Один из самых опасных стратегов мира.",
        "min_level": 46,
        "exp_reward": 1350,
        "one_time": True,
        "card": {
            "attack": 156,
            "defense": 108,
            "speed": 110,
            "hp": 1720,
            "max_ce": 430,
            "ce_regen": 34,
            "domain_level": 5,
            "rct_level": 2,
        },
        "profile": {
            "domain_name": "Чрево поглощённых проклятий",
            "domain_dot_pct": 0.19,
            "domain_damage_bonus": 0.33,
            "domain_effect": "dot",
            "specials": [
                {"key": "gravity", "name": "Гравитационный обвал", "icon": "🪐", "ce_cost": 2200, "multiplier": 1.95, "flat": 320},
                {"key": "uzumaki", "name": "Узумаки", "icon": "🌀", "ce_cost": 3600, "multiplier": 2.45, "flat": 520},
            ],
        },
        "rewards": {
            "coins": 21000,
            "title": {
                "name": "Сломивший Кендзяку",
                "description": "Поставил точку в интриге тысячелетнего кукловода.",
                "icon": "🌀",
            },
            "random_card": True,
        },
    },
    {
        "key": "sukuna_final",
        "name": "Сукуна",
        "description": "Финальный босс. Король проклятий, совмещающий чудовищную мощь, скорость и беспощадный домен.",
        "min_level": 60,
        "exp_reward": 2200,
        "one_time": True,
        "card": {
            "attack": 184,
            "defense": 124,
            "speed": 126,
            "hp": 2150,
            "max_ce": 540,
            "ce_regen": 42,
            "domain_level": 6,
            "rct_level": 3,
        },
        "profile": {
            "domain_name": "Храм Злобы",
            "domain_dot_pct": 0.22,
            "domain_damage_bonus": 0.38,
            "domain_effect": "sukuna_dot",
            "specials": [
                {"key": "cleave", "name": "Рассечение", "icon": "🗡", "ce_cost": 1600, "multiplier": 1.8, "flat": 280},
                {"key": "dismantle", "name": "Расщепление", "icon": "⚔️", "ce_cost": 2400, "multiplier": 2.1, "flat": 380},
                {"key": "fuga", "name": "Фуга", "icon": "🔥", "ce_cost": 4200, "multiplier": 2.9, "flat": 760},
            ],
        },
        "rewards": {
            "coins": 50000,
            "title": {
                "name": "Победитель Сукуны",
                "description": "Выстоял против Короля проклятий и победил финального босса.",
                "icon": "👑",
            },
            "random_card": True,
        },
    },
]


def get_boss_by_key(key: str) -> dict | None:
    for boss in BOSSES:
        if boss.get("key") == key:
            return boss
    return None
