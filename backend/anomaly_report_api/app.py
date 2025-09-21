from fastapi import FastAPI, APIRouter
from pydantic import BaseModel
from typing import List

from model import Orchestr

API_KEY = "AIzaSyABJ1jK42mi9ovXsnzJBt2bobl-WvAX5q8"
MODEL_NAME = "gemini-1.5-flash-latest"
GEMINI_API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL_NAME}:generateContent?key={API_KEY}"


# app = FastAPI(title="AI Incident Orchestrator API")
router = APIRouter()

class OldLog(BaseModel):
    timestamp: str
    response_time_ms: int

class AnomalyLog(BaseModel):
    timestamp: str
    log_level: str
    message: str

class OrchestratorRequest(BaseModel):
    old_logs: List[OldLog]
    logs_anomaly: List[AnomalyLog]
    choice_role: bool

orchestr = Orchestr(api_key=API_KEY, model_name=MODEL_NAME)

@router.get("/")
async def root():
    """Проверка сервиса."""
    return {"status": "OK", "message": "AI Orchestrator is running"}

@router.post("/run-orchestrator")
async def run_orchestrator(request: OrchestratorRequest):
    """Запускает оркестратор с анализом логов и генерацией отчета."""
    result = orchestr.get_predict(
        old_logs=[log.dict() for log in request.old_logs],
        logs_anomaly=[log.dict() for log in request.logs_anomaly],
        choice_role=request.choice_role
    )
    return {"status": "success", "report": result}
