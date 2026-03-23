import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")


def _parse_int_list(raw_value: str | None, fallback: list[int] | None = None) -> list[int]:
    values: list[int] = []
    for chunk in (raw_value or "").replace(";", ",").split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        try:
            values.append(int(chunk))
        except ValueError:
            continue
    return values or list(fallback or [])


def _resolve_database_path() -> Path:
    explicit_path = (os.getenv("DATABASE_PATH") or "").strip()
    if explicit_path:
        return Path(explicit_path).expanduser()

    railway_volume_path = (os.getenv("RAILWAY_VOLUME_MOUNT_PATH") or "").strip()
    if railway_volume_path:
        return Path(railway_volume_path).expanduser() / "jujutsu_bot.db"

    return Path("jujutsu_bot.db")

EXP_PER_MESSAGE = 1  #   
EXP_COOLDOWN = 30  #      
EXP_TO_NEXT_BASE = 100
EXP_TO_NEXT_MULTIPLIER = 1.06
EXP_TO_NEXT_FLAT = 20

PVE_COOLDOWN = 5  #   PvE 
PVP_COOLDOWN = 10  #   PvP 

EXP_PER_PVE_WIN = 20  #    PvE
POINTS_PER_PVE_WIN = 0  # Очки только за уровень
EXP_PER_PVP_WIN = 50  #   PvP
POINTS_PER_PVP_WIN = 0  # Очки только за уровень
POINTS_PER_LEVEL_UP = 1  #    
COINS_PER_LEVEL_UP = 100  #    

STAT_UPGRADE_COST = 1  #  1    
STAT_UPGRADE_VALUES = {
    "attack": 5,
    "defense": 5,
    "speed": 5,
    "hp": 10,
    "ce": 5,
    "ce_regen": 1,
}
   
DOMAIN_DOT_PER_POINT = 0.005  # +0.5% DOT  
DOMAIN_DAMAGE_BONUS_PER_POINT = 0.01  # +1%      
RCT_HEAL_BONUS_PER_POINT = 0.06  # +6%     

# Глобальный боевой баланс (PvP/PvE)
COMBAT_HP_SCALE = 1.65  # Повышает боевой запас HP, чтобы уменьшить ваншоты
COMBAT_ATTACK_SCALE = 0.82  # Небольшое ослабление базового урона атак
COMBAT_SPECIAL_FLAT_SCALE = 0.72  # Ослабление "плоской" части спец-урона
COMBAT_DOMAIN_DAMAGE_SCALE = 0.70  # Ослабление периодического урона доменов
COMBAT_MAX_HIT_RATIO = 0.48  # Мягкий лимит: один удар не снимает больше 48% HP
  
DIFFICULTY_MULTIPLIERS = {
    "easy": 0.5,
    "normal": 1.0,
    "hard": 1.5,
    "hardcore": 2.0
}
  
DAILY_REWARDS = {
    1: {"exp": 50, "points": 1, "coins": 100, "name": " 1"},
    2: {"exp": 75, "points": 1, "coins": 150, "name": " 2"},
    3: {"exp": 100, "points": 1, "coins": 200, "name": " 3"},
    4: {"exp": 125, "points": 1, "coins": 250, "name": " 4"},
    5: {"exp": 150, "points": 1, "coins": 300, "name": " 5"},
    6: {"exp": 200, "points": 1, "coins": 400, "name": " 6"},
    7: {"exp": 500, "points": 1, "coins": 1000, "card_chance": 0.3, "name": " 7 - !"}
}

ACADEMY_BASE_COST = 5000  #   
ACADEMY_COST_INCREASE = 100  #    
ACADEMY_COOLDOWN_HOURS = 24  #   

MARKET_TAX = 0.1  #   (10%)
MIN_PRICE = 50  #  
MAX_PRICE = 10000000  #  

BLACK_FLASH_CHANCES = {
    "common": 2,
    "rare": 5,
    "epic": 10,
    "legendary": 15,
    "mythical": 20
}
STARTER_COINS = 1000
STARTER_POINTS = 0

DEFAULT_ADMIN_IDS = [1296861067]
ADMIN_IDS = _parse_int_list(os.getenv("ADMIN_IDS"), fallback=DEFAULT_ADMIN_IDS)
ADMINS = list(ADMIN_IDS)
BACKUP_OWNER_IDS = _parse_int_list(os.getenv("BACKUP_OWNER_IDS"), fallback=ADMIN_IDS)

DATABASE_FILE_PATH = _resolve_database_path()
