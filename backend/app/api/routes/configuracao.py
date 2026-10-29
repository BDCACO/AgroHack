from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.configuracao import ConfiguracaoCadastro, ConfiguracaoResposta
from app.services import configuracao as servico

# Só o dono vê e mexe: é ajuste da fazenda inteira, não dado de uso diário do funcionário.
gestao = APIRouter(tags=["configuração"])


@gestao.get("/configuracao", response_model=ConfiguracaoResposta)
def obter_configuracao(db: Session = Depends(get_db)) -> ConfiguracaoResposta:
    """O calendário de safra da fazenda; vazio enquanto ninguém configurou."""
    return servico.obter(db)


@gestao.put("/configuracao", response_model=ConfiguracaoResposta)
def definir_configuracao(
    dados: ConfiguracaoCadastro, db: Session = Depends(get_db)
) -> ConfiguracaoResposta:
    return servico.definir(db, dados)
