from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import router as v1_router
from app.core.config import settings
from app.core.errors import NexusError, nexus_error_handler, unhandled_exception_handler

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# CORS — open for local development; tighten per environment in production
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Error handlers
app.add_exception_handler(NexusError, nexus_error_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)

# API routers
app.include_router(v1_router, prefix=settings.api_v1_prefix)
