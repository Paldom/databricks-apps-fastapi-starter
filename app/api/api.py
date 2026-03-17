from fastapi import APIRouter

from app.api.user_controller import router as user_router
from app.api.todo_controller import router as todo_router
from app.api.integrations.lakebase_controller import router as lakebase_router
from app.api.integrations.serving_controller import router as serving_router
from app.api.integrations.jobs_controller import router as jobs_router
from app.api.integrations.ai_gateway_controller import router as ai_gateway_router
from app.api.integrations.vector_search_controller import router as vector_search_router
from app.api.integrations.sql_delta_controller import router as delta_router
from app.api.integrations.genie_controller import router as genie_router
from app.api.integrations.uc_files_controller import router as uc_files_router

api_router = APIRouter()

# Core app routers
api_router.include_router(user_router)
api_router.include_router(todo_router)

# Integration demo routers
api_router.include_router(lakebase_router)
api_router.include_router(serving_router)
api_router.include_router(jobs_router)
api_router.include_router(ai_gateway_router)
api_router.include_router(vector_search_router)
api_router.include_router(delta_router)
api_router.include_router(genie_router)
api_router.include_router(uc_files_router)
