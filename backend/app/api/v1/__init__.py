from fastapi import APIRouter

from app.api.v1 import documents, health, identity, workspaces

router = APIRouter()
router.include_router(health.router, tags=["system"])
router.include_router(identity.router, tags=["identity"])
router.include_router(workspaces.router)
router.include_router(documents.router)
