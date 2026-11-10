from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import approvals, chat, finance, health, objectives, orders, payments, personal, products, workflows
from app.core.config import get_settings

settings = get_settings()

app = FastAPI(title=settings.app_name, version=settings.version)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    expose_headers=["X-PersonalIQ-User"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

api = APIRouter(prefix="/api/v1")
api.include_router(health.router)
api.include_router(products.router)
api.include_router(personal.router)
api.include_router(workflows.router)
api.include_router(chat.router)
api.include_router(approvals.router)
api.include_router(payments.router)
api.include_router(orders.router)
api.include_router(finance.router)
api.include_router(objectives.router)
app.include_router(api)
