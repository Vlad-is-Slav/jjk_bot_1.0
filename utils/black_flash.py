from __future__ import annotations


def _normalize_name(value: str | None) -> str:
    return "".join(ch.lower() for ch in (value or "") if ch.isalnum())


BLACK_FLASH_DEFAULT = 0.10
BLACK_FLASH_TOKENS: list[tuple[tuple[str, ...], float]] = [
    (("итадори", "юдзи", "itadori", "yuji"), 0.30),
    (("годжо", "gojo", "satoru"), 0.15),
    (("сукуна", "sukuna", "ryomen"), 0.15),
]


def get_black_flash_chance(card_name: str | None) -> float:
    normalized = _normalize_name(card_name)
    if not normalized:
        return BLACK_FLASH_DEFAULT

    for tokens, chance in BLACK_FLASH_TOKENS:
        if any(token in normalized for token in tokens):
            return chance

    return BLACK_FLASH_DEFAULT
