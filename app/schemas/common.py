from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str


class PhaseStatusResponse(BaseModel):
    phase: str
    message: str
