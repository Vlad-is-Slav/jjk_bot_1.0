from datetime import datetime, date

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from models import DailyQuest, UserDailyQuest


async def add_daily_quest_progress(session, user_id: int, quest_type: str, amount: int = 1) -> int:
    """Increase progress for today's daily quests of a specific type."""
    if amount <= 0 or not quest_type:
        return 0

    result = await session.execute(
        select(UserDailyQuest)
        .options(selectinload(UserDailyQuest.quest))
        .join(DailyQuest, UserDailyQuest.quest_id == DailyQuest.id)
        .where(
            UserDailyQuest.user_id == user_id,
            DailyQuest.quest_type == quest_type,
        )
    )
    user_quests = result.scalars().all()

    today = date.today()
    touched = 0

    for uq in user_quests:
        if not uq.quest:
            continue
        if not uq.assigned_date or uq.assigned_date.date() != today:
            continue
        if uq.claimed:
            continue

        requirement = max(1, int(uq.quest.requirement or 1))
        if uq.progress >= requirement and uq.completed:
            continue

        uq.progress = min(requirement, int(uq.progress or 0) + amount)
        if uq.progress >= requirement:
            uq.completed = True
            if not uq.completed_at:
                uq.completed_at = datetime.utcnow()
        touched += 1

    return touched

