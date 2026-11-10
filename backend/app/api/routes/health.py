from fastapi import APIRouter
from pydantic import BaseModel

from app.agents.llm import get_llm
from app.core.config import get_settings
from app.core.database import database_status

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str
    version: str
    database: str
    paypal_configured: bool
    llm_configured: bool
    llm_provider: str
    llm_model: str
    llm_error: str | None  # last LLM call problem, if any


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    s = get_settings()
    return HealthResponse(
        status="ok",
        version=s.version,
        database=database_status(),
        paypal_configured=bool(s.paypal_client_id and s.paypal_client_secret),
        llm_configured=bool(s.llm_api_key),
        llm_provider=s.llm_provider,
        llm_model=s.llm_model,
        llm_error=get_llm().last_error,
    )
