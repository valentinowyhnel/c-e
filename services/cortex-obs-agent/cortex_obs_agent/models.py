from pydantic import BaseModel


class AnomalyTestRequest(BaseModel):
    service: str
    metric: str
    value: float
    baseline: float


class ServiceStatus(BaseModel):
    status: str
    latency: float
    trend: str = "stable"
    last_check: int
