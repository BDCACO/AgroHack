from typing import Literal

from pydantic import BaseModel

StatusDependencia = Literal["ok", "erro"]


class HealthResponse(BaseModel):
    status: Literal["ok"]


class ReadinessResponse(BaseModel):
    status: Literal["pronto", "indisponivel"]
    database: StatusDependencia
