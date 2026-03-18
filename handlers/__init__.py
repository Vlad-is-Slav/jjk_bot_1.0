from .start import router as start_router
from .profile import router as profile_router
from .inventory import router as inventory_router
from .battle import router as battle_router
from .pve import router as pve_router
from .pvp import router as pvp_router
from .coop_pvp import router as coop_pvp_router
from .tops import router as tops_router
from .friends import router as friends_router
from .daily import router as daily_router
from .achievements import router as achievements_router
from .campaign import router as campaign_router
from .academy import router as academy_router
from .promocode import router as promocode_router
from .admin import router as admin_router
from .market import router as market_router
from .clans import router as clans_router

__all__ = [
    'start_router',
    'profile_router',
    'inventory_router',
    'battle_router',
    'pve_router',
    'pvp_router',
    'coop_pvp_router',
    'tops_router',
    'friends_router',
    'daily_router',
    'achievements_router',
    'campaign_router',
    'academy_router',
    'promocode_router',
    'admin_router',
    'market_router',
    'clans_router'
]
