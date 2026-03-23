from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from pathlib import Path

from config import DATABASE_FILE_PATH

Base = declarative_base()

# Создаем движок для SQLite
DATABASE_PATH = Path(DATABASE_FILE_PATH).expanduser().resolve()
DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)

engine = create_async_engine(
    f"sqlite+aiosqlite:///{DATABASE_PATH.as_posix()}",
    echo=False,
)

async_session = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

async def init_db():
    """Инициализация базы данных"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await _apply_schema_migrations(conn)


async def _apply_schema_migrations(conn):
    """Лёгкие миграции для добавления новых колонок без Alembic."""
    await _ensure_cards_columns(conn)
    await _ensure_user_cards_columns(conn)
    await _ensure_users_columns(conn)
    await _ensure_user_profiles_columns(conn)
    await _ensure_promo_codes_columns(conn)
    await _ensure_user_promo_codes_columns(conn)
    await _ensure_runtime_indexes(conn)


async def _ensure_cards_columns(conn):
    result = await conn.execute(text("PRAGMA table_info(cards)"))
    existing = {row[1] for row in result}

    columns = {
        "base_ce": "INTEGER DEFAULT 100",
        "ce_regen": "INTEGER DEFAULT 10",
        "innate_technique": "TEXT",
        "abilities": "TEXT",
        "black_flash_chance": "FLOAT DEFAULT 2.0",
        "image_url": "TEXT",
    }

    for name, ddl in columns.items():
        if name not in existing:
            await conn.execute(text(f"ALTER TABLE cards ADD COLUMN {name} {ddl}"))


async def _ensure_user_cards_columns(conn):
    result = await conn.execute(text("PRAGMA table_info(user_cards)"))
    existing = {row[1] for row in result}

    columns = {
        "bonus_attack": "INTEGER DEFAULT 0",
        "bonus_defense": "INTEGER DEFAULT 0",
        "bonus_speed": "INTEGER DEFAULT 0",
        "bonus_hp": "INTEGER DEFAULT 0",
        "bonus_ce": "INTEGER DEFAULT 0",
        "bonus_ce_regen": "INTEGER DEFAULT 0",
        "domain_level": "INTEGER DEFAULT 0",
        "rct_level": "INTEGER DEFAULT 0",
    }

    for name, ddl in columns.items():
        if name not in existing:
            await conn.execute(text(f"ALTER TABLE user_cards ADD COLUMN {name} {ddl}"))


async def _ensure_users_columns(conn):
    result = await conn.execute(text("PRAGMA table_info(users)"))
    existing = {row[1] for row in result}

    columns = {
        "slot_3_card_id": "INTEGER",
        "slot_4_card_id": "INTEGER",
        "slot_5_card_id": "INTEGER",
        "clan": "TEXT",
        "clan_joined_at": "DATETIME",
        "is_admin": "BOOLEAN DEFAULT 0",
        "is_banned": "BOOLEAN DEFAULT 0",
    }

    for name, ddl in columns.items():
        if name not in existing:
            await conn.execute(text(f"ALTER TABLE users ADD COLUMN {name} {ddl}"))


async def _ensure_user_profiles_columns(conn):
    result = await conn.execute(text("PRAGMA table_info(user_profiles)"))
    existing = {row[1] for row in result}

    columns = {
        "avatar_file_id": "TEXT",
        "avatar_file_unique_id": "TEXT",
    }

    for name, ddl in columns.items():
        if name not in existing:
            await conn.execute(text(f"ALTER TABLE user_profiles ADD COLUMN {name} {ddl}"))


async def _ensure_promo_codes_columns(conn):
    result = await conn.execute(text("PRAGMA table_info(promo_codes)"))
    existing = {row[1] for row in result}

    columns = {
        "points_reward": "INTEGER DEFAULT 0",
        "current_uses": "INTEGER DEFAULT 0",
        "expires_at": "DATETIME",
        "is_active": "BOOLEAN DEFAULT 1",
    }

    for name, ddl in columns.items():
        if name not in existing:
            await conn.execute(text(f"ALTER TABLE promo_codes ADD COLUMN {name} {ddl}"))


async def _ensure_user_promo_codes_columns(conn):
    result = await conn.execute(text("PRAGMA table_info(user_promo_codes)"))
    existing = {row[1] for row in result}

    columns = {
        "used_at": "DATETIME",
    }

    for name, ddl in columns.items():
        if name not in existing:
            await conn.execute(text(f"ALTER TABLE user_promo_codes ADD COLUMN {name} {ddl}"))


async def _ensure_runtime_indexes(conn):
    indexes = [
        "CREATE INDEX IF NOT EXISTS ix_users_username_lower ON users(lower(username))",
        "CREATE INDEX IF NOT EXISTS ix_users_level_experience ON users(level, experience)",
        "CREATE INDEX IF NOT EXISTS ix_users_pvp_record ON users(pvp_wins, pvp_losses)",
        "CREATE INDEX IF NOT EXISTS ix_users_clan ON users(clan)",
        "CREATE INDEX IF NOT EXISTS ix_users_clan_joined_at ON users(clan, clan_joined_at)",
        "CREATE INDEX IF NOT EXISTS ix_cards_name ON cards(name)",
        "CREATE INDEX IF NOT EXISTS ix_user_cards_user_equipped ON user_cards(user_id, is_equipped)",
        "CREATE INDEX IF NOT EXISTS ix_user_cards_equipped_user ON user_cards(is_equipped, user_id)",
        "CREATE INDEX IF NOT EXISTS ix_user_cards_user_slot ON user_cards(user_id, slot_number)",
        "CREATE INDEX IF NOT EXISTS ix_user_cards_card_id ON user_cards(card_id)",
        "CREATE INDEX IF NOT EXISTS ix_clans_owner_id ON clans(owner_id)",
        "CREATE INDEX IF NOT EXISTS ix_clan_join_requests_clan_created ON clan_join_requests(clan_name, created_at)",
    ]
    for ddl in indexes:
        await conn.execute(text(ddl))
