from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base

Base = declarative_base()

# Создаем движок для SQLite
engine = create_async_engine("sqlite+aiosqlite:///jujutsu_bot.db", echo=False)

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
    await _ensure_user_cards_columns(conn)
    await _ensure_users_columns(conn)
    await _ensure_user_profiles_columns(conn)


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
