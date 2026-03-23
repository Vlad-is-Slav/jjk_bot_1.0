def _normalize_name(value: str) -> str:
    return "".join(ch.lower() for ch in (value or "") if ch.isalnum())


CARD_QUOTES = {
    "годжосатору": [
        "В небе и на земле лишь я один достойный.",
        "Не, я выиграю.",
        "Сильнейший здесь я.",
    ],
    "gojosatoru": [
        "В небе и на земле лишь я один достойный.",
        "Не, я выиграю.",
        "Сильнейший здесь я.",
    ],
    "рёменсукуна": [
        "Покажи, на что ты способен.",
        "Слабых не щадят.",
        "Моя воля здесь закон.",
    ],
    "рёменсукунаryomen": [
        "Покажи, на что ты способен.",
        "Слабых не щадят.",
        "Моя воля здесь закон.",
    ],
    "рёменсукунаryomensukuna": [
        "Покажи, на что ты способен.",
        "Слабых не щадят.",
        "Моя воля здесь закон.",
    ],
    "саторугоджо": [
        "В небе и на земле лишь я один достойный.",
        "Не, я выиграю.",
        "Сильнейший здесь я.",
    ],
    "итадориюдзи": [
        "Я спасу как можно больше людей.",
        "Не сдамся, пока стою на ногах.",
    ],
    "фушигуромегуми": [
        "Выбирай, кого хочешь спасти.",
        "Решение должно быть твёрдым.",
    ],
    "кугисакинобара": [
        "Я остаюсь собой при любых обстоятельствах.",
        "Гордость важнее страха.",
    ],
    "ацуякусакабе": [
        "Простая территория тоже требует мастерства.",
        "Сначала выживи, потом спорь о стиле.",
    ],
    "такумаино": [
        "Раз уж мне доверили дело, я не отступлю.",
        "Благовестные звери, ведите меня.",
    ],
    "наобитодзэнин": [
        "Запоздал на кадр - уже проиграл.",
        "Скорость решает исход ещё до удара.",
    ],
}

FALLBACK_QUOTES = [
    "Сила растёт вместе с опытом.",
    "Каждый бой делает тебя лучше.",
    "Главное - думать на шаг вперёд.",
]


def get_quotes_for_card(card_name: str) -> list[str]:
    normalized = _normalize_name(card_name)
    if normalized in CARD_QUOTES:
        return CARD_QUOTES[normalized]

    # Грубое соответствие по ключевым токенам.
    if "годжо" in normalized or "gojo" in normalized or "satoru" in normalized:
        return CARD_QUOTES.get("годжосатору", FALLBACK_QUOTES)
    if "сукуна" in normalized or "sukuna" in normalized or "ryomen" in normalized:
        return CARD_QUOTES.get("рёменсукуна", FALLBACK_QUOTES)
    if "итадори" in normalized or "yuji" in normalized:
        return CARD_QUOTES.get("итадориюдзи", FALLBACK_QUOTES)
    if "фушигуро" in normalized or "megumi" in normalized:
        return CARD_QUOTES.get("фушигуромегуми", FALLBACK_QUOTES)
    if "кугисаки" in normalized or "nobara" in normalized:
        return CARD_QUOTES.get("кугисакинобара", FALLBACK_QUOTES)
    if "кусакабе" in normalized or "kusakabe" in normalized:
        return CARD_QUOTES.get("ацуякусакабе", FALLBACK_QUOTES)
    if "такума" in normalized or normalized.endswith("ино") or "ino" in normalized:
        return CARD_QUOTES.get("такумаино", FALLBACK_QUOTES)
    if "наобито" in normalized or "naobito" in normalized:
        return CARD_QUOTES.get("наобитодзэнин", FALLBACK_QUOTES)

    return FALLBACK_QUOTES
