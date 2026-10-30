"""API v1 router aggregation."""

from fastapi import APIRouter

from app.api.v1 import (
    admin,
    ai,
    alerts,
    auth,
    billing,
    contact,
    dashboard,
    dependencies,
    feedback,
    migration,
    organizations,
    repositories,
    scans,
    search,
    users,
    webhooks,
)

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(organizations.router, prefix="/organizations", tags=["organizations"])
api_router.include_router(billing.router, prefix="/billing", tags=["billing"])
api_router.include_router(repositories.router, prefix="/repositories", tags=["repositories"])
api_router.include_router(dependencies.router, prefix="/dependencies", tags=["dependencies"])
api_router.include_router(migration.router, prefix="/migration", tags=["migration"])
api_router.include_router(scans.router, prefix="/scans", tags=["scans"])
api_router.include_router(alerts.router, prefix="/alerts", tags=["alerts"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
api_router.include_router(search.router, prefix="/search", tags=["search"])
api_router.include_router(webhooks.router, prefix="/webhooks", tags=["webhooks"])
api_router.include_router(ai.router, prefix="/ai", tags=["ai"])
api_router.include_router(feedback.router, prefix="/feedback", tags=["feedback"])
api_router.include_router(contact.router, prefix="/contact", tags=["contact"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
