from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


class EventoResposta(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ocorrido_em: datetime
    # Quem fez (None: autenticação desligada, comando no servidor ou login recusado, em que
    # quem tentou não é conhecido) e o nome dele.
    usuario_id: int | None
    feito_por: str | None
    acao: str
    entidade: str | None
    entidade_id: int | None
    # O conteúdo do que foi apagado, o antes e o depois do que mudou, ou o resumo.
    dados: dict[str, Any]
    origem: Literal["api", "terminal"]
    ip: str | None
    dispositivo: str | None
