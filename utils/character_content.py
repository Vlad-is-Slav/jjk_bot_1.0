from __future__ import annotations

from copy import deepcopy


def _special(
    key: str,
    name: str,
    icon: str,
    ce_cost: int,
    multiplier: float,
    flat: int,
    **extra,
) -> dict:
    payload = {
        "key": key,
        "name": name,
        "icon": icon,
        "ce_cost": ce_cost,
        "multiplier": multiplier,
        "flat": flat,
    }
    payload.update(extra)
    return payload


def _profile(
    name: str,
    *,
    tokens: list[str],
    innate_technique: str,
    domain_name: str,
    domain_dot_pct: float,
    domain_damage_bonus: float,
    specials: list[dict],
    abilities: list[str] | None = None,
    domain_effect: str = "dot",
    domain_slow_pct: float | None = None,
    image_url: str | None = None,
    image_aliases: list[str] | None = None,
    combat_traits: dict | None = None,
) -> dict:
    payload = {
        "name": name,
        "tokens": list(tokens),
        "innate_technique": innate_technique,
        "abilities": list(abilities or [special["name"] for special in specials]),
        "domain_name": domain_name,
        "domain_dot_pct": domain_dot_pct,
        "domain_damage_bonus": domain_damage_bonus,
        "domain_effect": domain_effect,
        "specials": deepcopy(specials),
    }
    if domain_slow_pct is not None:
        payload["domain_slow_pct"] = domain_slow_pct
    if image_url:
        payload["image_url"] = image_url
    if image_aliases:
        payload["image_aliases"] = list(image_aliases)
    if combat_traits:
        payload["combat_traits"] = deepcopy(combat_traits)
    return payload


CHARACTER_DETAILS = [
    _profile(
        "Годжо Сатору",
        tokens=["годжосатору", "годжо", "satorugojo", "gojosatoru", "gojo"],
        innate_technique="Безграничность и Шесть Глаз",
        domain_name="Безграничная Пустота",
        domain_dot_pct=0.15,
        domain_damage_bonus=0.30,
        domain_effect="gojo_crit",
        specials=[
            _special(
                "blue",
                "Синий",
                "🔵",
                900,
                1.25,
                120,
                variants={
                    "amp": {
                        "name": "Усиленный синий",
                        "ce_cost": 1500,
                        "multiplier": 1.5,
                        "flat": 220,
                        "can_dodge": False,
                    }
                },
            ),
            _special(
                "red",
                "Красный",
                "🔴",
                2600,
                1.6,
                260,
                variants={
                    "amp": {
                        "name": "Усиленный красный",
                        "ce_cost": 3600,
                        "multiplier": 1.9,
                        "flat": 360,
                    }
                },
            ),
            _special(
                "purple",
                "Фиолетовый",
                "🟣",
                6200,
                2.7,
                580,
                variants={
                    "amp": {
                        "name": "Усиленный фиолетовый",
                        "ce_cost": 9000,
                        "multiplier": 3.25,
                        "flat": 840,
                        "can_dodge": False,
                        "critical": True,
                        "critical_multiplier": 1.35,
                    }
                },
            ),
        ],
    ),
    _profile(
        "Инумаки Тогэ",
        tokens=["инумаки", "тогэ", "toge", "inumaki"],
        innate_technique="Проклятая речь",
        domain_name="Хор запретов",
        domain_dot_pct=0.10,
        domain_damage_bonus=0.18,
        domain_effect="slow",
        domain_slow_pct=0.22,
        specials=[
            _special("halt", "Не двигайся", "🗣️", 900, 1.15, 120, can_dodge=False),
            _special("burst", "Взрывись", "💥", 1700, 1.65, 230, can_dodge=False),
            _special("sleep", "Усни", "🌫️", 1400, 1.4, 190, can_dodge=False),
        ],
    ),
    _profile(
        "Итадори Юдзи",
        tokens=["итадори", "юдзи", "itadori", "yuji"],
        innate_technique="Сверхчеловеческое тело",
        domain_name="Территория души",
        domain_dot_pct=0.12,
        domain_damage_bonus=0.20,
        domain_effect="soul_dot",
        specials=[
            _special("divergent_fist", "Дивергентный кулак", "👊", 700, 1.35, 150),
            _special(
                "black_flash_burst",
                "Чёрная молния",
                "⚫",
                1600,
                1.9,
                260,
                can_dodge=False,
                critical=True,
                critical_multiplier=1.3,
            ),
            _special("soul_strike", "Удар по душе", "💢", 2600, 2.1, 340, can_dodge=False),
        ],
    ),
    _profile(
        "Рёмен Сукуна",
        tokens=["сукуна", "рёмен", "ryomen", "sukuna"],
        innate_technique="Рассечение и Расщепление",
        domain_name="Храм Злобы",
        domain_dot_pct=0.14,
        domain_damage_bonus=0.28,
        domain_effect="sukuna_dot",
        specials=[
            _special("cleave", "Рассечение", "🗡️", 900, 1.45, 180),
            _special("dismantle", "Расщепление", "⚔️", 1300, 1.7, 260),
            _special("fuga", "Фуга", "🔥", 4500, 2.45, 520),
        ],
    ),
    _profile(
        "Камо Норитоши",
        tokens=["камо", "норитоши", "kamo", "noritoshi"],
        innate_technique="Кровавая манипуляция",
        domain_name="Багровый омут",
        domain_dot_pct=0.09,
        domain_damage_bonus=0.14,
        specials=[
            _special("piercing_blood", "Пронзающая кровь", "🩸", 1000, 1.35, 160, can_dodge=False),
            _special("crimson_net", "Багровая сеть", "🕸️", 1300, 1.45, 190, aoe=True),
            _special("scarlet_whirl", "Алый вихрь", "🌀", 1900, 1.7, 250),
        ],
    ),
    _profile(
        "Маки Дзэнин",
        tokens=["маки", "дзэнин", "maki", "zenin"],
        innate_technique="Небесное ограничение",
        domain_name="Резня клана Дзэнин",
        domain_dot_pct=0.11,
        domain_damage_bonus=0.18,
        specials=[
            _special("spear", "Инвертированное копьё", "🗡️", 900, 1.45, 180, can_dodge=False),
            _special(
                "soul_split",
                "Разделение души",
                "💀",
                1700,
                1.85,
                280,
                can_dodge=False,
                critical=True,
                critical_multiplier=1.2,
            ),
            _special("naginata", "Вихрь нагинаты", "🌀", 1300, 1.55, 220),
        ],
    ),
    _profile(
        "Мива Касуми",
        tokens=["мива", "касуми", "miwa", "kasumi"],
        innate_technique="Новый теневой стиль",
        domain_name="Лазурная простая территория",
        domain_dot_pct=0.08,
        domain_damage_bonus=0.12,
        domain_effect="slow",
        domain_slow_pct=0.12,
        specials=[
            _special("batto", "Летящий батто", "🩵", 500, 1.25, 110),
            _special("shadow_cut", "Теневой разрез", "🗡️", 900, 1.4, 160, can_dodge=False),
        ],
    ),
    _profile(
        "Мута Кокичи",
        tokens=["мута", "кокичи", "мехамару", "muta", "kokichi", "mechamaru"],
        innate_technique="Марионеточная манипуляция",
        domain_name="Полигон ультрамехи",
        domain_dot_pct=0.09,
        domain_damage_bonus=0.15,
        specials=[
            _special("laser", "Лазер Мехамару", "🔫", 900, 1.35, 150),
            _special("cannon", "Абсолютный выстрел", "💥", 1700, 1.75, 250, aoe=True),
            _special("ultra_mode", "Ультрамеха", "🤖", 2500, 2.1, 340),
        ],
    ),
    _profile(
        "Нанами Кенто",
        tokens=["нанами", "кенто", "nanami", "kento"],
        innate_technique="Техника соотношения 7:3",
        domain_name="Серая сверхурочная зона",
        domain_dot_pct=0.11,
        domain_damage_bonus=0.20,
        domain_effect="gojo_crit",
        specials=[
            _special("ratio", "Слабая точка", "📏", 700, 1.4, 170, can_dodge=False),
            _special(
                "overtime",
                "Овертайм",
                "⏰",
                1500,
                1.7,
                240,
                critical=True,
                critical_multiplier=1.2,
            ),
            _special("collapse", "Коллапс", "💥", 2400, 2.05, 320),
        ],
    ),
    _profile(
        "Панда",
        tokens=["панда", "panda"],
        innate_technique="Три ядра",
        domain_name="Арена трёх ядер",
        domain_dot_pct=0.10,
        domain_damage_bonus=0.16,
        specials=[
            _special("panda_punch", "Форма панды", "🐼", 600, 1.3, 130),
            _special("gorilla", "Гориллий рывок", "🦍", 1400, 1.65, 220),
            _special("rhino_guard", "Носороговый блок", "🦏", 1200, 1.35, 150, effect="duck_guard", block_hits=1),
        ],
    ),
    _profile(
        "Фушигуро Мегуми",
        tokens=["фушигуро", "мегуми", "fushiguro", "megumi"],
        innate_technique="Десять теней",
        domain_name="Сад Химер Теней",
        domain_dot_pct=0.11,
        domain_damage_bonus=0.18,
        domain_effect="slow",
        domain_slow_pct=0.15,
        specials=[
            _special("nue", "Нуэ", "🦅", 1000, 1.35, 150),
            _special("serpent", "Великая Змея", "🐍", 1600, 1.6, 220, can_dodge=False),
            _special("max_elephant", "Макс. Слон", "🐘", 2600, 2.0, 320, aoe=True),
        ],
    ),
    _profile(
        "Тоджи Фушигуро",
        tokens=["тоджи", "toji", "фушигуро"],
        innate_technique="Небесное ограничение",
        domain_name="Нулевая территория",
        domain_dot_pct=0.00,
        domain_damage_bonus=0.00,
        specials=[
            _special("spear", "Перевёрнутое небесное копьё", "🔱", 0, 1.55, 220, can_dodge=False),
            _special("chain", "Цепь тысячи миль", "⛓️", 0, 1.35, 160, can_dodge=False),
            _special(
                "cloud",
                "Игривое облако",
                "☁️",
                0,
                1.9,
                320,
                critical=True,
                critical_multiplier=1.2,
            ),
        ],
    ),
    _profile(
        "Хакари Киндзи",
        tokens=["хакари", "киндзи", "hakari", "kinji"],
        innate_technique="Смертельная азартность",
        domain_name="Частная Чистая Любовь",
        domain_dot_pct=0.00,
        domain_damage_bonus=0.00,
        domain_effect="hakari_jackpot",
        specials=[
            _special("rush", "Удар джекпота", "🎰", 900, 1.35, 170),
            _special("press", "Зубчатый пресс", "🦷", 1700, 1.7, 240),
            _special("fever", "Лихорадочный натиск", "🔥", 2600, 2.0, 320),
        ],
    ),
    _profile(
        "Хигурума",
        tokens=["хигурума", "higuruma"],
        innate_technique="Мёртвый приговор",
        domain_name="Судебное Заседание",
        domain_dot_pct=0.14,
        domain_damage_bonus=0.00,
        domain_effect="higuruma_dot",
        specials=[
            _special("gavel", "Судейский молот", "🔨", 500, 1.45, 150),
            _special("confiscation", "Конфискация", "⚖️", 1200, 1.55, 200, can_dodge=False),
            _special("verdict", "Вердикт", "📜", 2200, 1.95, 310),
        ],
    ),
    _profile(
        "Баттлердан",
        tokens=["баттлердан", "battlerdan"],
        innate_technique="Золотая правда",
        domain_name="Дебаты",
        domain_dot_pct=0.00,
        domain_damage_bonus=0.00,
        domain_effect="battlerdan_debate",
        specials=[
            _special("battle_blue", "Синие клинья", "🔵", 700, 1.25, 120),
            _special("battle_red", "Красный ключ", "🔴", 1000, 1.55, 220),
            _special("battle_bombs", "Маленькие бомбочки", "💣", 0, 0.7, 40),
        ],
    ),
    _profile(
        "Годжослав",
        tokens=["годжослав", "godzhoslav"],
        innate_technique="Бесконечные бели",
        domain_name="Бесконечные Бели",
        domain_dot_pct=0.15,
        domain_damage_bonus=0.30,
        domain_effect="gojo_crit",
        specials=[
            _special("gears", "Шестерёнки", "⚙️", 700, 1.2, 120),
            _special("ducks", "Уточки", "🦆", 800, 0.0, 0, effect="duck_guard", block_hits=1),
            _special("white", "Белый", "⚪", 5000, 2.6, 500),
        ],
    ),
    _profile(
        "Оккоцу Юта",
        tokens=["оккоцу", "юта", "okkotsu", "yuta"],
        innate_technique="Копирование и Рика",
        domain_name="Истинная взаимная любовь",
        domain_dot_pct=0.13,
        domain_damage_bonus=0.26,
        domain_effect="gojo_crit",
        specials=[
            _special("rika", "Рика", "👹", 1100, 1.45, 190),
            _special("copy", "Копирование техники", "📚", 2000, 1.75, 280),
            _special("love_beam", "Луч любви", "💘", 3600, 2.35, 460, can_dodge=False, aoe=True),
        ],
    ),
    _profile(
        "Кугисаки Нобара",
        tokens=["кугисаки", "нобара", "kugisaki", "nobara"],
        innate_technique="Соломенная кукла",
        domain_name="Резонанс боли",
        domain_dot_pct=0.12,
        domain_damage_bonus=0.20,
        domain_effect="soul_dot",
        specials=[
            _special("hairpin", "Шпилька", "📍", 700, 1.35, 160, can_dodge=False),
            _special("resonance", "Резонанс", "🪆", 1600, 1.8, 250, can_dodge=False),
            _special("nail_rain", "Гвоздевой дождь", "📌", 2400, 2.05, 320, aoe=True),
        ],
    ),
    _profile(
        "Тодо Аой",
        tokens=["тодо", "аой", "todo", "aoi"],
        innate_technique="Boogie Woogie",
        domain_name="Зал аплодисментов",
        domain_dot_pct=0.11,
        domain_damage_bonus=0.18,
        domain_effect="slow",
        domain_slow_pct=0.18,
        specials=[
            _special("boogie", "Boogie Woogie", "👏", 900, 1.4, 170),
            _special(
                "flash_clap",
                "Чёрная вспышка",
                "⚫",
                1700,
                1.85,
                260,
                critical=True,
                critical_multiplier=1.25,
            ),
            _special("combo", "Сокрушающий хлопок", "💥", 2400, 2.1, 340),
        ],
    ),
    _profile(
        "Мэй Мэй",
        tokens=["мэймэй", "мэй", "meimei", "mei"],
        innate_technique="Манипуляция воронами",
        domain_name="Воронье погребение",
        domain_dot_pct=0.10,
        domain_damage_bonus=0.20,
        domain_effect="gojo_crit",
        specials=[
            _special(
                "bird_strike",
                "Птичий удар",
                "🐦",
                1200,
                1.65,
                210,
                can_dodge=False,
                critical=True,
                critical_multiplier=1.2,
            ),
            _special("crow_swarm", "Воронья тень", "🪶", 1800, 1.55, 230, aoe=True),
            _special("black_bird", "Чёрная птица", "🦅", 2600, 2.0, 320),
        ],
    ),
    _profile(
        "Чосо",
        tokens=["чосо", "choso"],
        innate_technique="Кровавая манипуляция",
        domain_name="Багровый мавзолей",
        domain_dot_pct=0.13,
        domain_damage_bonus=0.24,
        domain_effect="soul_dot",
        specials=[
            _special("piercing_blood", "Пронзающая кровь", "🩸", 1000, 1.55, 210, can_dodge=False),
            _special("supernova", "Сверхновая", "☄️", 2200, 1.95, 320, aoe=True),
            _special("crimson_rain", "Кровавый дождь", "🌧️", 3200, 2.2, 420),
        ],
    ),
    _profile(
        "Цукумо Юки",
        tokens=["цукумо", "юки", "tsukumo", "yuki"],
        innate_technique="Звёздная ярость",
        domain_name="Звёздный горизонт",
        domain_dot_pct=0.14,
        domain_damage_bonus=0.26,
        domain_effect="gojo_crit",
        specials=[
            _special("garuda", "Гаруда", "🦅", 1200, 1.6, 220),
            _special("mass_punch", "Бомба массы", "🌌", 2200, 2.0, 340, can_dodge=False),
            _special(
                "singularity",
                "Сингулярный удар",
                "⭐",
                4200,
                2.55,
                520,
                can_dodge=False,
                critical=True,
                critical_multiplier=1.25,
            ),
        ],
    ),
    _profile(
        "Гэто Сугуру",
        tokens=["гэто", "сугуру", "geto", "suguru"],
        innate_technique="Манипуляция проклятыми духами",
        domain_name="Ночной парад ста духов",
        domain_dot_pct=0.14,
        domain_damage_bonus=0.25,
        specials=[
            _special("swarm", "Проклятый рой", "👻", 1300, 1.55, 220, aoe=True),
            _special("tamamo", "Тама-но-Ори", "🦊", 2200, 1.85, 300),
            _special("uzumaki", "Максимум: Узумаки", "🌀", 3600, 2.35, 460, can_dodge=False, aoe=True),
        ],
    ),
    _profile(
        "Наоя Дзэнин",
        tokens=["наоя", "дзэнин", "naoya", "zenin"],
        innate_technique="Проекционная магия",
        domain_name="Лунный дворец клеток времени",
        domain_dot_pct=0.11,
        domain_damage_bonus=0.20,
        domain_effect="slow",
        domain_slow_pct=0.22,
        specials=[
            _special("frame", "24 кадра", "🎞️", 800, 1.4, 170, can_dodge=False),
            _special("rush", "Рывок Mach", "💨", 1700, 1.8, 260),
            _special(
                "projection_crash",
                "Проекционный удар",
                "🪞",
                2500,
                2.1,
                340,
                critical=True,
                critical_multiplier=1.2,
            ),
        ],
    ),
    _profile(
        "Ацуя Кусакабе",
        tokens=["кусакабе", "ацуя", "kusakabe", "atsuya"],
        innate_technique="Простая территория школы новой тени",
        domain_name="Новая тень: простая территория",
        domain_dot_pct=0.00,
        domain_damage_bonus=0.08,
        specials=[
            _special("batto_draw", "Батто", "🗡️", 600, 1.35, 150, can_dodge=False),
            _special("evening_moon", "Вечерняя луна", "🌙", 1400, 1.65, 240),
            _special("shadow_intercept", "Перехват новой тени", "🛡️", 1800, 1.85, 290, can_dodge=False),
        ],
        combat_traits={
            "force_simple_domain": True,
            "disable_domain": True,
            "simple_domain_duration_bonus": 1,
        },
    ),
    _profile(
        "Такума Ино",
        tokens=["такумаино", "ино", "takuma", "ino"],
        innate_technique="Благовестные звери",
        domain_name="Печать четырёх благовестных зверей",
        domain_dot_pct=0.10,
        domain_damage_bonus=0.16,
        specials=[
            _special("kaichi", "Каити", "🐉", 700, 1.3, 150),
            _special("reiki", "Рэйки", "🐂", 1300, 1.55, 220, can_dodge=False),
            _special("ryu", "Рю", "🐲", 2200, 1.95, 320),
        ],
        combat_traits={
            "disable_domain": True,
        },
    ),
    _profile(
        "Наобито Дзэнин",
        tokens=["наобито", "naobito"],
        innate_technique="Проекционная магия",
        domain_name="Дворец двадцати четырёх кадров",
        domain_dot_pct=0.11,
        domain_damage_bonus=0.23,
        domain_effect="slow",
        domain_slow_pct=0.24,
        specials=[
            _special("frame_lock", "Стоп-кадр", "🎞️", 800, 1.4, 180, can_dodge=False),
            _special("speed_drift", "Пьяный рывок", "🍶", 1700, 1.8, 270),
            _special(
                "projection_blitz",
                "Проекционный блиц",
                "💨",
                2700,
                2.15,
                360,
                critical=True,
                critical_multiplier=1.2,
            ),
        ],
        combat_traits={
            "disable_domain": True,
        },
    ),
    _profile(
        "Дагон",
        tokens=["дагон", "dagon"],
        innate_technique="Океаническая катастрофа",
        domain_name="Горизонт плена скандхи",
        domain_dot_pct=0.17,
        domain_damage_bonus=0.26,
        specials=[
            _special("tidal", "Приливный обвал", "🌊", 1700, 1.65, 250),
            _special("swarm", "Стая глубин", "🦑", 2600, 2.05, 360, aoe=True),
        ],
    ),
    _profile(
        "Ханами",
        tokens=["ханами", "hanami"],
        innate_technique="Проклятая флора",
        domain_name="Цветущий гнев",
        domain_dot_pct=0.14,
        domain_damage_bonus=0.22,
        domain_effect="slow",
        domain_slow_pct=0.18,
        specials=[
            _special("roots", "Корни-ловушки", "🌿", 1100, 1.45, 180, can_dodge=False),
            _special("blossom", "Цветочный обвал", "🌸", 1800, 1.75, 260),
        ],
    ),
    _profile(
        "Дзёго",
        tokens=["дзёго", "джого", "jogo"],
        innate_technique="Огненная катастрофа",
        domain_name="Пылающий кратер",
        domain_dot_pct=0.16,
        domain_damage_bonus=0.28,
        domain_effect="gojo_crit",
        specials=[
            _special("ember", "Вулканический залп", "🔥", 1400, 1.55, 220),
            _special("eruption", "Извержение", "🌋", 2400, 2.0, 340, aoe=True),
        ],
    ),
    _profile(
        "Ураумэ",
        tokens=["ураумэ", "uraume"],
        innate_technique="Ледяная техника",
        domain_name="Ледяная камера",
        domain_dot_pct=0.12,
        domain_damage_bonus=0.18,
        domain_effect="slow",
        domain_slow_pct=0.18,
        specials=[
            _special("frost_lance", "Морозное копьё", "❄️", 1100, 1.55, 220, can_dodge=False),
            _special("icefall", "Ледопад", "🧊", 2200, 1.85, 320, aoe=True),
        ],
    ),
    _profile(
        "Кашимо Хадзимэ",
        tokens=["кашимо", "хадзимэ", "kashimo", "hajime"],
        innate_technique="Проклятое электричество",
        domain_name="Поле грома",
        domain_dot_pct=0.13,
        domain_damage_bonus=0.24,
        domain_effect="soul_dot",
        specials=[
            _special("lightning_bolt", "Громовой разряд", "⚡", 1000, 1.6, 220, can_dodge=False),
            _special(
                "amber_beast",
                "Мифический зверь: Янтарь",
                "🟨",
                3600,
                2.35,
                480,
                can_dodge=False,
                critical=True,
                critical_multiplier=1.25,
            ),
        ],
    ),
    _profile(
        "Махито",
        tokens=["махито", "mahito"],
        innate_technique="Преобразование души",
        domain_name="Мгновенное воплощение совершенства",
        domain_dot_pct=0.18,
        domain_damage_bonus=0.31,
        domain_effect="soul_dot",
        specials=[
            _special("idle_touch", "Преобразование души", "🫳", 1900, 1.8, 290, can_dodge=False),
            _special("distortion", "Искажённый обвал", "🧬", 3100, 2.2, 420),
        ],
    ),
    _profile(
        "Кендзяку",
        tokens=["кендзяку", "kenjaku"],
        innate_technique="Манипуляция проклятиями",
        domain_name="Чрево поглощённых проклятий",
        domain_dot_pct=0.19,
        domain_damage_bonus=0.33,
        specials=[
            _special("gravity", "Гравитационный обвал", "🪐", 2200, 1.95, 320),
            _special("uzumaki", "Узумаки", "🌀", 3600, 2.45, 520, aoe=True),
        ],
    ),
]


DEFAULT_CHARACTER_PROFILE = {
    "domain_name": "Расширение территории",
    "domain_dot_pct": 0.10,
    "domain_damage_bonus": 0.20,
    "domain_effect": "dot",
    "combat_traits": {},
    "specials": [
        _special("burst", "Выброс CE", "💥", 900, 1.35, 150),
    ],
}

CHARACTER_DETAILS_BY_NAME = {detail["name"]: detail for detail in CHARACTER_DETAILS}


def _normalize_name(value: str | None) -> str:
    return "".join(ch.lower() for ch in (value or "") if ch.isalnum())


def _find_character_detail(card_name: str | None) -> dict | None:
    if not card_name:
        return None

    detail = CHARACTER_DETAILS_BY_NAME.get(card_name)
    if detail:
        return detail

    normalized = _normalize_name(card_name)
    if not normalized:
        return None

    for candidate in CHARACTER_DETAILS:
        if any(token in normalized for token in candidate["tokens"]):
            return candidate
    return None


def get_character_card_metadata(card_name: str | None) -> dict:
    detail = _find_character_detail(card_name)
    if not detail:
        return {}

    metadata = {}
    for key in ("innate_technique", "abilities", "domain_name", "image_url", "image_aliases"):
        value = detail.get(key)
        if value not in (None, "", [], {}):
            metadata[key] = deepcopy(value)
    return metadata


def get_character_profile(card_name: str | None) -> dict:
    detail = _find_character_detail(card_name)
    if not detail:
        return deepcopy(DEFAULT_CHARACTER_PROFILE)

    profile = {
        "domain_name": detail["domain_name"],
        "domain_dot_pct": detail["domain_dot_pct"],
        "domain_damage_bonus": detail["domain_damage_bonus"],
        "domain_effect": detail.get("domain_effect", "dot"),
        "combat_traits": deepcopy(detail.get("combat_traits", {})),
        "specials": deepcopy(detail.get("specials", [])),
    }
    if "domain_slow_pct" in detail:
        profile["domain_slow_pct"] = detail["domain_slow_pct"]
    return profile
