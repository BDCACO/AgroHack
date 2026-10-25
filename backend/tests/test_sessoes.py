"""As sessões abertas de cada um: onde há login, o último uso, a validade que se renova
com o uso, e encerrar um aparelho sem derrubar os outros (o celular perdido)."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, select
from sqlalchemy.orm import Session

from app.models import Sessao
from app.services import autenticacao, sessoes
from tests.conftest import SENHA, CriarUsuario, entrar
from tests.test_eventos_de_auditoria import eventos

ENTRAR = "/api/v1/auth/entrar"
EU = "/api/v1/auth/eu"
SESSOES = "/api/v1/auth/sessoes"


def test_login_guarda_o_ip_e_o_ultimo_uso(
    cliente_autenticado: TestClient, criar_usuario: CriarUsuario, db: Session
) -> None:
    criar_usuario("ze")

    resposta = cliente_autenticado.post(
        ENTRAR, json={"login": "ze", "senha": SENHA, "dispositivo": "Celular do Zé"}
    )

    assert resposta.status_code == 200, resposta.text
    sessao = db.scalar(select(Sessao))
    # O mesmo critério da auditoria: o endereço que o servidor viu (o TestClient se chama
    # "testclient"), e nunca o X-Forwarded-For, que qualquer um escreve.
    assert sessao.ip == "testclient"
    assert sessao.ultimo_uso_em == sessao.criada_em


@pytest.fixture
def relogio(monkeypatch: pytest.MonkeyPatch) -> Callable[..., datetime]:
    """Põe o relógio do serviço no instante pedido (dias e minutos depois do início),
    sem dormir, como os testes do bloqueio."""
    inicio = datetime.now(UTC)

    def ajustar(**depois: float) -> datetime:
        momento = inicio + timedelta(**depois)
        monkeypatch.setattr(autenticacao, "agora", lambda: momento)
        monkeypatch.setattr(sessoes, "agora", lambda: momento)
        return momento

    ajustar()
    return ajustar


def _gravacoes_na_sessao(db: Session) -> list[str]:
    """Os UPDATE em `sessoes` que chegam ao banco a partir de agora."""
    gravacoes: list[str] = []

    def anotar(_conexao: object, _cursor: object, comando: str, *_: object) -> None:
        if comando.lstrip().upper().startswith("UPDATE SESSOES"):
            gravacoes.append(comando)

    event.listen(db.get_bind(), "before_cursor_execute", anotar)
    return gravacoes


def test_ultimo_uso_e_anotado_a_cada_5_minutos_e_nao_a_cada_pedido(
    cliente_autenticado: TestClient,
    criar_usuario: CriarUsuario,
    db: Session,
    relogio: Callable[..., datetime],
) -> None:
    criar_usuario("ze")
    login = relogio()
    cabecalho = entrar(cliente_autenticado, "ze")
    sessao = db.scalar(select(Sessao))
    gravacoes = _gravacoes_na_sessao(db)

    # Um pedido atrás do outro (o Painel abre vários de uma vez) não grava nada.
    for minutos in (0, 1, 4, 4.99):
        relogio(minutes=minutos)
        assert cliente_autenticado.get(EU, headers=cabecalho).status_code == 200
    assert gravacoes == []
    db.refresh(sessao)
    assert sessao.ultimo_uso_em == login

    # Passados 5 minutos do último registro, o pedido seguinte anota o uso e renova a
    # validade: 30 dias a partir dele.
    usado = relogio(minutes=5)
    assert cliente_autenticado.get(EU, headers=cabecalho).status_code == 200
    assert len(gravacoes) == 1
    db.refresh(sessao)
    assert sessao.ultimo_uso_em == usado
    assert sessao.expira_em == usado + timedelta(days=30)

    relogio(minutes=9)
    assert cliente_autenticado.get(EU, headers=cabecalho).status_code == 200
    assert len(gravacoes) == 1


def test_quem_usa_nao_e_derrubado_no_30o_dia(
    cliente_autenticado: TestClient, criar_usuario: CriarUsuario, relogio: Callable[..., datetime]
) -> None:
    criar_usuario("ze")
    cabecalho = entrar(cliente_autenticado, "ze")

    for dia in (10, 29, 45, 70):
        relogio(days=dia)
        assert cliente_autenticado.get(EU, headers=cabecalho).status_code == 200, dia


def test_nem_quem_usa_passa_de_90_dias_sem_entrar_de_novo(
    cliente_autenticado: TestClient,
    criar_usuario: CriarUsuario,
    db: Session,
    relogio: Callable[..., datetime],
) -> None:
    # O teto: um token copiado não vive para sempre só porque alguém o usa, e a senha é
    # pedida de novo de tempos em tempos.
    criar_usuario("ze")
    login = relogio()
    cabecalho = entrar(cliente_autenticado, "ze")

    for dia in (20, 40, 60, 80, 89):
        relogio(days=dia)
        assert cliente_autenticado.get(EU, headers=cabecalho).status_code == 200, dia
    sessao = db.scalar(select(Sessao))
    assert sessao.expira_em == login + timedelta(days=90)

    relogio(days=90, minutes=1)
    resposta = cliente_autenticado.get(EU, headers=cabecalho)
    assert resposta.status_code == 401
    assert "expirou" in resposta.json()["detail"]


def entrar_em(api: TestClient, login: str, dispositivo: str) -> dict[str, str]:
    """O login de um aparelho, com o nome que ele diz ter."""
    corpo = {"login": login, "senha": SENHA, "dispositivo": dispositivo}
    resposta = api.post(ENTRAR, json=corpo)
    assert resposta.status_code == 200, resposta.text
    return {"Authorization": f"Bearer {resposta.json()['token']}"}


def id_da_sessao(api: TestClient, cabecalho: dict[str, str], dispositivo: str) -> int:
    lista = api.get(SESSOES, headers=cabecalho).json()
    return next(s["id"] for s in lista if s["dispositivo"] == dispositivo)


def test_minhas_sessoes_lista_so_as_ativas_e_marca_a_atual(
    cliente_autenticado: TestClient, criar_usuario: CriarUsuario, relogio: Callable[..., datetime]
) -> None:
    api = cliente_autenticado
    criar_usuario("ze")
    criar_usuario("maria", papel="dono")
    celular = entrar_em(api, "ze", "Celular do Zé")
    relogio(minutes=1)
    notebook = entrar_em(api, "ze", "Notebook")
    api.post("/api/v1/auth/sair", headers=entrar_em(api, "ze", "Tablet"))
    entrar_em(api, "maria", "Computador do escritório")

    resposta = api.get(SESSOES, headers=notebook)

    assert resposta.status_code == 200, resposta.text
    lista = resposta.json()
    # A encerrada (o tablet) e as de outro usuário não aparecem; a usada por último vem
    # primeiro, e `atual` é a deste pedido, para a tela não oferecer encerrar a si mesma.
    assert [(s["dispositivo"], s["atual"]) for s in lista] == [
        ("Notebook", True),
        ("Celular do Zé", False),
    ]
    # Nunca o token nem o hash dele.
    assert set(lista[0]) == {
        "id",
        "dispositivo",
        "ip",
        "criada_em",
        "ultimo_uso_em",
        "expira_em",
        "atual",
    }
    assert lista[0]["ip"] == "testclient"
    assert [s["atual"] for s in api.get(SESSOES, headers=celular).json()] == [False, True]


def test_sessao_vencida_nao_aparece_na_lista(
    cliente_autenticado: TestClient, criar_usuario: CriarUsuario, relogio: Callable[..., datetime]
) -> None:
    api = cliente_autenticado
    criar_usuario("ze")
    entrar_em(api, "ze", "Celular antigo")
    relogio(days=29)
    novo = entrar_em(api, "ze", "Celular novo")

    relogio(days=31)

    assert [s["dispositivo"] for s in api.get(SESSOES, headers=novo).json()] == ["Celular novo"]


def test_encerrar_outro_aparelho_meu_derruba_so_ele_e_fica_na_trilha(
    cliente_autenticado: TestClient, criar_usuario: CriarUsuario, db: Session
) -> None:
    api = cliente_autenticado
    ze = criar_usuario("ze")
    celular = entrar_em(api, "ze", "Celular do Zé")
    notebook = entrar_em(api, "ze", "Notebook")
    id_do_celular = id_da_sessao(api, notebook, "Celular do Zé")

    resposta = api.delete(f"{SESSOES}/{id_do_celular}", headers=notebook)

    assert resposta.status_code == 204, resposta.text
    caiu = api.get(EU, headers=celular)
    assert caiu.status_code == 401
    assert "encerrada" in caiu.json()["detail"]
    assert api.get(EU, headers=notebook).status_code == 200
    # Quem tem a sessão roubada pode derrubar os outros aparelhos do dono dela: fica na
    # trilha, com o aparelho que encerrou (o da origem) e o encerrado (nos dados).
    [evento] = eventos(db)
    assert (evento.acao, evento.usuario_id, evento.entidade, evento.entidade_id) == (
        "sessao.encerrada",
        ze.id,
        "usuario",
        ze.id,
    )
    assert evento.dispositivo == "Notebook"
    assert evento.dados["login"] == "ze"
    encerrada = evento.dados["sessao"]
    assert (encerrada["id"], encerrada["dispositivo"]) == (id_do_celular, "Celular do Zé")
    assert set(encerrada) == {"id", "dispositivo", "ip", "criada_em", "ultimo_uso_em"}
    # Encerrada, não está mais lá para encerrar de novo.
    assert api.delete(f"{SESSOES}/{id_do_celular}", headers=notebook).status_code == 404


def test_encerrar_a_propria_sessao_pela_lista_e_como_sair(
    cliente_autenticado: TestClient, criar_usuario: CriarUsuario, db: Session
) -> None:
    api = cliente_autenticado
    criar_usuario("ze")
    celular = entrar_em(api, "ze", "Celular do Zé")
    esta = id_da_sessao(api, celular, "Celular do Zé")

    assert api.delete(f"{SESSOES}/{esta}", headers=celular).status_code == 204

    assert api.get(EU, headers=celular).status_code == 401
    assert eventos(db) == []  # como o sair, que não entra na trilha


def test_sessao_de_outro_usuario_e_404_como_a_que_nao_existe(
    cliente_autenticado: TestClient, criar_usuario: CriarUsuario, db: Session
) -> None:
    # Nem o dono encerra a sessão de outro por aqui (é pela gestão de usuários), e a
    # resposta não conta que aquele id existe.
    api = cliente_autenticado
    criar_usuario("ze")
    criar_usuario("maria", papel="dono")
    ze = entrar_em(api, "ze", "Celular do Zé")
    maria = entrar_em(api, "maria", "Computador do escritório")
    da_maria = id_da_sessao(api, maria, "Computador do escritório")
    do_ze = id_da_sessao(api, ze, "Celular do Zé")

    de_outro = api.delete(f"{SESSOES}/{da_maria}", headers=ze)
    inexistente = api.delete(f"{SESSOES}/999", headers=ze)
    do_dono = api.delete(f"{SESSOES}/{do_ze}", headers=maria)

    assert de_outro.status_code == inexistente.status_code == do_dono.status_code == 404
    assert de_outro.json() == inexistente.json() == do_dono.json()
    assert api.get(EU, headers=maria).status_code == 200
    assert api.get(EU, headers=ze).status_code == 200
    assert eventos(db) == []


def test_encerrar_as_outras_deixa_so_a_atual(
    cliente_autenticado: TestClient, criar_usuario: CriarUsuario, db: Session
) -> None:
    api = cliente_autenticado
    ze = criar_usuario("ze")
    criar_usuario("maria", papel="dono")
    celular = entrar_em(api, "ze", "Celular do Zé")
    tablet = entrar_em(api, "ze", "Tablet")
    notebook = entrar_em(api, "ze", "Notebook")
    maria = entrar_em(api, "maria", "Computador do escritório")

    resposta = api.post(f"{SESSOES}/encerrar-outras", headers=notebook)

    assert resposta.status_code == 200, resposta.text
    assert resposta.json() == {"encerradas": 2}
    assert [api.get(EU, headers=c).status_code for c in (celular, tablet)] == [401, 401]
    assert api.get(EU, headers=notebook).status_code == 200
    assert api.get(EU, headers=maria).status_code == 200  # as de outro usuário ficam
    [evento] = eventos(db)
    assert (evento.acao, evento.usuario_id, evento.entidade_id) == (
        "sessao.encerradas",
        ze.id,
        ze.id,
    )
    assert evento.dados["login"] == "ze"
    assert [s["dispositivo"] for s in evento.dados["sessoes"]] == ["Celular do Zé", "Tablet"]

    # Sem outras, nada a encerrar e nada na trilha.
    assert api.post(f"{SESSOES}/encerrar-outras", headers=notebook).json() == {"encerradas": 0}
    assert len(eventos(db)) == 1
