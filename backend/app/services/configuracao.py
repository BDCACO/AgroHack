from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.configuracao import Configuracao
from app.schemas.configuracao import ConfiguracaoCadastro, ConfiguracaoResposta


def _linha(db: Session) -> Configuracao | None:
    return db.scalars(select(Configuracao)).first()


def obter(db: Session) -> ConfiguracaoResposta:
    linha = _linha(db)
    return ConfiguracaoResposta(meses_de_safra=linha.meses_de_safra if linha else [])


def obter_meses_de_safra(db: Session) -> list[int]:
    linha = _linha(db)
    return linha.meses_de_safra if linha else []


def definir(db: Session, dados: ConfiguracaoCadastro) -> ConfiguracaoResposta:
    linha = _linha(db)
    if linha is None:
        linha = Configuracao(meses_de_safra=dados.meses_de_safra)
        db.add(linha)
    else:
        linha.meses_de_safra = dados.meses_de_safra
    db.commit()
    db.refresh(linha)
    return ConfiguracaoResposta(meses_de_safra=linha.meses_de_safra)
