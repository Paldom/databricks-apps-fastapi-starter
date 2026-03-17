from fastapi import APIRouter

from app.api.examples_controller import router as examples_router
from app.api.user_controller import router as user_router

api_router = APIRouter()

# Core app routers
api_router.include_router(user_router)

# Databricks example routes
api_router.include_router(examples_router)
